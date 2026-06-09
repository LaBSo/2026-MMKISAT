import sys
import os
import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.express as px

from models import Player, Squad, GAMEWEEKS, FREE_TRANSFERS, COUNTRY_LIMITS
from optimizer import optimize_squad, optimize_transfers
from scoring import estimate_points_per_game, points_value_ratio
from data.sample_data import SAMPLE_PLAYERS

# ── Country info: flag emojis + Finnish names ────────────────────────────────
# Keys are the FIFA 3-letter abbreviations used in the game data.

TEAM_INFO: dict[str, tuple[str, str]] = {
    # abbr : (flag_emoji, finnish_name)
    "ARG": ("🇦🇷", "Argentiina"),
    "AUT": ("🇦🇹", "Itävalta"),
    "DZA": ("🇩🇿", "Algeria"),
    "JOR": ("🇯🇴", "Jordania"),
    "AUS": ("🇦🇺", "Australia"),
    "PRY": ("🇵🇾", "Paraguay"),
    "TUR": ("🇹🇷", "Turkki"),
    "USA": ("🇺🇸", "Yhdysvallat"),
    "BEL": ("🇧🇪", "Belgia"),
    "EGY": ("🇪🇬", "Egypti"),
    "IRN": ("🇮🇷", "Iran"),
    "NZL": ("🇳🇿", "Uusi-Seelanti"),
    "BIH": ("🇧🇦", "Bosnia-Hertsegovina"),
    "CAN": ("🇨🇦", "Kanada"),
    "QAT": ("🇶🇦", "Qatar"),
    "SUI": ("🇨🇭", "Sveitsi"),
    "BRA": ("🇧🇷", "Brasilia"),
    "HTI": ("🇭🇹", "Haiti"),
    "MAR": ("🇲🇦", "Marokko"),
    "SCO": ("🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Skotlanti"),
    "CIV": ("🇨🇮", "Norsunluurannikko"),
    "CUW": ("🇨🇼", "Curaçao"),
    "ECU": ("🇪🇨", "Ecuador"),
    "GER": ("🇩🇪", "Saksa"),
    "COD": ("🇨🇩", "Kongon dem. tasavalta"),
    "COL": ("🇨🇴", "Kolumbia"),
    "POR": ("🇵🇹", "Portugali"),
    "UZB": ("🇺🇿", "Uzbekistan"),
    "CPV": ("🇨🇻", "Kap Verde"),
    "ESP": ("🇪🇸", "Espanja"),
    "KSA": ("🇸🇦", "Saudi-Arabia"),
    "URU": ("🇺🇾", "Uruguay"),
    "CRO": ("🇭🇷", "Kroatia"),
    "ENG": ("🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Englanti"),
    "GHA": ("🇬🇭", "Ghana"),
    "PAN": ("🇵🇦", "Panama"),
    "CZE": ("🇨🇿", "Tšekki"),
    "KOR": ("🇰🇷", "Etelä-Korea"),
    "MEX": ("🇲🇽", "Meksiko"),
    "ZAF": ("🇿🇦", "Etelä-Afrikka"),
    "FRA": ("🇫🇷", "Ranska"),
    "IRQ": ("🇮🇶", "Irak"),
    "NOR": ("🇳🇴", "Norja"),
    "SEN": ("🇸🇳", "Senegal"),
    "JPN": ("🇯🇵", "Japani"),
    "NED": ("🇳🇱", "Alankomaat"),
    "SWE": ("🇸🇪", "Ruotsi"),
    "TUN": ("🇹🇳", "Tunisia"),
}

def team_flag(abbr: str) -> str:
    """Return the flag emoji for a team abbreviation, or '' if unknown."""
    return TEAM_INFO.get(abbr, ("", abbr))[0]

def team_name(abbr: str) -> str:
    """Return the Finnish country name, falling back to the abbreviation."""
    return TEAM_INFO.get(abbr, ("", abbr))[1]

def team_display(abbr: str) -> str:
    """Return 'flag Finnish-name' for display in tables (e.g. '🇩🇪 Saksa')."""
    info = TEAM_INFO.get(abbr)
    if info:
        return f"{info[0]} {info[1]}"
    return abbr

def team_short(abbr: str) -> str:
    """Return 'flag ABBR' for compact display (e.g. '🇩🇪 GER')."""
    info = TEAM_INFO.get(abbr)
    if info:
        return f"{info[0]} {abbr}"
    return abbr


# ── Match & group data (loaded once at startup) ──────────────────────────────

def _parse_odd(val, default=3.0):
    """Parse odds value: handles string, float, or {'default': n} dict."""
    if isinstance(val, dict):
        val = val.get("default", default)
    try:
        v = float(val)
        return v if v > 1.0 else default
    except (TypeError, ValueError):
        return default

