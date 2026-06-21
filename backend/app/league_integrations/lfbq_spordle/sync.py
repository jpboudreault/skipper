"""Sync Skipper games from a Spordle team schedule."""

from __future__ import annotations

import json
from datetime import date as date_type

from sqlmodel import Session, select

from app.league_integrations.lfbq_spordle.client import SpordleClient
from app.league_integrations.lfbq_spordle.mapping import (
    games_for_team,
    pick_existing_game,
    spordle_game_to_fields,
)
from app.models import Availability, Game, Player, Team

_client = SpordleClient()


def _parse_config(team: Team) -> dict:
    if not team.integration_config_json:
        return {}
    try:
        parsed = json.loads(team.integration_config_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _seed_availability(session: Session, game_id: int, team_id: int) -> None:
    active_players = session.exec(
        select(Player).where(Player.team_id == team_id, Player.active == True, Player.is_coach == False)
    ).all()
    for player in active_players:
        session.add(
            Availability(
                game_id=game_id,
                player_id=player.id,
                status="absent" if player.is_substitute else "available",
            )
        )


def _apply_spordle_fields(game: Game, fields: dict) -> None:
    for key, value in fields.items():
        if value is None:
            continue
        if key in ("result_runs_for", "result_runs_against"):
            if getattr(game, key) is None:
                setattr(game, key, value)
            continue
        setattr(game, key, value)


def sync_team_schedule(session: Session, team: Team) -> dict:
    if team.integration_version != "lfbq_spordle":
        return {"ok": False, "reason": "integration_not_configured"}

    config = _parse_config(team)
    schedule_id = config.get("schedule_id")
    our_team_id = config.get("our_spordle_team_id")
    if not schedule_id or not our_team_id:
        return {"ok": False, "reason": "integration_not_configured"}

    our_team_id = int(our_team_id)
    cache_ttl_hours = config.get("cache_ttl_hours", 6)
    schedule_games = _client.get_schedule_games(
        int(schedule_id),
        cache_ttl_seconds=int(cache_ttl_hours * 3600),
    )
    team_games = games_for_team(schedule_games, our_team_id)

    existing_games = session.exec(select(Game).where(Game.team_id == team.id)).all()
    created = 0
    updated = 0
    linked = 0

    for spordle_game in team_games:
        fields = spordle_game_to_fields(
            spordle_game,
            our_team_id,
            default_league=team.default_league,
        )
        if fields.get("date"):
            fields["date"] = date_type.fromisoformat(fields["date"])
        match = pick_existing_game(existing_games, spordle_game)
        if match:
            had_external = bool(match.external_game_id)
            _apply_spordle_fields(match, fields)
            session.add(match)
            updated += 1
            if not had_external:
                linked += 1
            continue

        game = Game(team_id=team.id, **fields)
        session.add(game)
        session.commit()
        session.refresh(game)
        _seed_availability(session, game.id, team.id)
        existing_games.append(game)
        created += 1

    session.commit()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "linked": linked,
        "spordle_games": len(team_games),
    }
