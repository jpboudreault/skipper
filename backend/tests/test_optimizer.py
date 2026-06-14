"""
Tests for the lineup optimizer (CP-SAT solver).
"""
import pytest
from app.optimizer import solve_lineup, PlayerInfo, OptimizerConfig, LockedCell


def make_players(count: int) -> list:
    """Create test players with uniform position scores."""
    players = []
    for i in range(count):
        players.append(PlayerInfo(
            id=i + 1,
            name=f"Player {i + 1}",
            jersey=10 + i,
            position_scores={pos: 5 for pos in range(1, 10)},
            forbidden_positions=set(),
            pitcher_innings_last_7_days=0,
            is_pitch_eligible=True,
        ))
    return players


def test_basic_solve_10_players_5_innings():
    """10 players, 5 innings: 9 field + 1 bench per inning."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")

    # Check H1: each position filled once per inning
    for inn in range(1, 6):
        inn_cells = [a for a in result.assignments if a["inning"] == inn]
        positions = [a["position"] for a in inn_cells if a["position"] > 0]
        assert sorted(positions) == [1, 2, 3, 4, 5, 6, 7, 8, 9], f"Inning {inn} missing positions"

    # Check H2: each player appears once per inning
    for inn in range(1, 6):
        inn_cells = [a for a in result.assignments if a["inning"] == inn]
        player_ids = [a["player_id"] for a in inn_cells]
        assert len(player_ids) == len(set(player_ids)) == 10

    # Check H3: exactly 1 bench per inning (10 - 9 = 1)
    for inn in range(1, 6):
        bench = [a for a in result.assignments if a["inning"] == inn and a["position"] == 0]
        assert len(bench) == 1


def test_forbidden_position():
    """Player with forbidden pitcher position should never pitch."""
    players = make_players(10)
    players[0].forbidden_positions = {1}  # Player 1 can't pitch

    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")

    # Player 1 should never be at position 1
    p1_pitching = [a for a in result.assignments if a["player_id"] == 1 and a["position"] == 1]
    assert len(p1_pitching) == 0


def test_pitcher_innings_cap():
    """No player should pitch more than max_pitcher_innings_per_game."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=2,  # Strict cap
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")

    # Check H6: no player pitches more than 2 innings
    for p in players:
        pitching_innings = len([a for a in result.assignments if a["player_id"] == p.id and a["position"] == 1])
        assert pitching_innings <= 2, f"Player {p.id} pitched {pitching_innings} innings (max 2)"


def test_locked_cells():
    """Locked cells should be respected by the solver."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock player 1 as pitcher in innings 1 and 2
    locked = [
        LockedCell(player_id=1, inning=1, position=1),
        LockedCell(player_id=1, inning=2, position=1),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status in ("optimal", "feasible")

    # Verify locks are respected
    p1_inn1 = [a for a in result.assignments if a["player_id"] == 1 and a["inning"] == 1]
    assert len(p1_inn1) == 1
    assert p1_inn1[0]["position"] == 1

    p1_inn2 = [a for a in result.assignments if a["player_id"] == 1 and a["inning"] == 2]
    assert len(p1_inn2) == 1
    assert p1_inn2[0]["position"] == 1


def test_develop_mode():
    """Develop mode should produce a valid result."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="develop",
    )
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")

    # Same structural constraints should hold
    for inn in range(1, 6):
        inn_cells = [a for a in result.assignments if a["inning"] == inn]
        positions = [a["position"] for a in inn_cells if a["position"] > 0]
        assert sorted(positions) == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_pitcher_no_reentry():
    """H5: A player cannot re-enter the game as a pitcher once they leave the mound."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock player 1 to Pitcher in inning 1, and Shortstop in inning 2 (left the mound)
    locked = [
        LockedCell(player_id=1, inning=1, position=1),
        LockedCell(player_id=1, inning=2, position=6),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status in ("optimal", "feasible")
    
    p1_pitching_later = [
        a for a in result.assignments 
        if a["player_id"] == 1 and a["inning"] > 2 and a["position"] == 1
    ]
    assert len(p1_pitching_later) == 0, "Player 1 re-entered the mound after leaving!"


def test_pitcher_no_reentry_infeasible():
    """H5: Try to force a re-entry via locked cells, which should be infeasible."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock player 1 to Pitcher in inning 1, Shortstop in inning 2, and Pitcher again in inning 3
    locked = [
        LockedCell(player_id=1, inning=1, position=1),
        LockedCell(player_id=1, inning=2, position=6),
        LockedCell(player_id=1, inning=3, position=1),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status == "infeasible"


def test_pitcher_rolling_7_days_cap():
    """H6b: Pitcher innings cap for 7-day rolling period is respected."""
    players = make_players(10)
    # Player 1 has already pitched 3 innings in the last 7 days.
    players[0].pitcher_innings_last_7_days = 3
    
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,  # Only 4 - 3 = 1 inning remaining
        late_inning_weight=1.5,
        mode="compete",
    )
    
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")
    
    # Player 1 should pitch at most 1 inning in this game
    p1_pitching_innings = [a for a in result.assignments if a["player_id"] == 1 and a["position"] == 1]
    assert len(p1_pitching_innings) <= 1


