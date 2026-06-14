"""
Rest calculator for pitcher eligibility.

Two modes based on game_type:
  - season/postseason: innings-based (rolling 7-day window)
  - tournament: pitch-count-based (bucket table + mandatory rest days, pitches summed across same-day games)

Currently implements innings-based mode. Pitch-count mode is stubbed for later.
"""

from datetime import date, timedelta
from sqlmodel import Session, select
from app.models import Game, PitchingAppearance, Team
from typing import Optional
from dataclasses import dataclass


@dataclass
class PitcherEligibility:
    eligible: bool
    reason: str
    innings_today: int = 0
    innings_last_7_days: int = 0
    remaining_today: int = 0
    remaining_7_days: int = 0


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


def _check_pitch_count_based(
    player_id: int,
    game_date: date,
    team: Team,
    session: Session,
    exclude_game_id: Optional[int],
) -> PitcherEligibility:
    """
    Pitch-count-based rest rules (tournament).
    Pitches are summed across same-day games.
    Uses the team's pitch_count_rules_json bucket table.
    
    TODO: Implement when tournament season starts. For now, returns eligible.
    """
    return PitcherEligibility(
        eligible=True,
        reason="Pitch-count rules not yet implemented (tournament mode)",
    )