@st.cache_data
def load_match_data():
    """Load real_matches.json, derive groups, return (match_df, group_map)."""
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    matches_path = os.path.join(script_dir, "..", "real_matches.json")
    players_path = os.path.join(script_dir, "..", "players.json")

    if os.path.exists(matches_path):
        with open(matches_path, encoding="utf-8") as f:
            d = json.load(f)
    elif os.path.exists(players_path):
        with open(players_path, encoding="utf-8") as f:
            d = json.load(f)
    else:
        return pd.DataFrame(), {}

    rt_map = {t["id"]: t.get("abbr", t.get("name", "?")) for t in d.get("realTeams", [])}

    # Real national teams only (exclude knockout placeholders like "1st Group A")
    real_team_abbrs = {
        v for v in rt_map.values()
        if not any(v.startswith(p) for p in ("1st", "2nd", "3rd", "Win", "Los", "Qual"))
        and len(v) <= 5
    }

    # Derive groups via union-find on GW1-3 matches
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    def union(a, b): parent[find(a)] = find(b)

    for m in d.get("realMatches", []):
        if m.get("gameweek", 99) <= 3:
            teams = [rt_map.get(tid, "") for tid in m.get("realTeamIds", [])]
            if len(teams) == 2 and all(t in real_team_abbrs for t in teams):
                union(teams[0], teams[1])

    groups_raw = defaultdict(set)
    for t in real_team_abbrs:
        groups_raw[find(t)].add(t)

    sorted_groups = sorted(groups_raw.values(), key=lambda g: sorted(g)[0])
    letters = "ABCDEFGHIJKL"
    group_map = {}  # abbr -> "Group X"
    for i, grp in enumerate(sorted_groups):
        label = f"Group {letters[i]}" if i < len(letters) else f"Group {i+1}"
        for team in grp:
            group_map[team] = label

    # Stage labels by GW
    stage_map = {1: "Group Stage R1", 2: "Group Stage R2", 3: "Group Stage R3",
                 4: "Round of 32", 5: "Round of 16", 6: "Quarter-finals",
                 7: "Semi-finals", 8: "Final"}

    rows = []
    for m in d.get("realMatches", []):
        details = m.get("details", {})
        odds    = details.get("odds", {})
        xg      = details.get("expectedGoals", [0, 0])
        score   = m.get("score", [0, 0])
        tids    = m.get("realTeamIds", [])
        home_abbr = rt_map.get(tids[0], "?") if len(tids) > 0 else "?"
        away_abbr = rt_map.get(tids[1], "?") if len(tids) > 1 else "?"

        h_o  = _parse_odd(odds.get("home"), 3.0)
        d_o  = _parse_odd(odds.get("draw"), 3.0)
        a_o  = _parse_odd(odds.get("away"), 3.0)
        ov_o = _parse_odd(odds.get("over"), 0.0)
        un_o = _parse_odd(odds.get("under"), 0.0)
        ou_line = _parse_odd(odds.get("score"), 2.5)

        try:
            total = 1/h_o + 1/d_o + 1/a_o
            p_home = round((1/h_o) / total * 100, 1)
            p_draw = round((1/d_o) / total * 100, 1)
            p_away = round((1/a_o) / total * 100, 1)
        except ZeroDivisionError:
            p_home = p_draw = p_away = 33.3

        has_odds = not (h_o == 3.0 and d_o == 3.0 and a_o == 3.0)
        xg_home  = float(xg[0]) if xg and len(xg) > 0 else 0.0
        xg_away  = float(xg[1]) if xg and len(xg) > 1 else 0.0
        has_xg   = xg_home > 0 or xg_away > 0
        cs_home  = round(math.exp(-xg_away) * 100, 1) if xg_away > 0 else None
        cs_away  = round(math.exp(-xg_home) * 100, 1) if xg_home > 0 else None

        gw = m.get("gameweek", 0)
        start_raw = m.get("startTime", "")
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            dt_hki = dt.astimezone(timezone(timedelta(hours=3)))
            kickoff = dt_hki.strftime("%d %b %H:%M")
        except Exception:
            kickoff = start_raw[:16] if start_raw else "—"

        grp_label = group_map.get(home_abbr) or group_map.get(away_abbr) or stage_map.get(gw, f"GW{gw}")

        rows.append({
            "GW":         gw,
            "Stage":      stage_map.get(gw, f"GW{gw}"),
            "Group":      grp_label,
            "Kickoff":    kickoff,
            "Home":       home_abbr,
            "Away":       away_abbr,
            "Home 🏳":    team_short(home_abbr),
            "Away 🏳":    team_short(away_abbr),
            "Status":   m.get("status", "pending"),
            "Score":    f"{score[0]}–{score[1]}" if m.get("status") not in ("pending", "not_started") else "–",
            "H odds":   h_o,
            "D odds":   d_o,
            "A odds":   a_o,
            "P(H) %":   p_home,
            "P(D) %":   p_draw,
            "P(A) %":   p_away,
            "xG Home":  xg_home if has_xg else None,
            "xG Away":  xg_away if has_xg else None,
            "CS% Home": cs_home,
            "CS% Away": cs_away,
            "O/U line": ou_line if ov_o > 0 else None,
            "Over":     ov_o if ov_o > 0 else None,
            "Under":    un_o if un_o > 0 else None,
            "_has_odds": has_odds,
            "_has_xg":   has_xg,
        })

    return pd.DataFrame(rows), group_map

st.set_page_config(
    page_title="MM Fantasy Optimizer",
    page_icon="⚽",
    layout="wide",
)

# ── Session state defaults ──────────────────────────────────────────────────

