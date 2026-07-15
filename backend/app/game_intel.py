"""Serialize games with compact opponent intel for list views.

This module is integration-agnostic: it resolves opponent intel through the
`app.league_integrations` registry and reasons about games using core concepts
(`schedule_status`, the standard intel contract) rather than any specific
third-party provider.
"""

from __future__ import annotations

from datetime import date
from typing import List

from sqlmodel import Session, select

from app.game_status import is_disrupted_schedule_status
from app.models import Game, Team
from app.opponent_intel import intel_dashboard_summary


def serialize_games_with_intel(games: List[Game], team: Team) -> List[dict]:
    from app.league_integrations import get_opponent_intel

    result = []
    for game in games:
        payload = game.model_dump()
        payload["intel"] = intel_dashboard_summary(get_opponent_intel(game, team))
        result.append(payload)
    return result


def upcoming_games_for_team(session: Session, team_id: int) -> List[Game]:
    today = date.today()
    games = session.exec(
        select(Game)
        .where(Game.team_id == team_id)
        .where(Game.date >= today)
        .where(Game.result_runs_for.is_(None))
        .order_by(Game.date.asc(), Game.id.asc())
    ).all()
    return [game for game in games if not is_disrupted_schedule_status(game.schedule_status)]
