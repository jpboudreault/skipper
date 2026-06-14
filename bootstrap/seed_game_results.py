#!/usr/bin/env python3
"""Seed final scores and batting lines for demo games."""

from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def api_request(
    method: str,
    url: str,
    token: str,
    team_id: int,
    payload: Any | None = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Active-Team-ID": str(team_id),
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {body}") from exc


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pick_csv(script_dir: Path, name: str) -> Path:
    custom = script_dir / name
    if custom.exists():
        print(f"Using {name}")
        return custom
    example = script_dir / f"{name}.example"
    print(f"No {name} found — using {example.name}")
    return example


def find_game(games: list[dict[str, Any]], game_date: str, opponent: str) -> dict[str, Any]:
    for game in games:
        if game.get("date") == game_date and game.get("opponent") == opponent:
            return game
    raise RuntimeError(f"Game not found for {game_date} vs {opponent}")


def find_player(players: list[dict[str, Any]], first_name: str, last_name: str) -> dict[str, Any]:
    for player in players:
        if player.get("first_name") == first_name and player.get("last_name") == last_name:
            return player
    raise RuntimeError(f"Player not found: {first_name} {last_name}")


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: seed_game_results.py <URL> <TOKEN>")
        return 1

    base_url = sys.argv[1].rstrip("/")
    token = sys.argv[2]
    script_dir = Path(__file__).resolve().parent

    results_csv = pick_csv(script_dir, "game_results.csv")
    batting_csv = pick_csv(script_dir, "game_batting.csv")

    games_cache: dict[int, list[dict[str, Any]]] = {}
    players_cache: dict[int, list[dict[str, Any]]] = {}

    def get_games(team_id: int) -> list[dict[str, Any]]:
        if team_id not in games_cache:
            games_cache[team_id] = api_request("GET", f"{base_url}/api/games/", token, team_id)
        return games_cache[team_id]

    def get_players(team_id: int) -> list[dict[str, Any]]:
        if team_id not in players_cache:
            players_cache[team_id] = api_request("GET", f"{base_url}/api/players/", token, team_id)
        return players_cache[team_id]

    print(f"Seeding game results to: {base_url}")

    for row in read_csv(results_csv):
        team_id = int(row["team_id"])
        game_date = row["date"].strip()
        opponent = row["opponent"].strip()
        game = find_game(get_games(team_id), game_date, opponent)

        payload = {
            "date": game["date"],
            "opponent": game.get("opponent"),
            "venue": game.get("venue"),
            "home_away": game.get("home_away"),
            "mode": game.get("mode", "develop"),
            "game_type": game.get("game_type", "season"),
            "innings_played": int(row["innings_played"]),
            "result_runs_for": int(row["runs_for"]),
            "result_runs_against": int(row["runs_against"]),
        }
        api_request("PUT", f"{base_url}/api/games/{game['id']}", token, team_id, payload)
        print(
            f" -> Team {team_id}: {game_date} vs {opponent} "
            f"({row['runs_for']}-{row['runs_against']}, {row['innings_played']} IP)"
        )

    batting_groups: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    int_fields = ("batting_order", "singles", "doubles", "triples", "hr", "bb", "rbi", "r", "sb", "outs_not_k")

    for row in read_csv(batting_csv):
        key = (int(row["team_id"]), row["date"].strip(), row["opponent"].strip())
        batting_groups.setdefault(key, []).append(row)

    for (team_id, game_date, opponent), rows in batting_groups.items():
        game = find_game(get_games(team_id), game_date, opponent)
        players = get_players(team_id)
        lines = []

        for row in rows:
            player = find_player(players, row["first_name"].strip(), row["last_name"].strip())
            line = {"player_id": player["id"]}
            for field in int_fields:
                if row.get(field, "").strip():
                    line[field] = int(row[field])
            lines.append(line)

        api_request("PUT", f"{base_url}/api/games/{game['id']}/batting", token, team_id, lines)
        print(f" -> Team {team_id}: batting lines for {game_date} vs {opponent} ({len(lines)} players)")

    print("Game results seeding complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