def _load_csv(path) -> list[Player]:
    df = pd.read_csv(path)
    players = []
    for _, row in df.iterrows():
        p = Player(
            id=str(row["id"]),
            name=str(row["name"]),
            position=str(row["position"]),
            team=str(row["team"]),
            price=float(row["price"]),
            total_points=int(row.get("totalPoints", 0) or 0),
            form=float(row.get("form", 0) or 0),
        )
        last_pts  = float(row.get("lastPoints", 0) or 0)
        xpts      = float(row.get("xPts", 0) or 0)
        # Priority: model xPts > last round pts > form > price proxy
        p.expected_points = (
            xpts      if xpts > 0 else
            last_pts  if last_pts > 0 else
            p.form    if p.form > 0 else
            max(1.0, p.price * 0.6)
        )
        p.lineup = str(row.get("lineup", "unknown"))
        players.append(p)
    return players

if "players" not in st.session_state:
    _default_csv = os.path.join(os.path.dirname(__file__), "mm_players.csv")
    if os.path.exists(_default_csv):
        st.session_state.players = _load_csv(_default_csv)
    else:
        for p in SAMPLE_PLAYERS:
            p.expected_points = estimate_points_per_game(p)
        st.session_state.players = SAMPLE_PLAYERS

if "current_squad" not in st.session_state:
    st.session_state.current_squad = None

if "wildcard_used" not in st.session_state:
    st.session_state.wildcard_used = False

# ── Helpers ─────────────────────────────────────────────────────────────────

POS_ORDER = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
POS_COLOR = {"GK": "#f0c040", "DEF": "#4caf50", "MID": "#2196f3", "FWD": "#f44336"}


def player_df(players: list[Player]) -> pd.DataFrame:
    _, grp_map = load_match_data()
    rows = []
    for p in players:
        rows.append({
            "ID": p.id,
            "Name": p.name,
            "Joukkue": team_display(p.team),   # flag + Finnish name
            "Lyhenne": team_short(p.team),      # flag + 3-letter code (for compact views)
            "Team": p.team,                     # raw abbr for internal use
            "Group": grp_map.get(p.team, "—"),
            "Pos": p.position,
            "Lineup": getattr(p, "lineup", "—"),
            "Price (M)": p.price,
            "xPts": round(p.expected_points, 1),
            "Pts/M": round(points_value_ratio(p), 2),
        })
    return pd.DataFrame(rows).sort_values(["Pos", "xPts"], key=lambda s: s.map(POS_ORDER) if s.name == "Pos" else -s)


def squad_table(squad: Squad) -> pd.DataFrame:
    rows = []
    starters = {p.id for p in squad.starting_xi()}
    for p in squad.players:
        role = ""
        if p.id == squad.captain_id:
            role = "C"
        elif p.id == squad.vice_captain_id:
            role = "VC"
        rows.append({
            "Name": p.name,
            "Team": p.team,
            "Pos": p.position,
            "Price": p.price,
            "xPts": round(p.expected_points, 1),
            "Role": role,
            "Status": "Starter" if p.id in starters else "Bench",
        })
    df = pd.DataFrame(rows)
    df = df.sort_values(["Status", "Pos"], key=lambda s: (
        s.map({"Starter": 0, "Bench": 1}) if s.name == "Status" else s.map(POS_ORDER)
    ))
    return df


def display_squad_pitch(squad: Squad):
    """Visual pitch layout."""
    starters = squad.starting_xi()
    by_pos: dict[str, list[Player]] = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in starters:
        by_pos[p.position].append(p)

    for pos in ["FWD", "MID", "DEF", "GK"]:
        cols = st.columns(max(len(by_pos[pos]), 1))
        for col, p in zip(cols, by_pos[pos]):
            cap_label = " ★C" if p.id == squad.captain_id else (" ★VC" if p.id == squad.vice_captain_id else "")
            col.markdown(
                f"""<div style="background:{POS_COLOR[p.position]};border-radius:8px;
                    padding:6px 4px;text-align:center;font-size:12px;color:#fff;margin:2px">
                    <b>{p.name}{cap_label}</b><br>{p.team} · £{p.price}M<br>
                    <span style="font-size:14px">{p.expected_points:.1f} xPts</span>
                </div>""",
                unsafe_allow_html=True,
            )


# ── Sidebar ──────────────────────────────────────────────────────────────────

def load_players_from_csv(uploaded_file) -> list[Player]:
    return _load_csv(uploaded_file)


with st.sidebar:
    st.title("⚽ MM Fantasy")

    st.subheader("Player Data")
    uploaded = st.file_uploader("Upload mm_players.csv", type="csv", help="Run scraper_console.js in your browser, then upload the downloaded CSV here.")
    if uploaded:
        loaded = load_players_from_csv(uploaded)
        if loaded:
            st.session_state.players = loaded
            st.session_state.current_squad = None
            st.success(f"Loaded {len(loaded)} players from CSV")

    st.markdown("---")
    st.subheader("Settings")

    budget = st.number_input("Budget (M€)", min_value=50.0, max_value=200.0, value=100.0, step=0.5)
    gameweek = st.selectbox(
        "Gameweek",
        options=[gw["round"] for gw in GAMEWEEKS],
        format_func=lambda r: f"GW{r}: {next(g['name'] for g in GAMEWEEKS if g['round'] == r)}",
    )

    country_limit = COUNTRY_LIMITS.get(gameweek, 3)
    st.info(f"Max players per country: **{country_limit}**")

    free_tx = FREE_TRANSFERS.get(gameweek, 0)
    st.info(f"Free transfers this round: **{free_tx}**")

    use_wildcard = st.checkbox(
        "Use Wildcard",
        value=False,
        disabled=st.session_state.wildcard_used,
        help="Unlimited free transfers for this round",
    )

    st.markdown("---")
    st.subheader("Lock / Exclude players")
    all_names = [p.name for p in st.session_state.players]
    locked_names = st.multiselect("Lock in squad", all_names)
    excluded_names = st.multiselect("Exclude from squad", all_names)

    locked_ids = {p.id for p in st.session_state.players if p.name in locked_names}
    excluded_ids = {p.id for p in st.session_state.players if p.name in excluded_names}

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_optimize, tab_mysquad, tab_players, tab_schedule, tab_transfers, tab_rules = st.tabs(
    ["🏆 Optimize", "👤 My Squad", "📋 Players", "📅 Schedule", "🔄 Transfers", "📖 Rules"]
)

