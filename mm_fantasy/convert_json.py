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
from collections import Counter

# Make sure local imports work when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from expected_points import estimate_xpts

POS_MAP = {
    "goalkeeper": "GK",
    "defender":   "DEF",
    "midfielder": "MID",
    "forward":    "FWD",
}


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

    # Count xG coverage
    with_xg = sum(1 for m in match_list if sum(m["details"].get("expectedGoals", [0, 0])) > 0)
    print(f"Matches with real xG: {with_xg}/{len(match_list)}")

    team_map = {t["id"]: t["abbr"] for t in data.get("realTeams", [])}
    # Supplement with teams from the matches file in case of any gap
    team_map.update({k: v for k, v in match_teams.items() if k not in team_map})

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

        # Resolve match and home/away info
        match = match_map.get(pc.get("realMatchId"))
        real_team_ids = match["realTeamIds"] if match else None

        xpts = estimate_xpts(
            position=position,
            lineup=lineup,
            team_id=pc["realTeamId"],
            match=match,
            real_team_ids=real_team_ids,
        )

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
            "xPts":        xpts,
        })

    pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    rows.sort(key=lambda r: (pos_order.get(r["position"], 9), -r["xPts"]))

    fieldnames = ["id", "name", "position", "team", "price",
                  "totalPoints", "form", "lastPoints", "lineup", "xPts"]
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
        print(f"\nTop {pos}:")
        for r in top:
            print(f"  {r['name']:<25} {r['team']}  £{r['price']}M  lineup={r['lineup']:<12} xPts={r['xPts']}")


if __name__ == "__main__":
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    default_json = os.path.join(script_dir, "..", "players.json")
    default_csv  = os.path.join(script_dir, "mm_players.csv")

    json_path = sys.argv[1] if len(sys.argv) > 1 else default_json
    csv_path  = sys.argv[2] if len(sys.argv) > 2 else default_csv

    load(json_path, csv_path)
