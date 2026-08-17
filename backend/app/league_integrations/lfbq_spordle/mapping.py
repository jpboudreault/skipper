"""Map Spordle game payloads to Skipper fields and resolve games."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

from app.game_status import is_disrupted_schedule_status, normalize_schedule_status
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


def normalize_spordle_status(status: str | None) -> str | None:
    """Map Spordle's status labels onto canonical `schedule_status` values.

    Spordle uses `Active`, `Postponed`, `Cancelled`, ... which already match the
    canonical lowercase values, so this just normalizes casing/whitespace.
    """
    return normalize_schedule_status(status)


def _stat_for_team(game: dict, team_id: int) -> Optional[dict]:
    for row in game.get("teamStats") or []:
        if row.get("teamId") == team_id:
            return row
    return None


def _scores_from_score_dict(spordle_game: dict, our_team_id: int) -> tuple[Optional[int], Optional[int]]:
    score = spordle_game.get("score")
    if not isinstance(score, dict):
        return None, None
    home_id = spordle_game.get("homeTeamId")
    away_id = spordle_game.get("awayTeamId")
    if our_team_id not in (home_id, away_id):
        return None, None
    opp_id = away_id if home_id == our_team_id else home_id
    our_runs = score.get(str(our_team_id), score.get(our_team_id))
    opp_runs = score.get(str(opp_id), score.get(opp_id))
    if our_runs is None or opp_runs is None:
        return None, None
    return int(our_runs), int(opp_runs)


def _schedule_notes(spordle_game: dict) -> Optional[str]:
    comments = spordle_game.get("comments")
    if isinstance(comments, str):
        stripped = comments.strip()
        if stripped:
            return stripped
    return None


def _opponent_matches(game_opponent: str | None, spordle_game: dict, our_team_id: int) -> bool:
    expected = normalize_team_label(game_opponent)
    if not expected or expected == "TBD":
        return False
    actual = normalize_team_label(opponent_name(spordle_game, our_team_id))
    return expected == actual or expected in actual or actual in expected


def spordle_game_to_fields(spordle_game: dict, our_team_id: int, *, default_league: Optional[str]) -> dict:
    home_id = spordle_game.get("homeTeamId")
    is_home = home_id == our_team_id
    stat = _stat_for_team(spordle_game, our_team_id)
    schedule_status = normalize_spordle_status(spordle_game.get("status"))

    fields = {
        "date": spordle_game.get("date"),
        "game_number": spordle_game.get("number"),
        "opponent": opponent_name(spordle_game, our_team_id),
        "home_away": "H" if is_home else "A",
        "external_source": "spordle",
        "external_game_id": str(spordle_game["id"]),
        "league": default_league,
        "schedule_status": schedule_status,
    }

    surface = spordle_game.get("surface") or {}
    venue = surface.get("name") or surface.get("shortName")
    if venue:
        fields["venue"] = venue

    notes = _schedule_notes(spordle_game)
    if notes:
        fields["notes"] = notes

    if not is_disrupted_schedule_status(schedule_status):
        if stat and stat.get("gameResult"):
            fields["result_runs_for"] = stat.get("goalFor")
            fields["result_runs_against"] = stat.get("goalAgainst")
        else:
            runs_for, runs_against = _scores_from_score_dict(spordle_game, our_team_id)
            if runs_for is not None and runs_against is not None:
                fields["result_runs_for"] = runs_for
                fields["result_runs_against"] = runs_against

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


def _game_date_str(game: Game) -> str:
    return game.date.isoformat() if isinstance(game.date, date) else str(game.date)


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

    game_date = _game_date_str(game)
    candidates = [
        g
        for g in schedule_games
        if g.get("date") == game_date
        and our_team_id in (g.get("homeTeamId"), g.get("awayTeamId"))
    ]
    if not candidates:
        return None

    # Game number is unique per schedule per day, so it is the reliable key for
    # disambiguating double-headers (two games the same day, often vs the same
    # opponent).
    if game.game_number:
        numbered = [g for g in candidates if g.get("number") == game.game_number]
        if len(numbered) == 1:
            return numbered[0]
        if numbered:
            candidates = numbered

    if game.opponent:
        name_matches = [
            g for g in candidates if _opponent_matches(game.opponent, g, our_team_id)
        ]
        if len(name_matches) == 1:
            return name_matches[0]

    if len(candidates) == 1:
        return candidates[0] if _opponent_matches(game.opponent, candidates[0], our_team_id) else None

    # Still ambiguous (e.g. an unlinked double-header vs the same opponent):
    # don't guess, so we never link a game to the wrong Spordle fixture.
    return None


def pick_existing_game(
    existing_games: List[Game],
    spordle_game: dict,
    *,
    our_team_id: int | None = None,
) -> Optional[Game]:
    external_id = str(spordle_game["id"])
    for game in existing_games:
        if game.external_game_id == external_id:
            return game

    spordle_date = spordle_game.get("date")
    date_matches = [g for g in existing_games if _game_date_str(g) == spordle_date]
    if not date_matches:
        return None

    # Exact game-number match is the strongest signal and distinguishes the
    # halves of a double-header, which share a date (and often an opponent).
    number = spordle_game.get("number")
    if number:
        for game in date_matches:
            if game.game_number and game.game_number == number:
                return game

    # Only games not already linked to a *different* Spordle fixture can absorb
    # this one. A same-date game with a different external_game_id belongs to
    # another fixture (double-header half, or a league vs. tournament game on
    # the same day), so it must never be overwritten.
    linkable = [g for g in date_matches if not g.external_game_id]

    # A game the user already numbered differently is also a distinct fixture.
    if number:
        linkable = [g for g in linkable if not (g.game_number and g.game_number != number)]

    if our_team_id is not None:
        expected_opponent = normalize_team_label(opponent_name(spordle_game, our_team_id))
        if expected_opponent:
            name_matches = [
                g for g in linkable if normalize_team_label(g.opponent) == expected_opponent
            ]
            if len(name_matches) == 1:
                return name_matches[0]

    if len(linkable) == 1:
        return linkable[0]
    return None
