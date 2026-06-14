from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.db import get_session
from app.stats import get_season_batting, get_season_pitching, get_season_position, get_pitching_plan
from typing import List, Dict, Any
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/teams/{team_id}/stats", tags=["stats"])

@router.get("/batting")
def season_batting(team_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    current_user = session.get(User, current_user.id)
    if team_id not in {t.id for t in current_user.teams}:
        raise HTTPException(status_code=403, detail="Not authorized for this team")
    return get_season_batting(team_id, session)

@router.get("/pitching")
def season_pitching(team_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    current_user = session.get(User, current_user.id)
    if team_id not in {t.id for t in current_user.teams}:
        raise HTTPException(status_code=403, detail="Not authorized for this team")
    return get_season_pitching(team_id, session)

@router.get("/position")
def season_position(team_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    current_user = session.get(User, current_user.id)
    if team_id not in {t.id for t in current_user.teams}:
        raise HTTPException(status_code=403, detail="Not authorized for this team")
    return get_season_position(team_id, session)

@router.get("/pitching-plan")
def pitching_plan(team_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    current_user = session.get(User, current_user.id)
    if team_id not in {t.id for t in current_user.teams}:
        raise HTTPException(status_code=403, detail="Not authorized for this team")
    return get_pitching_plan(team_id, session)

from datetime import date
from sqlmodel import or_, select
from app.models import Game, Team

@router.get("/dashboard")
def team_dashboard(team_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    current_user = session.get(User, current_user.id)
    if team_id not in {t.id for t in current_user.teams}:
        raise HTTPException(status_code=403, detail="Not authorized for this team")

    team = session.get(Team, team_id)
    team_name = team.name if team else "Home Team"

    today = date.today()
    
    last_game = session.exec(
        select(Game)
        .where(Game.team_id == team_id)
        .where(or_(Game.date < today, Game.result_runs_for.is_not(None)))
        .order_by(Game.date.desc(), Game.id.desc())
        .limit(1)
    ).first()
    
    upcoming_games = session.exec(
        select(Game)
        .where(Game.team_id == team_id)
        .where(Game.date >= today)
        .where(Game.result_runs_for.is_(None))
        .order_by(Game.date.asc(), Game.id.asc())
        .limit(3)
    ).all()
    
    recent_games = session.exec(
        select(Game.id)
        .where(Game.team_id == team_id)
        .where(or_(Game.date < today, Game.result_runs_for.is_not(None)))
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
        "upcoming_games": upcoming_games,
        "recent_batting": recent_batting,
        "recent_pitching": recent_pitching
    }


