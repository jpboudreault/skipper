"""League standings point values (win / draw / loss) with tenant defaults."""

from __future__ import annotations

from typing import Mapping, TypedDict


class StandingsPoints(TypedDict):
    win: int
    draw: int
    loss: int


DEFAULT_STANDINGS_POINTS: StandingsPoints = {"win": 2, "draw": 1, "loss": 0}


def resolve_standings_points(config: Mapping[str, object] | None) -> StandingsPoints:
    """Read standings_points from integration/tenant config, with defaults."""
    raw = (config or {}).get("standings_points") or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "win": int(raw.get("win", DEFAULT_STANDINGS_POINTS["win"])),
        "draw": int(raw.get("draw", DEFAULT_STANDINGS_POINTS["draw"])),
        "loss": int(raw.get("loss", DEFAULT_STANDINGS_POINTS["loss"])),
    }


def points_from_record(
    wins: int,
    losses: int,
    draws: int,
    standings_points: StandingsPoints | None = None,
) -> int:
    pts = standings_points or DEFAULT_STANDINGS_POINTS
    return (
        wins * pts["win"]
        + draws * pts["draw"]
        + losses * pts["loss"]
    )


def win_pct(points: int, played: int, standings_points: StandingsPoints | None = None) -> float:
    """Win % = points earned / max points possible (win value per game)."""
    if played <= 0:
        return 0.0
    pts = standings_points or DEFAULT_STANDINGS_POINTS
    max_points = played * pts["win"]
    if max_points <= 0:
        return 0.0
    return round(points / max_points, 3)
