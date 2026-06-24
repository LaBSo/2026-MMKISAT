"""
Pre-tournament expected points model for MM Fantasy (WC 2026).

Uses three signals from the WebSocket JSON dump:
  1. playerChoice.lineup  → probability the player actually plays
  2. realMatch.odds       → implied win/draw/loss probabilities
  3. realMatch.expectedGoals (xG) → expected goals for/against each team

Scoring rules (from the game):
  All players:  play <60 min +1, play ≥60 min +2
                assist +3, yellow -1, red -3
                playing while winning +0.3, playing while losing -0.3
  GK:           clean sheet (60+) +4, save +0.5, goal +8, per 2 conceded -1
  DEF:          clean sheet (60+) +4, goal +6, per 2 conceded -1
  MID:          goal +5, clean sheet (60+) +1, full match +1
  FWD:          goal +4, full match +1
"""

import math
from typing import Optional

# ---------------------------------------------------------------------------
# Lineup → probability of starting / playing significant minutes
# ---------------------------------------------------------------------------

LINEUP_PROB = {
    "expected":   0.82,   # likely starter
    "possible":   0.50,   # rotation / injury doubt
    "unexpected": 0.12,   # squad player, unlikely to start
    "injured":    0.02,
    "suspended":  0.00,   # cannot play this round
}
DEFAULT_LINEUP_PROB = 0.12

# Given the player plays at all, P(≥60 min)
# Starters almost always go 60+; bench players often don't
LINEUP_P60_GIVEN_PLAYS = {
    "expected":   0.87,
    "possible":   0.62,
    "unexpected": 0.35,
    "injured":    0.20,
    "suspended":  0.00,
}
DEFAULT_P60 = 0.35

# ---------------------------------------------------------------------------
# Position-level contribution fractions (share of team xG / assists)
# Calibrated roughly on WC group-stage data.
# ---------------------------------------------------------------------------

# Expected fraction of team goals scored by one player of this position
GOAL_FRAC = {"GK": 0.005, "DEF": 0.05, "MID": 0.14, "FWD": 0.32}
# Expected assists per goal (most goals have an assist; ~0.75 of goals get credited)
ASSIST_PER_GOAL = 0.75
ASSIST_FRAC = {pos: GOAL_FRAC[pos] * ASSIST_PER_GOAL for pos in GOAL_FRAC}

# GK saves: ~4 saves per game on average (rough WC average)
AVG_SAVES_PER_GAME = 4.0

# Shots on target by position (per 90 min for a typical starter)
SHOTS_ON_TARGET = {"GK": 0.5, "DEF": 0.3, "MID": 0.5, "FWD": 0.9}

# Yellow card rate per game (roughly 0.10 per player per game at WC)
YELLOW_RATE = 0.10
# Goals per team per game used when a match has no xG data.
# Updated dynamically by convert_json.py from the real xG values in real_matches.json.
# Falls back to historical WC average (~1.35) if no real data is available yet.
FALLBACK_XG = 1.35

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_odd(val, default: float = 3.0) -> float:
    """Parse an odds value that may be a string, float, or {'default': n} dict."""
    if isinstance(val, dict):
        val = val.get("default", default)
    try:
        v = float(val)
        return v if v > 1.0 else default   # 0 / None means not set
    except (TypeError, ValueError):
        return default


def _odds_to_probs(odds: dict) -> tuple[float, float, float]:
    """Convert decimal odds to normalised win/draw/loss probabilities."""
    h  = _parse_odd(odds.get("home"), 3.0)
    dr = _parse_odd(odds.get("draw"), 3.0)
    a  = _parse_odd(odds.get("away"), 3.0)
    try:
        raw = (1 / h, 1 / dr, 1 / a)
        total = sum(raw)
        return raw[0] / total, raw[1] / total, raw[2] / total
    except ZeroDivisionError:
        return 1 / 3, 1 / 3, 1 / 3


