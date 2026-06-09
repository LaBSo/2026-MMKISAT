"""
Integer Linear Program to select the optimal 15-player squad and starting XI.

Constraints:
  - Exactly 2 GK, 5 DEF, 5 MID, 3 FWD in the squad
  - Exactly 15 players total
  - Budget cap
  - Country limit (depends on gameweek)
  - Starting XI: 1 GK, valid formation (DEF 3-5, MID 2-5, FWD 1-3)
  - Starting XI = 11 players
  - Captain must be in starting XI
"""

from typing import Optional
import pulp
from models import Player, Squad, FORMATIONS, SQUAD_SIZE, COUNTRY_LIMITS


def optimize_squad(
    players: list[Player],
    budget: float,
    gameweek: int,
    games_per_player: Optional[dict[str, int]] = None,  # player_id -> games in this round
    locked_ids: Optional[set[str]] = None,
    excluded_ids: Optional[set[str]] = None,
) -> Optional[Squad]:
    """
    Select the optimal 15-player squad maximising expected points in the starting XI.
    Returns a Squad or None if infeasible.
    """
    if games_per_player is None:
        games_per_player = {}
    if locked_ids is None:
        locked_ids = set()
    if excluded_ids is None:
        excluded_ids = set()

    country_limit = COUNTRY_LIMITS.get(gameweek, 3)
    available = [p for p in players if p.id not in excluded_ids]
    n = len(available)

    prob = pulp.LpProblem("MMFantasy_Squad", pulp.LpMaximize)

    # Binary variables: selected in squad, selected in starting XI
    squad_var = [pulp.LpVariable(f"squad_{i}", cat="Binary") for i in range(n)]
    start_var = [pulp.LpVariable(f"start_{i}", cat="Binary") for i in range(n)]
    captain_var = [pulp.LpVariable(f"cap_{i}", cat="Binary") for i in range(n)]

    # Formation selection: one formation among allowed
    formation_vars = [pulp.LpVariable(f"form_{j}", cat="Binary") for j in range(len(FORMATIONS))]
    prob += pulp.lpSum(formation_vars) == 1

    # Objective: maximise expected points of starting XI + captain bonus
    ep = [p.expected_points * games_per_player.get(p.id, 1) for p in available]
    prob += (
        pulp.lpSum(ep[i] * start_var[i] for i in range(n))
        + pulp.lpSum(ep[i] * captain_var[i] for i in range(n))  # captain gets double
    )

    # Budget
    prob += pulp.lpSum(available[i].price * squad_var[i] for i in range(n)) <= budget

    # Squad size by position
    for pos, count in SQUAD_SIZE.items():
        idx = [i for i, p in enumerate(available) if p.position == pos]
        prob += pulp.lpSum(squad_var[i] for i in idx) == count

    # Total squad = 15
    prob += pulp.lpSum(squad_var) == 15

    # Country limit
    teams = set(p.team for p in available)
    for team in teams:
        idx = [i for i, p in enumerate(available) if p.team == team]
        prob += pulp.lpSum(squad_var[i] for i in idx) <= country_limit

    # Starting XI is subset of squad
    for i in range(n):
        prob += start_var[i] <= squad_var[i]

    # Exactly 11 starters
    prob += pulp.lpSum(start_var) == 11

    # Exactly 1 GK in starting XI
    gk_idx = [i for i, p in enumerate(available) if p.position == "GK"]
    prob += pulp.lpSum(start_var[i] for i in gk_idx) == 1

    # Formation constraints: DEF/MID/FWD in starting XI
    def_idx = [i for i, p in enumerate(available) if p.position == "DEF"]
    mid_idx = [i for i, p in enumerate(available) if p.position == "MID"]
    fwd_idx = [i for i, p in enumerate(available) if p.position == "FWD"]

    M = 100  # big-M for formation linking

    for j, (d, m, f) in enumerate(FORMATIONS):
        prob += pulp.lpSum(start_var[i] for i in def_idx) >= d - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in def_idx) <= d + M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in mid_idx) >= m - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in mid_idx) <= m + M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in fwd_idx) >= f - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in fwd_idx) <= f + M * (1 - formation_vars[j])

    # Captain must be in starting XI, exactly one
    prob += pulp.lpSum(captain_var) == 1
    for i in range(n):
        prob += captain_var[i] <= start_var[i]

    # Locked players must be selected
    for pid in locked_ids:
        idx = [i for i, p in enumerate(available) if p.id == pid]
        for i in idx:
            prob += squad_var[i] == 1

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return None

    selected_idx = [i for i in range(n) if pulp.value(squad_var[i]) > 0.5]
    starting_idx = [i for i in range(n) if pulp.value(start_var[i]) > 0.5]
    cap_idx = next((i for i in range(n) if pulp.value(captain_var[i]) > 0.5), None)

    selected_players = [available[i] for i in selected_idx]
    starting_ids = [available[i].id for i in starting_idx]

    bench_players = [available[i] for i in selected_idx if i not in starting_idx]
    # Order bench: GK first, then rest by descending expected points
    bench_gk = [p for p in bench_players if p.position == "GK"]
    bench_outfield = sorted(
        [p for p in bench_players if p.position != "GK"],
        key=lambda p: -p.expected_points,
    )
    bench_ids = [p.id for p in bench_gk + bench_outfield]

    squad = Squad(
        players=selected_players,
        captain_id=available[cap_idx].id if cap_idx is not None else None,
        starting_ids=starting_ids,
        bench_ids=bench_ids,
    )

    # Set vice captain = highest EP starter excluding captain
    starters = squad.starting_xi()
    non_cap_starters = [p for p in starters if p.id != squad.captain_id]
    if non_cap_starters:
        squad.vice_captain_id = max(non_cap_starters, key=lambda p: p.expected_points).id

    return squad


