"""
Convert the players.json WebSocket dump to mm_players.csv for the Streamlit app.

Usage:
    python mm_fantasy/convert_json.py [path/to/players.json] [output.csv]

Defaults to ../players.json and mm_fantasy/mm_players.csv relative to this script.
"""

import json
import csv
import sys
import os
from collections import Counter, defaultdict

# Make sure local imports work when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expected_points import estimate_xpts

POS_MAP = {
    "goalkeeper": "GK",
    "defender":   "DEF",
    "midfielder": "MID",
    "forward":    "FWD",
}

# ---------------------------------------------------------------------------
# Outright WC 2026 winner odds (decimal format, DraftKings/BetMGM ~June 2026)
# Using full-tournament odds instead of GW1 match odds means France/Spain/Brazil
# are correctly ranked as strong even when their GW1 opponent is tough.
# ---------------------------------------------------------------------------
OUTRIGHT_ODDS_DEC: dict[str, float] = {
    "ESP": 5.50,   "FRA": 5.75,   "ENG": 8.00,   "BRA": 9.00,
    "POR": 10.0,   "ARG": 10.0,   "GER": 15.0,   "NED": 21.0,
    "BEL": 23.0,   "SUI": 31.0,   "COL": 41.0,
    "MAR": 51.0,   "JPN": 51.0,   "URU": 56.0,   "USA": 61.0,
    "MEX": 61.0,   "CRO": 76.0,   "SEN": 76.0,   "KOR": 76.0,
    "ECU": 101.0,  "TUR": 101.0,  "AUT": 101.0,  "NOR": 126.0,
    "SWE": 151.0,  "CZE": 151.0,  "AUS": 176.0,  "CAN": 176.0,
    "SCO": 201.0,  "GHA": 251.0,  "CIV": 251.0,  "EGY": 301.0,
    "IRN": 301.0,  "TUN": 301.0,  "DZA": 301.0,  "QAT": 301.0,
    "ZAF": 401.0,  "PRY": 401.0,  "KSA": 401.0,  "COD": 501.0,
    "IRQ": 501.0,  "JOR": 501.0,  "BIH": 501.0,  "PAN": 501.0,
    "NZL": 501.0,  "HTI": 1001.0, "CUW": 1001.0, "CPV": 1001.0,
    "UZB": 1001.0,
}
DEFAULT_OUTRIGHT_ODDS = 501.0   # fallback for any team not in the dict


def compute_team_advance_probs(team_map: dict) -> dict:
    """
    Build per-team GW advancement probabilities from outright tournament winner odds.

    Uses bookmaker outright odds to rank teams by true tournament-level strength
    rather than GW1 match odds, which are heavily skewed by the luck of the draw
    (France vs Spain in GW1 would give both ~50% win prob, understating their quality).

    Model:
      • GW1-3 (group stage)  → prob = 1.0  (everyone plays)
      • Normalise implied probs across all 48 teams → per-team strength ratio r
      • P(advance from groups) = clip(0.15, 0.95, 0.67 × r^0.35)
      • P(win a KO match)      = clip(0.25, 0.70, 0.50 × r^0.20)
      • P(GW k) = P(advance groups) × P(win KO)^(k-4)  for k = 4..8
    """
    # Implied probs from outright decimal odds (raw, contains bookmaker overround)
    raw = {tid: 1.0 / OUTRIGHT_ODDS_DEC.get(abbr, DEFAULT_OUTRIGHT_ODDS)
           for tid, abbr in team_map.items()}
    total = sum(raw.values()) or 1.0
    norm = {tid: p / total for tid, p in raw.items()}

    p_avg = 1.0 / max(48, len(team_map))   # expected prob for an average team

    team_probs: dict[int, dict[int, float]] = {}
    for tid in team_map:
        p = norm.get(tid, p_avg)
        r = p / p_avg   # relative strength: >1 strong, <1 weak

        p_groups = min(0.95, max(0.15, 0.67 * (r ** 0.35)))
        p_ko     = min(0.70, max(0.25, 0.50 * (r ** 0.20)))

        team_probs[tid] = {
            1: 1.0, 2: 1.0, 3: 1.0,
            4: p_groups,
            5: p_groups * p_ko,
            6: p_groups * p_ko ** 2,
            7: p_groups * p_ko ** 3,
            8: p_groups * p_ko ** 4,
        }

    return team_probs


