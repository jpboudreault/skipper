import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import Team, Player, Game, BattingLine, PitchingAppearance, Lineup
from datetime import date


@pytest.mark.asyncio
async def test_season_batting(client: TestClient, session: Session):
    # Setup
    team = Team(name="Stats Team", season="2026", innings_per_game=5, max_pitcher_innings_per_game=3, pitch_count_rules_json="{}")
    session.add(team)
    session.commit()
    
    p1 = Player(team_id=team.id, first_name="Babe", last_name="Ruth", jersey=3)
    p2 = Player(team_id=team.id, first_name="Lou", last_name="Gehrig", jersey=4)
    session.add_all([p1, p2])
    session.commit()
    
    game = Game(team_id=team.id, date=date(2026, 5, 1), mode="compete")
    session.add(game)
    session.commit()
    
    b1 = BattingLine(game_id=game.id, player_id=p1.id, singles=1, hr=1, bb=1)
    b2 = BattingLine(game_id=game.id, player_id=p2.id, doubles=1, outs_not_k=1)
    session.add_all([b1, b2])
    session.commit()
    
    response = await client.get(f"/teams/{team.id}/stats/batting")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Ruth: 1 single, 1 hr -> H=2. AB = H + 0 = 2. BB=1. PA = 2+1 = 3.
    # AVG = 2/2 = 1.0. OBP = (2+1)/(2+1) = 1.0. SLG = (1 + 4)/2 = 2.5. OPS = 3.5.
    ruth = next(x for x in data if x["player_id"] == p1.id)
    assert ruth["h"] == 2
    assert ruth["ab"] == 2
    assert ruth["pa"] == 3
    assert ruth["avg"] == 1.0
    assert ruth["ops"] == 3.5

@pytest.mark.asyncio
async def test_season_pitching(client: TestClient, session: Session):
    team = Team(name="Stats Pitch Team", season="2026", innings_per_game=5, max_pitcher_innings_per_game=3, pitch_count_rules_json="{}")
    session.add(team)
    session.commit()
    
    p1 = Player(team_id=team.id, first_name="Pedro", last_name="Martinez", jersey=45)
    session.add(p1)
    session.commit()
    
    game = Game(team_id=team.id, date=date(2026, 5, 1), mode="compete")
    session.add(game)
    session.commit()
    
    app = PitchingAppearance(game_id=game.id, player_id=p1.id, inning_entered=1, inning_exited=3, ip_outs=9, runs_allowed=1, k=5, bb=2)
    session.add(app)
    session.commit()
    
    response = await client.get(f"/teams/{team.id}/stats/pitching")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    pedro = data[0]
    assert pedro["ip"] == 3.0
    assert pedro["ip_display"] == "3"
    assert pedro["k_9"] == 15.0  # 5 * 9 / 3
    
@pytest.mark.asyncio
async def test_season_position(client: TestClient, session: Session):
    team = Team(name="Stats Pos Team", season="2026", innings_per_game=5, max_pitcher_innings_per_game=3, pitch_count_rules_json="{}")
    session.add(team)
    session.commit()
    
    p1 = Player(team_id=team.id, first_name="Ozzie", last_name="Smith", jersey=1)
    session.add(p1)
    session.commit()
    
    game = Game(team_id=team.id, date=date(2026, 5, 1), mode="compete", result_runs_for=5, result_runs_against=3)
    session.add(game)
    session.commit()
    
    l1 = Lineup(game_id=game.id, inning=1, player_id=p1.id, position=6)
    l2 = Lineup(game_id=game.id, inning=2, player_id=p1.id, position=0)
    session.add_all([l1, l2])
    session.commit()
    
    response = await client.get(f"/teams/{team.id}/stats/position")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    ozzie = data[0]
    assert ozzie["total_innings"] == 2
    assert ozzie["positions"]["6"] == 1
    assert ozzie["positions"]["0"] == 1
    assert ozzie["bench_pct"] == 50.0


@pytest.mark.asyncio
async def test_dashboard_includes_scored_disrupted_game_in_recent_history(
    client: TestClient, session: Session
):
    team = Team(
        name="Dashboard Team",
        season="2026",
        innings_per_game=5,
        max_pitcher_innings_per_game=3,
        pitch_count_rules_json="{}",
    )
    session.add(team)
    session.commit()

    player = Player(team_id=team.id, first_name="Clutch", last_name="Hitter", jersey=7)
    session.add(player)
    session.commit()

    game = Game(
        team_id=team.id,
        date=date.today(),
        opponent="Makeup Opponent",
        result_runs_for=8,
        result_runs_against=7,
        schedule_status="postponed",
        mode="compete",
    )
    session.add(game)
    session.commit()

    session.add(BattingLine(game_id=game.id, player_id=player.id, singles=1))
    session.commit()

    response = await client.get(f"/teams/{team.id}/stats/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["last_game"]["id"] == game.id
    assert data["recent_batting"][0]["player_id"] == player.id
    assert data["recent_batting"][0]["singles"] == 1


@pytest.mark.asyncio
async def test_pitching_plan_filters_coaches_and_subs(client: TestClient, session: Session):
    # 1. Create team
    team = Team(name="Plan Team", season="2026", innings_per_game=5, max_pitcher_innings_per_game=3, pitch_count_rules_json="{}")
    session.add(team)
    session.commit()
    
    # 2. Create players
    p1 = Player(team_id=team.id, first_name="Regular", last_name="Player", jersey=10, active=True, is_substitute=False, is_coach=False)
    p2 = Player(team_id=team.id, first_name="Substitute", last_name="Player", jersey=20, active=True, is_substitute=True, is_coach=False)
    p3 = Player(team_id=team.id, first_name="Chef", last_name="Coach", jersey=99, active=True, is_substitute=False, is_coach=True)
    session.add_all([p1, p2, p3])
    session.commit()
    
    # 3. Create a game within last 7 days
    game = Game(team_id=team.id, date=date.today(), mode="compete")
    session.add(game)
    session.commit()
    
    # 4. Fetch pitching-plan
    response = await client.get(f"/teams/{team.id}/stats/pitching-plan")
    assert response.status_code == 200
    data = response.json()
    
    # Verify that only the regular player is returned in the plan
    players = data["players"]
    assert len(players) == 1
    assert players[0]["id"] == p1.id
    assert players[0]["first_name"] == "Regular"

