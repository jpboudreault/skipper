"""Convert raw scoresheet cell transcriptions into batting stat totals."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

STAT_KEYS = [
    "singles", "doubles", "triples", "hr", "bb", "bbi", "hbp",
    "sac", "intf", "kd", "ke", "outs_not_k", "fc", "roe",
    "rbi", "r", "sb",
]

_EMPTY_CELL = {"", "-", "empty", "vide", "blank", "none", "null"}


def merge_transcriptions(rows: List[dict]) -> List[dict]:
    """Merge duplicate jersey rows from overlapping tiles."""
    by_jersey: Dict[int, dict] = {}
    for row in rows:
        jersey = int(row.get("jersey") or 0)
        if jersey <= 0:
            continue
        cells = [_normalize_cell(c) for c in row.get("cells") or []]
        confidence = float(row.get("confidence", 0.5))
        if jersey not in by_jersey:
            by_jersey[jersey] = {
                "jersey": jersey,
                "name": row.get("name", ""),
                "cells": cells,
                "confidence": confidence,
            }
            continue
        existing = by_jersey[jersey]
        existing["cells"] = _merge_cell_lists(existing["cells"], cells)
        existing["confidence"] = max(existing["confidence"], confidence)
        if row.get("name"):
            existing["name"] = row["name"]
    return list(by_jersey.values())


def _cell_score(cells: List[str]) -> int:
    return sum(1 for c in cells if c and c.lower() not in _EMPTY_CELL)


def _cells_overlap(left: List[str], right: List[str]) -> bool:
    left_keys = {_cell_key(c) for c in left if c and c.lower() not in _EMPTY_CELL}
    right_keys = {_cell_key(c) for c in right if c and c.lower() not in _EMPTY_CELL}
    return bool(left_keys & right_keys)


def _cell_key(cell: str) -> str:
    upper = cell.upper()
    for token in ("BB", "KD", "KE", "OPT", "FC", "1B", "2B", "3B", "F1", "E2", "ROE", "BV", "SB"):
        if token in upper:
            return token
    return upper[:12]


def _merge_cell_lists(left: List[str], right: List[str]) -> List[str]:
    """Merge inning cells from multiple tiles for the same batter."""
    if not left:
        return right
    if not right:
        return left
    if _cell_score(left) == 0:
        return right
    if _cell_score(right) == 0:
        return left
    if _cells_overlap(left, right):
        return right if _cell_score(right) > _cell_score(left) else left
    return left + right


def interpret_transcriptions(
    rows: List[dict],
    roster_jerseys: Iterable[int],
) -> List[dict]:
    """Turn transcribed rows into stat dicts; assign RBIs credited inside diamonds."""
    allowed = set(roster_jerseys)
    merged = merge_transcriptions(rows)
    merged = [r for r in merged if r["jersey"] in allowed]

    rbi_credits: Counter = Counter()
    interpreted: Dict[int, dict] = {}

    for row in merged:
        jersey = row["jersey"]
        stats, credits = _interpret_cells(row["cells"], jersey)
        for credited, count in credits.items():
            if credited in allowed:
                rbi_credits[credited] += count
        interpreted[jersey] = {
            "jersey": jersey,
            "name": row.get("name", ""),
            "confidence": row["confidence"],
            **stats,
        }

    results = []
    for jersey, row in interpreted.items():
        row["rbi"] = rbi_credits.get(jersey, 0)
        if _has_activity(row):
            results.append(row)
    return results


def _normalize_cell(cell) -> str:
    if cell is None:
        return ""
    return str(cell).strip()


def _has_activity(row: dict) -> bool:
    return any(int(row.get(k, 0)) > 0 for k in STAT_KEYS)


def _interpret_cells(cells: List[str], batter_jersey: int) -> Tuple[Dict[str, int], Counter]:
    stats = {k: 0 for k in STAT_KEYS}
    rbi_credits: Counter = Counter()

    for cell in cells:
        if not cell or cell.lower() in _EMPTY_CELL:
            continue

        text = cell.upper()
        lower = cell.lower()

        if _diamond_filled(lower):
            stats["r"] += 1

        if not re.search(r"\bBP\b", text):
            for credited in _rbi_jerseys_in_cell(cell):
                rbi_credits[credited] += 1

        if _circled_hit(lower, "1"):
            stats["singles"] += 1
            continue
        if _circled_hit(lower, "2"):
            stats["doubles"] += 1
            continue
        if _circled_hit(lower, "3"):
            stats["triples"] += 1
            continue
        if _circled_hit(lower, "cc"):
            stats["hr"] += 1
            continue

        if re.search(r"\bKD\b|\bKL\b|ꓘ", text):
            stats["kd"] += 1
            continue
        if re.search(r"\bKE\b|\bKS\b", text):
            stats["ke"] += 1
            continue
        if re.search(r"(?<![A-Z0-9])K(?![A-Z0-9])", text):
            stats["ke"] += 1
            continue

        if _circled_left_abbrev(lower, "bb"):
            stats["bb"] += 1
            continue
        if _circled_left_abbrev(lower, "bbi"):
            stats["bbi"] += 1
            continue
        if _circled_left_abbrev(lower, "fa") or _circled_left_abbrev(lower, "hbp"):
            stats["hbp"] += 1
            continue
        if _circled_left_abbrev(lower, "sac"):
            stats["sac"] += 1
            continue
        if _circled_left_abbrev(lower, "int") or _circled_left_abbrev(lower, "ob"):
            stats["intf"] += 1
            continue

        if re.search(r"\b1B\b|SIMPLE", text):
            stats["singles"] += 1
            continue
        if re.search(r"\b2B\b|DOUBLE", text):
            stats["doubles"] += 1
            continue
        if re.search(r"\b3B\b|TRIPLE", text):
            stats["triples"] += 1
            continue
        if re.search(r"\bCC\b|\bHR\b", text):
            stats["hr"] += 1
            continue
        if re.search(r"\bOPT\b|\bFC\b", text):
            stats["fc"] += 1
            continue
        if re.search(r"\bROE\b|\bROER\b", text) or re.search(r"\bE\d?\b|\bE\*", text):
            stats["roe"] += 1
            continue
        if re.search(r"\bBV\b|\bSB\b", text):
            stats["sb"] += 1
            continue

        if re.search(r"\bFI\b|\bF\d\b|\bOUT\b|\bRETRAIT\b", text):
            stats["outs_not_k"] += 1
            continue
        if re.search(r"barre|slash|diagonal|/", lower) and re.search(r"\b[1-9]\b", text):
            stats["outs_not_k"] += 1
            continue
        if re.search(r"^\s*[1-9]\s*$", text) or re.search(r"\b[1-9]\b.*(?:OUT|RETRAIT)", text):
            stats["outs_not_k"] += 1

    return stats, rbi_credits


def _diamond_filled(lower: str) -> bool:
    markers = (
        "losange complet",
        "losange tracé",
        "losange trace",
        "diamond filled",
        "filled diamond",
        "complete diamond",
        "diamond complete",
    )
    return any(m in lower for m in markers)


def _circled_hit(lower: str, label: str) -> bool:
    """Detect circled 1/2/3/CC at top of cell from transcription text."""
    if label == "cc":
        return bool(re.search(r"\bcc\s*encercl|\bencercl\w*\s*cc\b", lower))
    return bool(re.search(rf"\b{label}\s*encercl|\bencercl\w*\s*{label}\b", lower))


def _is_circled(lower: str) -> bool:
    if re.search(r"rien\s+encercl|non\s+encercl|pas\s+encercl|aucun\s+encercl", lower):
        return False
    return bool(re.search(r"encercl|circle|cercle", lower))


def _circled_left_abbrev(lower: str, label: str) -> bool:
    """Detect circled left-column abbreviation (BB, BBI, FA, SAC, INT)."""
    if not _is_circled(lower):
        return False
    if label == "bb":
        return bool(re.search(r"\bbb\b", lower)) and not re.search(r"\bbbi\b", lower)
    if label == "bbi":
        return bool(re.search(r"\bbbi\b|\bibb\b", lower))
    if label in ("fa", "hbp"):
        return bool(re.search(r"\bfa\b|\bhbp\b", lower))
    if label == "sac":
        return bool(re.search(r"\bsac\b", lower))
    if label in ("int", "ob"):
        return bool(re.search(r"\bint\b|\bob\b", lower))
    return False


def _rbi_jerseys_in_cell(cell: str) -> List[int]:
    """Jersey numbers inside a diamond credit an RBI to that batter."""
    if re.search(r"\bBP\b", cell, flags=re.IGNORECASE):
        return []
    jerseys: List[int] = []
    for match in re.finditer(
        r"(?:losange|diamond)[^0-9]{0,40}(\d{1,2})|"
        r"(?:à l'intérieur|inside|intérieur|interieur)[^0-9]{0,20}(\d{1,2})|"
        r"(?:losange|diamond)\s*(?:avec|with)\s*(\d{1,2})|"
        r"(?:losange|diamond)\s*(?:avec|with)?\s*(\d{1,2})",
        cell,
        flags=re.IGNORECASE,
    ):
        num = next(g for g in match.groups() if g)
        jerseys.append(int(num))
    return jerseys
