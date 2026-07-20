from fastapi import APIRouter, Depends, UploadFile, File
from app.auth import get_active_team
from app.i18n.errors import raise_api_error
from sqlmodel import Session, select
from app.models import (
    Game, GameCreate, Availability, BattingLine, PitchingAppearance,
    Lineup, Player, Team
)
from app.optimizer import solve_lineup_options, OptimizerConfig, LockedCell, GAME_MODES
from app.rest_calculator import get_pitcher_eligibility
from app.lineup_service import (
    get_available_players,
    load_position_scores,
    build_player_infos,
    validate_locked_cells,
    prune_unavailable_lineup_cells,
    persist_solver_result,
    snapshot_lineup,
    list_snapshots,
    restore_snapshot,
)
from app.db import get_session
from typing import List, Optional
from pydantic import BaseModel
import os
import re

router = APIRouter(prefix="/games", tags=["games"])

MIN_LINEUP_INNINGS = 1
MAX_LINEUP_INNINGS = 12
MIN_LINEUP_POSITION = 0
MAX_LINEUP_POSITION = 9


def validate_game_mode(mode: str) -> None:
    if mode not in GAME_MODES:
        raise_api_error(400, "invalid_game_mode", mode=mode)


class ApplySolveBody(BaseModel):
    assignments: List[dict]

# --- Helper Dependency ---

def resolve_lineup_innings(game: Game, team: Team) -> int:
    return game.innings_played or team.innings_per_game

def is_aa_or_aaa(team: Team) -> bool:
    level = (team.classe or "").strip().upper()
    return level in {"AA", "AAA"}

def cleanup_lineup_beyond_innings(game: Game, max_inning: int, session: Session) -> None:
    extra_cells = session.exec(
        select(Lineup).where(Lineup.game_id == game.id, Lineup.inning > max_inning)
    ).all()
    for cell in extra_cells:
        session.delete(cell)

    avails = session.exec(select(Availability).where(Availability.game_id == game.id)).all()
    for avail in avails:
        if avail.injury_inning is not None and avail.injury_inning > max_inning:
            avail.injury_inning = None
            session.add(avail)

def get_active_game(
    game_id: int,
    session: Session = Depends(get_session),
    active_team: Team = Depends(get_active_team)
) -> Game:
    game = session.get(Game, game_id)
    if not game or game.team_id != active_team.id:
        raise_api_error(404, "game_not_found")
    return game

def normalize_external_game_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        return stripped
    match = re.search(r"(?:gameId|game_id|id)=(\d+)", stripped, re.IGNORECASE)
    if match:
        return match.group(1)
    trailing = re.search(r"/(\d+)/?$", stripped)
    if trailing:
        return trailing.group(1)
    return stripped

def apply_external_game_fields(updates: dict, team: Team) -> None:
    if "external_game_id" not in updates:
        return
    normalized = normalize_external_game_id(updates.get("external_game_id"))
    updates["external_game_id"] = normalized
    if normalized and team.integration_version == "lfbq_spordle":
        updates["external_source"] = "spordle"
    elif not normalized:
        updates["external_source"] = None

# --- Game CRUD ---

