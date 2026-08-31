"""Tests for LFBQ Spordle schedule sync and opponent intel."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.league_integrations.lfbq_spordle.config import parse_schedules
from app.league_integrations.lfbq_spordle.intel import (
    build_spordle_game_url,
    build_spordle_team_url,
    compute_standings,
    get_opponent_intel_from_data,
    intel_dashboard_summary,
    recent_games_for_team,
)
from app.league_integrations.lfbq_spordle.mapping import (
    pick_existing_game,
    resolve_opponent_by_name,
    resolve_spordle_game,
    spordle_game_to_fields,
    is_disrupted_schedule_status,
)
from app.models import Availability, Game, Player, Team

FIXTURES = Path(__file__).parent / "fixtures" / "spordle"


def load_fixture(name: str):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def test_spordle_game_to_fields_postponed_status():
    fields = spordle_game_to_fields(
        {
            "id": 829373,
            "date": "2026-07-17",
            "number": "13UB-0130",
            "homeTeamId": 167215,
            "awayTeamId": 170000,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 170000, "shortName": "PHÉNIX"},
            "status": "Postponed",
            "comments": "Equipe en tournoi",
            "teamStats": [],
        },
        167215,
        default_league="LFBQ",
    )
    assert fields["schedule_status"] == "postponed"
    assert fields["notes"] == "Equipe en tournoi"
    assert "result_runs_for" not in fields
    assert is_disrupted_schedule_status(fields["schedule_status"])


def test_spordle_game_to_fields_score_dict_fallback():
    fields = spordle_game_to_fields(
        {
            "id": 900100,
            "date": "2026-07-13",
            "number": "13UB-0126",
            "homeTeamId": 167215,
            "awayTeamId": 158339,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 158339, "shortName": "BRAVES"},
            "status": "Active",
            "teamStats": [],
            "score": {"167215": 7, "158339": 3},
        },
        167215,
        default_league="LFBQ",
    )
    assert fields["result_runs_for"] == 7
    assert fields["result_runs_against"] == 3


def test_pick_existing_game_matches_opponent_on_same_date():
    existing = [
        Game(
            id=1,
            team_id=1,
            date=date(2026, 7, 17),
            opponent="BRAVES",
            game_type="tournament",
        ),
        Game(
            id=2,
            team_id=1,
            date=date(2026, 7, 17),
            opponent="PHÉNIX",
            game_type="season",
        ),
    ]
    spordle_game = {
        "id": 880343,
        "date": "2026-07-17",
        "number": "F18",
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
    }
    match = pick_existing_game(existing, spordle_game, our_team_id=167215)
    assert match is not None
    assert match.opponent == "BRAVES"


def test_pick_existing_game_does_not_clobber_other_linked_game_on_same_date():
    # A postponed league game is already linked to a different Spordle id on the
    # same day as a tournament game. The tournament game must NOT be merged into
    # it — pick_existing_game should return None so the caller creates a new game.
    existing = [
        Game(
            id=1,
            team_id=1,
            date=date(2026, 7, 17),
            opponent="PHÉNIX",
            game_number="13UB-0130",
            game_type="season",
            external_source="spordle",
            external_game_id="829373",
            schedule_status="postponed",
        )
    ]
    tournament_game = {
        "id": 880343,
        "date": "2026-07-17",
        "number": "F18",
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
    }
    assert pick_existing_game(existing, tournament_game, our_team_id=167215) is None


def test_pick_existing_game_double_header_second_leg_not_merged():
    # Double-header: two games same day vs the same opponent. Once the first leg
    # is linked, the second leg (distinct Spordle number) must not merge into it.
    existing = [
        Game(
            id=1,
            team_id=1,
            date=date(2026, 7, 20),
            opponent="BRAVES",
            game_number="F1",
            game_type="tournament",
            external_source="spordle",
            external_game_id="900001",
        )
    ]
    second_leg = {
        "id": 900002,
        "date": "2026-07-20",
        "number": "F2",
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
    }
    assert pick_existing_game(existing, second_leg, our_team_id=167215) is None


def test_pick_existing_game_double_header_matches_by_number_on_resync():
    existing = [
        Game(
            id=1,
            team_id=1,
            date=date(2026, 7, 20),
            opponent="BRAVES",
            game_number="F1",
            external_source="spordle",
            external_game_id="900001",
        ),
        Game(
            id=2,
            team_id=1,
            date=date(2026, 7, 20),
            opponent="BRAVES",
            game_number="F2",
            external_source="spordle",
            external_game_id="900002",
        ),
    ]
    second_leg = {
        "id": 900002,
        "date": "2026-07-20",
        "number": "F2",
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
    }
    match = pick_existing_game(existing, second_leg, our_team_id=167215)
    assert match is not None
    assert match.id == 2


def test_resolve_spordle_game_double_header_by_number():
    schedule = [
        {
            "id": 900001,
            "date": "2026-07-20",
            "number": "F1",
            "homeTeamId": 167215,
            "awayTeamId": 158339,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        },
        {
            "id": 900002,
            "date": "2026-07-20",
            "number": "F2",
            "homeTeamId": 167215,
            "awayTeamId": 158339,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        },
    ]
    game = Game(team_id=1, date=date(2026, 7, 20), opponent="BRAVES", game_number="F2")
    resolved = resolve_spordle_game(game, schedule, 167215)
    assert resolved is not None
    assert resolved["id"] == 900002


def test_resolve_spordle_game_ambiguous_double_header_returns_none():
    schedule = [
        {
            "id": 900001,
            "date": "2026-07-20",
            "number": "F1",
            "homeTeamId": 167215,
            "awayTeamId": 158339,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        },
        {
            "id": 900002,
            "date": "2026-07-20",
            "number": "F2",
            "homeTeamId": 167215,
            "awayTeamId": 158339,
            "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
            "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        },
    ]
    game = Game(team_id=1, date=date(2026, 7, 20), opponent="BRAVES")
    assert resolve_spordle_game(game, schedule, 167215) is None


@pytest.mark.asyncio
async def test_sync_tournament_schedule_creates_game(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "our_spordle_team_id": 167215,
            "schedules": [
                {"schedule_id": 193093, "game_type": "season"},
                {
                    "schedule_id": 191260,
                    "game_type": "tournament",
                    "label": "Tournoi Longueuil",
                    "page_slug": "tournoi-longueuil",
                },
            ],
        }
    )
    session.add(team)
    session.commit()

    tournament_game = {
        "id": 880343,
        "date": "2026-07-17",
        "number": "F18",
        "scheduleId": 191260,
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        "status": "Active",
        "teamStats": [],
    }

    def fake_get_schedule_games(schedule_id, **kwargs):
        if schedule_id == 191260:
            return [tournament_game]
        return []

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        side_effect=fake_get_schedule_games,
    ):
        res = await client.post("/games/sync-schedule")

    payload = res.json()
    assert res.status_code == 200
    assert payload["ok"] is True
    assert payload["created"] == 1

    list_res = await client.get("/games/")
    synced = list_res.json()
    tournament = next(g for g in synced if g.get("external_game_id") == "880343")
    assert tournament["game_type"] == "tournament"
    assert tournament["opponent"] == "BRAVES"


@pytest.mark.asyncio
async def test_sync_same_day_league_and_tournament_games_both_created(
    client: AsyncClient, session
):
    # Regression: a postponed league game and a tournament game on the same day
    # must both sync. Previously the tournament game was merged into the league
    # game because they shared a date.
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {
            "our_spordle_team_id": 167215,
            "schedules": [
                {"schedule_id": 193093, "game_type": "season"},
                {
                    "schedule_id": 191260,
                    "game_type": "tournament",
                    "label": "Tournoi Longueuil",
                    "page_slug": "tournoi-longueuil",
                },
            ],
        }
    )
    session.add(team)
    session.commit()

    league_game = {
        "id": 829373,
        "date": "2026-07-17",
        "number": "13UB-0130",
        "scheduleId": 193093,
        "homeTeamId": 167215,
        "awayTeamId": 170000,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 170000, "shortName": "PHÉNIX"},
        "status": "Postponed",
        "comments": "Equipe en tournoi",
        "teamStats": [],
    }
    tournament_game = {
        "id": 880343,
        "date": "2026-07-17",
        "number": "F18",
        "scheduleId": 191260,
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        "status": "Active",
        "teamStats": [],
    }

    def fake_get_schedule_games(schedule_id, **kwargs):
        if schedule_id == 193093:
            return [league_game]
        if schedule_id == 191260:
            return [tournament_game]
        return []

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        side_effect=fake_get_schedule_games,
    ):
        res = await client.post("/games/sync-schedule")

    payload = res.json()
    assert res.status_code == 200
    assert payload["created"] == 2

    list_res = await client.get("/games/")
    synced = list_res.json()
    league = next(g for g in synced if g.get("external_game_id") == "829373")
    tournament = next(g for g in synced if g.get("external_game_id") == "880343")
    assert league["opponent"] == "PHÉNIX"
    assert league["schedule_status"] == "postponed"
    assert tournament["opponent"] == "BRAVES"
    assert tournament["game_type"] == "tournament"


@pytest.mark.asyncio
async def test_sync_double_header_same_opponent_creates_two_and_is_idempotent(
    client: AsyncClient, session
):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193093, "our_spordle_team_id": 167215}
    )
    session.add(team)
    session.commit()

    leg1 = {
        "id": 900001,
        "date": "2026-07-20",
        "number": "F1",
        "scheduleId": 193093,
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        "status": "Active",
        "teamStats": [],
    }
    leg2 = {
        "id": 900002,
        "date": "2026-07-20",
        "number": "F2",
        "scheduleId": 193093,
        "homeTeamId": 167215,
        "awayTeamId": 158339,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 158339, "shortName": "BRAVES"},
        "status": "Active",
        "teamStats": [],
    }

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        return_value=[leg1, leg2],
    ):
        first = await client.post("/games/sync-schedule")
        assert first.status_code == 200
        assert first.json()["created"] == 2

        # Re-sync must update in place, not duplicate.
        second = await client.post("/games/sync-schedule")
        assert second.status_code == 200
        assert second.json()["created"] == 0

    list_res = await client.get("/games/")
    double_header = [
        g for g in list_res.json() if g.get("external_game_id") in ("900001", "900002")
    ]
    assert len(double_header) == 2
    assert {g["external_game_id"] for g in double_header} == {"900001", "900002"}
    assert all(g["opponent"] == "BRAVES" for g in double_header)


@pytest.mark.asyncio
async def test_sync_postponed_game_excluded_from_upcoming_intel(client: AsyncClient, session):
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193093, "our_spordle_team_id": 167215}
    )
    session.add(team)
    session.commit()

    postponed_game = {
        "id": 829373,
        "date": "2026-07-17",
        "number": "13UB-0130",
        "homeTeamId": 167215,
        "awayTeamId": 170000,
        "homeTeam": {"id": 167215, "shortName": "DUCHESSES"},
        "awayTeam": {"id": 170000, "shortName": "PHÉNIX"},
        "status": "Postponed",
        "comments": "Equipe en tournoi",
        "teamStats": [],
    }

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        return_value=[postponed_game],
    ):
        res = await client.post("/games/sync-schedule")

    assert res.status_code == 200
    list_res = await client.get("/games/")
    synced = list_res.json()
    game = next(g for g in synced if g.get("external_game_id") == "829373")
    assert game["schedule_status"] == "postponed"

    intel_res = await client.get("/games/upcoming-intel")
    upcoming_ids = {row["id"] for row in intel_res.json()}
    assert game["id"] not in upcoming_ids

    dashboard_res = await client.get(f"/teams/{team.id}/stats/dashboard")
    assert dashboard_res.status_code == 200
    dashboard_upcoming_ids = {g["id"] for g in dashboard_res.json()["upcoming_games"]}
    assert game["id"] not in dashboard_upcoming_ids


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


def test_resolve_opponent_by_name():
    games = load_fixture("schedule_games.json")
    game = Game(
        team_id=1,
        date=date(2026, 8, 15),
        opponent="rival stars",
        game_type="tournament",
        mode="compete",
    )
    resolved = resolve_opponent_by_name(game, games, 167495)
    assert resolved == {"team_id": 162670, "name": "RIVAL STARS"}


@pytest.mark.asyncio
async def test_opponent_intel_manual_tournament_by_opponent_name(client: AsyncClient, session):
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

    game_res = await client.post(
        "/games/",
        json={
            "date": "2026-08-15",
            "opponent": "Rival Stars",
            "mode": "compete",
            "game_type": "tournament",
        },
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
    assert payload["standing"]["losses"] == 3
    assert payload["spordle_game_url"] is None
    assert payload["spordle_team_url"].endswith("/teams/162670")


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


def _add_sync_players(session):
    regular = Player(
        team_id=1,
        first_name="Regular",
        last_name="Player",
        jersey=11,
        active=True,
    )
    substitute = Player(
        team_id=1,
        first_name="Sub",
        last_name="Player",
        jersey=12,
        active=True,
        is_substitute=True,
    )
    session.add(regular)
    session.add(substitute)
    session.commit()
    session.refresh(regular)
    session.refresh(substitute)
    return regular, substitute


def _availability_statuses(session, game_id: int) -> dict[int, str]:
    rows = session.exec(
        select(Availability).where(Availability.game_id == game_id)
    ).all()
    return {row.player_id: row.status for row in rows}


def test_sync_failure_keeps_created_game_availability_atomic(session):
    from app.league_integrations.lfbq_spordle.sync import sync_team_schedule

    regular, substitute = _add_sync_players(session)
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
    session.add(team)
    session.commit()

    def fail_second_schedule(schedule_id: int, **_kwargs):
        if schedule_id == 193095:
            return [
                {
                    "id": 920001,
                    "date": "2026-07-05",
                    "number": "S1",
                    "homeTeamId": 167495,
                    "awayTeamId": 162670,
                    "homeTeam": {"id": 167495, "name": "BLUE EXPOS"},
                    "awayTeam": {"id": 162670, "name": "RIVAL STARS"},
                    "status": "Active",
                    "teamStats": [],
                }
            ]
        raise RuntimeError("schedule fetch failed")

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        side_effect=fail_second_schedule,
    ), pytest.raises(RuntimeError):
        sync_team_schedule(session, team)

    session.rollback()
    created = session.exec(
        select(Game).where(Game.external_game_id == "920001")
    ).one()
    assert _availability_statuses(session, created.id) == {
        regular.id: "available",
        substitute.id: "absent",
    }


def test_sync_backfills_missing_availability_for_matched_game(session):
    from app.league_integrations.lfbq_spordle.sync import sync_team_schedule

    regular, substitute = _add_sync_players(session)
    team = session.get(Team, 1)
    team.integration_version = "lfbq_spordle"
    team.integration_config_json = json.dumps(
        {"schedule_id": 193095, "our_spordle_team_id": 167495}
    )
    session.add(team)
    existing = Game(
        team_id=1,
        date=date(2026, 7, 5),
        opponent="RIVAL STARS",
        game_number="S1",
        game_type="season",
        external_source="spordle",
        external_game_id="920001",
    )
    session.add(existing)
    session.commit()
    session.refresh(existing)
    assert _availability_statuses(session, existing.id) == {}

    with patch(
        "app.league_integrations.lfbq_spordle.sync._client.get_schedule_games",
        return_value=[
            {
                "id": 920001,
                "date": "2026-07-05",
                "number": "S1",
                "homeTeamId": 167495,
                "awayTeamId": 162670,
                "homeTeam": {"id": 167495, "name": "BLUE EXPOS"},
                "awayTeam": {"id": 162670, "name": "RIVAL STARS"},
                "status": "Active",
                "teamStats": [],
            }
        ],
    ):
        result = sync_team_schedule(session, team)

    assert result["updated"] == 1
    assert _availability_statuses(session, existing.id) == {
        regular.id: "available",
        substitute.id: "absent",
    }


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
        "app.game_intel.date"
    ) as mock_intel_date, patch(
        "app.league_integrations.lfbq_spordle.intel._client.get_schedule_games",
        return_value=schedule,
    ), patch(
        "app.league_integrations.lfbq_spordle.warmup.date"
    ) as mock_warmup_date, patch(
        "app.league_integrations.lfbq_spordle.warmup._client.get_schedule_games",
        return_value=schedule,
    ):
        mock_date.today.return_value = date(2026, 5, 15)
        mock_intel_date.today.return_value = date(2026, 5, 15)
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