# ═══════════════════════════════════════════════════════
# TAB 1: OPTIMIZE
# ═══════════════════════════════════════════════════════
with tab_optimize:
    st.header(f"Optimal Squad — GW{gameweek}")

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🚀 Run Optimizer", type="primary", use_container_width=True):
            with st.spinner("Solving..."):
                squad = optimize_squad(
                    players=st.session_state.players,
                    budget=budget,
                    gameweek=gameweek,
                    locked_ids=locked_ids,
                    excluded_ids=excluded_ids,
                )
            if squad is None:
                st.error("No valid squad found — try relaxing constraints or increasing budget.")
            else:
                st.session_state.current_squad = squad
                st.success(f"Squad found! Total cost: £{squad.total_price:.1f}M | xPts: {squad.total_expected_points:.1f}")

    if st.session_state.current_squad:
        squad = st.session_state.current_squad

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Cost", f"£{squad.total_price:.1f}M", delta=f"{budget - squad.total_price:.1f}M left")
        col_b.metric("Expected Points", f"{squad.total_expected_points:.1f}")
        cap = next((p for p in squad.players if p.id == squad.captain_id), None)
        col_c.metric("Captain", cap.name if cap else "—", delta=f"2× {cap.expected_points:.1f} = {cap.expected_points*2:.1f} pts" if cap else "")

        st.markdown("#### Pitch View")
        display_squad_pitch(squad)

        st.markdown("#### Full Squad")
        df = squad_table(squad)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="£%.1fM"),
                "xPts": st.column_config.NumberColumn("xPts"),
                "Status": st.column_config.TextColumn("Status"),
            },
        )

        # Formation breakdown
        starters = squad.starting_xi()
        def_count = sum(1 for p in starters if p.position == "DEF")
        mid_count = sum(1 for p in starters if p.position == "MID")
        fwd_count = sum(1 for p in starters if p.position == "FWD")
        st.caption(f"Formation: 1-{def_count}-{mid_count}-{fwd_count}")

