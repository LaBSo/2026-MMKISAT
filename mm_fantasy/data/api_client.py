"""
Fetches player stats from football-data.org (free tier).
Falls back to sample data if API key not set.
"""

import os
import requests
from models import Player

API_BASE = "https://api.football-data.org/v4"
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")

HEADERS = {"X-Auth-Token": API_KEY}

# FIFA WC 2026 competition id (update when known; 2018=467, 2022=2000)
WC_2026_ID = 2000  # placeholder — update when football-data.org lists 2026


def get_competition_teams() -> list[dict]:
    """Return list of teams in the competition."""
    if not API_KEY:
        return []
    url = f"{API_BASE}/competitions/{WC_2026_ID}/teams"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("teams", [])


def get_squad_players(team_id: int) -> list[dict]:
    """Return raw squad members for a team."""
    if not API_KEY:
        return []
    url = f"{API_BASE}/teams/{team_id}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("squad", [])


def position_map(raw: str) -> str:
    mapping = {
        "Goalkeeper": "GK",
        "Centre-Back": "DEF",
        "Left-Back": "DEF",
        "Right-Back": "DEF",
        "Defensive Midfield": "MID",
        "Central Midfield": "MID",
        "Attacking Midfield": "MID",
        "Left Midfield": "MID",
        "Right Midfield": "MID",
        "Left Winger": "MID",
        "Right Winger": "MID",
        "Centre-Forward": "FWD",
        "Second Striker": "FWD",
    }
    return mapping.get(raw, "MID")


def fetch_all_players() -> list[Player]:
    """Fetch all WC squads and return Player objects with zeroed stats."""
    teams = get_competition_teams()
    players: list[Player] = []
    seen: set[str] = set()

    for team in teams:
        team_code = team.get("tla", team.get("shortName", "UNK"))[:3].upper()
        for member in get_squad_players(team["id"]):
            pid = str(member["id"])
            if pid in seen:
                continue
            seen.add(pid)
            players.append(
                Player(
                    id=pid,
                    name=member.get("name", "Unknown"),
                    team=team_code,
                    position=position_map(member.get("position", "")),
                    price=5.0,  # placeholder — override with scraped prices
                )
            )

    return players
