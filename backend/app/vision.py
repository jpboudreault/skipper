"""
vision.py — Anthropic Claude Sonnet vision API wrapper for parsing league scoresheets.

Parse modes (SCORESHEET_PARSE_MODE):
  legacy (default) — upscale + horizontal tiles, single-pass stat extraction
  rows            — one crop per batter row (best for tight partial scans)
  transcribe      — tile + literal cell transcription, Python stat mapping
"""

import os
import re
import json
import base64
import asyncio
import httpx
from typing import List, Dict, Optional, Any

from app.league_formats import get_scoresheet_prompt, get_scoresheet_row_prompt, get_scoresheet_transcribe_prompt
from app.scoresheet_image import prepare_scoresheet_row_tiles, prepare_scoresheet_tiles
from app.scoresheet_interpret import STAT_KEYS, interpret_transcriptions

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


async def parse_scoresheet(
    image_bytes: bytes,
    content_type: str,
    players: List[Dict],
    scoresheet_version: Optional[str] = None,
) -> List[Dict]:
    """
    Send a scoresheet image to Claude Sonnet and return parsed batting stats
    matched to player IDs.
    """
    mode = os.environ.get("SCORESHEET_PARSE_MODE", "legacy").lower()
    if mode == "legacy":
        return await _parse_scoresheet_legacy(image_bytes, content_type, players, scoresheet_version)
    if mode == "transcribe":
        return await _parse_scoresheet_transcribe(image_bytes, content_type, players, scoresheet_version)
    return await _parse_scoresheet_rows(image_bytes, content_type, players, scoresheet_version)


async def _parse_scoresheet_rows(
    image_bytes: bytes,
    content_type: str,
    players: List[Dict],
    scoresheet_version: Optional[str],
) -> List[Dict]:
    prompt = get_scoresheet_row_prompt(scoresheet_version, players)
    from app.scoresheet_image import _load_rgb, _upscale_if_needed

    img = _upscale_if_needed(_load_rgb(image_bytes))
    estimated_rows = max(4, round(img.height / 150))
    expected_rows = min(len(players), estimated_rows) if len(players) <= 12 else estimated_rows
    tiles = prepare_scoresheet_row_tiles(
        image_bytes,
        content_type,
        expected_rows=expected_rows,
    )

    content: List[Dict[str, Any]] = []
    for tile_bytes, media_type, label in tiles:
        content.append({"type": "text", "text": label})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(tile_bytes).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": prompt})

    text = await _call_claude(content, max_tokens=4096, temperature=0.1)
    parsed = _merge_parsed_by_jersey(_parse_json_array(text))
    return _attach_player_ids(parsed, players)


async def _parse_scoresheet_transcribe(
    image_bytes: bytes,
    content_type: str,
    players: List[Dict],
    scoresheet_version: Optional[str],
) -> List[Dict]:
    tiles = prepare_scoresheet_tiles(image_bytes, content_type)
    prompt = get_scoresheet_transcribe_prompt(scoresheet_version, players)

    content: List[Dict[str, Any]] = []
    for i, (tile_bytes, media_type) in enumerate(tiles, start=1):
        if len(tiles) > 1:
            content.append({
                "type": "text",
                "text": f"Tuile {i}/{len(tiles)} (gauche vers droite de la feuille):",
            })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(tile_bytes).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": prompt})

    text = await _call_claude(content, max_tokens=4096, temperature=0.0)
    transcriptions = _parse_json_array(text)
    roster_jerseys = [p["jersey"] for p in players]
    interpreted = interpret_transcriptions(transcriptions, roster_jerseys)
    return _attach_player_ids(interpreted, players)


async def _parse_scoresheet_legacy(
    image_bytes: bytes,
    content_type: str,
    players: List[Dict],
    scoresheet_version: Optional[str],
) -> List[Dict]:
    prompt = get_scoresheet_prompt(scoresheet_version, players)
    tiles = prepare_scoresheet_tiles(image_bytes, content_type)

    content: List[Dict[str, Any]] = []
    for i, (tile_bytes, media_type) in enumerate(tiles, start=1):
        if len(tiles) > 1:
            content.append({
                "type": "text",
                "text": f"Tuile {i}/{len(tiles)} (gauche vers droite de la feuille):",
            })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(tile_bytes).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": prompt})

    text = await _call_claude(content, max_tokens=4096, temperature=0.1)
    parsed = _parse_json_array(text)
    return _attach_player_ids(parsed, players)


async def _call_claude(content: List[Dict[str, Any]], max_tokens: int, temperature: float) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or "your_anthropic_api" in api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    max_retries = 3
    retry_delay = 1.0

    async with httpx.AsyncClient(timeout=90.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    json=payload,
                    headers=headers,
                )
                if response.status_code in (529, 429) and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Claude API error ({response.status_code}): {response.text[:500]}"
                    )
                break
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                raise RuntimeError(f"Network error connecting to Claude API: {e}") from e

    result = response.json()
    try:
        return result["content"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Claude response structure: {e}") from e


def _merge_parsed_by_jersey(parsed: List[dict]) -> List[dict]:
    """Keep the best entry when row tiles return duplicate jerseys."""
    by_jersey: Dict[int, dict] = {}
    for entry in parsed:
        jersey = _safe_int(entry.get("jersey", 0))
        if jersey <= 0:
            continue
        if jersey not in by_jersey:
            by_jersey[jersey] = entry
            continue
        existing = by_jersey[jersey]
        if float(entry.get("confidence", 0)) > float(existing.get("confidence", 0)):
            by_jersey[jersey] = entry
    return list(by_jersey.values())


def _parse_json_array(text: str) -> List[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    text = re.sub(r",\s*([\]}])", r"\1", text)
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise RuntimeError(f"Expected JSON array from Claude, got {type(parsed).__name__}")
    return parsed


def _attach_player_ids(parsed: List[dict], players: List[Dict]) -> List[Dict]:
    jersey_to_player = {p["jersey"]: p["id"] for p in players}
    results = []
    for entry in parsed:
        jersey = _safe_int(entry.get("jersey", 0))
        player_id = jersey_to_player.get(jersey)
        row = {
            "player_id": player_id,
            "jersey": jersey,
            "name": entry.get("name", ""),
            "confidence": float(entry.get("confidence", 0.5)),
            "matched": player_id is not None,
        }
        for key in STAT_KEYS:
            row[key] = _safe_int(entry.get(key, 0))
        results.append(row)
    return results


def _normalize_media_type(content_type: str) -> str:
    if content_type in ("image/heic", "image/heif"):
        return "image/jpeg"
    return content_type


def _safe_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
