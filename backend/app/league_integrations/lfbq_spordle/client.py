"""Spordle Play API client for LFBQ schedule data."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

import httpx

DEFAULT_API_KEY = "f08ed9064e3cdc382e6abb305ff543d0150fb52f"
BASE_URL = "https://pub-api.play.spordle.com/api"

_schedule_cache: Dict[int, tuple[float, List[dict]]] = {}


class SpordleClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ.get("SPORDLE_API_KEY", DEFAULT_API_KEY)
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"API-Key {self.api_key}",
            "Accept": "application/json",
        }

    def get_game(self, game_id: int | str) -> dict:
        flt = json.dumps({"include": ["homeTeam", "awayTeam", "teamStats"]})
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{BASE_URL}/sp/games/{game_id}",
                headers=self._headers(),
                params={"filter": flt},
            )
            response.raise_for_status()
            return response.json()

    def get_schedule_games(
        self,
        schedule_id: int,
        *,
        cache_ttl_seconds: int = 6 * 3600,
    ) -> List[dict]:
        now = time.time()
        cached = _schedule_cache.get(schedule_id)
        if cached and now - cached[0] < cache_ttl_seconds:
            return cached[1]

        games: List[dict] = []
        skip = 0
        page_size = 200
        while True:
            batch = self._fetch_games_page(schedule_id, skip=skip, limit=page_size)
            if not batch:
                break
            games.extend(batch)
            if len(batch) < page_size:
                break
            skip += page_size

        _schedule_cache[schedule_id] = (now, games)
        return games

    def _fetch_games_page(self, schedule_id: int, *, skip: int, limit: int) -> List[dict]:
        flt = json.dumps(
            {
                "where": {"scheduleId": schedule_id},
                "limit": limit,
                "skip": skip,
                "include": ["homeTeam", "awayTeam", "teamStats"],
                "order": ["startTime ASC"],
            }
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{BASE_URL}/sp/games",
                headers=self._headers(),
                params={"filter": flt},
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []


def clear_schedule_cache() -> None:
    _schedule_cache.clear()
