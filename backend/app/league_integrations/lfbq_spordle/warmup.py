"""Lightweight dashboard warmup: cache schedule, link games, prefetch intel."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.league_integrations.lfbq_spordle.client import SpordleClient
from app.league_integrations.lfbq_spordle.config import (
    integration_is_configured,
    parse_integration_config,
    parse_schedules,
)
from app.league_integrations.lfbq_spordle.mapping import resolve_spordle_game
from app.league_integrations.registry import get_opponent_intel
from app.models import Game, Team

_client = SpordleClient()


def _link_game_to_spordle(game: Game, schedule_games: list, our_team_id: int) -> bool:
    if game.external_game_id:
        return False
    spordle_game = resolve_spordle_game(game, schedule_games, our_team_id)
    if spordle_game is None:
        return False
    game.external_source = "spordle"
    game.external_game_id = str(spordle_game["id"])
    return True


def warmup_team_dashboard(session: Session, team: Team, *, limit: int = 3) -> dict:
    if team.integration_version != "lfbq_spordle":
        return {"ok": False, "reason": "integration_not_configured"}

    config = parse_integration_config(team.integration_config_json)
    if not integration_is_configured(config):
        return {"ok": False, "reason": "integration_not_configured"}

    our_team_id = int(config["our_spordle_team_id"])
    schedules = parse_schedules(config)
    cache_ttl_hours = config.get("cache_ttl_hours", 6)
    cache_ttl_seconds = int(cache_ttl_hours * 3600)

    today = date.today()
    upcoming = session.exec(
        select(Game)
        .where(Game.team_id == team.id)
        .where(Game.date >= today)
        .where(Game.result_runs_for.is_(None))
        .order_by(Game.date.asc(), Game.id.asc())
        .limit(limit)
    ).all()

    linked = 0
    for game in upcoming:
        if game.external_game_id:
            continue
        for schedule in schedules:
            schedule_games = _client.get_schedule_games(
                schedule["schedule_id"],
                cache_ttl_seconds=cache_ttl_seconds,
            )
            if _link_game_to_spordle(game, schedule_games, our_team_id):
                session.add(game)
                linked += 1
                break
    if linked:
        session.commit()

    intel_prefetched = 0
    for game in upcoming:
        intel = get_opponent_intel(game, team)
        if intel.get("available"):
            intel_prefetched += 1

    return {
        "ok": True,
        "linked": linked,
        "intel_prefetched": intel_prefetched,
        "upcoming_games": len(upcoming),
    }
