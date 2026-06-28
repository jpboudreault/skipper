"""
Lineup optimizer using Google OR-Tools CP-SAT solver.

Supports two modes:
  - COMPETE: maximize fielding quality weighted by position scores,
             with late-inning weighting.
  - DEVELOP: maximize developmental exposure (position variety,
             time at positions the player hasn't tried much).

Hard constraints (from baseball-lineup-plan.md §5.2):
  H1: One field player per position per inning.
  H2: Each player in exactly one slot per inning (field or bench).
  H3: Bench count = available_count - 9.
  H4: Bench-rotation fairness.
  H5: No pitcher re-entry after leaving the mound.
  H6: Pitcher innings cap (game).
  H6b: Pitcher innings cap (7-day rolling).
  H7: Pitch-count rest eligibility.
  H8: Catcher -> pitcher rest (≥1 inning gap).
  H9: Forbidden positions are forbidden.
"""

from ortools.sat.python import cp_model
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PlayerInfo:
    id: int
    name: str
    jersey: int
    position_scores: Dict[int, int]      # pos -> score (0-10)
    forbidden_positions: set              # set of pos ids
    pitcher_innings_last_7_days: int      # rolling 7-day pitcher innings
    is_pitch_eligible: bool               # can they pitch today?
    injury_inning: Optional[int] = None   # 1-indexed inning they got injured
    max_pitcher_innings_this_game: Optional[int] = None


@dataclass
class OptimizerConfig:
    innings: int                           # number of innings in this game
    max_pitcher_innings_per_game: int
    max_pitcher_innings_per_7_days: int
    late_inning_weight: float
    mode: str                              # 'compete' or 'develop'
    strict_bench_fairness: bool = False    # hard fairness/rotation (non AA/AAA)
    h8_is_soft: bool = False               # catcher->pitcher next inning handled as penalty


@dataclass
class LockedCell:
    player_id: int
    inning: int       # 1-indexed
    position: int     # 0=bench, 1-9=field


@dataclass
class SolverResult:
    assignments: List[dict]   # [{inning, player_id, position}, ...]
    objective_value: float
    status: str               # 'optimal', 'feasible', 'infeasible'

EARLY_INFIELD_SOFT_PENALTY = 8000