# ═══════════════════════════════════════════════════════
# TAB 2: PLAYERS
# ═══════════════════════════════════════════════════════
with tab_players:
    st.header("Player Database")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        pos_filter = st.multiselect("Position", ["GK", "DEF", "MID", "FWD"], default=["GK", "DEF", "MID", "FWD"])
    with col_f2:
        max_price = st.slider("Max price (M€)", 4.0, 15.0, 15.0, 0.5)
    with col_f3:
        sort_by = st.selectbox("Sort by", ["xPts", "Price (M)", "Pts/M", "Name"])
    with col_f4:
        _, _pgrp_map = load_match_data()
        grp_labels = sorted({v for v in _pgrp_map.values()})
        group_filter_p = st.multiselect("Group", grp_labels, key="players_group_filter")

    df_all = player_df(st.session_state.players)
    df_filtered = df_all[
        (df_all["Pos"].isin(pos_filter)) &
        (df_all["Price (M)"] <= max_price)
    ]
    if group_filter_p:
        df_filtered = df_filtered[df_filtered["Group"].isin(group_filter_p)]
    df_filtered = df_filtered.sort_values(sort_by, ascending=(sort_by == "Name"))

    st.dataframe(
        df_filtered.drop(columns=["ID", "Team", "Lyhenne"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Joukkue": st.column_config.TextColumn("Joukkue"),
            "Group": st.column_config.TextColumn("Lohko"),
            "Pos": st.column_config.TextColumn("Pelipaikka"),
            "Lineup": st.column_config.TextColumn(
                "Kokoonpano",
                help=(
                    "Pelaajan todennäköinen aloitusasema joukkueessa:\n"
                    "• expected — todennäköinen aloittaja (82 % pelaa)\n"
                    "• possible — kiertopelissä / epävarma (50 %)\n"
                    "• unexpected — vaihtopelaaja (12 %)\n"
                    "• injured — loukkaantunut (2 %)"
                ),
            ),
            "Price (M)": st.column_config.NumberColumn(
                "Hinta (M€)",
                format="£%.1fM",
                help="Pelaajan hinta miljoonissa euroissa. Budjetti on 110 M€ 15 pelaajalle.",
            ),
            "xPts": st.column_config.NumberColumn(
                "Odotetut pisteet",
                help=(
                    "Mallin ennustama pistemäärä ennen ottelua.\n"
                    "Laskettu: kokoonpanotodennäköisyys × veikkauskerroin × xG-data (Poisson).\n"
                    "Maalivahti/puolustaja saa lisää CS%-bonuksesta."
                ),
            ),
            "Pts/M": st.column_config.NumberColumn(
                "Pisteet / £M",
                help="Odotetut pisteet jaettuna hinnalla — mittaa pelaajan arvo-hinta-suhdetta. Korkeampi = parempi arvo.",
            ),
        },
    )

    st.markdown("#### Expected Points Distribution")
    fig = px.scatter(
        df_all,
        x="Price (M)", y="xPts",
        color="Pos", text="Name",
        color_discrete_map={"GK": "#f0c040", "DEF": "#4caf50", "MID": "#2196f3", "FWD": "#f44336"},
        size_max=10,
    )
    fig.update_traces(textposition="top center", textfont_size=9)
    fig.update_layout(height=450, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Points per £M (value chart)")
    df_val = df_all.copy().sort_values("Pts/M", ascending=False).head(30)
    fig2 = px.bar(
        df_val, x="Name", y="Pts/M", color="Pos",
        color_discrete_map={"GK": "#f0c040", "DEF": "#4caf50", "MID": "#2196f3", "FWD": "#f44336"},
    )
    fig2.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)

# ═══════════════════════════════════════════════════════
# TAB 2: MY SQUAD
# ═══════════════════════════════════════════════════════
with tab_mysquad:
    st.header("Enter My Current Squad")
    st.caption("Select the 15 players you have already picked in the game. This sets your squad so the Transfer Planner can suggest optimal swaps.")

    players_by_pos = {
        "GK":  sorted([p for p in st.session_state.players if p.position == "GK"],  key=lambda p: p.name),
        "DEF": sorted([p for p in st.session_state.players if p.position == "DEF"], key=lambda p: p.name),
        "MID": sorted([p for p in st.session_state.players if p.position == "MID"], key=lambda p: p.name),
        "FWD": sorted([p for p in st.session_state.players if p.position == "FWD"], key=lambda p: p.name),
    }

    def _player_label(p):
        return f"{p.name} ({p.team}, £{p.price}M, xPts {p.expected_points:.1f})"

    def _options(pos):
        return {_player_label(p): p for p in players_by_pos[pos]}

    col_gk, col_def = st.columns(2)
    with col_gk:
        st.subheader("Goalkeepers (pick 2)")
        gk_opts = _options("GK")
        gk_sel  = st.multiselect("GK", list(gk_opts), max_selections=2, label_visibility="collapsed",
                                 key="mysquad_gk")
    with col_def:
        st.subheader("Defenders (pick 5)")
        def_opts = _options("DEF")
        def_sel  = st.multiselect("DEF", list(def_opts), max_selections=5, label_visibility="collapsed",
                                  key="mysquad_def")

    col_mid, col_fwd = st.columns(2)
    with col_mid:
        st.subheader("Midfielders (pick 5)")
        mid_opts = _options("MID")
        mid_sel  = st.multiselect("MID", list(mid_opts), max_selections=5, label_visibility="collapsed",
                                  key="mysquad_mid")
    with col_fwd:
        st.subheader("Forwards (pick 3)")
        fwd_opts = _options("FWD")
        fwd_sel  = st.multiselect("FWD", list(fwd_opts), max_selections=3, label_visibility="collapsed",
                                  key="mysquad_fwd")

    all_sel = gk_sel + def_sel + mid_sel + fwd_sel
    n_sel   = len(all_sel)
    total_cost = sum(
        p.price for label, p in
        {**gk_opts, **def_opts, **mid_opts, **fwd_opts}.items()
        if label in all_sel
    )

    st.markdown("---")
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        status_color = "green" if n_sel == 15 else "orange"
        st.markdown(
            f"**Selected:** <span style='color:{status_color};font-size:18px'>{n_sel}/15</span> &nbsp;&nbsp; "
            f"**Cost:** £{total_cost:.1f}M",
            unsafe_allow_html=True,
        )
        if len(gk_sel) != 2:  st.warning(f"Need exactly 2 GK (have {len(gk_sel)})")
        if len(def_sel) != 5: st.warning(f"Need exactly 5 DEF (have {len(def_sel)})")
        if len(mid_sel) != 5: st.warning(f"Need exactly 5 MID (have {len(mid_sel)})")
        if len(fwd_sel) != 3: st.warning(f"Need exactly 3 FWD (have {len(fwd_sel)})")

    with col_btn:
        save_disabled = n_sel != 15
        if st.button("Set as My Squad", type="primary", disabled=save_disabled, use_container_width=True):
            all_opts = {**gk_opts, **def_opts, **mid_opts, **fwd_opts}
            chosen_players = [all_opts[label] for label in all_sel]

            # Build a Squad object — let optimizer pick best XI and captain from these 15
            from optimizer import optimize_squad as _opt
            # Pass only the chosen 15; lock all of them so the optimizer just picks XI/captain
            chosen_ids = {p.id for p in chosen_players}
            mini_squad = _opt(
                players=chosen_players,
                budget=total_cost + 0.1,   # tiny slack so budget constraint passes
                gameweek=gameweek,
                locked_ids=chosen_ids,
            )
            if mini_squad:
                st.session_state.current_squad = mini_squad
                st.success("Squad saved! Go to Transfer Planner to plan your next round.")
            else:
                # Fallback: build squad manually with a simple XI guess
                import models as _m
                starters = []
                bench    = []
                gks  = [p for p in chosen_players if p.position == "GK"]
                defs = sorted([p for p in chosen_players if p.position == "DEF"], key=lambda p: -p.expected_points)
                mids = sorted([p for p in chosen_players if p.position == "MID"], key=lambda p: -p.expected_points)
                fwds = sorted([p for p in chosen_players if p.position == "FWD"], key=lambda p: -p.expected_points)
                starters = [gks[0]] + defs[:4] + mids[:4] + fwds[:2]
                bench    = [gks[1]] + defs[4:] + mids[4:] + fwds[2:]
                captain  = max(starters, key=lambda p: p.expected_points)
                vc       = max([p for p in starters if p.id != captain.id], key=lambda p: p.expected_points)
                sq = _m.Squad(
                    players=chosen_players,
                    captain_id=captain.id,
                    starting_ids=[p.id for p in starters],
                    bench_ids=[p.id for p in bench],
                )
                sq.vice_captain_id = vc.id
                st.session_state.current_squad = sq
                st.success("Squad saved! Go to Transfer Planner to plan your next round.")

    # Preview if squad is set
    if st.session_state.current_squad and n_sel == 15:
        sq = st.session_state.current_squad
        chosen_ids_preview = {
            p.id for label, p in {**gk_opts, **def_opts, **mid_opts, **fwd_opts}.items()
            if label in all_sel
        }
        # Only show preview if the current squad matches what's selected
        if {p.id for p in sq.players} == chosen_ids_preview:
            st.markdown("#### Best XI from your selection")
            display_squad_pitch(sq)
            cap = next((p for p in sq.players if p.id == sq.captain_id), None)
            st.caption(f"Captain: {cap.name} | Total xPts: {sq.total_expected_points:.1f}")

    st.markdown("---")
    st.subheader("Best available picks for remaining slots")
    st.caption("Players not yet in your squad, ranked by xPts — useful when filling the last few spots.")

    selected_ids_now = set()
    all_opts_now = {**gk_opts, **def_opts, **mid_opts, **fwd_opts}
    for label in all_sel:
        if label in all_opts_now:
            selected_ids_now.add(all_opts_now[label].id)

    remaining_budget = 110.0 - total_cost
    not_picked = [p for p in st.session_state.players if p.id not in selected_ids_now]

    # Show best affordable remaining per position
    slots = {"GK": 2 - len(gk_sel), "DEF": 5 - len(def_sel), "MID": 5 - len(mid_sel), "FWD": 3 - len(fwd_sel)}
    for pos, slots_left in slots.items():
        if slots_left <= 0:
            continue
        candidates = sorted(
            [p for p in not_picked if p.position == pos and p.price <= remaining_budget],
            key=lambda p: -p.expected_points,
        )[:10]
        if candidates:
            st.markdown(f"**{pos}** — {slots_left} slot(s) left, budget remaining £{remaining_budget:.1f}M")
            rows = [{"Name": p.name, "Team": p.team, "Price": p.price,
                     "xPts": p.expected_points, "Lineup": getattr(p, "lineup", "—"),
                     "Pts/M": round(points_value_ratio(p), 2)} for p in candidates]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         column_config={"Price": st.column_config.NumberColumn(format="£%.1fM")})


