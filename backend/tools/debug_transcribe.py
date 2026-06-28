#!/usr/bin/env python3
"""Debug helper: print raw transcription JSON for one scenario."""
import asyncio
import base64
import json
import sys
from pathlib import Path

from app.league_formats import get_scoresheet_transcribe_prompt
from app.scoresheet_image import prepare_scoresheet_tiles
from app.scoresheet_interpret import interpret_transcriptions
from app.vision import _call_claude, _parse_json_array


async def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "scenario_01"
    base = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "scoresheets"
    data = json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
    img = (base / data.get("image", f"{name}.jpg")).read_bytes()
    tiles = prepare_scoresheet_tiles(img, "image/jpeg")
    print(f"tiles: {len(tiles)}")
    prompt = get_scoresheet_transcribe_prompt(data.get("scoresheet_version"), data["roster"])
    content = []
    for i, (tb, mt) in enumerate(tiles, 1):
        content.append({"type": "text", "text": f"Tuile {i}/{len(tiles)}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mt,
                "data": base64.b64encode(tb).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": prompt})
    text = await _call_claude(content, 4096, 0.0)
    parsed = _parse_json_array(text)
    print("--- transcription ---")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    interpreted = interpret_transcriptions(parsed, [p["jersey"] for p in data["roster"]])
    print("--- interpreted ---")
    print(json.dumps(interpreted, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
