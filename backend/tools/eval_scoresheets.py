#!/usr/bin/env python3
"""
eval_scoresheets.py — Evaluate scoresheet OCR accuracy against labelled fixtures.

Runs the REAL `app.vision.parse_scoresheet` (which calls the Anthropic API) against
each scenario in backend/tests/fixtures/scoresheets/ and compares the parsed stats to
the expected stats you hand-label. Prints a field-by-field diff per scenario plus an
overall accuracy summary.

This is NOT part of the pytest suite — it costs money and needs a network + API key.
Run it manually from the repo root, in WSL:

    export ANTHROPIC_API_KEY=sk-ant-...
    PYTHONPATH=./backend backend/.venv/bin/python backend/tools/eval_scoresheets.py

See backend/tests/fixtures/scoresheets/README.md for the fixture format.
"""

import os
import sys
import json
import asyncio
import argparse
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from app.vision import parse_scoresheet

# Stat keys must stay in sync with app/vision.py
STAT_KEYS = [
    "singles", "doubles", "triples", "hr", "bb", "bbi", "hbp",
    "sac", "intf", "kd", "ke", "outs_not_k", "fc", "roe",
    "rbi", "r", "sb",
]

EXT_TO_CONTENT_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# ANSI colors (disabled automatically when output is not a tty)
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str:
    return _c(t, "32")


def red(t: str) -> str:
    return _c(t, "31")


def yellow(t: str) -> str:
    return _c(t, "33")


def bold(t: str) -> str:
    return _c(t, "1")


def _normalize_expected_row(row: Dict) -> Dict:
    """Fill omitted stat fields with 0 so partial labels are allowed."""
    out = {"jersey": int(row["jersey"])}
    for k in STAT_KEYS:
        out[k] = int(row.get(k, 0))
    return out


def _find_image(scenario_json: Path, data: Dict) -> Path:
    """Resolve the image path for a scenario, falling back to same-base-name lookup."""
    if data.get("image"):
        candidate = scenario_json.parent / data["image"]
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Image '{data['image']}' referenced by {scenario_json.name} not found")
    base = scenario_json.with_suffix("")
    for ext in EXT_TO_CONTENT_TYPE:
        candidate = base.with_suffix(ext)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No image found for scenario {scenario_json.name}")


async def _parse_with_voting(image_bytes, content_type, roster, version, passes: int) -> List[Dict]:
    """Run parse_scoresheet `passes` times and majority-vote each stat field per jersey."""
    runs = []
    for _ in range(passes):
        runs.append(await parse_scoresheet(image_bytes, content_type, roster, version))
    if passes == 1:
        return runs[0]

    # Collect every jersey seen across runs, then vote each field.
    jerseys = set()
    for run in runs:
        for row in run:
            jerseys.add(int(row.get("jersey", 0)))

    voted = []
    for jersey in jerseys:
        # How many runs included this jersey at all?
        present = [row for run in runs for row in run if int(row.get("jersey", 0)) == jersey]
        if len(present) < (passes / 2):
            continue  # appeared in a minority of runs -> drop
        voted_row = {"jersey": jersey, "name": present[0].get("name", "")}
        for k in STAT_KEYS:
            votes = Counter(int(r.get(k, 0)) for r in present)
            voted_row[k] = votes.most_common(1)[0][0]
        confidences = [float(r.get("confidence", 0.5)) for r in present]
        voted_row["confidence"] = sum(confidences) / len(confidences)
        voted.append(voted_row)
    return voted


def _empty_stat_counts() -> Dict[str, Dict[str, int]]:
    """Per-stat tally: tp (caught), exp (actual), got (reported)."""
    return {k: {"tp": 0, "exp": 0, "got": 0} for k in STAT_KEYS}


def _score_scenario(expected: List[Dict], parsed: List[Dict]) -> Dict:
    """Compare expected vs parsed; return metrics + a printable diff."""
    expected_by_jersey = {r["jersey"]: r for r in expected}
    parsed_by_jersey = {int(r.get("jersey", 0)): r for r in parsed}

    lines = []
    total_fields = 0
    correct_fields = 0
    exact_rows = 0
    stat_counts = _empty_stat_counts()

    all_jerseys = sorted(set(expected_by_jersey) | set(parsed_by_jersey))

    for jersey in all_jerseys:
        exp = expected_by_jersey.get(jersey)
        got = parsed_by_jersey.get(jersey)

        if exp is None:
            # Extra batter: everything reported is a false positive (hurts precision).
            for k in STAT_KEYS:
                stat_counts[k]["got"] += int(got.get(k, 0))
            lines.append(red(f"  #{jersey:<3} EXTRA   — model returned a batter not in expected"))
            continue
        if got is None:
            # Missing batter: everything expected is missed (hurts recall).
            for k in STAT_KEYS:
                stat_counts[k]["exp"] += int(exp.get(k, 0))
            lines.append(red(f"  #{jersey:<3} MISSING — expected batter not returned by model"))
            total_fields += len(STAT_KEYS)
            continue

        diffs = []
        row_correct = True
        for k in STAT_KEYS:
            e = int(exp.get(k, 0))
            g = int(got.get(k, 0))
            total_fields += 1
            stat_counts[k]["exp"] += e
            stat_counts[k]["got"] += g
            stat_counts[k]["tp"] += min(e, g)
            if e == g:
                correct_fields += 1
            else:
                row_correct = False
                diffs.append(f"{k} exp={e} got={g}")

        if row_correct:
            exact_rows += 1
            lines.append(green(f"  #{jersey:<3} OK"))
        else:
            conf = got.get("confidence")
            conf_str = f" (conf={conf:.2f})" if isinstance(conf, (int, float)) else ""
            lines.append(red(f"  #{jersey:<3} WRONG{conf_str}: " + ", ".join(diffs)))

    expected_rows = len(expected_by_jersey)
    return {
        "lines": lines,
        "total_fields": total_fields,
        "correct_fields": correct_fields,
        "exact_rows": exact_rows,
        "expected_rows": expected_rows,
        "stat_counts": stat_counts,
    }


