from fastapi import APIRouter, Depends, UploadFile, File
from app.auth import get_current_user, get_active_team
from app.i18n.errors import raise_api_error
from sqlmodel import Session, select
from app.models import (
    Game, GameCreate, Availability, BattingLine, PitchingAppearance,
    Lineup, Player, PositionScore, Team
)
from app.optimizer import solve_lineup, PlayerInfo, OptimizerConfig, LockedCell
from app.rest_calculator import get_pitcher_eligibility
from app.db import get_session
from typing import List, Optional
from pydantic import BaseModel
import os
import re

router = APIRouter(prefix="/games", tags=["games"])

MIN_LINEUP_INNINGS = 1
MAX_LINEUP_INNINGS = 12

# --- Helper Dependency ---

def resolve_lineup_innings(game: Game, team: Team) -> int:
    return game.innings_played or team.innings_per_game

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

def delete_game_dependencies(game_id: int, session: Session) -> None:
    for model in (Availability, BattingLine, PitchingAppearance, Lineup):
        rows = session.exec(select(model).where(model.game_id == game_id)).all()
        for row in rows:
            session.delete(row)

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
    delete_game_dependencies(game.id, session)
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

    # Delete existing lineup for this game and re-insert
    existing = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    for e in existing:
        session.delete(e)
    
    for cell in cells:
        lineup = Lineup(game_id=game.id, **cell.model_dump())
        session.add(lineup)
    session.commit()
    return {"ok": True}

# --- Solve (Optimizer) ---

