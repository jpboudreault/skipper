"""Integration-agnostic opponent intel contract and helpers.

League integrations (see `app.league_integrations`) return opponent intel as a
standard dict so the rest of the app never depends on a specific provider:

    {
        "available": bool,
        "opponent_name": str,
        "standing": {
            "rank": int | None,
            "wins": int,
            "losses": int,
            "draws": int,
            "avg_runs_for": float | None,
            ...
        } | None,
        "recent_games": [
            {
                "result": "win" | "loss" | "tie" | "draw" | None,
                "score": str | None,
                "home_away": "H" | "A" | None,
                "opponent": str | None,
                ...
            },
            ...
        ],
        ...
    }

Anything that consumes intel (dashboards, game lists) should work purely off of
this shape, allowing new third-party integrations to plug in without touching
core code.
"""

from __future__ import annotations

from typing import Optional


def matchup_prefix(home_away: Optional[str]) -> str:
    """Sports notation: away games are '@ opponent', otherwise 'vs opponent'."""
    return "@" if home_away == "A" else "vs"


def format_record(wins: int, losses: int, draws: int) -> str:
    return f"{wins}-{losses}-{draws}"


def _last_result_label(recent_games: list) -> Optional[str]:
    last = recent_games[0] if recent_games else None
    if not last:
        return None
    result = last.get("result")
    prefix = (
        "W"
        if result == "win"
        else "L"
        if result == "loss"
        else "D"
        if result in ("tie", "draw")
        else None
    )
    if not prefix or not last.get("score"):
        return None
    label = f"{prefix} {last['score']}"
    if last.get("opponent"):
        label += f" {matchup_prefix(last.get('home_away'))} {last['opponent']}"
    return label


def intel_dashboard_summary(intel: dict) -> dict:
    """Compact opponent intel for dashboard game cards.

    Operates on the standard intel contract, so it is shared by every
    integration rather than being provider-specific.
    """
    if not intel.get("available"):
        return {"available": False}

    standing = intel.get("standing") or {}
    recent = intel.get("recent_games") or []
    return {
        "available": True,
        "rank": standing.get("rank"),
        "record": format_record(
            standing.get("wins", 0),
            standing.get("losses", 0),
            standing.get("draws", 0),
        ),
        "runs_per_game": standing.get("avg_runs_for"),
        "last_result": _last_result_label(recent),
    }