def optimize_transfers(
    current_squad: Squad,
    all_players: list[Player],
    budget: float,
    gameweek: int,
    free_transfers: int,
    use_wildcard: bool = False,
    locked_ids: Optional[set[str]] = None,
    excluded_ids: Optional[set[str]] = None,
) -> tuple[Optional[Squad], int]:
    """
    Optimise transfers for next round.

    The transfer penalty is baked into the ILP objective so the solver
    genuinely weighs "is this player worth -4 pts to bring in?"

    Returns (new_squad, total_penalty_points).
    """
    if use_wildcard:
        # Unlimited free transfers — just optimise freely
        new_squad = optimize_squad(
            all_players, budget, gameweek,
            locked_ids=locked_ids, excluded_ids=excluded_ids,
        )
        return new_squad, 0

    if locked_ids is None:
        locked_ids = set()
    if excluded_ids is None:
        excluded_ids = set()

    TRANSFER_PENALTY = 4  # pts per extra transfer beyond free allowance

    current_ids = {p.id for p in current_squad.players}
    available = [p for p in all_players if p.id not in excluded_ids]
    n = len(available)
    country_limit = COUNTRY_LIMITS.get(gameweek, 3)

    prob = pulp.LpProblem("MMFantasy_Transfers", pulp.LpMaximize)

    squad_var   = [pulp.LpVariable(f"squad_{i}",  cat="Binary") for i in range(n)]
    start_var   = [pulp.LpVariable(f"start_{i}",  cat="Binary") for i in range(n)]
    captain_var = [pulp.LpVariable(f"cap_{i}",    cat="Binary") for i in range(n)]
    # 1 if this player is NOT in the current squad (i.e. a transfer in)
    new_var     = [pulp.LpVariable(f"new_{i}",    cat="Binary") for i in range(n)]
    # Number of extra transfers beyond the free allowance (continuous ≥ 0)
    extra_tx    = pulp.LpVariable("extra_tx", lowBound=0, cat="Continuous")

    formation_vars = [pulp.LpVariable(f"form_{j}", cat="Binary") for j in range(len(FORMATIONS))]
    prob += pulp.lpSum(formation_vars) == 1

    ep = [p.expected_points for p in available]

    # Objective: XI points + captain bonus − penalty for extra transfers
    prob += (
        pulp.lpSum(ep[i] * start_var[i]   for i in range(n))
        + pulp.lpSum(ep[i] * captain_var[i] for i in range(n))
        - TRANSFER_PENALTY * extra_tx
    )

    # Budget
    prob += pulp.lpSum(available[i].price * squad_var[i] for i in range(n)) <= budget

    # Squad size by position
    for pos, count in SQUAD_SIZE.items():
        idx = [i for i, p in enumerate(available) if p.position == pos]
        prob += pulp.lpSum(squad_var[i] for i in idx) == count

    prob += pulp.lpSum(squad_var) == 15

    # Country limit
    for team in set(p.team for p in available):
        idx = [i for i, p in enumerate(available) if p.team == team]
        prob += pulp.lpSum(squad_var[i] for i in idx) <= country_limit

    # Starting XI
    for i in range(n):
        prob += start_var[i] <= squad_var[i]
    prob += pulp.lpSum(start_var) == 11

    gk_idx  = [i for i, p in enumerate(available) if p.position == "GK"]
    def_idx = [i for i, p in enumerate(available) if p.position == "DEF"]
    mid_idx = [i for i, p in enumerate(available) if p.position == "MID"]
    fwd_idx = [i for i, p in enumerate(available) if p.position == "FWD"]
    prob += pulp.lpSum(start_var[i] for i in gk_idx) == 1

    M = 100
    for j, (d, m, f) in enumerate(FORMATIONS):
        prob += pulp.lpSum(start_var[i] for i in def_idx) >= d - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in def_idx) <= d + M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in mid_idx) >= m - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in mid_idx) <= m + M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in fwd_idx) >= f - M * (1 - formation_vars[j])
        prob += pulp.lpSum(start_var[i] for i in fwd_idx) <= f + M * (1 - formation_vars[j])

    # Captain
    prob += pulp.lpSum(captain_var) == 1
    for i in range(n):
        prob += captain_var[i] <= start_var[i]

    # Locked players
    for pid in locked_ids:
        for i, p in enumerate(available):
            if p.id == pid:
                prob += squad_var[i] == 1

    # Transfer counting:
    # new_var[i] = 1 if squad_var[i]=1 AND player was NOT in current squad
    for i, p in enumerate(available):
        if p.id in current_ids:
            prob += new_var[i] == 0          # already owned — not a new transfer
        else:
            prob += new_var[i] >= squad_var[i] - 0  # new_var[i] = squad_var[i] for non-owned
            prob += new_var[i] <= squad_var[i]

    # extra_tx ≥ transfers_in − free_transfers
    prob += extra_tx >= pulp.lpSum(new_var) - free_transfers

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return None, 0

    selected_idx = [i for i in range(n) if pulp.value(squad_var[i]) > 0.5]
    starting_idx = [i for i in range(n) if pulp.value(start_var[i]) > 0.5]
    cap_idx      = next((i for i in range(n) if pulp.value(captain_var[i]) > 0.5), None)
    transfers_in = int(round(pulp.value(pulp.lpSum(new_var))))
    extra        = int(round(pulp.value(extra_tx)))
    penalty      = extra * -TRANSFER_PENALTY

    selected_players = [available[i] for i in selected_idx]
    starting_ids     = [available[i].id for i in starting_idx]
    bench_players    = [available[i] for i in selected_idx if i not in starting_idx]
    bench_gk         = [p for p in bench_players if p.position == "GK"]
    bench_outfield   = sorted(
        [p for p in bench_players if p.position != "GK"],
        key=lambda p: -p.expected_points,
    )
    bench_ids = [p.id for p in bench_gk + bench_outfield]

    squad = Squad(
        players=selected_players,
        captain_id=available[cap_idx].id if cap_idx is not None else None,
        starting_ids=starting_ids,
        bench_ids=bench_ids,
    )
    starters = squad.starting_xi()
    non_cap  = [p for p in starters if p.id != squad.captain_id]
    if non_cap:
        squad.vice_captain_id = max(non_cap, key=lambda p: p.expected_points).id

    return squad, penalty