@router.post("/", response_model=Game)
def create_game(game_data: GameCreate, session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    validate_game_mode(game_data.mode)
    game_dict = game_data.model_dump()
    apply_external_game_fields(game_dict, active_team)
    game_dict["team_id"] = active_team.id
    game = Game(**game_dict)
    session.add(game)
    session.commit()
    session.refresh(game)

    # Auto-seed availability for all active players on the team (excluding coaches)
    active_players = session.exec(
        select(Player).where(Player.team_id == active_team.id, Player.active == True, Player.is_coach == False)
    ).all()
    for player in active_players:
        initial_status = "absent" if player.is_substitute else "available"
        avail = Availability(game_id=game.id, player_id=player.id, status=initial_status)
        session.add(avail)
    session.commit()
    session.refresh(game)

    return game

@router.get("/", response_model=List[Game])
def list_games(session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    games = session.exec(select(Game).where(Game.team_id == active_team.id)).all()
    return games

@router.post("/sync-schedule")
def sync_schedule(session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    if active_team.integration_version != "lfbq_spordle":
        raise_api_error(400, "schedule_sync_not_configured")
    from app.league_integrations.lfbq_spordle.sync import sync_team_schedule

    result = sync_team_schedule(session, active_team)
    if not result.get("ok"):
        raise_api_error(400, "schedule_sync_not_configured")
    return result


@router.get("/upcoming-intel")
def upcoming_games_intel(
    session: Session = Depends(get_session),
    active_team: Team = Depends(get_active_team),
):
    from app.game_intel import serialize_games_with_intel, upcoming_games_for_team

    games = upcoming_games_for_team(session, active_team.id)
    return serialize_games_with_intel(games, active_team)


@router.get("/{game_id}", response_model=Game)
def get_game(game: Game = Depends(get_active_game)):
    return game

@router.put("/{game_id}", response_model=Game)
def update_game(game_data: GameCreate, game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    updates = game_data.model_dump(exclude_unset=True)
    apply_external_game_fields(updates, team)
    if "mode" in updates:
        validate_game_mode(updates["mode"])
    if "innings_played" in updates and updates["innings_played"] is not None:
        innings = updates["innings_played"]
        if innings < MIN_LINEUP_INNINGS or innings > MAX_LINEUP_INNINGS:
            raise_api_error(
                400,
                "invalid_inning_count",
                min_innings=MIN_LINEUP_INNINGS,
                max_innings=MAX_LINEUP_INNINGS,
            )

    for key, value in updates.items():
        setattr(game, key, value)

    if "innings_played" in updates:
        cleanup_lineup_beyond_innings(game, resolve_lineup_innings(game, team), session)

    session.add(game)
    session.commit()
    session.refresh(game)
    return game

@router.get("/{game_id}/opponent-intel")
def get_game_opponent_intel(
    game: Game = Depends(get_active_game),
    active_team: Team = Depends(get_active_team),
):
    from app.league_integrations import get_opponent_intel

    return get_opponent_intel(game, active_team)

@router.delete("/{game_id}")
def delete_game(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    session.delete(game)
    session.commit()
    return {"ok": True}

# --- Availability ---

class AvailabilityUpdate(BaseModel):
    player_id: int
    status: str  # available, absent, late, injured

@router.get("/{game_id}/availability", response_model=List[Availability])
def get_availability(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    avails = session.exec(select(Availability).where(Availability.game_id == game.id)).all()
    return avails

@router.put("/{game_id}/availability")
def set_availability(updates: List[AvailabilityUpdate], game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    player_ids = [upd.player_id for upd in updates]
    players = session.exec(select(Player).where(Player.id.in_(player_ids), Player.team_id == game.team_id)).all()
    valid_player_ids = {p.id for p in players}
    
    for upd in updates:
        if upd.player_id not in valid_player_ids:
            raise_api_error(400, "player_not_found", player_id=upd.player_id)
            
        existing = session.exec(
            select(Availability).where(
                Availability.game_id == game.id,
                Availability.player_id == upd.player_id
            )
        ).first()
        if existing:
            existing.status = upd.status
            session.add(existing)
        else:
            avail = Availability(game_id=game.id, player_id=upd.player_id, status=upd.status)
            session.add(avail)
    
    session.commit()
    return {"status": "success"}

class InjuryUpdate(BaseModel):
    player_id: int
    injury_inning: Optional[int]

@router.post("/{game_id}/injury")
def report_injury(update: InjuryUpdate, game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    avail = session.exec(select(Availability).where(
        Availability.game_id == game.id,
        Availability.player_id == update.player_id
    )).first()
    if not avail:
        avail = Availability(game_id=game.id, player_id=update.player_id)
        session.add(avail)
    
    avail.injury_inning = update.injury_inning
    session.commit()
    return {"status": "success"}


# --- Batting ---

@router.get("/{game_id}/batting", response_model=List[BattingLine])
def get_batting(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    lines = session.exec(select(BattingLine).where(BattingLine.game_id == game.id)).all()
    return lines

class BattingLineUpdate(BaseModel):
    player_id: int
    batting_order: Optional[int] = None
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    hr: int = 0
    bb: int = 0
    bbi: int = 0
    hbp: int = 0
    sac: int = 0
    intf: int = 0
    kd: int = 0
    ke: int = 0
    outs_not_k: int = 0
    fc: int = 0
    roe: int = 0
    rbi: int = 0
    r: int = 0
    sb: int = 0

@router.put("/{game_id}/batting")
def set_batting(lines: List[BattingLineUpdate], game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    player_ids = [line.player_id for line in lines]
    players = session.exec(select(Player).where(Player.id.in_(player_ids), Player.team_id == game.team_id)).all()
    valid_player_ids = {p.id for p in players}

    for line in lines:
        if line.player_id not in valid_player_ids:
            raise_api_error(400, "player_not_found", player_id=line.player_id)
            
        existing = session.exec(
            select(BattingLine).where(
                BattingLine.game_id == game.id,
                BattingLine.player_id == line.player_id
            )
        ).first()
        if existing:
            for key, value in line.model_dump(exclude={"player_id"}).items():
                setattr(existing, key, value)
            session.add(existing)
        else:
            bl = BattingLine(game_id=game.id, **line.model_dump())
            session.add(bl)
    session.commit()
    return {"ok": True}

# --- Batting Ingest (Photo-Assisted) ---

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

@router.post("/{game_id}/batting/ingest")
async def ingest_batting(
    game: Game = Depends(get_active_game),
    active_team: Team = Depends(get_active_team),
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
):
    """
    Upload a scoresheet photo and parse batting stats using Claude Vision AI.
    Returns parsed stats for review — does NOT auto-save to the database.
    The coach must review the pre-filled grid and click Save All.
    """
    # Check API key availability
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise_api_error(503, "photo_ingestion_not_configured")

    # Validate file type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise_api_error(400, "invalid_file_type", content_type=content_type)

    # Read file bytes
    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise_api_error(400, "file_empty")
    if len(image_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise_api_error(400, "file_too_large")

    # Load active (non-coach) players for this team
    players = session.exec(
        select(Player).where(
            Player.team_id == game.team_id,
            Player.active == True,
            Player.is_coach == False,
        )
    ).all()

    player_dicts = [
        {"id": p.id, "jersey": p.jersey, "first_name": p.first_name, "last_name": p.last_name}
        for p in players
    ]

    # Call Claude Vision
    from app.vision import parse_scoresheet
    try:
        parsed = await parse_scoresheet(
            image_bytes, content_type, player_dicts, active_team.scoresheet_version
        )
    except ValueError as e:
        if "Unknown scoresheet version" in str(e):
            raise_api_error(400, "unknown_scoresheet_version")
        raise_api_error(503, "ai_service_unavailable", reason=str(e))
    except RuntimeError as e:
        raise_api_error(502, "ai_parsing_failed", reason=str(e))

    return {"parsed": parsed, "player_count": len(players)}

# --- Pitching ---

class PitchingAppearanceCreate(BaseModel):
    player_id: int
    inning_entered: float
    inning_exited: float
    ip_outs: int
    runs_allowed: int = 0
    k: int = 0
    bb: int = 0
    hbp: int = 0
    pitch_count: Optional[int] = None

@router.get("/{game_id}/pitching", response_model=List[PitchingAppearance])
def get_pitching(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    apps = session.exec(select(PitchingAppearance).where(PitchingAppearance.game_id == game.id)).all()
    return apps

@router.put("/{game_id}/pitching")
def set_pitching(appearances: List[PitchingAppearanceCreate], game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    player_ids = [app.player_id for app in appearances]
    players = session.exec(select(Player).where(Player.id.in_(player_ids), Player.team_id == game.team_id)).all()
    valid_player_ids = {p.id for p in players}

    for app in appearances:
        if app.player_id not in valid_player_ids:
            raise_api_error(400, "player_not_found", player_id=app.player_id)

    # Delete existing appearances for this game and re-insert
    existing = session.exec(select(PitchingAppearance).where(PitchingAppearance.game_id == game.id)).all()
    for e in existing:
        session.delete(e)
    
    for app in appearances:
        pa = PitchingAppearance(game_id=game.id, **app.model_dump())
        session.add(pa)
    session.commit()
    return {"ok": True}

# --- Lineup ---

class LineupCell(BaseModel):
    inning: int
    player_id: int
    position: int  # 0=bench, 1-9=field
    locked: bool = False


def _player_display_name(player: Optional[Player], player_id: int) -> str:
    if player:
        return f"{player.first_name} {player.last_name}"
    return f"Player #{player_id}"


def validate_lineup_payload(
    cells: List[LineupCell],
    players: List[Player],
    forbidden_by_player: dict[int, set[int]],
) -> None:
    players_by_id = {player.id: player for player in players}
    positions_by_inning: dict[tuple[int, int], list[str]] = {}
    player_positions_by_inning: dict[tuple[int, int], list[int]] = {}

    for cell in cells:
        if cell.position < MIN_LINEUP_POSITION or cell.position > MAX_LINEUP_POSITION:
            raise_api_error(
                400,
                "invalid_lineup_position",
                inning=cell.inning,
                position=cell.position,
            )

        player = players_by_id.get(cell.player_id)
        player_positions_by_inning.setdefault((cell.inning, cell.player_id), []).append(cell.position)

        if cell.position <= 0:
            continue

        p_name = _player_display_name(player, cell.player_id)
        positions_by_inning.setdefault((cell.inning, cell.position), []).append(p_name)

        forbidden = set(forbidden_by_player.get(cell.player_id, set()))
        if player and player.is_substitute:
            forbidden.add(1)
        if cell.position in forbidden:
            if cell.position == 1 and player and player.is_substitute:
                raise_api_error(
                    400,
                    "forbidden_position_substitute_pitch",
                    player_name=p_name,
                    inning=cell.inning,
                )
            raise_api_error(
                400,
                "forbidden_position",
                player_name=p_name,
                position=cell.position,
                position_id=cell.position,
                inning=cell.inning,
            )

    for (inning, player_id), positions in player_positions_by_inning.items():
        if len(positions) > 1:
            player = players_by_id.get(player_id)
            raise_api_error(
                400,
                "multiple_lineup_positions",
                inning=inning,
                player_name=_player_display_name(player, player_id),
                positions=", ".join(str(position) for position in positions),
            )

    for (inning, position), player_names in positions_by_inning.items():
        if len(player_names) > 1:
            raise_api_error(
                400,
                "duplicate_lineup_position",
                inning=inning,
                position=position,
                players=", ".join(player_names),
            )

@router.get("/{game_id}/lineup", response_model=List[Lineup])
def get_lineup(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    cells = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    return cells

@router.put("/{game_id}/lineup")
def set_lineup(cells: List[LineupCell], game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    max_inning = resolve_lineup_innings(game, team)
    player_ids = [cell.player_id for cell in cells]
    players = session.exec(select(Player).where(Player.id.in_(player_ids), Player.team_id == game.team_id)).all()
    valid_player_ids = {p.id for p in players}

    for cell in cells:
        if cell.player_id not in valid_player_ids:
            raise_api_error(400, "player_not_found", player_id=cell.player_id)
        if cell.inning < 1 or cell.inning > max_inning:
            raise_api_error(
                400,
                "lineup_inning_out_of_range",
                inning=cell.inning,
                max_inning=max_inning,
            )

    _, forbidden_by_player = load_position_scores(game, session)
    validate_lineup_payload(cells, players, forbidden_by_player)

    # Delete existing lineup for this game and re-insert
    existing = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    for e in existing:
        session.delete(e)
    
    for cell in cells:
        lineup = Lineup(game_id=game.id, **cell.model_dump())
        session.add(lineup)
    session.commit()
    return {"ok": True}

# --- Lineup history / undo ---

class SnapshotCreate(BaseModel):
    label: Optional[str] = None

@router.get("/{game_id}/lineup/snapshots")
def get_lineup_snapshots(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    return list_snapshots(game, session)

@router.post("/{game_id}/lineup/snapshots")
def create_lineup_snapshot(
    payload: SnapshotCreate = SnapshotCreate(),
    game: Game = Depends(get_active_game),
    session: Session = Depends(get_session),
):
    snapshot = snapshot_lineup(game, session, label=(payload.label or "manual"))
    if snapshot is None:
        raise_api_error(400, "lineup_empty")
    return {
        "id": snapshot.id,
        "label": snapshot.label,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }

@router.post("/{game_id}/lineup/snapshots/{snapshot_id}/restore")
def restore_lineup_snapshot(
    snapshot_id: int,
    game: Game = Depends(get_active_game),
    session: Session = Depends(get_session),
):
    restored = restore_snapshot(game, snapshot_id, session)
    return {"ok": True, "restored_cells": restored}

# --- Solve (Optimizer) ---

@router.post("/{game_id}/solve")
def solve_game_lineup(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    """
    Run the CP-SAT optimizer for this game.
    Optimal mode auto-applies one lineup; compete/develop return up to 5 options.
    """
    validate_game_mode(game.mode)
    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    innings = resolve_lineup_innings(game, team)

    available_players, avails = get_available_players(game, session)

    if len(available_players) < 9:
        raise_api_error(400, "insufficient_players", count=len(available_players))

    scores_by_player, forbidden_by_player = load_position_scores(game, session)

    player_infos = build_player_infos(
        available_players, avails, scores_by_player, forbidden_by_player, game, team, session
    )

    available_ids = {p.id for p in available_players}
    existing_lineup = prune_unavailable_lineup_cells(game, available_ids, session)
    locked = [
        LockedCell(player_id=lc.player_id, inning=lc.inning, position=lc.position)
        for lc in existing_lineup if lc.locked
    ]

    validate_locked_cells(
        existing_lineup, available_players, forbidden_by_player, game, team, session
    )

    tolerance = getattr(team, "compete_score_tolerance_pct", 15.0)
    config = OptimizerConfig(
        innings=innings,
        max_pitcher_innings_per_game=team.max_pitcher_innings_per_game,
        max_pitcher_innings_per_7_days=team.max_pitcher_innings_per_7_days,
        late_inning_weight=team.late_inning_weight,
        mode=game.mode,
        strict_bench_fairness=not is_aa_or_aaa(team),
        h8_is_soft=True,
        compete_score_tolerance_pct=tolerance,
    )

    result = solve_lineup_options(player_infos, config, locked)

    if not result.options:
        raise_api_error(400, "no_feasible_lineup")

    options_payload = [
        {
            "option_id": opt.option_id,
            "status": opt.status,
            "quality_score": opt.quality_score,
            "dev_score": opt.dev_score,
            "objective_value": opt.objective_value,
            "assignments": opt.assignments,
        }
        for opt in result.options
    ]

    applied = game.mode == "optimal"
    if applied:
        snapshot_lineup(game, session, label="before_solve")
        from app.optimizer import SolverResult

        first = result.options[0]
        persist_solver_result(
            game,
            existing_lineup,
            SolverResult(first.assignments, first.objective_value, first.status),
            session,
        )

    return {
        "applied": applied,
        "mode": game.mode,
        "best_quality_score": result.best_quality_score,
        "tolerance_pct": result.tolerance_pct,
        "options": options_payload,
        # Backward-compatible fields when optimal auto-applied
        "status": result.options[0].status if applied else None,
        "objective_value": result.options[0].objective_value if applied else None,
        "assignments": result.options[0].assignments if applied else None,
    }


@router.post("/{game_id}/solve/apply")
def apply_solve_option(
    body: ApplySolveBody,
    game: Game = Depends(get_active_game),
    session: Session = Depends(get_session),
):
    """Persist a lineup option chosen from a compete/develop solve."""
    if game.mode == "optimal":
        raise_api_error(400, "solve_apply_not_needed")
    if not body.assignments:
        raise_api_error(400, "empty_lineup_assignments")

    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    available_players, _ = get_available_players(game, session)
    available_ids = {p.id for p in available_players}
    existing_lineup = prune_unavailable_lineup_cells(game, available_ids, session)

    from app.optimizer import SolverResult

    snapshot_lineup(game, session, label="before_solve")
    persist_solver_result(
        game,
        existing_lineup,
        SolverResult(body.assignments, 0, "applied"),
        session,
    )
    return {"ok": True}

# --- Pitcher Status ---

@router.get("/{game_id}/pitcher-status")
def get_pitcher_status(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    """
    Return pitcher eligibility for all active players for this game.
    Used by the frontend to show 🟢/🔴 indicators on the availability and lineup screens.
    """
    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    players = session.exec(select(Player).where(Player.team_id == game.team_id, Player.active == True, Player.is_coach == False)).all()

    statuses = []
    for p in players:
        eligibility = get_pitcher_eligibility(
            player_id=p.id,
            game_date=game.date,
            game_type=game.game_type,
            team=team,
            session=session,
            exclude_game_id=game.id,
        )
        statuses.append({
            "player_id": p.id,
            "jersey": p.jersey,
            "name": f"{p.first_name} {p.last_name}",
            "eligible": eligibility.eligible,
            "reason": eligibility.reason,
            "innings_today": eligibility.innings_today,
            "innings_last_7_days": eligibility.innings_last_7_days,
            "remaining_today": eligibility.remaining_today,
            "remaining_7_days": eligibility.remaining_7_days,
            "pitches_today": eligibility.pitches_today,
            "remaining_pitches_today": eligibility.remaining_pitches_today,
            "rest_until": eligibility.rest_until,
        })

    return statuses
