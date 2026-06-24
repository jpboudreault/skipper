"""Serialize games with compact opponent intel for list views."""

from __future__ import annotations

from datetime import date
from typing import List

from sqlmodel import Session, select

from app.models import Game, Team


def serialize_games_with_intel(games: List[Game], team: Team) -> List[dict]:
    from app.league_integrations import get_opponent_intel
    from app.league_integrations.lfbq_spordle.intel import intel_dashboard_summary

    result = []
    for game in games:
        payload = game.model_dump()
        payload["intel"] = intel_dashboard_summary(get_opponent_intel(game, team))
        result.append(payload)
    return result


def upcoming_games_for_team(session: Session, team_id: int) -> List[Game]:
    today = date.today()
    return session.exec(
        select(Game)
        .where(Game.team_id == team_id)
        .where(Game.date >= today)
        .where(Game.result_runs_for.is_(None))
        .order_by(Game.date.asc(), Game.id.asc())
    ).all()
