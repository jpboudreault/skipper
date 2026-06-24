"""Map Spordle game payloads to Skipper fields and resolve games."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

from app.models import Game


def games_for_team(schedule_games: List[dict], our_team_id: int) -> List[dict]:
    return [
        g
        for g in schedule_games
        if g.get("homeTeamId") == our_team_id or g.get("awayTeamId") == our_team_id
    ]


def opponent_name(game: dict, our_team_id: int) -> str:
    if game.get("homeTeamId") == our_team_id:
        team = game.get("awayTeam") or {}
    else:
        team = game.get("homeTeam") or {}
    return team.get("shortName") or team.get("name") or "TBD"


def _stat_for_team(game: dict, team_id: int) -> Optional[dict]:
    for row in game.get("teamStats") or []:
        if row.get("teamId") == team_id:
            return row
    return None


def spordle_game_to_fields(spordle_game: dict, our_team_id: int, *, default_league: Optional[str]) -> dict:
    home_id = spordle_game.get("homeTeamId")
    away_id = spordle_game.get("awayTeamId")
    is_home = home_id == our_team_id
    stat = _stat_for_team(spordle_game, our_team_id)

    fields = {
        "date": spordle_game.get("date"),
        "game_number": spordle_game.get("number"),
        "opponent": opponent_name(spordle_game, our_team_id),
        "home_away": "H" if is_home else "A",
        "external_source": "spordle",
        "external_game_id": str(spordle_game["id"]),
        "league": default_league,
    }

    surface = spordle_game.get("surface") or {}
    venue = surface.get("name") or surface.get("shortName")
    if venue:
        fields["venue"] = venue

    if stat and stat.get("gameResult"):
        fields["result_runs_for"] = stat.get("goalFor")
        fields["result_runs_against"] = stat.get("goalAgainst")

    return fields


def normalize_team_label(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.upper().split())


def team_catalog_from_schedule(schedule_games: List[dict]) -> Dict[int, dict]:
    catalog: Dict[int, dict] = {}
    for game in schedule_games:
        for side in ("homeTeam", "awayTeam"):
            team = game.get(side) or {}
            team_id = team.get("id")
            if team_id is None:
                continue
            team_id = int(team_id)
            entry = catalog.setdefault(team_id, {"labels": set(), "display_name": None})
            labels: Set[str] = entry["labels"]
            for key in ("name", "shortName"):
                raw = team.get(key)
                if not raw:
                    continue
                labels.add(normalize_team_label(raw))
                if key == "name" or entry["display_name"] is None:
                    entry["display_name"] = raw
    return catalog


def resolve_opponent_by_name(
    game: Game,
    schedule_games: List[dict],
    our_team_id: int,
) -> Optional[dict]:
    """Match a Skipper opponent name to a Spordle team in the schedule."""
    query = normalize_team_label(game.opponent)
    if not query:
        return None

    catalog = team_catalog_from_schedule(schedule_games)
    exact_matches: List[tuple[int, str]] = []
    for team_id, entry in catalog.items():
        if team_id == our_team_id:
            continue
        if query in entry["labels"]:
            exact_matches.append((team_id, entry["display_name"] or query))

    if len(exact_matches) == 1:
        team_id, display_name = exact_matches[0]
        return {"team_id": team_id, "name": display_name}

    if len(exact_matches) > 1:
        return None

    substring_matches: List[tuple[int, str]] = []
    for team_id, entry in catalog.items():
        if team_id == our_team_id:
            continue
        for label in entry["labels"]:
            if query in label or label in query:
                substring_matches.append((team_id, entry["display_name"] or label))
                break

    if len(substring_matches) == 1:
        team_id, display_name = substring_matches[0]
        return {"team_id": team_id, "name": display_name}

    return None


def resolve_spordle_game(
    game: Game,
    schedule_games: List[dict],
    our_team_id: int,
) -> Optional[dict]:
    if game.external_game_id:
        for spordle_game in schedule_games:
            if str(spordle_game.get("id")) == str(game.external_game_id):
                return spordle_game
        return None

    game_date = game.date.isoformat() if isinstance(game.date, date) else str(game.date)
    candidates = [
        g
        for g in schedule_games
        if g.get("date") == game_date
        and our_team_id in (g.get("homeTeamId"), g.get("awayTeamId"))
    ]
    if not candidates:
        return None
    if game.game_number:
        numbered = [g for g in candidates if g.get("number") == game.game_number]
        if numbered:
            candidates = numbered
    if len(candidates) == 1:
        return candidates[0]
    return candidates[0]


def pick_existing_game(
    existing_games: List[Game],
    spordle_game: dict,
) -> Optional[Game]:
    external_id = str(spordle_game["id"])
    for game in existing_games:
        if game.external_game_id == external_id:
            return game

    spordle_date = spordle_game.get("date")
    date_matches = [
        g
        for g in existing_games
        if (g.date.isoformat() if isinstance(g.date, date) else str(g.date)) == spordle_date
    ]
    if not date_matches:
        return None

    number = spordle_game.get("number")
    if number:
        for game in date_matches:
            if game.game_number == number:
                return game

    unmatched = [g for g in date_matches if not g.external_game_id]
    if len(unmatched) == 1:
        return unmatched[0]
    if len(date_matches) == 1:
        return date_matches[0]
    return None
