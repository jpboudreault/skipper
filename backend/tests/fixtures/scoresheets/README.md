# Scoresheet OCR evaluation fixtures

Drop your test scenarios here. Each scenario is **one image + one JSON file** with the
same base name:

```
scenario_01.jpg     # the scoresheet photo (player names can be obfuscated)
scenario_01.json    # the roster + the EXPECTED stats you want the scan to produce
```

Supported image extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.

## JSON format

```json
{
  "image": "scenario_01.jpg",
  "scoresheet_version": "baseball_quebec",
  "roster": [
    { "id": 1, "jersey": 3,  "first_name": "Player", "last_name": "A" },
    { "id": 2, "jersey": 12, "first_name": "Player", "last_name": "B" }
  ],
  "expected": [
    { "jersey": 3,  "singles": 1, "r": 1, "sb": 1 },
    { "jersey": 12, "doubles": 1, "rbi": 2, "r": 1 }
  ]
}
```

### Rules to keep filling these in easy

- In `expected`, **only list the non-zero stats** for each batter. Any stat you omit is
  assumed to be `0`. (So a batter who only hit a single and scored is just
  `{ "jersey": 3, "singles": 1, "r": 1 }`.)
- Only include batters who actually appear / batted. Batters you leave out of `expected`
  are expected NOT to appear in the scan output (the harness flags extras).
- `image` is optional — if omitted, the harness looks for a file with the same base name
  as the JSON.
- `scoresheet_version` is optional — defaults to `baseball_quebec`.
- **Partial crops**: the image may cut off inning columns. RBIs can still appear as
  jersey numbers inside diamonds on visible cells — credit `rbi` to that jersey in
  `expected` even if the scoring play started in the cut-off area.
- **RBI rule**: a jersey number written inside the diamond = that player gets the RBI.
  `BP` (ball passée) in the diamond = no RBI for that cell.
- **Hits**: at the top of each cell, `1  2  3  CC` are pre-printed; the scorekeeper
  **circles** the hit type. Only count circled numbers as singles/doubles/triples/hr.
- **Left column**: to the left of the diamond's leftmost dot, each cell has a vertical
  list `BB`, `BBI`, `FA`, `SAC`, `INT` pre-printed. The scorekeeper **circles** one when
  it applies (walk, intentional walk, hit-by-pitch, sacrifice, interference). Only count
  circled abbreviations — not the printed labels alone.

## Stat keys (must match the model's JSON keys)

| key           | meaning (Baseball Québec)                  |
|---------------|--------------------------------------------|
| `singles`     | 1B simple                                  |
| `doubles`     | 2B double                                  |
| `triples`     | 3B triple                                  |
| `hr`          | CC / HR coup de circuit                    |
| `bb`          | BB but sur balles                          |
| `bbi`         | BBI / IBB intentionnel                     |
| `hbp`         | FA / HBP frappé par le lanceur             |
| `sac`         | SAC sacrifice                              |
| `intf`        | INT / OB obstruction / interference        |
| `kd`          | KD / KL retrait sur décision (looking)     |
| `ke`          | KE / KS retrait sur élan (swinging)        |
| `outs_not_k`  | R / OUT retiré autrement                   |
| `fc`          | OPT / FC fielder's choice                  |
| `roe`         | E / ROE atteint sur erreur                 |
| `rbi`         | PP / RBI points produits                   |
| `r`           | P / R points marqués                       |
| `sb`          | BV / SB but volé                           |

## Running the eval

From the repo root, in WSL (needs your Anthropic key):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
PYTHONPATH=./backend backend/.venv/bin/python backend/tools/eval_scoresheets.py
```

The summary ends with a **per-stat table** showing, for every stat key, how many were
actually on the sheets vs how many the model caught:

- **recall** = caught / actual (did we find the real stats?)
- **precision** = correct / reported (is what we reported real, or noise?)

Use this to see *which* stats are weak (e.g. runs at 0% recall) instead of one blended
accuracy number. Run with `--passes 3` to average out run-to-run model variance before
trusting small differences.

Optional flags:

- `--scenario scenario_01` run a single scenario by base name
- `--passes 2` run each scan N times and majority-vote each field (self-consistency)
- `--dir <path>` use a different fixtures directory

Set `SCORESHEET_PARSE_MODE=rows` (default), `legacy` (single-pass tiled), or `transcribe` (experimental).