# ═══════════════════════════════════════════════════════
# TAB: SCHEDULE
# ═══════════════════════════════════════════════════════
with tab_schedule:
    st.header("Match Schedule & Odds")

    with st.expander("ℹ️ Termien selitykset — mitä luvut tarkoittavat?", expanded=False):
        st.markdown("""
**Kertoimet (odds) — H · D · A**
Desimaalikertoimet kertovat maksetun palkkion per panostettu euro, jos veikkaus osuu oikein.
Esim. kerroin **2.50** tarkoittaa: panostat 1 €, saat 2.50 € takaisin (voitto 1.50 €).
- **H** = kotijoukkue voittaa · **D** = tasapeli · **A** = vierasjoukkue voittaa

**P(H/D/A) % — implisiittinen todennäköisyys**
Lasketaan kertoimista kääntämällä ne (1 / kerroin) ja normalisoimalla summa 100 %:iin.
Tämä poistaa vedonvälittäjän katteen ja kertoo markkinoiden arvioidun todennäköisyyden kullekin lopputulokselle.
> Esim. kertoimet 2.00 / 3.50 / 4.00 → raakasumma 50% + 28.6% + 25% = 103.6% (kate 3.6%) → normalisoitu ≈ **48% / 28% / 24%**

**xG — odotetut maalit (expected goals)**
Tilastollinen arvio siitä, kuinka monta maalia joukkue "pitäisi" tehdä ottaen huomioon laukausten laatu ja paikka.
Korkea xG = vaarallinen hyökkäys tai helppo vastustaja.
Matala xG omaan maaliin = hyvä mahdollisuus puhtaalle pelille.

**CS% — puhtaan pelin todennäköisyys (clean sheet)**
*Puhdas peli* = joukkue ei päästä yhtään maalia.
Lasketaan xG:stä Poissonin jakauman kaavalla: **CS% = e^(−xG vastustajalle)**
> Esim. vastustajan xG = 1.2 → CS% = e^(−1.2) ≈ **30%**
> Vastustajan xG = 0.6 → CS% = e^(−0.6) ≈ **55%**
CS% on erityisen tärkeä maalivahdeille ja puolustajille, jotka saavat lisäpisteet puhtaasta pelistä.

**O/U — yli/alle maalirajaan (over/under)**
Vedonlyönnin raja-arvo, tyypillisesti **2.5 maalia**.
- **Over**: ottelussa tehdään ≥ 3 maalia
- **Under**: ottelussa tehdään ≤ 2 maalia
        """)

    match_df, _group_map = load_match_data()

    if match_df.empty:
        st.warning("No match data found. Place real_matches.json next to players.json.")
    else:
        # ── Filters ──────────────────────────────────────
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            gw_options = sorted(match_df["GW"].unique())
            selected_gws = st.multiselect("Gameweek", gw_options, default=gw_options[:1])
        with col_f2:
            grp_options = sorted(match_df["Group"].dropna().unique())
            group_filter = st.multiselect("Group", grp_options)
        with col_f3:
            all_teams = sorted({t for t in list(match_df["Home"]) + list(match_df["Away"]) if len(t) <= 5})
            team_filter = st.multiselect("Team", all_teams)
        with col_f4:
            show_only_odds = st.toggle("Only matches with odds/xG", value=False)

        df = match_df.copy()
        if selected_gws:
            df = df[df["GW"].isin(selected_gws)]
        if group_filter:
            df = df[df["Group"].isin(group_filter)]
        if team_filter:
            df = df[df["Home"].isin(team_filter) | df["Away"].isin(team_filter)]
        if show_only_odds:
            df = df[df["_has_odds"] | df["_has_xg"]]

        # ── Group summary table (group stage only) ───────
        if any(g <= 3 for g in (selected_gws or [])):
            grp_df = df[df["GW"] <= 3][["Group", "Home 🏳", "Away 🏳", "Kickoff", "H odds", "D odds", "A odds",
                                         "P(H) %", "P(A) %", "xG Home", "xG Away", "CS% Home", "CS% Away"]].copy()
            if not grp_df.empty and group_filter:
                with st.expander("Group summary table", expanded=True):
                    st.dataframe(grp_df.sort_values(["Group", "Kickoff"]), hide_index=True, use_container_width=True)

        # ── Per-match cards ───────────────────────────────
        prev_group = None
        for _, row in df.sort_values(["GW", "Kickoff"]).iterrows():
            grp = row.get("Group", "")
            if grp and grp != prev_group:
                st.subheader(f"GW{row['GW']} · {grp}")
                prev_group = grp

            status_icon = {"pending": "🕐", "live": "🟢", "finished": "✅", "cancelled": "❌"}.get(row["Status"], "🕐")

            col_home, col_score, col_away = st.columns([3, 1, 3])
            with col_home:
                st.markdown(f"**{row['Home 🏳']}**  \n`{row['H odds']:.2f}` &nbsp; {row['P(H) %']:.0f}%")
            with col_score:
                st.markdown(
                    f"<div style='text-align:center;padding-top:4px'>"
                    f"{status_icon} <b>{row['Score']}</b><br>"
                    f"<small>{row['Kickoff']}</small></div>",
                    unsafe_allow_html=True,
                )
            with col_away:
                st.markdown(f"**{row['Away 🏳']}**  \n`{row['A odds']:.2f}` &nbsp; {row['P(A) %']:.0f}%")

            detail_parts = [f"Tasapeli `{row['D odds']:.2f}` ({row['P(D) %']:.0f}%)"]
            if row["_has_xg"]:
                detail_parts.append(f"xG (odotetut maalit): **{row['xG Home']:.2f}** – **{row['xG Away']:.2f}**")
            if row["CS% Home"] is not None:
                detail_parts.append(
                    f"Puhdas peli (CS%): koti {row['CS% Home']:.0f}% · vieras {row['CS% Away']:.0f}%"
                )
            if row["O/U line"] is not None:
                detail_parts.append(
                    f"Yli/Alle {row['O/U line']:.1f} maalit — yli `{row['Over']:.2f}` alle `{row['Under']:.2f}`"
                )
            st.caption("  ·  ".join(detail_parts))
            st.divider()

        # ── Win probability chart ─────────────────────────
        st.subheader("Win probability overview")
        chart_df = df[df["_has_odds"]].copy()
        chart_df["Match"] = chart_df["Home 🏳"] + " v " + chart_df["Away 🏳"]
        chart_melt = chart_df.melt(
            id_vars=["Match", "Group"], value_vars=["P(H) %", "P(D) %", "P(A) %"],
            var_name="Outcome", value_name="Probability %"
        )
        chart_melt["Outcome"] = chart_melt["Outcome"].map(
            {"P(H) %": "Home win", "P(D) %": "Draw", "P(A) %": "Away win"}
        )
        if not chart_melt.empty:
            fig = px.bar(
                chart_melt, x="Match", y="Probability %", color="Outcome", barmode="stack",
                color_discrete_map={"Home win": "#2196f3", "Draw": "#9e9e9e", "Away win": "#f44336"},
                height=400,
            )
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), xaxis_tickangle=-40, legend_title="")
            st.plotly_chart(fig, use_container_width=True)

        # ── xG scatter ───────────────────────────────────
        xg_df = df[df["_has_xg"]].copy()
        if not xg_df.empty:
            st.subheader("Expected goals (xG)")
            xg_df["Match"] = xg_df["Home 🏳"] + " v " + xg_df["Away 🏳"]
            fig2 = px.scatter(
                xg_df, x="xG Home", y="xG Away", text="Match",
                color="Group",
                labels={"xG Home": "Home team xG", "xG Away": "Away team xG"},
                height=420,
            )
            fig2.add_hline(y=1.3, line_dash="dot", line_color="gray", annotation_text="avg")
            fig2.add_vline(x=1.3, line_dash="dot", line_color="gray")
            fig2.update_traces(textposition="top center", textfont_size=8)
            fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("Top-left = strong home team. Bottom-right = strong away team. Good for spotting clean sheet candidates.")


