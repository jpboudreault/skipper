"""Tests for LFBQ Spordle schedule sync and opponent intel."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.league_integrations.lfbq_spordle.config import parse_schedules
from app.league_integrations.lfbq_spordle.intel import (
    build_spordle_game_url,
    build_spordle_team_url,
    compute_standings,
    get_opponent_intel_from_data,
    intel_dashboard_summary,
    recent_games_for_team,
)
from app.league_integrations.lfbq_spordle.mapping import resolve_spordle_game
from app.models import Game, Team

FIXTURES = Path(__file__).parent / "fixtures" / "spordle"


def load_fixture(name: str):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def test_parse_schedules_legacy_single_schedule_id():
    schedules = parse_schedules({"schedule_id": 193095})
    assert schedules == [{"schedule_id": 193095, "game_type": "season", "label": None}]


def test_parse_schedules_multiple():
    schedules = parse_schedules(
        {
            "schedules": [
                {"schedule_id": 193095, "game_type": "season", "label": "Regular"},
                {"schedule_id": 195112, "game_type": "postseason", "label": "Playoffs"},
                {"schedule_id": 196000, "game_type": "tournament", "label": "Provincial"},
            ]
        }
    )
    assert len(schedules) == 3
    assert schedules[1]["game_type"] == "postseason"


def test_compute_standings_with_draw():
    games = [
        {
            "id": 1,
            "date": "2026-05-01",
            "homeTeamId": 100,
            "awayTeamId": 200,
            "homeTeam": {"id": 100, "name": "HOME"},
            "awayTeam": {"id": 200, "name": "AWAY"},
            "teamStats": [
                {"teamId": 100, "goalFor": 5, "goalAgainst": 5, "gameResult": "draw", "points": 1},
                {"teamId": 200, "goalFor": 5, "goalAgainst": 5, "gameResult": "draw", "points": 1},
            ],
        },
        {
            "id": 2,
            "date": "2026-05-02",
            "homeTeamId": 100,
            "awayTeamId": 300,
            "homeTeam": {"id": 100, "name": "HOME"},
            "awayTeam": {"id": 300, "name": "OTHER"},
            "teamStats": [
                {"teamId": 100, "goalFor": 8, "goalAgainst": 3, "gameResult": "win", "points": 2},
                {"teamId": 300, "goalFor": 3, "goalAgainst": 8, "gameResult": "loss", "points": 0},
            ],
        },
    ]
    standings = compute_standings(games)
    home = standings[100]
    assert home["wins"] == 1
    assert home["losses"] == 0
    assert home["draws"] == 1
    assert home["points"] == 3
    assert home["played"] == 2
    assert home["pct"] == 0.75  # 3 pts / 4 max pts (2 pts per win)


def test_compute_standings_custom_points_config():
    games = [
        {
            "id": 1,
            "date": "2026-05-01",
            "homeTeamId": 100,
            "awayTeamId": 200,
            "homeTeam": {"id": 100, "name": "HOME"},
            "awayTeam": {"id": 200, "name": "AWAY"},
            "teamStats": [
                {"teamId": 100, "goalFor": 5, "goalAgainst": 5, "gameResult": "draw", "points": 1},
                {"teamId": 200, "goalFor": 5, "goalAgainst": 5, "gameResult": "draw", "points": 1},
            ],
        },
        {
            "id": 2,
            "date": "2026-05-02",
            "homeTeamId": 100,
            "awayTeamId": 300,
            "homeTeam": {"id": 100, "name": "HOME"},
            "awayTeam": {"id": 300, "name": "OTHER"},
            "teamStats": [
                {"teamId": 100, "goalFor": 8, "goalAgainst": 3, "gameResult": "win", "points": 3},
                {"teamId": 300, "goalFor": 3, "goalAgainst": 8, "gameResult": "loss", "points": 0},
            ],
        },
    ]
    config = {"standings_points": {"win": 3, "draw": 1, "loss": 0}}
    standings = compute_standings(games, config)
    home = standings[100]
    assert home["points"] == 4
    assert home["pct"] == round(4 / 6, 3)


def test_intel_dashboard_summary_draw_last_result():
    games = load_fixture("schedule_games.json") + [
        {
            "id": 999999,
            "date": "2026-05-26",
            "homeTeamId": 162670,
            "awayTeamId": 170000,
            "homeTeam": {"id": 162670, "name": "RIVAL STARS"},
            "awayTeam": {"id": 170000, "name": "TIGERS"},
            "teamStats": [
                {"teamId": 162670, "goalFor": 6, "goalAgainst": 6, "gameResult": "draw", "points": 1},
                {"teamId": 170000, "goalFor": 6, "goalAgainst": 6, "gameResult": "draw", "points": 1},
            ],
        }
    ]
    upcoming = load_fixture("upcoming_game.json")
    config = {"page_slug": "ligue-feminine-de-baseball-du-quebec", "schedule_id": 193095, "locale": "fr"}
    intel = get_opponent_intel_from_data(
        spordle_game=upcoming,
        schedule_games=games,
        our_team_id=167495,
        config=config,
    )
    summary = intel_dashboard_summary(intel)
    assert summary["record"] == "0-3-1"
    assert summary["last_result"].startswith("D 6-6")


def test_compute_standings_and_recent_games():
    games = load_fixture("schedule_games.json")
    standings = compute_standings(games)
    rival = standings[162670]
    assert rival["wins"] == 0
    assert rival["losses"] == 3
    assert rival["draws"] == 0
    assert rival["pct"] == 0.0
    assert rival["rank"] >= 1
    assert rival["avg_runs_for"] == round((11 + 5 + 9) / 3, 1)
    assert rival["avg_runs_against"] == round((12 + 10 + 13) / 3, 1)

    recent = recent_games_for_team(games, 162670, limit=3)
    assert len(recent) == 3
    assert recent[0]["opponent"] == "CARDINALS"


def test_get_opponent_intel_from_data():
    games = load_fixture("schedule_games.json")
    upcoming = load_fixture("upcoming_game.json")
    config = {
        "page_slug": "ligue-feminine-de-baseball-du-quebec",
        "page_id": "fe1509f0-a2b2-4964-8c2a-c2c24cad5f37",
        "schedule_id": 193095,
        "locale": "fr",
    }
    intel = get_opponent_intel_from_data(
        spordle_game=upcoming,
        schedule_games=games,
        our_team_id=167495,
        config=config,
    )
    assert intel["available"] is True
    assert intel["opponent_name"] == "RIVAL STARS"
    assert intel["standing"]["losses"] == 3
    assert intel["standing"]["avg_runs_for"] == round((11 + 5 + 9) / 3, 1)
    assert len(intel["recent_games"]) == 3
    assert intel["recent_games_limit"] == 5
    assert intel["spordle_game_url"] == (
        "https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/schedule/900001"
    )
    assert intel["spordle_team_url"] == (
        "https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/teams/162670"
    )
    assert intel["recent_games"][0]["spordle_url"].endswith("/schedule/842370")


def test_intel_dashboard_summary():
    games = load_fixture("schedule_games.json")
    upcoming = load_fixture("upcoming_game.json")
    config = {
        "page_slug": "ligue-feminine-de-baseball-du-quebec",
        "schedule_id": 193095,
        "locale": "fr",
    }
    intel = get_opponent_intel_from_data(
        spordle_game=upcoming,
        schedule_games=games,
        our_team_id=167495,
        config=config,
    )
    summary = intel_dashboard_summary(intel)
    assert summary["available"] is True
    assert summary["rank"] >= 1
    assert summary["record"] == "0-3-0"
    assert summary["runs_per_game"] == round((11 + 5 + 9) / 3, 1)
    assert summary["last_result"] is not None
    assert summary["last_result"].startswith("L ")


def test_intel_dashboard_summary_unavailable():
    assert intel_dashboard_summary({"available": False}) == {"available": False}


def test_spordle_page_urls():
    config = {
        "page_slug": "ligue-feminine-de-baseball-du-quebec",
        "locale": "fr",
    }
    assert build_spordle_game_url(config, 846892) == (
        "https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/schedule/846892"
    )
    assert build_spordle_team_url(config, 163211) == (
        "https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/teams/163211"
    )


def test_resolve_spordle_game_by_date():
    games = load_fixture("schedule_games.json")
    game = Game(
        team_id=1,
        date=date(2026, 6, 1),
        opponent="Rival",
        mode="compete",
    )
    resolved = resolve_spordle_game(game, games, 167495)
    assert resolved is not None
    assert resolved["id"] == 900001


@pytest.mark.asyncio
async def test_opponent_intel_endpoint_by_date(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "schedule_id": 193095,
            "our_spordle_team_id": 167495,
            "page_slug": "ligue-feminine-de-baseball-du-quebec",
            "page_id": "fe1509f0-a2b2-4964-8c2a-c2c24cad5f37",
        }
    )
    session.add(team)
    session.commit()

    game_res = await client.post(
        "/games/",
        json={"date": "2026-06-01", "opponent": "Rival", "mode": "compete"},
    )
    game_id = game_res.json()["id"]
    schedule = load_fixture("schedule_games.json")

    with patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        return_value=schedule,
    ):
        res = await client.get(f"/games/{game_id}/opponent-intel")

    payload = res.json()
    assert res.status_code == 200
    assert payload["available"] is True
    assert payload["opponent_name"] == "RIVAL STARS"


@pytest.mark.asyncio
async def test_sync_schedule_endpoint(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193095, "our_spordle_team_id": 167495}
    )
    team.default_league = "LFBQ"
    session.add(team)
    session.commit()

    schedule = load_fixture("schedule_games.json")
    team_games = [
        g for g in schedule if g["homeTeamId"] == 167495 or g["awayTeamId"] == 167495
    ]

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        return_value=schedule,
    ):
        res = await client.post("/games/sync-schedule")

    payload = res.json()
    assert res.status_code == 200
    assert payload["ok"] is True
    assert payload["created"] >= 1

    list_res = await client.get("/games/")
    synced = list_res.json()
    assert any(g.get("external_game_id") for g in synced)


@pytest.mark.asyncio
async def test_sync_schedule_preserves_game_mode(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193095, "our_spordle_team_id": 167495}
    )
    session.add(team)
    session.commit()

    game_res = await client.post(
        "/games/",
        json={"date": "2026-06-01", "opponent": "Rival", "mode": "develop"},
    )
    assert game_res.status_code == 200
    game_id = game_res.json()["id"]

    schedule = load_fixture("schedule_games.json")
    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        return_value=schedule,
    ):
        res = await client.post("/games/sync-schedule")

    assert res.status_code == 200
    assert res.json()["ok"] is True

    updated = await client.get(f"/games/{game_id}")
    assert updated.json()["mode"] == "develop"


@pytest.mark.asyncio
async def test_dashboard_warmup_links_and_prefetches(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193095, "our_spordle_team_id": 167495}
    )
    session.add(team)
    session.commit()

    game_res = await client.post(
        "/games/",
        json={"date": "2026-06-01", "opponent": "Rival", "mode": "compete"},
    )
    game_id = game_res.json()["id"]
    schedule = load_fixture("schedule_games.json")

    with patch(
        "app.league_integrations.lfbq_spordle.warmup.date"
    ) as mock_date, patch(
        "app.league_integrations.lfbq_spordle.warmup._client.get_schedule_games",
        return_value=schedule,
    ), patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        return_value=schedule,
    ):
        mock_date.today.return_value = date(2026, 5, 15)
        res = await client.post(f"/teams/{team.id}/stats/dashboard/warmup")

    payload = res.json()
    assert res.status_code == 200
    assert payload["ok"] is True
    assert payload["linked"] == 1
    assert payload["intel_prefetched"] == 1

    linked = await client.get(f"/games/{game_id}")
    assert linked.json()["external_game_id"] == "900001"


PLAYOFF_GAME = {
    "id": 910001,
    "date": "2026-07-01",
    "scheduleId": 195112,
    "number": "P1",
    "homeTeamId": 167495,
    "awayTeamId": 162670,
    "homeTeam": {"id": 167495, "name": "BLUE EXPOS"},
    "awayTeam": {"id": 162670, "name": "RIVAL STARS"},
    "teamStats": [],
}


def _schedule_games_side_effect(schedule_id: int, **_kwargs):
    if schedule_id == 193095:
        return load_fixture("schedule_games.json")
    if schedule_id == 195112:
        return [PLAYOFF_GAME]
    return []


@pytest.mark.asyncio
async def test_sync_multiple_schedules_sets_game_type(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "our_spordle_team_id": 167495,
            "schedules": [
                {"schedule_id": 193095, "game_type": "season"},
                {"schedule_id": 195112, "game_type": "postseason"},
            ],
        }
    )
    team.default_league = "LFBQ"
    session.add(team)
    session.commit()

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        side_effect=_schedule_games_side_effect,
    ):
        res = await client.post("/games/sync-schedule")

    payload = res.json()
    assert res.status_code == 200
    assert payload["ok"] is True
    assert len(payload["schedules"]) == 2

    list_res = await client.get("/games/")
    synced = list_res.json()
    postseason = [g for g in synced if g.get("game_type") == "postseason"]
    assert len(postseason) == 1
    assert postseason[0]["external_game_id"] == "910001"


@pytest.mark.asyncio
async def test_opponent_intel_playoff_game_uses_season_standings(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "our_spordle_team_id": 167495,
            "page_slug": "ligue-feminine-de-baseball-du-quebec",
            "schedules": [
                {"schedule_id": 193095, "game_type": "season"},
                {"schedule_id": 195112, "game_type": "postseason"},
            ],
        }
    )
    session.add(team)
    session.commit()

    game_res = await client.post(
        "/games/",
        json={
            "date": "2026-07-01",
            "opponent": "Rival",
            "mode": "compete",
            "game_type": "postseason",
            "external_source": "spordle",
            "external_game_id": "910001",
        },
    )
    game_id = game_res.json()["id"]

    with patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        side_effect=_schedule_games_side_effect,
    ):
        res = await client.get(f"/games/{game_id}/opponent-intel")

    payload = res.json()
    assert res.status_code == 200
    assert payload["available"] is True
    assert payload["opponent_name"] == "RIVAL STARS"
    assert payload["standing"]["losses"] == 3


@pytest.mark.asyncio
async def test_upcoming_intel_returns_all_games(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "our_spordle_team_id": 167495,
            "page_slug": "ligue-feminine-de-baseball-du-quebec",
            "schedules": [{"schedule_id": 193095, "game_type": "season"}],
        }
    )
    session.add(team)
    session.commit()

    schedule = load_fixture("schedule_games.json")
    created_ids = []
    for offset, game_date in enumerate(["2026-06-01", "2026-06-08", "2026-06-15", "2026-06-22", "2026-06-29"]):
        game_res = await client.post(
            "/games/",
            json={"date": game_date, "opponent": f"Rival {offset}", "mode": "compete"},
        )
        created_ids.append(game_res.json()["id"])

    with patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        return_value=schedule,
    ), patch("app.game_intel.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 15)
        res = await client.get("/games/upcoming-intel")

    payload = res.json()
    assert res.status_code == 200
    assert len(payload) == 5
    assert {row["id"] for row in payload} == set(created_ids)
    assert all("intel" in row for row in payload)


@pytest.mark.asyncio
async def test_dashboard_includes_intel_teaser(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "schedule_id": 193095,
            "our_spordle_team_id": 167495,
            "page_slug": "ligue-feminine-de-baseball-du-quebec",
        }
    )
    session.add(team)
    session.commit()

    game_res = await client.post(
        "/games/",
        json={"date": "2026-06-01", "opponent": "Rival", "mode": "compete"},
    )
    assert game_res.status_code == 200
    game_id = game_res.json()["id"]

    schedule = load_fixture("schedule_games.json")
    with patch(
        "app.stats_routes.date"
    ) as mock_date, patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        return_value=schedule,
    ), patch(
        "app.league_integrations.lfbq_spordle.warmup.date"
    ) as mock_warmup_date, patch(
        "app.league_integrations.lfbq_spordle.warmup._client.get_schedule_games",
        return_value=schedule,
    ):
        mock_date.today.return_value = date(2026, 5, 15)
        mock_warmup_date.today.return_value = date(2026, 5, 15)
        await client.post(f"/teams/{team.id}/stats/dashboard/warmup")
        res = await client.get(f"/teams/{team.id}/stats/dashboard")

    payload = res.json()
    assert res.status_code == 200
    upcoming = payload["upcoming_games"]
    assert len(upcoming) >= 1
    matched = next(g for g in upcoming if g["id"] == game_id)
    assert matched["intel"]["available"] is True
    assert matched["intel"]["record"] == "0-3-0"
