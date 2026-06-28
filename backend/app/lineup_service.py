"""
Service layer for lineup solving.

This module isolates the optimizer orchestration and the coach-lock pre-solver
validations from the HTTP layer in ``game_routes.py`` so they can be unit-tested
directly against a database session without going through FastAPI/auth.
"""

import json
from typing import Dict, List, Optional, Set, Tuple

from sqlmodel import Session, select

from app.i18n.errors import raise_api_error
from app.models import Availability, Game, Lineup, LineupSnapshot, Player, PositionScore, Team
from app.optimizer import PlayerInfo, SolverResult
from app.rest_calculator import get_pitcher_eligibility


def get_available_players(
    game: Game, session: Session
) -> Tuple[List[Player], List[Availability]]:
    """Return active, non-coach players who are not absent/injured, plus availability rows."""
    all_players = session.exec(
        select(Player).where(
            Player.team_id == game.team_id,
            Player.active == True,  # noqa: E712 (SQLModel needs == comparison)
            Player.is_coach == False,  # noqa: E712
        )
    ).all()
    avails = session.exec(
        select(Availability).where(Availability.game_id == game.id)
    ).all()
    absent_ids = {a.player_id for a in avails if a.status in ("absent", "injured")}
    available = [p for p in all_players if p.id not in absent_ids]
    return available, avails


def load_position_scores(
    game: Game, session: Session
) -> Tuple[Dict[int, Dict[int, int]], Dict[int, Set[int]]]:
    """Load position scores for this team's players only (avoids cross-tenant leakage)."""
    all_scores = session.exec(
        select(PositionScore).join(Player).where(Player.team_id == game.team_id)
    ).all()
    scores_by_player: Dict[int, Dict[int, int]] = {}
    forbidden_by_player: Dict[int, Set[int]] = {}
    for s in all_scores:
        scores_by_player.setdefault(s.player_id, {})[s.position] = s.score
        if s.is_forbidden:
            forbidden_by_player.setdefault(s.player_id, set()).add(s.position)
    return scores_by_player, forbidden_by_player


def build_player_infos(
    available_players: List[Player],
    avails: List[Availability],
    scores_by_player: Dict[int, Dict[int, int]],
    forbidden_by_player: Dict[int, Set[int]],
    game: Game,
    team: Team,
    session: Session,
) -> List[PlayerInfo]:
    player_infos: List[PlayerInfo] = []
    for p in available_players:
        eligibility = get_pitcher_eligibility(
            player_id=p.id,
            game_date=game.date,
            game_type=game.game_type,
            team=team,
            session=session,
            exclude_game_id=game.id,
        )
        forbidden = set(forbidden_by_player.get(p.id, set()))
        if p.is_substitute:
            forbidden.add(1)

        avail_record = next((a for a in avails if a.player_id == p.id), None)
        injury_inning = avail_record.injury_inning if avail_record else None

        player_infos.append(
            PlayerInfo(
                id=p.id,
                name=f"{p.first_name} {p.last_name}",
                jersey=p.jersey,
                position_scores=scores_by_player.get(p.id, {}),
                forbidden_positions=forbidden,
                pitcher_innings_last_7_days=eligibility.innings_last_7_days,
                is_pitch_eligible=eligibility.eligible if not p.is_substitute else False,
                injury_inning=injury_inning,
            )
        )
    return player_infos