# ═══════════════════════════════════════════════════════
# TAB 3: TRANSFERS
# ═══════════════════════════════════════════════════════
with tab_transfers:
    st.header("Transfer Planner")

    if st.session_state.current_squad is None:
        st.info("Set your squad first — use the Optimizer tab or enter your current squad in the My Squad tab.")
    else:
        squad = st.session_state.current_squad
        st.write("**Current squad:**")
        st.dataframe(squad_table(squad).drop(columns=[]), use_container_width=True, hide_index=True)

        st.markdown("---")
        next_gw = st.selectbox("Optimise for Gameweek", [gw["round"] for gw in GAMEWEEKS if gw["round"] > 1],
                               format_func=lambda r: f"GW{r}: {next(g['name'] for g in GAMEWEEKS if g['round'] == r)}")

        tx_budget = st.number_input("Available budget for next GW (M€)", value=budget, step=0.5)
        free_tx_next = FREE_TRANSFERS.get(next_gw, 2)
        use_wc = st.checkbox("Use Wildcard for next GW", disabled=st.session_state.wildcard_used)

        if st.button("🔄 Plan Transfers", type="primary"):
            with st.spinner("Optimising transfers..."):
                new_squad, penalty = optimize_transfers(
                    current_squad=squad,
                    all_players=st.session_state.players,
                    budget=tx_budget,
                    gameweek=next_gw,
                    free_transfers=free_tx_next,
                    use_wildcard=use_wc,
                    locked_ids=locked_ids,
                    excluded_ids=excluded_ids,
                )

            if new_squad is None:
                st.error("Could not find a valid squad.")
            else:
                current_ids = {p.id for p in squad.players}
                new_ids = {p.id for p in new_squad.players}
                transfers_in = [p for p in new_squad.players if p.id not in current_ids]
                transfers_out = [p for p in squad.players if p.id not in new_ids]
                n_transfers = len(transfers_in)
                extra = max(0, n_transfers - free_tx_next)

                col1, col2, col3 = st.columns(3)
                col1.metric("Transfers made", n_transfers)
                col2.metric("Free transfers", free_tx_next)
                col3.metric("Point penalty", penalty, delta_color="inverse")

                col_in, col_out = st.columns(2)
                with col_in:
                    st.markdown("**Transfers IN** 🟢")
                    for p in transfers_in:
                        st.write(f"+ {p.name} ({p.position}, {p.team}) £{p.price}M — {p.expected_points:.1f} xPts")
                with col_out:
                    st.markdown("**Transfers OUT** 🔴")
                    for p in transfers_out:
                        st.write(f"− {p.name} ({p.position}, {p.team}) £{p.price}M")

                if st.button("✅ Confirm — set as current squad"):
                    st.session_state.current_squad = new_squad
                    if use_wc:
                        st.session_state.wildcard_used = True
                    st.success("Squad updated!")

