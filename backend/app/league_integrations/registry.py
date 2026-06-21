"""Registry for league-specific integrations (schedule intel, etc.)."""

from typing import Any, Callable, Dict, List, Optional

from app.models import Game, Team

OpponentIntelProvider = Callable[[Game, Team, dict], dict]

_INTEGRATIONS: Dict[str, OpponentIntelProvider] = {}


def register_integration(version: str):
    """Decorator to register an opponent intel provider for a league integration."""

    def decorator(fn: OpponentIntelProvider) -> OpponentIntelProvider:
        _INTEGRATIONS[version] = fn
        return fn

    return decorator


def get_opponent_intel(
    game: Game,
    team: Team,
    config: Optional[dict] = None,
) -> dict:
    """Return opponent intel payload for a game, or {available: False}."""
    version = team.integration_version
    if not version:
        return {"available": False}

    provider = _INTEGRATIONS.get(version)
    if provider is None:
        return {"available": False}

    resolved_config = config if config is not None else _parse_team_config(team)
    return provider(game, team, resolved_config)


def _parse_team_config(team: Team) -> dict:
    if not team.integration_config_json:
        return {}
    import json

    try:
        parsed = json.loads(team.integration_config_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def list_integration_versions() -> List[str]:
    return sorted(_INTEGRATIONS.keys())