def solve_lineup(
    players: List[PlayerInfo],
    config: OptimizerConfig,
    locked_cells: Optional[List[LockedCell]] = None,
) -> SolverResult:
    """
    Solve the lineup assignment problem.
    
    Returns the best assignment of players to positions per inning.
    """
    if locked_cells is None:
        locked_cells = []

    model = cp_model.CpModel()

    num_players = len(players)
    num_innings = config.innings
    positions = list(range(0, 10))  # 0=bench, 1=P, 2=C, ..., 9=RF
    field_positions = list(range(1, 10))  # 1-9

    player_ids = [p.id for p in players]
    player_map = {p.id: p for p in players}
    p_idx = {p.id: i for i, p in enumerate(players)}

    # Decision variables: x[p_idx, inning_idx, pos]
    x = {}
    for pi, p in enumerate(players):
        for inn in range(num_innings):
            for pos in positions:
                x[pi, inn, pos] = model.NewBoolVar(f"x_{p.id}_{inn+1}_{pos}")

    # ========== HARD CONSTRAINTS ==========

    # H1: Max One field player per position per inning
    for inn in range(num_innings):
        num_active = sum(1 for p in players if p.injury_inning is None or p.injury_inning > inn + 1)
        field_count = min(9, num_active)

        for pos in field_positions:
            model.Add(sum(x[pi, inn, pos] for pi in range(num_players)) <= 1)
            
        model.Add(sum(x[pi, inn, pos] for pi in range(num_players) for pos in field_positions) == field_count)

    # H2: Each player in exactly one slot per inning
    for pi in range(num_players):
        for inn in range(num_innings):
            model.Add(sum(x[pi, inn, pos] for pos in positions) == 1)

    # H3: Bench count = available_count - 9 + injured forced to bench
    for inn in range(num_innings):
        injured_count = sum(1 for p in players if p.injury_inning is not None and p.injury_inning <= inn + 1)
        num_active = num_players - injured_count
        active_bench = max(0, num_active - 9)
        
        model.Add(sum(x[pi, inn, 0] for pi in range(num_players)) == injured_count + active_bench)
        
        for pi, p in enumerate(players):
            if p.injury_inning is not None and p.injury_inning <= inn + 1:
                model.Add(x[pi, inn, 0] == 1)

    # H5: No pitcher re-entry
    # If player pitches in inning i but not i+1, they can't pitch again
    for pi in range(num_players):
        for inn in range(num_innings - 2):
            # If x[pi, inn, 1]=1 and x[pi, inn+1, 1]=0, then x[pi, j, 1]=0 for j > inn+1
            # Encoded as: for each pair (inn, inn+2..end), 
            # x[pi,inn,1] + (1-x[pi,inn+1,1]) + x[pi,j,1] <= 2
            for j in range(inn + 2, num_innings):
                b_pitched_now = x[pi, inn, 1]
                b_not_next = model.NewBoolVar(f"not_pitch_{pi}_{inn+1}")
                model.Add(b_not_next == 1).OnlyEnforceIf(x[pi, inn + 1, 1].Not())
                model.Add(b_not_next == 0).OnlyEnforceIf(x[pi, inn + 1, 1])
                # If pitched now AND didn't pitch next, then can't pitch later
                model.Add(x[pi, j, 1] == 0).OnlyEnforceIf(b_pitched_now, b_not_next)

    # H6: Pitcher innings cap (game). Some players may have a lower same-day
    # remainder because of earlier games on the same date.
    for pi, p in enumerate(players):
        game_cap = config.max_pitcher_innings_per_game
        if p.max_pitcher_innings_this_game is not None:
            game_cap = max(0, min(game_cap, p.max_pitcher_innings_this_game))
        model.Add(
            sum(x[pi, inn, 1] for inn in range(num_innings))
            <= game_cap
        )

    # H6b: Pitcher innings cap (7-day rolling)
    for pi, p in enumerate(players):
        remaining = config.max_pitcher_innings_per_7_days - p.pitcher_innings_last_7_days
        if remaining < 0:
            remaining = 0
        model.Add(
            sum(x[pi, inn, 1] for inn in range(num_innings)) <= remaining
        )

    # H7: Pitch-count rest eligibility
    for pi, p in enumerate(players):
        if not p.is_pitch_eligible:
            for inn in range(num_innings):
                model.Add(x[pi, inn, 1] == 0)

    # H8: Catcher -> pitcher rest (cannot pitch the inning after catching)
    # In strict mode this remains a hard constraint; when configured soft, violations are penalized.
    h8_violation_vars = []
    for pi in range(num_players):
        for inn in range(num_innings - 1):
            if config.h8_is_soft:
                # violation is 1 only when player catches in inning i and pitches in inning i+1
                v = model.NewBoolVar(f"h8_violation_{pi}_{inn}")
                model.Add(v <= x[pi, inn, 2])
                model.Add(v <= x[pi, inn + 1, 1])
                model.Add(v >= x[pi, inn, 2] + x[pi, inn + 1, 1] - 1)
                h8_violation_vars.append(v)
            else:
                model.Add(x[pi, inn + 1, 1] == 0).OnlyEnforceIf(x[pi, inn, 2])

    # H9: Forbidden positions
    for pi, p in enumerate(players):
        for pos in p.forbidden_positions:
            if pos in positions:
                for inn in range(num_innings):
                    model.Add(x[pi, inn, pos] == 0)

    # Locked cells (coach pre-assignments)
    for lock in locked_cells:
        if lock.player_id in p_idx:
            pi = p_idx[lock.player_id]
            inn = lock.inning - 1  # convert to 0-indexed
            if 0 <= inn < num_innings and lock.position in positions:
                model.Add(x[pi, inn, lock.position] == 1)

    # H4 strict bench fairness (non AA/AAA categories)
    if config.strict_bench_fairness:
        # 1) If a player sits inning 1 and is healthy inning 2, they must play inning 2.
        if num_innings >= 2:
            for pi, p in enumerate(players):
                if p.injury_inning is not None and p.injury_inning <= 2:
                    continue
                model.Add(x[pi, 1, 0] == 0).OnlyEnforceIf(x[pi, 0, 0])

        # 2) No back-to-back bench innings for healthy players.
        for pi, p in enumerate(players):
            for inn in range(num_innings - 1):
                if p.injury_inning is not None and p.injury_inning <= inn + 1:
                    continue
                if p.injury_inning is not None and p.injury_inning <= inn + 2:
                    continue
                model.Add(x[pi, inn, 0] + x[pi, inn + 1, 0] <= 1)

        # 3) Prefix fairness: by any inning, bench counts between healthy players differ by at most 1.
        # This enforces "no one benches again before the others have had their turn."
        # Exception: when the comparator player is currently on the mound, this check is relaxed.
        for inn in range(num_innings):
            for pi, p in enumerate(players):
                if p.injury_inning is not None and p.injury_inning <= inn + 1:
                    continue
                left = sum(x[pi, k, 0] for k in range(inn + 1))
                for pj, q in enumerate(players):
                    if pi == pj:
                        continue
                    if q.injury_inning is not None and q.injury_inning <= inn + 1:
                        continue
                    right = sum(x[pj, k, 0] for k in range(inn + 1))
                    model.Add(left <= right + 1).OnlyEnforceIf(x[pj, inn, 1].Not())

    # Shared soft preference: each player should get at least one infield inning
    # (positions 1..6) in the first 4 innings, when they are healthy/active.
    infield_positions = list(range(1, 7))
    early_window = min(4, num_innings)
    early_infield_missing_vars = []
    for pi, p in enumerate(players):
        eligible_early_innings = [
            inn for inn in range(early_window)
            if p.injury_inning is None or p.injury_inning > inn + 1
        ]
        if not eligible_early_innings:
            continue

        early_infield_terms = [
            x[pi, inn, pos]
            for inn in eligible_early_innings
            for pos in infield_positions
        ]
        played_early_infield = model.NewBoolVar(f"early_infield_{pi}")
        model.AddMaxEquality(played_early_infield, early_infield_terms)

        miss_early_infield = model.NewBoolVar(f"miss_early_infield_{pi}")
        model.Add(miss_early_infield + played_early_infield == 1)
        early_infield_missing_vars.append(miss_early_infield)

    # ========== OBJECTIVE ==========

    # Calculate late-inning boundary
    late_start = num_innings - math.ceil(num_innings / 3)

    if config.mode == "compete":
        # COMPETE: maximize sum of position_score * x, with late-inning weighting
        objective_terms = []
        for pi, p in enumerate(players):
            for inn in range(num_innings):
                weight = config.late_inning_weight if inn >= late_start else 1.0
                for pos in field_positions:
                    score = p.position_scores.get(pos, 0)
                    # Scale to integer for CP-SAT (multiply by 100)
                    scaled = int(score * weight * 100)
                    objective_terms.append(scaled * x[pi, inn, pos])

        # Objective: maximize fielding quality (plus optional soft H8 penalty)
        total_quality = model.NewIntVar(-1000000, 1000000, "total_quality")
        model.Add(total_quality == sum(objective_terms))

        # Combined: quality minus soft catcher->pitcher-rest violations.
        combined = model.NewIntVar(-10000000, 10000000, "combined")
        h8_penalty = sum(h8_violation_vars) * 20000 if h8_violation_vars else 0
        early_infield_penalty = (
            sum(early_infield_missing_vars) * EARLY_INFIELD_SOFT_PENALTY
            if early_infield_missing_vars else 0
        )
        model.Add(combined == total_quality - h8_penalty - early_infield_penalty)
        model.Maximize(combined)

    else:
        # DEVELOP: maximize position variety and exposure to new positions
        objective_terms = []
        
        for pi, p in enumerate(players):
            # Reward positions they haven't scored highly on (developmental need)
            for inn in range(num_innings):
                for pos in field_positions:
                    score = p.position_scores.get(pos, 0)
                    # Invert: low score = high development need
                    dev_need = max(0, 10 - score)
                    scaled = dev_need * 100
                    objective_terms.append(scaled * x[pi, inn, pos])

            # Reward position variety: use indicator variables for "played pos at least once"
            for pos in field_positions:
                played_pos = model.NewBoolVar(f"played_{pi}_{pos}")
                model.AddMaxEquality(played_pos, [x[pi, inn, pos] for inn in range(num_innings)])
                objective_terms.append(played_pos * 200)  # variety bonus

        combined = model.NewIntVar(-10000000, 10000000, "combined_dev")
        h8_penalty = sum(h8_violation_vars) * 20000 if h8_violation_vars else 0
        early_infield_penalty = (
            sum(early_infield_missing_vars) * EARLY_INFIELD_SOFT_PENALTY
            if early_infield_missing_vars else 0
        )
        model.Add(combined == sum(objective_terms) - h8_penalty - early_infield_penalty)
        model.Maximize(combined)

    # ========== SOLVE ==========

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = []
        for pi, p in enumerate(players):
            for inn in range(num_innings):
                for pos in positions:
                    if solver.Value(x[pi, inn, pos]) == 1:
                        assignments.append({
                            "inning": inn + 1,
                            "player_id": p.id,
                            "position": pos,
                            "locked": any(
                                lc.player_id == p.id and lc.inning == inn + 1 and lc.position == pos
                                for lc in locked_cells
                            )
                        })

        status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"
        return SolverResult(
            assignments=assignments,
            objective_value=solver.ObjectiveValue(),
            status=status_str
        )
    else:
        return SolverResult(
            assignments=[],
            objective_value=0,
            status="infeasible"
        )