@router.post("/{game_id}/solve")
def solve_game_lineup(game: Game = Depends(get_active_game), session: Session = Depends(get_session)):
    """
    Run the CP-SAT optimizer for this game.
    Uses locked lineup cells as pre-assignments, respects availability,
    and uses position scores + game mode (compete/develop).
    """
    team = session.get(Team, game.team_id)
    if not team:
        raise_api_error(404, "team_not_found")

    innings = resolve_lineup_innings(game, team)

    # Get available players (excluding coaches)
    all_players = session.exec(select(Player).where(Player.team_id == game.team_id, Player.active == True, Player.is_coach == False)).all()
    
    # Check availability
    avails = session.exec(select(Availability).where(Availability.game_id == game.id)).all()
    absent_ids = {a.player_id for a in avails if a.status in ("absent", "injured")}
    available_players = [p for p in all_players if p.id not in absent_ids]

    if len(available_players) < 9:
        raise_api_error(400, "insufficient_players", count=len(available_players))

    # Gather position scores
    all_scores = session.exec(select(PositionScore)).all()
    scores_by_player = {}
    forbidden_by_player = {}
    for s in all_scores:
        scores_by_player.setdefault(s.player_id, {})[s.position] = s.score
        if s.is_forbidden:
            forbidden_by_player.setdefault(s.player_id, set()).add(s.position)

    # Build PlayerInfo list with real rest eligibility
    player_infos = []
    for p in available_players:
        eligibility = get_pitcher_eligibility(
            player_id=p.id,
            game_date=game.date,
            game_type=game.game_type,
            team=team,
            session=session,
            exclude_game_id=game.id,
        )
        forbidden = forbidden_by_player.get(p.id, set())
        if p.is_substitute:
            forbidden.add(1)
        
        avail_record = next((a for a in avails if a.player_id == p.id), None)
        injury_inning = avail_record.injury_inning if avail_record else None
            
        player_infos.append(PlayerInfo(
            id=p.id,
            name=f"{p.first_name} {p.last_name}",
            jersey=p.jersey,
            position_scores=scores_by_player.get(p.id, {}),
            forbidden_positions=forbidden,
            pitcher_innings_last_7_days=eligibility.innings_last_7_days,
            is_pitch_eligible=eligibility.eligible if not p.is_substitute else False,
            injury_inning=injury_inning
        ))

    # Clean up and delete any existing lineup cells for players who are NOT available
    existing_lineup = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    available_ids = {p.id for p in available_players}
    for lc in existing_lineup:
        if lc.player_id not in available_ids:
            session.delete(lc)
    session.commit()

    # Re-fetch the cleaned lineup to build locked cells list
    existing_lineup = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    locked = [
        LockedCell(player_id=lc.player_id, inning=lc.inning, position=lc.position)
        for lc in existing_lineup if lc.locked
    ]

    # Pre-solver validations for coach lock constraints

    # 1. H1 duplicate positions in the same inning
    pos_locks = {}
    for lc in existing_lineup:
        if lc.locked and lc.position > 0:
            p = next((p for p in available_players if p.id == lc.player_id), None)
            p_name = f"{p.first_name} {p.last_name}" if p else f"Player #{lc.player_id}"
            pos_locks.setdefault((lc.inning, lc.position), []).append(p_name)
            
    for (inn, pos), p_names in pos_locks.items():
        if len(p_names) > 1:
            raise_api_error(
                400,
                "duplicate_position_lock",
                inning=inn,
                position_id=pos,
                players=", ".join(p_names),
            )

    # 2. H2 duplicate player assignments in the same inning
    player_locks = {}
    for lc in existing_lineup:
        if lc.locked:
            player_locks.setdefault((lc.inning, lc.player_id), []).append(lc.position)
            
    for (inn, p_id), positions in player_locks.items():
        if len(positions) > 1:
            p = next((p for p in available_players if p.id == p_id), None)
            p_name = f"{p.first_name} {p.last_name}" if p else f"Player #{p_id}"
            raise_api_error(
                400,
                "multiple_positions_lock",
                inning=inn,
                player_name=p_name,
                position_ids=positions,
            )

    # 3. H6 & H5 Pitcher Innings Cap & Re-entry checks
    for p in available_players:
        p_cells = [lc for lc in existing_lineup if lc.player_id == p.id]
        p_locked_cells = [c for c in p_cells if c.locked]
        pitching_innings = sorted([c.inning for c in p_locked_cells if c.position == 1])
        
        if pitching_innings:
            p_name = f"{p.first_name} {p.last_name}"
            
            # Game Cap
            if len(pitching_innings) > team.max_pitcher_innings_per_game:
                raise_api_error(
                    400,
                    "pitcher_game_cap",
                    player_name=p_name,
                    count=len(pitching_innings),
                    max=team.max_pitcher_innings_per_game,
                )
                
            # 7-day Cap
            eligibility = get_pitcher_eligibility(
                player_id=p.id,
                game_date=game.date,
                game_type=game.game_type,
                team=team,
                session=session,
                exclude_game_id=game.id,
            )
            remaining_7_days = team.max_pitcher_innings_per_7_days - eligibility.innings_last_7_days
            if remaining_7_days < 0:
                remaining_7_days = 0
            if len(pitching_innings) > remaining_7_days:
                raise_api_error(
                    400,
                    "pitcher_7day_cap",
                    player_name=p_name,
                    count=len(pitching_innings),
                    remaining=remaining_7_days,
                    pitched=eligibility.innings_last_7_days,
                )

            # Re-entry check
            if len(pitching_innings) > 1:
                # Minimum required innings because of no re-entry (must pitch continuously)
                min_required = pitching_innings[-1] - pitching_innings[0] + 1
                
                # Check for direct lock violations in intermediate innings
                for inn in range(pitching_innings[0] + 1, pitching_innings[-1]):
                    between_cell = next((c for c in p_cells if c.inning == inn), None)
                    if between_cell and between_cell.locked and between_cell.position != 1:
                        raise_api_error(
                            400,
                            "pitcher_reentry_violation",
                            player_name=p_name,
                            first_inning=pitching_innings[0],
                            last_inning=pitching_innings[-1],
                            between_inning=inn,
                            position_id=between_cell.position,
                        )
                
                # Check if the continuous block length exceeds caps
                if min_required > team.max_pitcher_innings_per_game:
                    raise_api_error(
                        400,
                        "pitcher_reentry_game_cap",
                        player_name=p_name,
                        first_inning=pitching_innings[0],
                        last_inning=pitching_innings[-1],
                        min_required=min_required,
                        max=team.max_pitcher_innings_per_game,
                    )
                if min_required > remaining_7_days:
                    raise_api_error(
                        400,
                        "pitcher_reentry_7day_cap",
                        player_name=p_name,
                        first_inning=pitching_innings[0],
                        last_inning=pitching_innings[-1],
                        min_required=min_required,
                        remaining=remaining_7_days,
                    )

    # 4. H8 Catcher -> Pitcher rest violation (Catcher in Inning i, Pitcher in Inning i+1)
    for p in available_players:
        p_locks = [lc for lc in existing_lineup if lc.locked and lc.player_id == p.id]
        p_name = f"{p.first_name} {p.last_name}"
        for c in p_locks:
            if c.position == 2:  # Catcher
                next_lock = next((nl for nl in p_locks if nl.inning == c.inning + 1), None)
                if next_lock and next_lock.position == 1:  # Pitcher next inning
                    raise_api_error(
                        400,
                        "catcher_pitcher_rest",
                        player_name=p_name,
                        catcher_inning=c.inning,
                        pitcher_inning=c.inning + 1,
                    )

    # 5. H9 Forbidden positions or substitutes pitching
    for p in available_players:
        forbidden = forbidden_by_player.get(p.id, set())
        if p.is_substitute:
            forbidden.add(1)
        p_locks = [lc for lc in existing_lineup if lc.locked and lc.player_id == p.id]
        p_name = f"{p.first_name} {p.last_name}"
        for c in p_locks:
            if c.position in forbidden:
                if c.position == 1 and p.is_substitute:
                    raise_api_error(
                        400,
                        "forbidden_position_substitute_pitch",
                        player_name=p_name,
                        inning=c.inning,
                    )
                raise_api_error(
                    400,
                    "forbidden_position",
                    player_name=p_name,
                    position_id=c.position,
                    inning=c.inning,
                )

    config = OptimizerConfig(
        innings=innings,
        max_pitcher_innings_per_game=team.max_pitcher_innings_per_game,
        max_pitcher_innings_per_7_days=team.max_pitcher_innings_per_7_days,
        late_inning_weight=team.late_inning_weight,
        mode=game.mode,
    )

    result = solve_lineup(player_infos, config, locked)

    if result.status == "infeasible":
        raise_api_error(400, "no_feasible_lineup")

    # Save the result to the lineup table (replace non-locked cells)
    # First remove non-locked cells
    for lc in existing_lineup:
        if not lc.locked:
            session.delete(lc)
    
    # Add solver results (skip cells that are already locked)
    locked_set = {(l.player_id, l.inning, l.position) for l in existing_lineup if l.locked}
    for a in result.assignments:
        key = (a["player_id"], a["inning"], a["position"])
        if key not in locked_set:
            cell = Lineup(
                game_id=game.id,
                inning=a["inning"],
                player_id=a["player_id"],
                position=a["position"],
                locked=a["locked"],
            )
            session.add(cell)
    
    session.commit()

    return {
        "status": result.status,
        "objective_value": result.objective_value,
        "assignments": result.assignments,
    }

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
        })

    return statuses
