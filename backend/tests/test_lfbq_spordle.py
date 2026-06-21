"""Tests for LFBQ Spordle schedule sync and opponent intel."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.league_integrations.lfbq_spordle.intel import (
    compute_standings,
    get_opponent_intel_from_data,
    recent_games_for_team,
)
from app.league_integrations.lfbq_spordle.mapping import resolve_spordle_game
from app.models import Game, Team

FIXTURES = Path(__file__).parent / "fixtures" / "spordle"


def load_fixture(name: str):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def test_compute_standings_and_recent_games():
    games = load_fixture("schedule_games.json")
    standings = compute_standings(games)
    rival = standings[162670]
    assert rival["wins"] == 0
    assert rival["losses"] == 3
    assert rival["rank"] >= 1

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
    assert len(intel["recent_games"]) == 3
    assert "spordle.com" in intel["spordle_url"]


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
