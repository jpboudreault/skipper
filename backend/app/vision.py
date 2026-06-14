"""
vision.py — Anthropic Claude Sonnet vision API wrapper for parsing Baseball Québec scoresheets.

Sends a scoresheet photo + team roster to Claude and returns structured batting stats
matched to player IDs.
"""

import os
import re
import json
import base64
import asyncio
import httpx
from typing import Optional, List, Dict

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


def _build_prompt(players: List[Dict]) -> str:
    """Build the bilingual fr-CA prompt for Claude, including the roster for jersey matching."""
    roster_lines = "\n".join(
        f"  - #{p['jersey']} {p['first_name']} {p['last_name']}"
        for p in players
    )

    return f"""Voici une feuille de pointage (scoresheet) Baseball Québec pour une partie de softball/baseball.

OBJECTIF: Extraire les statistiques de chaque frappeur. Tu peux utiliser la ligne de TOTAUX de chaque frappeur ainsi que les losanges (diamond cells) de chaque manche pour t'aider à bien calculer les statistiques.

Voici des indices cruciaux pour interpréter les losanges (diamond cells) :
- POINT (Run) : Si un losange est complètement tracé/dessiné, le joueur a marqué un point. Compte-le.
- POINT PRODUIT (RBI) : Un numéro inscrit à l'intérieur du losange indique le numéro du joueur qui doit être crédité d'un point produit.
- BUT VOLÉ (Stolen Base / SB) : La mention "BV" sur le losange équivaut à un but volé.
- ERREUR (ROE) : Si "E*" est écrit sur la ligne allant au 1er but, le joueur est sauf sur erreur.
- BUT SUR BALLES (BB) : La mention "BB" encerclée signifie un but sur balles.
- ATTEINT (HBP) : La mention "FA" encerclée signifie un frappé par le lanceur.
- RETRAIT (Out) : Si la case n'a pas de barre (trait) allant vers le 1er but et qu'elle contient des numéros, le coureur a été retiré.

ÉQUIPE LOCALE (notre équipe) — voici le roster pour t'aider à associer les noms/numéros:
{roster_lines}

IMPORTANT: La feuille peut être pour l'équipe locale (Home) ou visiteuse (Visitor). Identifie d'abord quelle section correspond à NOTRE équipe en comparant les numéros de chandail (jersey) et noms ci-dessus avec ceux sur la feuille. Extrais UNIQUEMENT les stats de notre équipe.

LÉGENDE des abréviations Baseball Québec (feuille de pointage) → nos clés JSON:
  - 1B (simple/single) → "singles"
  - 2B (double) → "doubles"  
  - 3B (triple) → "triples"
  - CC ou HR (coup de circuit / home run) → "hr"
  - BB (but sur balles / base on balls) → "bb"
  - BBI ou IBB (but sur balles intentionnel) → "bbi"
  - FA ou HBP (frappé par le lanceur / hit by pitch) → "hbp"
  - SAC (sacrifice) → "sac"
  - INT ou OB (obstruction/interference) → "intf"
  - KD ou KL ou ꓘ (retrait sur décision / strikeout looking) → "kd"
  - KE ou KS ou K (retrait sur élan / strikeout swinging) → "ke"
  - R ou OUT (retiré autrement / outs not strikeouts) → "outs_not_k"
  - OPT ou FC (option / fielder's choice) → "fc"
  - E ou ROE ou RoE (atteint sur erreur / reached on error) → "roe"
  - PP ou RBI (points produits / runs batted in) → "rbi"
  - P ou R (points marqués / runs scored) → "r"
  - BV ou SB (but volé / stolen base) → "sb"

RÈGLES:
1. Retourner un JSON array. Chaque élément a les clés: "jersey" (int), "name" (string), puis chaque stat ci-dessus.
2. IMPORTANT: Inclure UNIQUEMENT les joueurs qui ont effectivement joué ou qui ont au moins une statistique non-nulle (ex. au moins 1 simple, double, point marqué, point produit, but sur balles, ou retrait). Ne génère PAS de lignes avec uniquement des zéros pour les joueurs qui étaient sur le banc.
3. Si une valeur est vide, illisible ou absente pour un joueur actif, utiliser 0.
4. Ne PAS inventer de valeurs — uniquement ce qui est écrit sur la feuille.
5. Inclure un champ "confidence" (float 0.0-1.0) indiquant ta confiance dans la lecture de cette ligne.
6. Si tu ne peux pas identifier le numéro de chandail, utilise 0 et mets confidence à 0.0.

Retourner UNIQUEMENT le JSON array, sans texte additionnel, sans markdown, sans ```json```.
"""


async def parse_scoresheet(
    image_bytes: bytes,
    content_type: str,
    players: List[Dict],
) -> List[Dict]:
    """
    Send a scoresheet image to Claude Sonnet and return parsed batting stats
    matched to player IDs.
    
    Args:
        image_bytes: Raw image file bytes
        content_type: MIME type (e.g. "image/jpeg")
        players: List of dicts with keys: id, jersey, first_name, last_name
        
    Returns:
        List of dicts with keys: player_id, jersey, name, confidence, and all stat fields.
        Unmatched jerseys will have player_id=None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or "your_anthropic_api" in api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    # Build the prompt with roster context
    prompt = _build_prompt(players)

    # Encode image as base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Map content types — Claude supports jpeg, png, gif, webp natively
    media_type = content_type
    if media_type in ("image/heic", "image/heif"):
        media_type = "image/jpeg"  # HEIC should be converted client-side

    # Build the Claude API request
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "temperature": 0.1,  # Low temperature for factual extraction
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    # Call Claude API with automatic retry on transient errors (529, 429) or network hiccups
    max_retries = 3
    retry_delay = 1.0  # initial delay in seconds

    async with httpx.AsyncClient(timeout=90.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    json=payload,
                    headers=headers,
                )
                
                # Retry on 529 (overloaded) or 429 (rate limited)
                if response.status_code in (529, 429) and attempt < max_retries - 1:
                    print(f"Claude API returned {response.status_code}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                
                if response.status_code != 200:
                    error_detail = response.text[:500]
                    raise RuntimeError(f"Claude API error ({response.status_code}): {error_detail}")
                
                break
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    print(f"Network error: {e}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2.0
                    continue
                raise RuntimeError(f"Network error connecting to Claude API: {e}")

    # Extract the text response
    result = response.json()
    try:
        text = result["content"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Claude response structure: {e}")

    # Clean up the response — strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Robust trailing comma cleaning (very common LLM mistake)
    # E.g. [1, 2, ] -> [1, 2] or {"a": 1, } -> {"a": 1}
    text = re.sub(r',\s*([\]}])', r'\1', text)

    # Parse JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Claude response as JSON: {e}\nRaw response: {text[:800]}")

    if not isinstance(parsed, list):
        raise RuntimeError(f"Expected JSON array from Claude, got {type(parsed).__name__}")

    # Build jersey → player_id lookup
    jersey_to_player = {}
    for p in players:
        jersey_to_player[p["jersey"]] = p["id"]

    # Stat keys we expect
    stat_keys = [
        "singles", "doubles", "triples", "hr", "bb", "bbi", "hbp",
        "sac", "intf", "kd", "ke", "outs_not_k", "fc", "roe",
        "rbi", "r", "sb",
    ]

    # Match parsed results to player IDs
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
        for key in stat_keys:
            row[key] = _safe_int(entry.get(key, 0))

        results.append(row)

    return results


def _safe_int(val) -> int:
    """Safely convert a value to int, defaulting to 0."""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
