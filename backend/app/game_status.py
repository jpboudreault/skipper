"""Integration-agnostic game schedule-status helpers.

`Game.schedule_status` is a core, provider-neutral concept. Each league
integration is responsible for mapping its own provider-specific status
strings onto these canonical values before persisting a game. The rest of the
app (upcoming lists, dashboards, warmup) only ever reasons about the canonical
values defined here, so it never depends on a specific third-party system.
"""

from __future__ import annotations

from typing import Optional

SCHEDULE_STATUS_POSTPONED = "postponed"
SCHEDULE_STATUS_CANCELLED = "cancelled"

# Statuses that mean a game is no longer a normal, playable fixture and should
# be hidden from "upcoming" surfaces.
DISRUPTED_SCHEDULE_STATUSES = frozenset(
    {SCHEDULE_STATUS_POSTPONED, SCHEDULE_STATUS_CANCELLED}
)


def normalize_schedule_status(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    normalized = status.strip().lower()
    return normalized or None


def is_disrupted_schedule_status(status: Optional[str]) -> bool:
    return normalize_schedule_status(status) in DISRUPTED_SCHEDULE_STATUSES
