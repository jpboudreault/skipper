"""
Rest calculator for pitcher eligibility.

Two modes based on game_type:
  - season/postseason: innings-based (rolling 7-day window)
  - tournament: pitch-count-based (bucket table + mandatory rest days, pitches summed across same-day games)
"""

import json
from datetime import date, timedelta
from sqlmodel import Session, select
from app.models import Game, PitchingAppearance, Team
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class PitcherEligibility:
    eligible: bool
    reason: str
    innings_today: int = 0
    innings_last_7_days: int = 0
    remaining_today: int = 0
    remaining_7_days: int = 0
    # Pitch-count (tournament) fields. Left at defaults in innings-based mode.
    pitches_today: int = 0
    remaining_pitches_today: Optional[int] = None
    rest_until: Optional[str] = None  # ISO date the player is eligible again, if resting


def get_pitcher_eligibility(
    player_id: int,
    game_date: date,
    game_type: str,
    team: Team,
    session: Session,
    exclude_game_id: Optional[int] = None,
) -> PitcherEligibility:
    """
    Calculate whether a player is eligible to pitch for a given game date.
    
    Args:
        player_id: The player to check.
        game_date: The date of the upcoming game.
        game_type: 'season', 'postseason', or 'tournament'.
        team: The team config (contains innings caps and pitch count rules).
        session: DB session.
        exclude_game_id: If solving for a specific game, exclude it from history
                         so we don't count the game we're about to fill.
    """
    if game_type in ("season", "postseason"):
        return _check_innings_based(player_id, game_date, team, session, exclude_game_id)
    elif game_type == "tournament":
        return _check_pitch_count_based(player_id, game_date, team, session, exclude_game_id)
    else:
        # Unknown game type, assume eligible
        return PitcherEligibility(eligible=True, reason="Unknown game type, assuming eligible")


def tournament_pitch_count_rules_configured(team: Team) -> bool:
    rules = _parse_pitch_count_rules(team)
    return rules.get("max_pitches_per_day") is not None or bool(
        rules.get("rest_requirements") or []
    )


def _check_innings_based(
    player_id: int,
    game_date: date,
    team: Team,
    session: Session,
    exclude_game_id: Optional[int],
) -> PitcherEligibility:
    """
    Innings-based rest rules (season + postseason):
    - Max N innings pitched per day (max_pitcher_innings_per_game)
    - Max M innings pitched in rolling 7 days (max_pitcher_innings_per_7_days)
    """
    max_per_day = team.max_pitcher_innings_per_game
    max_per_7_days = team.max_pitcher_innings_per_7_days

    # Get all pitching appearances in the last 7 days (inclusive of today for multi-game days)
    window_start = game_date - timedelta(days=6)  # 7-day window including today
    
    # Find games in the window
    games_in_window = session.exec(
        select(Game).where(
            Game.team_id == team.id,
            Game.date >= window_start,
            Game.date <= game_date,
        )
    ).all()

    # Sum innings from pitching appearances
    innings_today = 0
    innings_last_7_days = 0

    for game in games_in_window:
        if exclude_game_id and game.id == exclude_game_id:
            continue

        appearances = session.exec(
            select(PitchingAppearance).where(
                PitchingAppearance.game_id == game.id,
                PitchingAppearance.player_id == player_id,
            )
        ).all()

        for app in appearances:
            # ip_outs is innings × 3 (e.g. 2 full innings = 6)
            # For rest purposes, we count whole innings (round up partial)
            innings = (app.ip_outs + 2) // 3  # ceiling division
            innings_last_7_days += innings
            if game.date == game_date:
                innings_today += innings

    remaining_today = max(0, max_per_day - innings_today)
    remaining_7_days = max(0, max_per_7_days - innings_last_7_days)

    if innings_today >= max_per_day:
        return PitcherEligibility(
            eligible=False,
            reason=f"Already pitched {innings_today} innings today (max {max_per_day}/day)",
            innings_today=innings_today,
            innings_last_7_days=innings_last_7_days,
            remaining_today=0,
            remaining_7_days=remaining_7_days,
        )

    if innings_last_7_days >= max_per_7_days:
        return PitcherEligibility(
            eligible=False,
            reason=f"Pitched {innings_last_7_days} innings in last 7 days (max {max_per_7_days})",
            innings_today=innings_today,
            innings_last_7_days=innings_last_7_days,
            remaining_today=remaining_today,
            remaining_7_days=0,
        )

    return PitcherEligibility(
        eligible=True,
        reason=f"{remaining_today} inn left today, {remaining_7_days} inn left in 7-day window",
        innings_today=innings_today,
        innings_last_7_days=innings_last_7_days,
        remaining_today=remaining_today,
        remaining_7_days=remaining_7_days,
    )


