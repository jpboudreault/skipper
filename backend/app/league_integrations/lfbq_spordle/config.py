"""LFBQ Spordle integration config helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models import Game

VALID_GAME_TYPES = frozenset({"season", "postseason", "tournament"})


def parse_integration_config(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_schedules(config: dict) -> List[Dict[str, Any]]:
    """Normalize schedule entries from integration config."""
    raw = config.get("schedules")
    if isinstance(raw, list) and raw:
        schedules: List[Dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            schedule_id = entry.get("schedule_id")
            if schedule_id is None:
                continue
            game_type = entry.get("game_type") or "season"
            if game_type not in VALID_GAME_TYPES:
                game_type = "season"
            schedules.append(
                {
                    "schedule_id": int(schedule_id),
                    "game_type": game_type,
                    "label": entry.get("label"),
                }
            )
        if schedules:
            return schedules

    schedule_id = config.get("schedule_id")
    if schedule_id is not None:
        game_type = config.get("game_type") or "season"
        if game_type not in VALID_GAME_TYPES:
            game_type = "season"
        return [
            {
                "schedule_id": int(schedule_id),
                "game_type": game_type,
                "label": None,
            }
        ]
    return []


def integration_is_configured(config: dict) -> bool:
    return bool(parse_schedules(config) and config.get("our_spordle_team_id"))


def get_intel_schedule_id(config: dict) -> Optional[int]:
    """Spordle schedule used for opponent standings and recent games."""
    for schedule in parse_schedules(config):
        if schedule["game_type"] == "season":
            return schedule["schedule_id"]
    schedules = parse_schedules(config)
    if schedules:
        return schedules[0]["schedule_id"]
    return None


def resolve_spordle_game_across_schedules(
    game: Game,
    our_team_id: int,
    schedules: List[Dict[str, Any]],
    client: Any,
    *,
    cache_ttl_seconds: int,
) -> Optional[dict]:
    from app.league_integrations.lfbq_spordle.mapping import resolve_spordle_game

    for schedule in schedules:
        schedule_games = client.get_schedule_games(
            schedule["schedule_id"],
            cache_ttl_seconds=cache_ttl_seconds,
        )
        spordle_game = resolve_spordle_game(game, schedule_games, our_team_id)
        if spordle_game is not None:
            return spordle_game
    return None