def load(json_path: str, csv_path: str):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Prefer real_matches.json (full tournament) next to players.json;
    # fall back to the matches embedded inside players.json (GW1 only).
    matches_path = os.path.join(os.path.dirname(os.path.abspath(json_path)), "real_matches.json")
    if os.path.exists(matches_path):
        with open(matches_path, encoding="utf-8") as f:
            matches_data = json.load(f)
        match_list  = matches_data.get("realMatches", [])
        # real_matches.json has its own realTeams list — use it for the match lookups
        match_teams = {t["id"]: t.get("abbr", t.get("name", "?")) for t in matches_data.get("realTeams", [])}
        print(f"Loaded {len(match_list)} matches from {os.path.basename(matches_path)}")
    else:
        match_list  = data.get("realMatches", [])
        match_teams = {}
        print("real_matches.json not found — using embedded matches from players.json")

    match_map = {m["id"]: m for m in match_list}

    # Count xG coverage and derive a data-driven fallback from available xG values
    xg_values = []
    for m in match_list:
        xg = m["details"].get("expectedGoals", [0, 0])
        h, a = float(xg[0]), float(xg[1])
        if h > 0 or a > 0:
            xg_values += [h, a]

    with_xg = len(xg_values) // 2
    print(f"Matches with real xG: {with_xg}/{len(match_list)}")

    if xg_values:
        import expected_points as ep_module
        ep_module.FALLBACK_XG = round(sum(xg_values) / len(xg_values), 3)
        print(f"Fallback xG set from real data: {ep_module.FALLBACK_XG:.3f} "
              f"(mean of {len(xg_values)} team-match xG values)")
    else:
        print(f"No real xG data — using default fallback xG: {__import__('expected_points').FALLBACK_XG}")

    # Build team → {gw: match} lookup for GW1-3 group stage only.
    # GW4+ matches have placeholder team IDs ("1st Group A") so real teams
    # won't be found — they fall back to the neutral baseline automatically.
    real_team_id_set = {t["id"] for t in data.get("realTeams", [])}
    team_gw_map: dict[int, dict[int, dict]] = defaultdict(dict)
    for m in match_list:
        gw = m.get("gameweek", 0)
        for tid in m.get("realTeamIds", []):
            if tid in real_team_id_set:
                team_gw_map[tid][gw] = m

    team_map = {t["id"]: t["abbr"] for t in data.get("realTeams", [])}
    # Supplement with teams from the matches file in case of any gap
    team_map.update({k: v for k, v in match_teams.items() if k not in team_map})

    # Per-team advancement probabilities derived from outright tournament winner odds
    team_advance = compute_team_advance_probs(team_map)
    flat_advance  = {1:1.0, 2:1.0, 3:1.0, 4:32/48, 5:16/48, 6:8/48, 7:4/48, 8:2/48}

    # Print summary for a few representative teams
    team_abbr_rev = {v: k for k, v in team_map.items()}
    print("\nSample team advancement probabilities (GW4/5/6/7/8):")
    sample_abbrs = ["ESP", "FRA", "BRA", "ENG", "ARG", "GER", "SUI", "SCO", "QAT", "HTI"]
    for abbr in sample_abbrs:
        tid = team_abbr_rev.get(abbr)
        if tid and tid in team_advance:
            p = team_advance[tid]
            print(f"  {abbr:4s}  GW4={p[4]:.2f}  GW5={p[5]:.2f}  "
                  f"GW6={p[6]:.2f}  GW7={p[7]:.2f}  GW8={p[8]:.2f}")
    print(f"  (flat) GW4={flat_advance[4]:.2f}  GW5={flat_advance[5]:.2f}  "
          f"GW6={flat_advance[6]:.2f}  GW7={flat_advance[7]:.2f}  GW8={flat_advance[8]:.2f}\n")

    # Current round from the data file (e.g. 2 = GW2)
    current_round = int(data.get("round") or 1)
    print(f"Current round from data: GW{current_round}")

    choices = data.get("playerChoices", [])
    print(f"Found {len(choices)} playerChoice entries")

    # Deduplicate by realPlayerId — keep entry with highest gameweek (most current)
    seen: dict[int, dict] = {}
    for pc in choices:
        pid = pc["realPlayerId"]
        if pid not in seen or pc["gameweek"] > seen[pid]["gameweek"]:
            seen[pid] = pc

    rows = []
    for pc in seen.values():
        rp = pc.get("realPlayer", {})
        first  = rp.get("firstName") or ""
        last   = rp.get("lastName") or ""
        custom = rp.get("customName")
        name   = custom if custom else f"{first} {last}".strip()

        position    = POS_MAP.get(pc["position"], pc["position"].upper())
        team        = team_map.get(pc["realTeamId"], str(pc["realTeamId"]))
        price       = float(pc["price"])
        total_points = float(pc.get("totalPoints") or 0)
        form        = float(pc.get("form") or 0)
        last_points = float(pc.get("lastPoints") or 0)
        lineup      = pc.get("lineup", "unexpected")
        player_id   = pc["id"]

        # Cumulative tournament stats from totalStats (populated after matches played)
        stats = pc.get("totalStats") or pc.get("avgStats") or {}
        s_mins    = int(stats.get("minutesPlayed", 0))
        s_goals   = int(stats.get("goal", 0))
        s_assists = int(stats.get("assist", 0))
        s_cs      = int(stats.get("cleanSheet", 0))
        s_shots   = int(stats.get("shotOnTarget", 0))
        s_saves   = int(stats.get("save", 0))
        s_concede = int(stats.get("concededGoal", 0))
        s_yellow  = int(stats.get("yellowCard", 0))
        s_red     = int(stats.get("redCard", 0))

        tid = pc["realTeamId"]

        # Model 1 — current round xPts (uses match data for the active round)
        cur_match = team_gw_map[tid].get(current_round)
        cur_tids  = cur_match["realTeamIds"] if cur_match else None
        xpts_round = estimate_xpts(
            position=position, lineup=lineup,
            team_id=tid, match=cur_match, real_team_ids=cur_tids,
        )

        # Model 2 — full tournament (GW1-8, team-specific advancement probs)
        advance_probs = team_advance.get(tid, flat_advance)
        xpts_total = 0.0
        for gw, prob in advance_probs.items():
            gw_match = team_gw_map[tid].get(gw)
            gw_tids  = gw_match["realTeamIds"] if gw_match else None
            xpts_total += estimate_xpts(
                position=position, lineup=lineup,
                team_id=tid, match=gw_match, real_team_ids=gw_tids,
            ) * prob
        xpts_total = round(xpts_total, 2)

        rows.append({
            "id":          player_id,
            "name":        name,
            "position":    position,
            "team":        team,
            "price":       price,
            "totalPoints": total_points,
            "form":        form,
            "lastPoints":  last_points,
            "lineup":      lineup,
            "xPtsRound":   round(xpts_round, 2),
            "xPts":        xpts_total,
            "mins":        s_mins,
            "goals":       s_goals,
            "assists":     s_assists,
            "cleanSheet":  s_cs,
            "shotsOnTarget": s_shots,
            "saves":       s_saves,
            "conceded":    s_concede,
            "yellowCards": s_yellow,
            "redCards":    s_red,
        })

    pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    rows.sort(key=lambda r: (pos_order.get(r["position"], 9), -r["xPts"]))

    fieldnames = ["id", "name", "position", "team", "price",
                  "totalPoints", "form", "lastPoints", "lineup", "xPtsRound", "xPts",
                  "mins", "goals", "assists", "cleanSheet", "shotsOnTarget",
                  "saves", "conceded", "yellowCards", "redCards"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written {len(rows)} unique players → {csv_path}")

    pos_counts = Counter(r["position"] for r in rows)
    print(f"Positions: {dict(pos_counts)}")

    # Show top 5 per position by xPts
    for pos in ["GK", "DEF", "MID", "FWD"]:
        top = sorted([r for r in rows if r["position"] == pos], key=lambda r: -r["xPts"])[:5]
        print(f"\nTop {pos} (tournament):")
        for r in top:
            print(f"  {r['name']:<25} {r['team']}  £{r['price']}M  "
                  f"GW{current_round}={r['xPtsRound']:.2f}  total={r['xPts']:.2f}")


if __name__ == "__main__":
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    # Prefer players_data.json (richer GW2+ data); fall back to players.json
    for candidate in ("players_data.json", "players.json"):
        candidate_path = os.path.join(script_dir, "..", candidate)
        if os.path.exists(candidate_path):
            default_json = candidate_path
            print(f"Using {candidate}")
            break
    else:
        default_json = os.path.join(script_dir, "..", "players_data.json")
    default_csv  = os.path.join(script_dir, "mm_players.csv")

    json_path = sys.argv[1] if len(sys.argv) > 1 else default_json
    csv_path  = sys.argv[2] if len(sys.argv) > 2 else default_csv

    load(json_path, csv_path)
