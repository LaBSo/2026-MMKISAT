"""
Expected points estimation from raw player stats.
Used to project future performance for the optimizer.
"""

from models import Player


def estimate_points_per_game(p: Player, games_in_round: int = 1) -> float:
    """Estimate expected fantasy points for a player in a single game."""
    if p.minutes == 0:
        return 0.0

    games_played = max(1, p.minutes // 90)
    avg_min = p.minutes / games_played

    pts = 0.0

    # Playing time: ~1pt for any play, +1 if 60+ min
    play_prob = 0.85  # assume they probably play
    pts += play_prob * 1.0
    if avg_min >= 60:
        pts += play_prob * 1.0

    # Goals
    goals_per_game = p.goals / games_played
    if p.position == "GK":
        pts += goals_per_game * 8
    elif p.position == "DEF":
        pts += goals_per_game * 6
    elif p.position == "MID":
        pts += goals_per_game * 5
    else:  # FWD
        pts += goals_per_game * 4

    # Assists (fantasy assist = 3 pts)
    assists_per_game = p.assists / games_played
    pts += assists_per_game * 3

    # Shots on target
    sot_per_game = p.shots_on_target / games_played
    if p.position == "GK":
        pts += sot_per_game * 1.0
    elif p.position == "DEF":
        pts += sot_per_game * 0.6
    elif p.position == "MID":
        pts += sot_per_game * 0.4
    else:
        pts += sot_per_game * 0.4

    # Clean sheets (60+ min)
    cs_per_game = p.clean_sheets / games_played
    if avg_min >= 60:
        if p.position in ("GK", "DEF"):
            pts += cs_per_game * 4
        elif p.position == "MID":
            pts += cs_per_game * 1

    # GK saves
    if p.position == "GK":
        saves_per_game = p.saves / games_played
        pts += saves_per_game * 0.5

    # Yellow cards
    yc_per_game = p.yellow_cards / games_played
    pts -= yc_per_game * 1.0

    # Red cards
    rc_per_game = p.red_cards / games_played
    pts -= rc_per_game * 3.0

    # Full match bonus for MID/FWD
    if p.position in ("MID", "FWD"):
        full_match_prob = 1.0 if avg_min >= 90 else avg_min / 90
        pts += full_match_prob * 1.0

    return round(pts * games_in_round, 2)


def points_value_ratio(p: Player, games_in_round: int = 1) -> float:
    """Points per million — useful for comparing players."""
    if p.price == 0:
        return 0.0
    ep = estimate_points_per_game(p, games_in_round)
    return round(ep / p.price, 3)
