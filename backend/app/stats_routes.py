from fastapi import APIRouter, Depends
from datetime import date
from sqlmodel import Session, or_, select
from app.db import get_session
from app.game_status import DISRUPTED_SCHEDULE_STATUSES
from app.stats import (
    get_season_batting,
    get_season_pitching,
    get_season_position,
    get_pitching_plan,
    get_development_trends,
)
from typing import List, Dict, Any
from app.auth import get_team_membership
from app.models import Game, Team
from app.game_intel import serialize_games_with_intel, upcoming_games_for_team


def _not_disrupted():
    """SQL predicate excluding postponed/cancelled games (NULL status is kept)."""
    return or_(
        Game.schedule_status.is_(None),
        Game.schedule_status.notin_(tuple(DISRUPTED_SCHEDULE_STATUSES)),
    )

router = APIRouter(prefix="/teams/{team_id}/stats", tags=["stats"])

@router.get("/batting")
def season_batting(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    return get_season_batting(team.id, session)

@router.get("/pitching")
def season_pitching(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    return get_season_pitching(team.id, session)

@router.get("/position")
def season_position(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    return get_season_position(team.id, session)

@router.get("/pitching-plan")
def pitching_plan(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> Dict[str, Any]:
    return get_pitching_plan(team.id, session)

@router.get("/trends")
def development_trends(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> Dict[str, Any]:
    return get_development_trends(team.id, session)

def _serialize_upcoming_games(games: List[Game], team: Team) -> List[dict]:
    return serialize_games_with_intel(games, team)

@router.get("/dashboard")
def team_dashboard(team: Team = Depends(get_team_membership), session: Session = Depends(get_session)) -> Dict[str, Any]:
    team_id = team.id
    team_name = team.name if team else "Home Team"

    today = date.today()
    
    last_game = session.exec(
        select(Game)
        .where(Game.team_id == team_id)
        .where(or_(Game.date < today, Game.result_runs_for.is_not(None)))
        .where(_not_disrupted())
        .order_by(Game.date.desc(), Game.id.desc())
        .limit(1)
    ).first()

    upcoming_games = upcoming_games_for_team(session, team_id)[:3]

    recent_games = session.exec(
        select(Game.id)
        .where(Game.team_id == team_id)
        .where(or_(Game.date < today, Game.result_runs_for.is_not(None)))
        .where(_not_disrupted())
        .order_by(Game.date.desc(), Game.id.desc())
        .limit(5)
    ).all()
    
    recent_batting = []
    recent_pitching = []
    if recent_games:
        batting_stats = get_season_batting(team_id, session, game_ids=recent_games)
        batting_stats = [s for s in batting_stats if s.get("pa", 0) > 0]
        recent_batting = batting_stats[:5]
        
        pitching_stats = get_season_pitching(team_id, session, game_ids=recent_games)
        pitching_stats = [s for s in pitching_stats if s.get("ip_outs", 0) > 0]
        recent_pitching = pitching_stats[:5]

    return {
        "team_name": team_name,
        "last_game": last_game,
        "upcoming_games": _serialize_upcoming_games(upcoming_games, team),
        "recent_batting": recent_batting,
        "recent_pitching": recent_pitching
    }


@router.post("/dashboard/warmup")
def dashboard_warmup(
    team: Team = Depends(get_team_membership),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    from app.league_integrations.warmup import warmup_dashboard

    return warmup_dashboard(session, team)