def _parse_pitch_count_rules(team: Team) -> dict:
    try:
        return json.loads(team.pitch_count_rules_json or "{}") or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _required_rest_days(pitches: int, rest_requirements: List[Dict]) -> int:
    """
    Map a daily pitch total to the number of mandatory rest days using the
    bucket table. Buckets are inclusive ranges (min_pitches..max_pitches).
    If the total exceeds every defined bucket, the largest rest requirement applies.
    """
    if pitches <= 0 or not rest_requirements:
        return 0
    for bucket in rest_requirements:
        lo = bucket.get("min_pitches", 0)
        hi = bucket.get("max_pitches")
        if pitches >= lo and (hi is None or pitches <= hi):
            return bucket.get("days_rest", 0)
    # Over the top of the table: apply the strictest rest requirement defined.
    return max((b.get("days_rest", 0) for b in rest_requirements), default=0)


def _check_pitch_count_based(
    player_id: int,
    game_date: date,
    team: Team,
    session: Session,
    exclude_game_id: Optional[int],
) -> PitcherEligibility:
    """
    Pitch-count-based rest rules (tournament).

    - Pitches are summed across all same-day games.
    - A daily maximum (max_pitches_per_day) caps how much a pitcher can throw on game day.
    - Each prior pitching day requires a number of rest days based on the bucket table;
      the player cannot pitch again until those rest days have elapsed.
    """
    rules = _parse_pitch_count_rules(team)
    max_per_day = rules.get("max_pitches_per_day")
    rest_requirements = rules.get("rest_requirements", []) or []

    if not tournament_pitch_count_rules_configured(team):
        return PitcherEligibility(
            eligible=True,
            reason="No tournament pitch-count rules configured, assuming eligible",
        )

    max_rest = max((b.get("days_rest", 0) for b in rest_requirements), default=0)
    window_start = game_date - timedelta(days=max_rest + 1)

    games_in_window = session.exec(
        select(Game).where(
            Game.team_id == team.id,
            Game.game_type == "tournament",
            Game.date >= window_start,
            Game.date <= game_date,
        )
    ).all()

    pitches_by_date: Dict[date, int] = {}
    missing_pitch_count_dates: set[date] = set()
    for game in games_in_window:
        if exclude_game_id and game.id == exclude_game_id:
            continue
        appearances = session.exec(
            select(PitchingAppearance).where(
                PitchingAppearance.game_id == game.id,
                PitchingAppearance.player_id == player_id,
            )
        ).all()
        thrown = 0
        for app in appearances:
            if app.pitch_count is None and app.ip_outs > 0:
                missing_pitch_count_dates.add(game.date)
                continue
            thrown += app.pitch_count or 0
        if thrown:
            pitches_by_date[game.date] = pitches_by_date.get(game.date, 0) + thrown

    pitches_today = pitches_by_date.get(game_date, 0)
    remaining_pitches_today = (
        max(0, max_per_day - pitches_today) if max_per_day is not None else None
    )

    if missing_pitch_count_dates:
        dates = ", ".join(d.isoformat() for d in sorted(missing_pitch_count_dates))
        return PitcherEligibility(
            eligible=False,
            reason=f"Missing tournament pitch count for prior pitching appearance on {dates}",
            pitches_today=pitches_today,
            remaining_pitches_today=remaining_pitches_today,
        )

    # Daily cap: already maxed out for today.
    if max_per_day is not None and pitches_today >= max_per_day:
        return PitcherEligibility(
            eligible=False,
            reason=f"Already threw {pitches_today} pitches today (max {max_per_day}/day)",
            pitches_today=pitches_today,
            remaining_pitches_today=0,
        )

    # Rest requirement from prior pitching days.
    latest_rest_until: Optional[date] = None
    for day, pitches in pitches_by_date.items():
        if day == game_date:
            continue
        days_rest = _required_rest_days(pitches, rest_requirements)
        eligible_again = day + timedelta(days=days_rest + 1)
        if game_date < eligible_again:
            if latest_rest_until is None or eligible_again > latest_rest_until:
                latest_rest_until = eligible_again

    if latest_rest_until is not None:
        return PitcherEligibility(
            eligible=False,
            reason=f"Resting until {latest_rest_until.isoformat()} (pitch-count rest requirement)",
            pitches_today=pitches_today,
            remaining_pitches_today=remaining_pitches_today,
            rest_until=latest_rest_until.isoformat(),
        )

    reason = "Eligible (tournament pitch-count rules)"
    if remaining_pitches_today is not None:
        reason = f"{remaining_pitches_today} pitches left today"
    return PitcherEligibility(
        eligible=True,
        reason=reason,
        pitches_today=pitches_today,
        remaining_pitches_today=remaining_pitches_today,
    )