def test_pitch_eligibility_false():
    """H7: If is_pitch_eligible is False, the player cannot pitch."""
    players = make_players(10)
    players[0].is_pitch_eligible = False  # Not eligible due to rest rules
    
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")
    
    # Player 1 should never pitch
    p1_pitching = [a for a in result.assignments if a["player_id"] == 1 and a["position"] == 1]
    assert len(p1_pitching) == 0


def test_catcher_pitcher_rest():
    """H8: A player catching in inning i cannot pitch in inning i+1."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock player 1 as Catcher (2) in inning 2
    locked = [
        LockedCell(player_id=1, inning=2, position=2),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status in ("optimal", "feasible")
    
    # Player 1 should not pitch in inning 3
    p1_pitching_inn3 = [
        a for a in result.assignments 
        if a["player_id"] == 1 and a["inning"] == 3 and a["position"] == 1
    ]
    assert len(p1_pitching_inn3) == 0


def test_catcher_pitcher_rest_infeasible():
    """H8: Try to force catcher to pitch next inning via locked cells, which should be infeasible."""
    players = make_players(10)
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock player 1 to Catcher in inning 2, and Pitcher in inning 3
    locked = [
        LockedCell(player_id=1, inning=2, position=2),
        LockedCell(player_id=1, inning=3, position=1),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status == "infeasible"


def test_infeasible_locked_forbidden_position():
    """H9 & Lock conflict: Try to lock a player to a forbidden position, should be infeasible."""
    players = make_players(10)
    players[0].forbidden_positions = {1}  # Player 1 cannot pitch (H9)
    
    config = OptimizerConfig(
        innings=5,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    
    # Lock Player 1 to Pitcher (position 1) in inning 1
    locked = [
        LockedCell(player_id=1, inning=1, position=1),
    ]
    
    result = solve_lineup(players, config, locked)
    assert result.status == "infeasible"


def test_bench_fairness_distribution():
    """Verify that benching is distributed fairly (spread is at most 1)."""
    players = make_players(11)
    config = OptimizerConfig(
        innings=6,
        max_pitcher_innings_per_game=3,
        max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5,
        mode="compete",
    )
    result = solve_lineup(players, config)
    assert result.status in ("optimal", "feasible")

    # Count how many times each player sits
    bench_counts = {p.id: 0 for p in players}
    for a in result.assignments:
        if a["position"] == 0:
            bench_counts[a["player_id"]] += 1

    # In a perfectly fair distribution of 12 bench appearances among 11 players:
    # 10 players sit 1 time, 1 player sits 2 times, 0 players sit 0 times.
    # The spread (max - min) should be exactly 1.
    max_b = max(bench_counts.values())
    min_b = min(bench_counts.values())
    assert max_b - min_b <= 1, f"Bench spread is unfair: {bench_counts}"