# ═══════════════════════════════════════════════════════
# TAB 4: RULES
# ═══════════════════════════════════════════════════════
with tab_rules:
    st.header("Scoring & Rules Reference")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("All players")
        st.markdown("""
| Event | Points |
|---|---|
| Playing time < 60 min | 1 |
| Playing time ≥ 60 min | +1 (total 2) |
| Assist / Fantasy assist | 3 |
| Penalty won | −2 |
| Caused goal-bound free kick | −2 |
| Missed penalty | −2 |
| Own goal | −2 |
| Yellow card | −1 |
| Red card | −3 |
| Playing while winning | +0.3 |
| Playing while losing | −0.3 |
""")

        st.subheader("Goalkeepers")
        st.markdown("""
| Event | Points |
|---|---|
| Goal | 8 |
| Clean sheet (60+ min) | 4 |
| Penalty save | 5 |
| Save | 0.5 |
| Shot on target | 1 |
| Per 2 goals conceded | −1 |
""")

    with col2:
        st.subheader("Defenders")
        st.markdown("""
| Event | Points |
|---|---|
| Goal | 6 |
| Clean sheet (60+ min) | 4 |
| Shot on target | 0.6 |
| Per 2 goals conceded | −1 |
""")

        st.subheader("Midfielders")
        st.markdown("""
| Event | Points |
|---|---|
| Goal | 5 |
| Clean sheet (60+ min) | 1 |
| Full match | 1 |
| Shot on target | 0.4 |
""")

        st.subheader("Forwards")
        st.markdown("""
| Event | Points |
|---|---|
| Goal | 4 |
| Full match | 1 |
| Shot on target | 0.4 |
""")

    st.subheader("Transfer rules")
    st.markdown("""
| Gameweek | Free transfers | Extra transfer cost |
|---|---|---|
| 1 (initial) | Unlimited | — |
| 2–4 | 2 | −4 pts each |
| 5–8 | 4 | −4 pts each |
| Wildcard | Unlimited (once) | — |

Unused transfers are lost at the end of each gameweek.
""")

    st.subheader("Country limits")
    st.markdown("""
| Gameweek | Max from same country |
|---|---|
| 1–4 | 3 |
| 5–6 | 4 |
| 7 | 6 |
| 8 | 8 |
""")
