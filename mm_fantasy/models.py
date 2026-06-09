from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Player:
    id: str
    name: str
    team: str          # country code e.g. "FIN"
    position: str      # GK, DEF, MID, FWD
    price: float       # in millions
    expected_points: float = 0.0
    total_points: int = 0
    form: float = 0.0  # recent avg points
    # raw stats for scoring model
    goals: int = 0
    assists: int = 0
    clean_sheets: int = 0
    saves: int = 0
    minutes: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    shots_on_target: int = 0
    image_url: Optional[str] = None


@dataclass
class Squad:
    players: list[Player] = field(default_factory=list)
    captain_id: Optional[str] = None
    vice_captain_id: Optional[str] = None
    # starting XI ids (11 players)
    starting_ids: list[str] = field(default_factory=list)
    # bench order: [backup_gk, sub1, sub2, sub3]
    bench_ids: list[str] = field(default_factory=list)

    def starting_xi(self) -> list[Player]:
        ids = set(self.starting_ids)
        return [p for p in self.players if p.id in ids]

    def bench(self) -> list[Player]:
        id_order = {pid: i for i, pid in enumerate(self.bench_ids)}
        bench_players = [p for p in self.players if p.id in id_order]
        return sorted(bench_players, key=lambda p: id_order[p.id])

    @property
    def total_price(self) -> float:
        return sum(p.price for p in self.players)

    @property
    def total_expected_points(self) -> float:
        pts = sum(p.expected_points for p in self.starting_xi())
        cap = next((p for p in self.players if p.id == self.captain_id), None)
        if cap:
            pts += cap.expected_points  # double captain
        return pts


POSITIONS = ["GK", "DEF", "MID", "FWD"]

FORMATIONS = [
    (3, 4, 3),
    (3, 5, 2),
    (4, 5, 1),
    (4, 4, 2),
    (4, 3, 3),
    (5, 4, 1),
    (5, 3, 2),
    (5, 2, 3),
]

SQUAD_SIZE = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}

# max players from same country per gameweek
COUNTRY_LIMITS = {
    1: 3, 2: 3, 3: 3, 4: 3,
    5: 4, 6: 4,
    7: 6,
    8: 8,
}

FREE_TRANSFERS = {
    1: 0,   # initial team selection
    2: 2, 3: 2, 4: 2,
    5: 4, 6: 4, 7: 4, 8: 4,
}

TRANSFER_PENALTY = -4  # per extra transfer

GAMEWEEKS = [
    {"round": 1, "name": "Group Stage Round 1", "dates": "11–18 Jun"},
    {"round": 2, "name": "Group Stage Round 2", "dates": "18–24 Jun"},
    {"round": 3, "name": "Group Stage Round 3", "dates": "24–28 Jun"},
    {"round": 4, "name": "Round of 32", "dates": "28 Jun – 4 Jul"},
    {"round": 5, "name": "Round of 16", "dates": "4–7 Jul"},
    {"round": 6, "name": "Quarter-finals", "dates": "9–12 Jul"},
    {"round": 7, "name": "Semi-finals", "dates": "14–15 Jul"},
    {"round": 8, "name": "Final", "dates": "19 Jul"},
]
