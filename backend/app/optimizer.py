"""
Lineup optimizer using Google OR-Tools CP-SAT solver.

Game modes:
  - OPTIMAL: maximize fielding quality (late-inning weighted); single lineup.
  - COMPETE: balanced — hard early-infield rule + quality within tolerance band;
             returns up to 5 diverse lineup options.
  - DEVELOP: maximize developmental exposure; hard early-infield rule;
             returns up to 5 diverse lineup options.

Hard constraints (from baseball-lineup-plan.md §5.2):
  H1–H9 as documented in the original plan.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

GAME_MODES = ("compete", "develop", "optimal")
DEFAULT_COMPETE_TOLERANCE_PCT = 15.0
MAX_MULTI_OPTIONS = 5
TOTAL_SOLVE_TIME_SECONDS = 15.0
H8_PENALTY = 20000


@dataclass
class PlayerInfo:
    id: int
    name: str
    jersey: int
    position_scores: Dict[int, int]
    forbidden_positions: set
    pitcher_innings_last_7_days: int
    is_pitch_eligible: bool
    injury_inning: Optional[int] = None


@dataclass
class OptimizerConfig:
    innings: int
    max_pitcher_innings_per_game: int
    max_pitcher_innings_per_7_days: int
    late_inning_weight: float
    mode: str
    strict_bench_fairness: bool = False
    h8_is_soft: bool = False
    compete_score_tolerance_pct: float = DEFAULT_COMPETE_TOLERANCE_PCT


@dataclass
class LockedCell:
    player_id: int
    inning: int
    position: int


@dataclass
class SolverResult:
    assignments: List[dict]
    objective_value: float
    status: str


@dataclass
class LineupOption:
    option_id: int
    assignments: List[dict]
    quality_score: float
    dev_score: float
    objective_value: float
    status: str


@dataclass
class MultiSolverResult:
    options: List[LineupOption]
    mode: str
    best_quality_score: Optional[float]
    tolerance_pct: Optional[float]


AssignmentMap = Dict[Tuple[int, int], int]


def _requires_hard_early_infield(mode: str) -> bool:
    return mode in ("compete", "develop")


def _late_start(num_innings: int) -> int:
    return num_innings - math.ceil(num_innings / 3)


def compute_quality_score(
    players: List[PlayerInfo], assignments: List[dict], config: OptimizerConfig
) -> float:
    """Sum of position scores with late-inning weighting (reporting metric)."""
    player_map = {p.id: p for p in players}
    late_start = _late_start(config.innings)
    total = 0.0
    for cell in assignments:
        if cell["position"] == 0:
            continue
        player = player_map.get(cell["player_id"])
        if not player:
            continue
        inn_idx = cell["inning"] - 1
        weight = config.late_inning_weight if inn_idx >= late_start else 1.0
        score = player.position_scores.get(cell["position"], 0)
        total += score * weight
    return total


def compute_dev_score(players: List[PlayerInfo], assignments: List[dict]) -> float:
    """Development objective mirror for UI (need exposure + variety)."""
    player_map = {p.id: p for p in players}
    field_positions = list(range(1, 10))
    total = 0.0
    for p in players:
        player_cells = [a for a in assignments if a["player_id"] == p.id and a["position"] > 0]
        for cell in player_cells:
            score = p.position_scores.get(cell["position"], 0)
            total += max(0, 10 - score) * 100
        positions_played = {a["position"] for a in player_cells}
        for pos in field_positions:
            if pos in positions_played:
                total += 200
    return total


def _assignments_to_map(
    assignments: List[dict], players: List[PlayerInfo]
) -> AssignmentMap:
    p_idx = {p.id: i for i, p in enumerate(players)}
    result: AssignmentMap = {}
    for cell in assignments:
        pi = p_idx.get(cell["player_id"])
        if pi is None:
            continue
        inn = cell["inning"] - 1
        result[(pi, inn)] = cell["position"]
    return result


def _maps_equal(a: AssignmentMap, b: AssignmentMap) -> bool:
    return a == b


def _build_model(
    players: List[PlayerInfo],
    config: OptimizerConfig,
    locked_cells: List[LockedCell],
    prior_maps: List[AssignmentMap],
    min_quality: Optional[int],
    objective_kind: str,
):
    model = cp_model.CpModel()
    num_players = len(players)
    num_innings = config.innings
    positions = list(range(0, 10))
    field_positions = list(range(1, 10))
    p_idx = {p.id: i for i, p in enumerate(players)}

    x = {}
    for pi, p in enumerate(players):
        for inn in range(num_innings):
            for pos in positions:
                x[pi, inn, pos] = model.NewBoolVar(f"x_{p.id}_{inn + 1}_{pos}")

    for inn in range(num_innings):
        num_active = sum(
            1 for p in players if p.injury_inning is None or p.injury_inning > inn + 1
        )
        field_count = min(9, num_active)
        for pos in field_positions:
            model.Add(sum(x[pi, inn, pos] for pi in range(num_players)) <= 1)
        model.Add(
            sum(x[pi, inn, pos] for pi in range(num_players) for pos in field_positions)
            == field_count
        )

    for pi in range(num_players):
        for inn in range(num_innings):
            model.Add(sum(x[pi, inn, pos] for pos in positions) == 1)

    for inn in range(num_innings):
        injured_count = sum(
            1 for p in players if p.injury_inning is not None and p.injury_inning <= inn + 1
        )
        num_active = num_players - injured_count
        active_bench = max(0, num_active - 9)
        model.Add(sum(x[pi, inn, 0] for pi in range(num_players)) == injured_count + active_bench)
        for pi, p in enumerate(players):
            if p.injury_inning is not None and p.injury_inning <= inn + 1:
                model.Add(x[pi, inn, 0] == 1)

    for pi in range(num_players):
        for inn in range(num_innings - 2):
            for j in range(inn + 2, num_innings):
                b_pitched_now = x[pi, inn, 1]
                b_not_next = model.NewBoolVar(f"not_pitch_{pi}_{inn + 1}_{j}")
                model.Add(b_not_next == 1).OnlyEnforceIf(x[pi, inn + 1, 1].Not())
                model.Add(b_not_next == 0).OnlyEnforceIf(x[pi, inn + 1, 1])
                model.Add(x[pi, j, 1] == 0).OnlyEnforceIf(b_pitched_now, b_not_next)

    for pi in range(num_players):
        model.Add(
            sum(x[pi, inn, 1] for inn in range(num_innings))
            <= config.max_pitcher_innings_per_game
        )

    for pi, p in enumerate(players):
        remaining = config.max_pitcher_innings_per_7_days - p.pitcher_innings_last_7_days
        if remaining < 0:
            remaining = 0
        model.Add(sum(x[pi, inn, 1] for inn in range(num_innings)) <= remaining)

    for pi, p in enumerate(players):
        if not p.is_pitch_eligible:
            for inn in range(num_innings):
                model.Add(x[pi, inn, 1] == 0)

    h8_violation_vars = []
    for pi in range(num_players):
        for inn in range(num_innings - 1):
            if config.h8_is_soft:
                v = model.NewBoolVar(f"h8_violation_{pi}_{inn}")
                model.Add(v <= x[pi, inn, 2])
                model.Add(v <= x[pi, inn + 1, 1])
                model.Add(v >= x[pi, inn, 2] + x[pi, inn + 1, 1] - 1)
                h8_violation_vars.append(v)
            else:
                model.Add(x[pi, inn + 1, 1] == 0).OnlyEnforceIf(x[pi, inn, 2])

    for pi, p in enumerate(players):
        for pos in p.forbidden_positions:
            if pos in positions:
                for inn in range(num_innings):
                    model.Add(x[pi, inn, pos] == 0)

    for lock in locked_cells:
        if lock.player_id in p_idx:
            pi = p_idx[lock.player_id]
            inn = lock.inning - 1
            if 0 <= inn < num_innings and lock.position in positions:
                model.Add(x[pi, inn, lock.position] == 1)

    if config.strict_bench_fairness:
        if num_innings >= 2:
            for pi, p in enumerate(players):
                if p.injury_inning is not None and p.injury_inning <= 2:
                    continue
                model.Add(x[pi, 1, 0] == 0).OnlyEnforceIf(x[pi, 0, 0])
        for pi, p in enumerate(players):
            for inn in range(num_innings - 1):
                if p.injury_inning is not None and p.injury_inning <= inn + 1:
                    continue
                if p.injury_inning is not None and p.injury_inning <= inn + 2:
                    continue
                model.Add(x[pi, inn, 0] + x[pi, inn + 1, 0] <= 1)
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

    infield_positions = list(range(1, 7))
    early_window = min(4, num_innings)
    if _requires_hard_early_infield(config.mode):
        for pi, p in enumerate(players):
            eligible_early_innings = [
                inn
                for inn in range(early_window)
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
            model.Add(played_early_infield == 1)

    late_start = _late_start(num_innings)
    quality_terms = []
    for pi, p in enumerate(players):
        for inn in range(num_innings):
            weight = config.late_inning_weight if inn >= late_start else 1.0
            for pos in field_positions:
                score = p.position_scores.get(pos, 0)
                quality_terms.append(int(score * weight * 100) * x[pi, inn, pos])

    total_quality = model.NewIntVar(0, 10_000_000, "total_quality")
    model.Add(total_quality == sum(quality_terms))

    dev_terms = []
    for pi, p in enumerate(players):
        for inn in range(num_innings):
            for pos in field_positions:
                dev_need = max(0, 10 - p.position_scores.get(pos, 0))
                dev_terms.append(dev_need * 100 * x[pi, inn, pos])
        for pos in field_positions:
            played_pos = model.NewBoolVar(f"played_{pi}_{pos}")
            model.AddMaxEquality(played_pos, [x[pi, inn, pos] for inn in range(num_innings)])
            dev_terms.append(played_pos * 200)

    total_dev = model.NewIntVar(0, 10_000_000, "total_dev")
    model.Add(total_dev == sum(dev_terms))

    if min_quality is not None:
        model.Add(total_quality >= min_quality)

    for idx, prior in enumerate(prior_maps):
        lits = []
        for (pi, inn), ref_pos in prior.items():
            lits.append(x[pi, inn, ref_pos].Not())
        if lits:
            model.Add(sum(lits) >= 1)

    h8_penalty = sum(h8_violation_vars) * H8_PENALTY if h8_violation_vars else 0

    if objective_kind == "quality":
        combined = model.NewIntVar(-10_000_000, 10_000_000, "combined")
        model.Add(combined == total_quality - h8_penalty)
        model.Maximize(combined)
    elif objective_kind == "develop":
        combined = model.NewIntVar(-10_000_000, 10_000_000, "combined_dev")
        model.Add(combined == total_dev - h8_penalty)
        model.Maximize(combined)
    elif objective_kind == "diversity":
        diversity_terms = []
        for ref_idx, prior in enumerate(prior_maps):
            for (pi, inn), ref_pos in prior.items():
                diff = model.NewBoolVar(f"diff_{ref_idx}_{pi}_{inn}")
                model.Add(diff == 1).OnlyEnforceIf(x[pi, inn, ref_pos].Not())
                model.Add(diff == 0).OnlyEnforceIf(x[pi, inn, ref_pos])
                diversity_terms.append(diff)
        diversity_sum = sum(diversity_terms) if diversity_terms else 0
        if config.mode == "compete":
            model.Maximize(diversity_sum * 100_000 + total_quality - h8_penalty)
        else:
            model.Maximize(diversity_sum)
    else:
        raise ValueError(f"Unknown objective_kind: {objective_kind}")

    return model, x, num_players, num_innings, positions


def _extract_assignments(
    solver: cp_model.CpSolver,
    x: dict,
    players: List[PlayerInfo],
    num_innings: int,
    positions: List[int],
    locked_cells: List[LockedCell],
) -> List[dict]:
    assignments = []
    for pi, p in enumerate(players):
        for inn in range(num_innings):
            for pos in positions:
                if solver.Value(x[pi, inn, pos]) == 1:
                    assignments.append(
                        {
                            "inning": inn + 1,
                            "player_id": p.id,
                            "position": pos,
                            "locked": any(
                                lc.player_id == p.id
                                and lc.inning == inn + 1
                                and lc.position == pos
                                for lc in locked_cells
                            ),
                        }
                    )
    return assignments


def _solve_once(
    players: List[PlayerInfo],
    config: OptimizerConfig,
    locked_cells: List[LockedCell],
    prior_maps: List[AssignmentMap],
    min_quality: Optional[int],
    objective_kind: str,
    time_limit: float,
) -> Optional[SolverResult]:
    model, x, num_players, num_innings, positions = _build_model(
        players, config, locked_cells, prior_maps, min_quality, objective_kind
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.5, time_limit)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    assignments = _extract_assignments(
        solver, x, players, num_innings, positions, locked_cells
    )
    status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"
    return SolverResult(
        assignments=assignments,
        objective_value=solver.ObjectiveValue(),
        status=status_str,
    )


def solve_lineup_options(
    players: List[PlayerInfo],
    config: OptimizerConfig,
    locked_cells: Optional[List[LockedCell]] = None,
) -> MultiSolverResult:
    if locked_cells is None:
        locked_cells = []

    if config.mode not in GAME_MODES:
        raise ValueError(f"Invalid mode: {config.mode}")

    num_wanted = 1 if config.mode == "optimal" else MAX_MULTI_OPTIONS
    deadline = time.monotonic() + TOTAL_SOLVE_TIME_SECONDS
    prior_maps: List[AssignmentMap] = []
    options: List[LineupOption] = []
    best_quality: Optional[float] = None
    tolerance = config.compete_score_tolerance_pct if config.mode == "compete" else None

    for i in range(num_wanted):
        remaining = deadline - time.monotonic()
        if remaining < 0.5:
            break

        if i == 0:
            objective_kind = "quality" if config.mode in ("optimal", "compete") else "develop"
            min_quality = None
        else:
            objective_kind = "diversity"
            if config.mode == "compete" and best_quality is not None:
                min_quality = int(best_quality * 100 * (1 - config.compete_score_tolerance_pct / 100))
            else:
                min_quality = None

        result = _solve_once(
            players,
            config,
            locked_cells,
            prior_maps,
            min_quality,
            objective_kind,
            remaining,
        )
        if result is None:
            break

        amap = _assignments_to_map(result.assignments, players)
        if any(_maps_equal(amap, prev) for prev in prior_maps):
            break

        prior_maps.append(amap)
        quality = compute_quality_score(players, result.assignments, config)
        dev = compute_dev_score(players, result.assignments)

        if i == 0 and config.mode in ("optimal", "compete"):
            best_quality = quality

        options.append(
            LineupOption(
                option_id=len(options) + 1,
                assignments=result.assignments,
                quality_score=quality,
                dev_score=dev,
                objective_value=result.objective_value,
                status=result.status,
            )
        )

    return MultiSolverResult(
        options=options,
        mode=config.mode,
        best_quality_score=best_quality,
        tolerance_pct=tolerance,
    )


def solve_lineup(
    players: List[PlayerInfo],
    config: OptimizerConfig,
    locked_cells: Optional[List[LockedCell]] = None,
) -> SolverResult:
    """Return the first/best lineup option (backward-compatible wrapper)."""
    multi = solve_lineup_options(players, config, locked_cells)
    if not multi.options:
        return SolverResult(assignments=[], objective_value=0, status="infeasible")
    first = multi.options[0]
    return SolverResult(
        assignments=first.assignments,
        objective_value=first.objective_value,
        status=first.status,
    )
