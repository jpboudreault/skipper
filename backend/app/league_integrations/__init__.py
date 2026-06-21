"""League-specific integrations (opponent intel, schedule sources)."""

from app.league_integrations.registry import (
    get_opponent_intel,
    list_integration_versions,
    register_integration,
)

from app.league_integrations.lfbq_spordle import intel  # noqa: F401

__all__ = [
    "get_opponent_intel",
    "list_integration_versions",
    "register_integration",
]