def validate_locked_cells(
    existing_lineup: List[Lineup],
    available_players: List[Player],
    forbidden_by_player: Dict[int, Set[int]],
    game: Game,
    team: Team,
    session: Session,
) -> None:
    """Run the coach-lock pre-solver validations (H1, H2, H5/H6, H9).

    Raises an API error on the first violation; returns ``None`` when locks are valid.
    """
    # H1: duplicate positions in the same inning
    pos_locks: Dict[Tuple[int, int], List[str]] = {}
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

    # H2: duplicate player assignments in the same inning
    player_locks: Dict[Tuple[int, int], List[int]] = {}
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

    # H6 & H5: pitcher innings cap & re-entry checks
    for p in available_players:
        p_cells = [lc for lc in existing_lineup if lc.player_id == p.id]
        p_locked_cells = [c for c in p_cells if c.locked]
        pitching_innings = sorted([c.inning for c in p_locked_cells if c.position == 1])

        if pitching_innings:
            p_name = f"{p.first_name} {p.last_name}"

            # Game cap
            if len(pitching_innings) > team.max_pitcher_innings_per_game:
                raise_api_error(
                    400,
                    "pitcher_game_cap",
                    player_name=p_name,
                    count=len(pitching_innings),
                    max=team.max_pitcher_innings_per_game,
                )

            # 7-day cap
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

    # H9: forbidden positions or substitutes pitching
    for p in available_players:
        forbidden = set(forbidden_by_player.get(p.id, set()))
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


def prune_unavailable_lineup_cells(
    game: Game, available_player_ids: Set[int], session: Session
) -> List[Lineup]:
    """Delete lineup cells for players who are no longer available; return the cleaned list."""
    existing_lineup = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    for lc in existing_lineup:
        if lc.player_id not in available_player_ids:
            session.delete(lc)
    session.commit()
    return session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()


def persist_solver_result(
    game: Game, existing_lineup: List[Lineup], result: SolverResult, session: Session
) -> None:
    """Replace non-locked cells with the solver's assignments."""
    for lc in existing_lineup:
        if not lc.locked:
            session.delete(lc)

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


# --- Lineup history / undo (snapshots) ---

MAX_SNAPSHOTS_PER_GAME = 20


def snapshot_lineup(
    game: Game, session: Session, label: str = "snapshot"
) -> Optional[LineupSnapshot]:
    """Save the current lineup grid as a snapshot. Returns None if the lineup is empty.

    Keeps at most ``MAX_SNAPSHOTS_PER_GAME`` snapshots per game (oldest pruned).
    """
    cells = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    if not cells:
        return None

    payload = [
        {"inning": c.inning, "player_id": c.player_id, "position": c.position, "locked": c.locked}
        for c in cells
    ]
    snapshot = LineupSnapshot(game_id=game.id, label=label, cells_json=json.dumps(payload))
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    existing = session.exec(
        select(LineupSnapshot)
        .where(LineupSnapshot.game_id == game.id)
        .order_by(LineupSnapshot.created_at.desc(), LineupSnapshot.id.desc())
    ).all()
    for stale in existing[MAX_SNAPSHOTS_PER_GAME:]:
        session.delete(stale)
    session.commit()
    return snapshot


def list_snapshots(game: Game, session: Session) -> List[dict]:
    snapshots = session.exec(
        select(LineupSnapshot)
        .where(LineupSnapshot.game_id == game.id)
        .order_by(LineupSnapshot.created_at.desc(), LineupSnapshot.id.desc())
    ).all()
    result = []
    for s in snapshots:
        try:
            cell_count = len(json.loads(s.cells_json))
        except (json.JSONDecodeError, TypeError):
            cell_count = 0
        result.append(
            {
                "id": s.id,
                "label": s.label,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "cell_count": cell_count,
            }
        )
    return result


def restore_snapshot(game: Game, snapshot_id: int, session: Session) -> int:
    """Replace the game's lineup with the snapshot's cells. Returns number of cells restored."""
    snapshot = session.get(LineupSnapshot, snapshot_id)
    if not snapshot or snapshot.game_id != game.id:
        raise_api_error(404, "lineup_snapshot_not_found")

    try:
        cells = json.loads(snapshot.cells_json)
    except (json.JSONDecodeError, TypeError):
        cells = []

    existing = session.exec(select(Lineup).where(Lineup.game_id == game.id)).all()
    for c in existing:
        session.delete(c)

    for cell in cells:
        session.add(
            Lineup(
                game_id=game.id,
                inning=cell["inning"],
                player_id=cell["player_id"],
                position=cell["position"],
                locked=cell.get("locked", False),
            )
        )
    session.commit()
    return len(cells)
