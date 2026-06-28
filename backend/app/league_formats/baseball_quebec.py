"""Baseball Québec scoresheet and lineup print format (default)."""

from typing import List

from app.league_formats.registry import register_scoresheet, register_scoresheet_rows, register_scoresheet_transcribe


# All stat keys the model must emit for every batter (0 when absent).
STAT_KEYS = [
    "singles", "doubles", "triples", "hr", "bb", "bbi", "hbp",
    "sac", "intf", "kd", "ke", "outs_not_k", "fc", "roe",
    "rbi", "r", "sb",
]


def _roster_lines(players: List[dict]) -> str:
    return "\n".join(
        f"  - #{p['jersey']}"
        + (
            f" {p.get('first_name', '')} {p.get('last_name', '')}".rstrip()
            if p.get("first_name") or p.get("last_name")
            else ""
        )
        for p in players
    )


def _stat_legend() -> str:
    return """STAT KEYS (sheet mark -> JSON key):
  singles      1 circled (top of cell)
  doubles      2 circled (top of cell)
  triples      3 circled (top of cell)
  hr           CC circled (top of cell)
  bb           BB circled (left column)
  bbi          BBI / IBB circled (left column)
  hbp          FA circled (left column)
  sac          SAC circled (left column)
  intf         INT circled (left column)
  kd           KD / KL / backwards-K (called strikeout)
  ke           KE / KS / K (swinging strikeout)
  outs_not_k   any other out: F1-F9, ground out, out line (NOT a strikeout)
  fc           OPT / FC (fielder's choice)
  roe          E, E2, ROE (reached on error)
  rbi          jersey number written inside a diamond (see RBI rule)
  r            diamond fully drawn/filled = that runner scored
  sb           BV / SB (stolen base)"""


def _cell_reading_rules() -> str:
    return """HOW TO READ ONE INNING CELL (the diamond):

HITS (printed across the TOP of each cell): "1  2  3  CC".
  The scorer CIRCLES the one that happened. Count a hit ONLY if circled:
    1 circled -> singles ; 2 -> doubles ; 3 -> triples ; CC -> hr.
  Nothing circled on top = no hit.
  CRITICAL: a hit comes ONLY from one of the printed top numbers being visibly
  CIRCLED (an ellipse drawn around it). 
  - How far the runner advanced (line drawn to 2nd/3rd, full diamond) is NOT a hit.
  - Handwritten numbers INSIDE the cell body are NOT hits. In particular a
    hyphenated sequence like "5-3", "4-3", "6-3", "1-3", "2-3" is a FIELDING OUT
    (see outs_not_k), NOT a triple — the "3" there is the first baseman, not a 3B.
  If nothing on top is circled, singles/doubles/triples/hr = 0.

LEFT COLUMN (printed vertically left of the diamond): BB, BBI, FA, SAC, INT.
  The scorer CIRCLES the one that happened. Count ONLY if circled:
    BB -> bb ; BBI/IBB -> bbi ; FA -> hbp ; SAC -> sac ; INT -> intf.
  Printed-but-not-circled = 0. Do not count the printed labels themselves.

RUNS (r) — IMPORTANT, often missed:
  A run is scored when the DIAMOND IS FULLY DRAWN/FILLED IN (all four legs traced,
  often shaded). For each batter row, count how many of their diamonds are fully
  drawn = that batter's "r". A diamond only partly drawn (runner left on base) is NOT a run.

RBI — IMPORTANT, can credit ANOTHER batter:
  A jersey number written INSIDE a diamond names WHO gets the RBI for that play.
  Example: "44" inside batter #50's diamond -> add 1 to "rbi" for player #44
  (not #50). So a batter's rbi total = every diamond on the WHOLE sheet that
  contains THEIR jersey number, regardless of which row it sits in.
  "BP" (passed ball) inside a diamond -> nobody gets an RBI.
  Cropped image: still credit the rbi to the roster jersey shown in the diamond.

OTHER MARKS inside/around the diamond:
  BV -> sb ; E/E2/ROE on the way to 1st -> roe ; OPT/FC -> fc ;
  KD/KL/backwards-K -> kd ; KE/KS/K -> ke.
  outs_not_k when an explicit out mark is present: a hyphenated fielding sequence
  (e.g. 5-3, 4-3, 6-3, 1-3, 2-3, 6-4-3), a single fielder putout (F8, P4, L6),
  or a clear "out" line. Count one out per such mark. An empty cell, or a runner
  left on base with no out notation, is NOT an out — outs_not_k = 0 there. Do not
  assume an out just because there is no hit.

PROCEDURE (per batter row):
  1. Read the jersey (#) in the left margin.
  2. Scan each inning cell L->R: circled hit on top, circled left-column abbrev,
     then marks inside the diamond (fully-drawn = run, jersey number = RBI credit).
  3. Sum runs = filled diamonds in this row; sum steals, outs, etc.
  4. Sweep ALL diamonds on the sheet for jersey numbers to assign rbi credits."""