def _merge_stat_counts(into: Dict[str, Dict[str, int]], other: Dict[str, Dict[str, int]]) -> None:
    for k in STAT_KEYS:
        for field in ("tp", "exp", "got"):
            into[k][field] += other[k][field]


def _print_stat_table(stat_counts: Dict[str, Dict[str, int]]) -> None:
    """Per-stat recall (caught/actual) and precision (correct/reported)."""
    print(bold("\n=== PER-STAT (recall = caught/actual, precision = correct/reported) ==="))
    print(f"  {'stat':<12}{'actual':>7}{'caught':>7}{'recall':>8}   {'reported':>8}{'prec':>6}")
    for k in STAT_KEYS:
        c = stat_counts[k]
        exp, got, tp = c["exp"], c["got"], c["tp"]
        if exp == 0 and got == 0:
            continue
        recall = (100.0 * tp / exp) if exp else None
        prec = (100.0 * tp / got) if got else None

        def _tone(pct: Optional[float], width: int) -> str:
            s = f"{pct:.0f}%" if pct is not None else "-"
            s = s.rjust(width)
            if pct is None:
                return s
            if pct >= 80:
                return green(s)
            if pct >= 50:
                return yellow(s)
            return red(s)

        print(
            f"  {k:<12}{exp:>7}{tp:>7}{_tone(recall, 8)}   "
            f"{got:>8}{_tone(prec, 6)}"
        )


async def run_scenario(scenario_json: Path, passes: int) -> Optional[Dict]:
    data = json.loads(scenario_json.read_text(encoding="utf-8"))
    image_path = _find_image(scenario_json, data)
    content_type = EXT_TO_CONTENT_TYPE.get(image_path.suffix.lower())
    if content_type is None:
        raise ValueError(f"Unsupported image type: {image_path.suffix}")

    roster = data["roster"]
    version = data.get("scoresheet_version")
    expected = [_normalize_expected_row(r) for r in data.get("expected", [])]

    image_bytes = image_path.read_bytes()

    print(bold(f"\n=== {scenario_json.stem}  ({image_path.name}, {len(image_bytes)//1024} KB) ==="))
    try:
        parsed = await _parse_with_voting(image_bytes, content_type, roster, version, passes)
    except Exception as e:
        print(red(f"  ERROR calling parse_scoresheet: {e}"))
        return None

    result = _score_scenario(expected, parsed)
    for line in result["lines"]:
        print(line)

    tf = result["total_fields"]
    cf = result["correct_fields"]
    field_pct = (100.0 * cf / tf) if tf else 0.0
    row_pct = (100.0 * result["exact_rows"] / result["expected_rows"]) if result["expected_rows"] else 0.0
    print(
        f"  -> rows exact: {result['exact_rows']}/{result['expected_rows']} ({row_pct:.0f}%)   "
        f"fields correct: {cf}/{tf} ({field_pct:.0f}%)"
    )
    return result


async def main():
    parser = argparse.ArgumentParser(description="Evaluate scoresheet OCR against labelled fixtures.")
    default_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "scoresheets"
    parser.add_argument("--dir", default=str(default_dir), help="fixtures directory")
    parser.add_argument("--scenario", help="run a single scenario by base name (e.g. scenario_01)")
    parser.add_argument("--passes", type=int, default=1, help="runs per scan; >1 enables majority voting")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(red("ANTHROPIC_API_KEY is not set. Export it before running."))
        sys.exit(1)

    fixtures_dir = Path(args.dir)
    if not fixtures_dir.is_dir():
        print(red(f"Fixtures directory not found: {fixtures_dir}"))
        sys.exit(1)

    scenarios = sorted(
        p for p in fixtures_dir.glob("*.json")
        if not p.name.startswith("_")
    )
    if args.scenario:
        scenarios = [p for p in scenarios if p.stem == args.scenario]
    if not scenarios:
        print(yellow(f"No scenarios found in {fixtures_dir} (skipping files starting with '_')."))
        print(yellow("Add <name>.jpg + <name>.json pairs. See README.md."))
        return

    print(bold(f"Running {len(scenarios)} scenario(s), {args.passes} pass(es) each...\n"))

    agg_tf = agg_cf = agg_exact = agg_expected = 0
    agg_stats = _empty_stat_counts()
    for scenario_json in scenarios:
        result = await run_scenario(scenario_json, args.passes)
        if result:
            agg_tf += result["total_fields"]
            agg_cf += result["correct_fields"]
            agg_exact += result["exact_rows"]
            agg_expected += result["expected_rows"]
            _merge_stat_counts(agg_stats, result["stat_counts"])

    print(bold("\n=== OVERALL ==="))
    field_pct = (100.0 * agg_cf / agg_tf) if agg_tf else 0.0
    row_pct = (100.0 * agg_exact / agg_expected) if agg_expected else 0.0
    print(f"  rows exact:     {agg_exact}/{agg_expected} ({row_pct:.1f}%)")
    print(f"  fields correct: {agg_cf}/{agg_tf} ({field_pct:.1f}%)")
    _print_stat_table(agg_stats)


if __name__ == "__main__":
    asyncio.run(main())
