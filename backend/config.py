"""Configuration module for the arbitrage application."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Rate limiting (free tier: 500 requests/month)
RATE_LIMIT_REQUESTS_PER_MONTH = 500
CACHE_TTL_SECONDS = 300  # 5 minutes cache for odds data

# Supported sports (The Odds API sport keys)
SUPPORTED_SPORTS = {
    # American Football
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "NCAAF",
    # Basketball
    "basketball_nba": "NBA",
    "basketball_ncaab": "NCAAB",
    # Baseball
    "baseball_mlb": "MLB",
    # Hockey
    "icehockey_nhl": "NHL",
    # Soccer
    "soccer_epl": "EPL (England)",
    "soccer_spain_la_liga": "La Liga (Spain)",
    "soccer_germany_bundesliga": "Bundesliga (Germany)",
    "soccer_italy_serie_a": "Serie A (Italy)",
    "soccer_france_ligue_one": "Ligue 1 (France)",
    "soccer_usa_mls": "MLS",
    # Tennis
    "tennis_atp_french_open": "ATP French Open",
    "tennis_wta_french_open": "WTA French Open",
    # MMA
    "mma_mixed_martial_arts": "MMA/UFC",
    # Boxing
    "boxing_boxing": "Boxing",
}

# Supported bookmakers
SUPPORTED_BOOKMAKERS = {
    # US Bookmakers
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "pointsbetus": "PointsBet",
    "betrivers": "BetRivers",
    "unibet_us": "Unibet",
    "wynnbet": "WynnBET",
    "barstool": "Barstool",
    # International Bookmakers
    "bet365": "Bet365",
    "betfair": "Betfair",
    "williamhill": "William Hill",
    "pinnacle": "Pinnacle",
    "bovada": "Bovada",
    "betonlineag": "BetOnline",
}

# Default markets to fetch
DEFAULT_MARKETS = ["h2h"]  # head-to-head (moneyline)

# Minimum profit margin to display (as decimal, e.g., 0.01 = 1%)
MIN_PROFIT_MARGIN = 0.001  # 0.1%

# Database configuration
DATABASE_PATH = "arbitrage.db"
