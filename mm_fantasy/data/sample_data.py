"""
Sample player data for development / demo when no API key or scraper available.
Covers a realistic WC 2026 squad mix with varied prices and positions.
"""

from models import Player

SAMPLE_PLAYERS: list[Player] = [
    # --- Goalkeepers ---
    Player("gk1",  "M. Neuer",       "GER", "GK",  5.5, expected_points=7.0, mins=270, saves=9, clean_sheets=1),
    Player("gk2",  "A. Onana",       "CMR", "GK",  4.5, expected_points=5.5, mins=270, saves=8),
    Player("gk3",  "D. Vlachodimos", "GRE", "GK",  4.0, expected_points=5.0, mins=270, saves=7),
    Player("gk4",  "Y. Sommer",      "SUI", "GK",  4.5, expected_points=5.8, mins=270, saves=10, clean_sheets=1),
    Player("gk5",  "T. Courtois",    "BEL", "GK",  6.0, expected_points=7.5, mins=270, saves=11, clean_sheets=2),
    Player("gk6",  "G. Donnarumma",  "ITA", "GK",  6.0, expected_points=7.2, mins=270, saves=10, clean_sheets=1),
    Player("gk7",  "A. Rui Patricio","POR", "GK",  4.5, expected_points=5.2, mins=180),
    Player("gk8",  "W. Szczesny",    "POL", "GK",  5.0, expected_points=6.0, mins=270, saves=9),

    # --- Defenders ---
    Player("def1", "V. van Dijk",    "NED", "DEF", 6.5, expected_points=8.0, mins=270, goals=1, clean_sheets=1),
    Player("def2", "A. Rüdiger",     "GER", "DEF", 5.5, expected_points=6.5, mins=270, clean_sheets=1),
    Player("def3", "T. Alexander-Arnold", "ENG", "DEF", 7.0, expected_points=9.0, mins=270, goals=1, assists=2, shots_on_target=3),
    Player("def4", "A. Robertson",   "SCO", "DEF", 5.5, expected_points=6.0, mins=270, assists=1),
    Player("def5", "K. Walker",      "ENG", "DEF", 5.0, expected_points=5.5, mins=270, clean_sheets=1),
    Player("def6", "R. Dias",        "POR", "DEF", 6.0, expected_points=6.5, mins=270, clean_sheets=2),
    Player("def7", "D. Upamecano",   "FRA", "DEF", 5.5, expected_points=5.8, mins=270),
    Player("def8", "T. Hernandez",   "FRA", "DEF", 6.0, expected_points=7.0, mins=270, goals=1, assists=1),
    Player("def9", "A. Davies",      "CAN", "DEF", 5.5, expected_points=6.2, mins=270, assists=1),
    Player("def10","J. Timber",      "NED", "DEF", 5.0, expected_points=5.5, mins=270, clean_sheets=1),
    Player("def11","B. Pavard",      "FRA", "DEF", 5.0, expected_points=5.2, mins=270),
    Player("def12","N. Süle",        "GER", "DEF", 4.5, expected_points=4.8, mins=180),
    Player("def13","G. Mancini",     "ITA", "DEF", 4.5, expected_points=5.0, mins=270, clean_sheets=1),
    Player("def14","S. Dest",        "USA", "DEF", 4.5, expected_points=4.5, mins=180),
    Player("def15","C. Richards",    "USA", "DEF", 4.0, expected_points=4.0, mins=180),
    Player("def16","E. Dier",        "ENG", "DEF", 4.5, expected_points=4.5, mins=180, clean_sheets=1),
    Player("def17","W. Saliba",      "FRA", "DEF", 5.5, expected_points=6.0, mins=270, clean_sheets=2),
    Player("def18","K. Koulibaly",   "SEN", "DEF", 5.0, expected_points=5.0, mins=270),
    Player("def19","M. Acuna",       "ARG", "DEF", 5.0, expected_points=5.5, mins=270, assists=1),
    Player("def20","L. Martinez",    "ARG", "DEF", 5.0, expected_points=5.2, mins=270, clean_sheets=1),

    # --- Midfielders ---
    Player("mid1", "K. De Bruyne",   "BEL", "MID", 10.0, expected_points=13.0, mins=270, goals=2, assists=3, shots_on_target=5),
    Player("mid2", "J. Bellingham",  "ENG", "MID", 10.5, expected_points=13.5, mins=270, goals=3, assists=2, shots_on_target=6),
    Player("mid3", "V. Rodríguez",   "ESP", "MID", 6.5,  expected_points=7.5,  mins=270, goals=1, assists=2),
    Player("mid4", "L. Modric",      "CRO", "MID", 7.0,  expected_points=8.0,  mins=270, goals=1, assists=1),
    Player("mid5", "T. Kroos",       "GER", "MID", 7.5,  expected_points=8.5,  mins=270, assists=2, shots_on_target=3),
    Player("mid6", "B. Fernandes",   "POR", "MID", 8.0,  expected_points=9.0,  mins=270, goals=2, assists=1, shots_on_target=4),
    Player("mid7", "A. Griezmann",   "FRA", "MID", 8.5,  expected_points=9.5,  mins=270, goals=2, assists=2, shots_on_target=4),
    Player("mid8", "P. Foden",       "ENG", "MID", 8.5,  expected_points=9.0,  mins=270, goals=1, assists=2, shots_on_target=5),
    Player("mid9", "M. Zielinski",   "POL", "MID", 6.0,  expected_points=6.5,  mins=270, assists=1),
    Player("mid10","F. Valverde",    "URU", "MID", 7.0,  expected_points=7.5,  mins=270, goals=1, assists=1, shots_on_target=3),
    Player("mid11","C. Camavinga",   "FRA", "MID", 6.5,  expected_points=6.5,  mins=270),
    Player("mid12","J. Mac Allister","ARG", "MID", 6.5,  expected_points=7.0,  mins=270, goals=1, assists=1),
    Player("mid13","M. Sissoko",     "SEN", "MID", 5.0,  expected_points=5.0,  mins=270),
    Player("mid14","G. Reyna",       "USA", "MID", 5.5,  expected_points=5.5,  mins=180, goals=1),
    Player("mid15","S. Milinkovic-Savic","SRB","MID",6.5, expected_points=6.5, mins=270, goals=1, assists=1),
    Player("mid16","P. Schick",      "CZE", "MID", 6.0,  expected_points=6.0,  mins=270, goals=1),
    Player("mid17","D. Nouri",       "NED", "MID", 5.5,  expected_points=5.5,  mins=180),
    Player("mid18","T. Hazard",      "BEL", "MID", 5.0,  expected_points=4.5,  mins=180),
    Player("mid19","N. Barella",     "ITA", "MID", 7.0,  expected_points=7.5,  mins=270, assists=2, shots_on_target=2),
    Player("mid20","M. Verratti",    "ITA", "MID", 6.5,  expected_points=6.5,  mins=270, assists=1),

    # --- Forwards ---
    Player("fwd1", "K. Mbappé",      "FRA", "FWD", 13.0, expected_points=16.0, mins=270, goals=5, assists=2, shots_on_target=10),
    Player("fwd2", "E. Haaland",     "NOR", "FWD", 13.0, expected_points=15.5, mins=270, goals=5, shots_on_target=9),
    Player("fwd3", "H. Kane",        "ENG", "FWD", 12.0, expected_points=14.0, mins=270, goals=4, assists=1, shots_on_target=8),
    Player("fwd4", "R. Lewandowski", "POL", "FWD", 11.0, expected_points=12.5, mins=270, goals=3, assists=1, shots_on_target=7),
    Player("fwd5", "C. Ronaldo",     "POR", "FWD", 11.5, expected_points=12.0, mins=270, goals=3, shots_on_target=6),
    Player("fwd6", "L. Messi",       "ARG", "FWD", 13.5, expected_points=15.0, mins=270, goals=3, assists=4, shots_on_target=7),
    Player("fwd7", "R. Lukaku",      "BEL", "FWD", 9.5,  expected_points=10.5, mins=270, goals=2, assists=1, shots_on_target=5),
    Player("fwd8", "L. Digne",       "FRA", "FWD", 6.0,  expected_points=6.0,  mins=180),
    Player("fwd9", "C. Pulisic",     "USA", "FWD", 7.5,  expected_points=7.5,  mins=270, goals=1, assists=1, shots_on_target=4),
    Player("fwd10","G. Jesus",       "BRA", "FWD", 8.5,  expected_points=9.0,  mins=270, goals=2, shots_on_target=5),
    Player("fwd11","V. Osimhen",     "NGA", "FWD", 9.0,  expected_points=9.5,  mins=270, goals=2, shots_on_target=5),
    Player("fwd12","D. Vlahovic",    "SRB", "FWD", 8.5,  expected_points=8.5,  mins=270, goals=2, shots_on_target=4),
    Player("fwd13","E. Forsberg",    "SWE", "FWD", 6.5,  expected_points=6.5,  mins=270, goals=1, shots_on_target=3),
    Player("fwd14","R. Deeney",      "WAL", "FWD", 5.5,  expected_points=5.0,  mins=180),
    Player("fwd15","T. Werner",      "GER", "FWD", 7.5,  expected_points=7.0,  mins=270, goals=1, shots_on_target=4),
    Player("fwd16","M. Rashford",    "ENG", "FWD", 8.5,  expected_points=9.0,  mins=270, goals=2, assists=1, shots_on_target=5),
    Player("fwd17","A. Mitrovic",    "SRB", "FWD", 8.0,  expected_points=8.0,  mins=270, goals=2, shots_on_target=4),
    Player("fwd18","L. Suarez",      "URU", "FWD", 7.0,  expected_points=7.0,  mins=270, goals=1, shots_on_target=3),
]