def _output_rules() -> str:
    keys = ", ".join(f'"{k}"' for k in STAT_KEYS)
    return f"""OUTPUT RULES:
1. Return ONLY a JSON array, no markdown.
2. One object per batter who actually batted (jersey in the roster above and at
   least one non-zero stat). Skip players who did not appear.
3. Every object MUST contain ALL of these keys, using 0 when the stat did not
   happen (never omit a key, never leave one null):
   "jersey" (int), "name" (string), {keys}, "confidence" (0.0-1.0).
4. Only report a stat you can SEE the mark for. When unsure, use 0 — a wrong
   non-zero value is worse than a 0. Never invent triples, outs, or runs to fill a cell.
5. Unreadable value -> 0. Unreadable jersey -> jersey 0, confidence 0.0. Do not invent."""


@register_scoresheet("baseball_quebec")
def build_scoresheet_prompt(players: List[dict]) -> str:
    """Build the English prompt for Claude, including the roster for jersey matching."""
    roster_lines = _roster_lines(players)

    return f"""You are reading one or more image tiles (left to right) of a Baseball Québec scoresheet.

GOAL: Extract each visible batter's stats. If several tiles are given, merge them
(same rows, adjacent inning columns). The image may be a partial crop — extract
every visible row whose jersey is in the roster below.

OUR TEAM — expected jerseys:
{roster_lines}

{_cell_reading_rules()}

{_stat_legend()}

{_output_rules()}
"""


@register_scoresheet_transcribe("baseball_quebec")
def build_scoresheet_transcribe_prompt(players: List[dict]) -> str:
    """Prompt for pass 1: transcribe each inning cell literally, no stat math."""
    roster_lines = _roster_lines(players)

    return f"""You are reading one or more image tiles (left to right) of a Baseball Québec scoresheet.

GOAL: TRANSCRIBE only what is written/drawn — do NOT compute stats.

OUR TEAM — expected jerseys:
{roster_lines}

For each batter, describe each inning cell (left -> right). Examples:
  - "1 2 3 CC on top, none circled"
  - "2 circled on top, 1 3 CC not circled"
  - "BB circled in left column"
  - "left column BB BBI FA SAC INT, none circled"
  - "diamond fully drawn/filled (run scored)"
  - "diamond with 52 inside"
  - "BP inside diamond"
  - "KD" / "OPT" / "E2" / "F1" / "empty"

Reminders:
  - Hits: say which of 1/2/3/CC is CIRCLED on top (or "none circled").
  - Left column: say which of BB/BBI/FA/SAC/INT is CIRCLED (or "none circled").
  - Run: say explicitly when a diamond is fully drawn/filled.
  - RBI: a jersey number inside the diamond, or BP if passed ball.

RULES:
1. JSON array: "jersey", "name", "cells" (array of strings), "confidence".
2. Active batters only. Unreadable -> "unreadable".
3. One entry per player per tile when tiles show different columns.

Return ONLY the JSON array, no markdown.
"""


@register_scoresheet_rows("baseball_quebec")
def build_scoresheet_row_prompt(players: List[dict]) -> str:
    """Prompt when each image is a single batter row (max resolution per row)."""
    roster_lines = _roster_lines(players)

    return f"""These are individual batter-row images (labeled "Row N", top -> bottom).
Some rows have 2 horizontal tiles — merge them for that row.

GOAL: Extract each visible batter's stats. Read the jersey (#) on the left and the
TOTALS row on the right (if visible).

OUR TEAM — expected jerseys:
{roster_lines}

{_cell_reading_rules()}

{_stat_legend()}

{_output_rules()}
"""