def _cs_prob(xg_against: float) -> float:
    """P(clean sheet) = P(Poisson(xg) = 0)."""
    return math.exp(-max(xg_against, 0))


def _win_malus(p_win: float, p_loss: float) -> float:
    """Expected win/loss bonus: +0.3 while winning, -0.3 while losing."""
    return 0.3 * p_win - 0.3 * p_loss


# ---------------------------------------------------------------------------
# Core estimator
# ---------------------------------------------------------------------------

def estimate_xpts(
    position: str,
    lineup: str,
    team_id: int,
    match: Optional[dict],
    real_team_ids: Optional[list],
) -> float:
    """
    Return expected fantasy points for one player in one GW.

    Args:
        position:       'GK' | 'DEF' | 'MID' | 'FWD'
        lineup:         value from playerChoice.lineup
        team_id:        player's realTeamId
        match:          realMatch dict (may be None)
        real_team_ids:  ordered [home_team_id, away_team_id] from the match
    """
    p_plays = LINEUP_PROB.get(lineup, DEFAULT_LINEUP_PROB)
    p_60 = p_plays * LINEUP_P60_GIVEN_PLAYS.get(lineup, DEFAULT_P60)

    if match and real_team_ids:
        details = match.get("details", {})
        odds = details.get("odds", {})
        xg = details.get("expectedGoals", [0.0, 0.0])
        xg_home = float(xg[0]) if xg else 0.0
        xg_away = float(xg[1]) if xg else 0.0
        is_home = (team_id == real_team_ids[0])
        xg_for     = (xg_home if is_home else xg_away)  or FALLBACK_XG
        xg_against = (xg_away if is_home else xg_home)  or FALLBACK_XG
        p_win, p_draw, p_loss = _odds_to_probs(odds)
        if not is_home:
            p_win, p_loss = p_loss, p_win   # flip perspective to player's team
    else:
        # No match data — use tournament averages as neutral baseline
        xg_for     = FALLBACK_XG
        xg_against = FALLBACK_XG
        p_win = p_draw = p_loss = 1 / 3

    p_cs = _cs_prob(xg_against)

    # --- Appearance points ---
    pts = p_plays * 1.0        # +1 for any play
    pts += p_60 * 1.0          # +1 bonus for 60+ min (total 2)

    # --- Win/loss bonus ---
    pts += p_plays * _win_malus(p_win, p_loss)

    # --- Yellow card malus ---
    pts += p_plays * (-1.0) * YELLOW_RATE

    # --- Scoring contributions ---
    goal_pts = {"GK": 8, "DEF": 6, "MID": 5, "FWD": 4}[position]
    exp_goals = xg_for * GOAL_FRAC[position]
    exp_assists = xg_for * ASSIST_FRAC[position]
    pts += p_plays * (exp_goals * goal_pts + exp_assists * 3.0)

    # --- Clean sheet ---
    if position in ("GK", "DEF"):
        cs_pts = 4.0
        pts += p_60 * p_cs * cs_pts
        # Goals conceded malus: E[-1 per 2 conceded] = -0.5 * xg_against
        pts += p_plays * (-0.5) * xg_against
    elif position == "MID":
        pts += p_60 * p_cs * 1.0
        # Full match bonus
        pts += p_60 * 1.0
    elif position == "FWD":
        # Full match bonus
        pts += p_60 * 1.0

    # --- GK saves ---
    if position == "GK":
        # Saves ≈ roughly proportional to opponent xG
        exp_saves = max(xg_against, 1.0) * 2.5   # ~2.5 saves per xG
        pts += p_plays * exp_saves * 0.5           # 0.5 pts per save

    # --- Shots on target (non-GK) ---
    if position != "GK":
        pts += p_plays * SHOTS_ON_TARGET[position] * {"DEF": 0.6, "MID": 0.4, "FWD": 0.4}[position]

    return round(max(pts, 0.0), 2)
