"""Build opponent intel from Spordle game and schedule data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.league_integrations.lfbq_spordle.client import SpordleClient
from app.league_integrations.lfbq_spordle.config import (
    get_intel_schedule_id,
    integration_is_configured,
    parse_schedules,
    resolve_spordle_game_across_schedules,
)
from app.league_integrations.lfbq_spordle.mapping import resolve_opponent_by_name
from app.standings_points import resolve_standings_points, win_pct as standings_win_pct
from app.league_integrations.registry import register_integration
from app.models import Game, Team

_client = SpordleClient()


def _team_name(game: dict, team_id: int) -> str:
    if game.get("homeTeamId") == team_id:
        return (game.get("homeTeam") or {}).get("name") or f"Team {team_id}"
    if game.get("awayTeamId") == team_id:
        return (game.get("awayTeam") or {}).get("name") or f"Team {team_id}"
    return f"Team {team_id}"


def _stat_for_team(game: dict, team_id: int) -> Optional[dict]:
    for row in game.get("teamStats") or []:
        if row.get("teamId") == team_id:
            return row
    return None


def _game_has_result(game: dict) -> bool:
    stats = game.get("teamStats") or []
    return len(stats) >= 2 and any(s.get("gameResult") for s in stats)


def _matchup_prefix(home_away: str | None) -> str:
    return "@" if home_away == "A" else "vs"


def _is_draw_result(game_result: str | None) -> bool:
    return game_result in ("draw", "tie")


def _format_wld_record(wins: int, losses: int, draws: int) -> str:
    return f"{wins}-{losses}-{draws}"


def _format_recent_game(game: dict, team_id: int) -> dict:
    stat = _stat_for_team(game, team_id)
    opponent_id = game["awayTeamId"] if game["homeTeamId"] == team_id else game["homeTeamId"]
    opponent_name = _team_name(game, opponent_id)
    home_away = "H" if game.get("homeTeamId") == team_id else "A"
    runs_for = stat.get("goalFor") if stat else None
    runs_against = stat.get("goalAgainst") if stat else None
    result = stat.get("gameResult") if stat else None
    if _is_draw_result(result):
        result = "tie"
    return {
        "date": game.get("date"),
        "opponent": opponent_name,
        "home_away": home_away,
        "score": f"{runs_for}-{runs_against}" if runs_for is not None and runs_against is not None else None,
        "result": result,
        "spordle_game_id": game.get("id"),
    }


def compute_standings(games: List[dict], config: dict | None = None) -> Dict[int, dict]:
    standings_points = resolve_standings_points(config)
    records: Dict[int, dict] = {}
    names: Dict[int, str] = {}

    for game in games:
        if not _game_has_result(game):
            continue
        for side in ("homeTeamId", "awayTeamId"):
            team_id = game.get(side)
            if team_id is None:
                continue
            names[team_id] = _team_name(game, team_id)
        for stat in game.get("teamStats") or []:
            team_id = stat.get("teamId")
            if team_id is None:
                continue
            rec = records.setdefault(
                team_id,
                {"wins": 0, "losses": 0, "draws": 0, "points": 0, "runs_for": 0, "runs_against": 0},
            )
            game_result = stat.get("gameResult")
            if game_result == "win":
                rec["wins"] += 1
            elif game_result == "loss":
                rec["losses"] += 1
            elif _is_draw_result(game_result):
                rec["draws"] += 1
            rec["points"] += stat.get("points") or 0
            rec["runs_for"] += stat.get("goalFor") or 0
            rec["runs_against"] += stat.get("goalAgainst") or 0

    ranked = sorted(
        records.items(),
        key=lambda item: (-item[1]["points"], -item[1]["wins"], item[1]["runs_against"]),
    )
    for rank, (team_id, rec) in enumerate(ranked, start=1):
        played = rec["wins"] + rec["losses"] + rec["draws"]
        rec["rank"] = rank
        rec["played"] = played
        rec["pct"] = standings_win_pct(rec["points"], played, standings_points)
        rec["avg_runs_for"] = round(rec["runs_for"] / played, 1) if played else None
        rec["avg_runs_against"] = round(rec["runs_against"] / played, 1) if played else None
        rec["team_name"] = names.get(team_id)

    return records


def recent_games_for_team(games: List[dict], team_id: int, *, limit: int = 5) -> List[dict]:
    completed = [g for g in games if _game_has_result(g)]
    completed.sort(key=lambda g: g.get("date") or "", reverse=True)
    results: List[dict] = []
    for game in completed:
        if game.get("homeTeamId") != team_id and game.get("awayTeamId") != team_id:
            continue
        results.append(_format_recent_game(game, team_id))
        if len(results) >= limit:
            break
    return results


RECENT_GAMES_LIMIT = 5


def _page_base(config: dict) -> Optional[str]:
    page_slug = config.get("page_slug")
    locale = config.get("locale", "fr")
    if not page_slug:
        return None
    return f"https://page.spordle.com/{locale}/{page_slug}"


def build_spordle_game_url(config: dict, game_id: int | str) -> Optional[str]:
    base = _page_base(config)
    if not base or game_id is None:
        return None
    return f"{base}/schedule/{game_id}"


def build_spordle_team_url(config: dict, team_id: int | str) -> Optional[str]:
    base = _page_base(config)
    if not base or team_id is None:
        return None
    return f"{base}/teams/{team_id}"


def build_spordle_schedule_url(config: dict, *, schedule_id: int | None = None) -> Optional[str]:
    """Division schedule page (schedule-stats-standings). Used to discover config IDs."""
    page_slug = config.get("page_slug")
    page_id = config.get("page_id")
    resolved_schedule_id = schedule_id or get_intel_schedule_id(config) or config.get("schedule_id")
    locale = config.get("locale", "fr")
    if not page_slug or not page_id or not resolved_schedule_id:
        return None
    return (
        f"https://page.spordle.com/{locale}/{page_slug}/schedule-stats-standings/"
        f"{page_id}?tab=schedule&scheduleId={resolved_schedule_id}"
    )


def build_spordle_url(config: dict) -> Optional[str]:
    """Backward-compatible alias for the league schedule page."""
    return build_spordle_schedule_url(config)


def get_opponent_intel_for_team(
    *,
    opponent_id: int,
    opponent_name: str,
    schedule_games: List[dict],
    config: dict,
    spordle_game_id: int | str | None = None,
) -> dict:
    standings = compute_standings(schedule_games, config)
    standing = standings.get(opponent_id)
    recent = recent_games_for_team(schedule_games, opponent_id, limit=RECENT_GAMES_LIMIT)
    for row in recent:
        row["spordle_url"] = build_spordle_game_url(config, row.get("spordle_game_id"))

    return {
        "available": True,
        "opponent_name": opponent_name,
        "standing": standing,
        "recent_games": recent,
        "recent_games_limit": RECENT_GAMES_LIMIT,
        "spordle_game_url": build_spordle_game_url(config, spordle_game_id),
        "spordle_team_url": build_spordle_team_url(config, opponent_id),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_opponent_intel_from_data(
    *,
    spordle_game: dict,
    schedule_games: List[dict],
    our_team_id: int,
    config: dict,
) -> dict:
    home_id = spordle_game.get("homeTeamId")
    away_id = spordle_game.get("awayTeamId")
    if our_team_id not in (home_id, away_id):
        return {"available": False, "reason": "our_team_not_in_game"}

    opponent_id = away_id if home_id == our_team_id else home_id
    opponent_name = _team_name(spordle_game, opponent_id)
    return get_opponent_intel_for_team(
        opponent_id=int(opponent_id),
        opponent_name=opponent_name,
        schedule_games=schedule_games,
        config=config,
        spordle_game_id=spordle_game.get("id"),
    )


def intel_dashboard_summary(intel: dict) -> dict:
    """Compact opponent intel for dashboard game cards."""
    if not intel.get("available"):
        return {"available": False}

    standing = intel.get("standing") or {}
    recent = intel.get("recent_games") or []
    last = recent[0] if recent else None
    last_result = None
    if last:
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
        if prefix and last.get("score"):
            last_result = f"{prefix} {last['score']}"
            if last.get("opponent"):
                last_result += f" {_matchup_prefix(last.get('home_away'))} {last['opponent']}"

    wins = standing.get("wins", 0)
    losses = standing.get("losses", 0)
    draws = standing.get("draws", 0)
    return {
        "available": True,
        "rank": standing.get("rank"),
        "record": _format_wld_record(wins, losses, draws),
        "runs_per_game": standing.get("avg_runs_for"),
        "last_result": last_result,
    }


@register_integration("lfbq_spordle")
def lfbq_spordle_opponent_intel(game: Game, team: Team, config: dict) -> dict:
    if not integration_is_configured(config):
        return {"available": False, "reason": "integration_not_configured"}

    our_team_id = int(config["our_spordle_team_id"])
    intel_schedule_id = get_intel_schedule_id(config)
    if not intel_schedule_id:
        return {"available": False, "reason": "integration_not_configured"}

    cache_ttl_hours = config.get("cache_ttl_hours", 6)
    cache_ttl_seconds = int(cache_ttl_hours * 3600)
    schedules = parse_schedules(config)

    try:
        season_games = _client.get_schedule_games(
            int(intel_schedule_id),
            cache_ttl_seconds=cache_ttl_seconds,
        )
        spordle_game = resolve_spordle_game_across_schedules(
            game,
            our_team_id,
            schedules,
            _client,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        if spordle_game is not None:
            return get_opponent_intel_from_data(
                spordle_game=spordle_game,
                schedule_games=season_games,
                our_team_id=our_team_id,
                config=config,
            )

        opponent = resolve_opponent_by_name(game, season_games, our_team_id)
        if opponent is None:
            return {"available": False, "reason": "game_not_linked"}

        return get_opponent_intel_for_team(
            opponent_id=opponent["team_id"],
            opponent_name=opponent["name"],
            schedule_games=season_games,
            config=config,
        )
    except Exception:
        return {"available": False, "reason": "fetch_failed"}
