# Sports Betting Arbitrage Application

A web application that scans multiple sportsbooks for arbitrage opportunities and calculates optimal stake distribution for guaranteed profits.

## Features

- Scan multiple sportsbooks for arbitrage opportunities
- Calculate optimal stake distribution
- Support for 30+ sports via The Odds API
- Real-time profit margin calculations
- API usage tracking (free tier: 500 requests/month)

## Supported Bookmakers

**US Markets:**
- DraftKings, FanDuel, BetMGM, Caesars, PointsBet, BetRivers, Unibet, WynnBET, Barstool

**International:**
- Bet365, Betfair, William Hill, Pinnacle

## Setup

### 1. Get API Key

Sign up for a free API key at [The Odds API](https://the-odds-api.com/).

### 2. Install Dependencies

```bash
cd arbitrage-app
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API key
```

### 4. Run the Application

```bash
uvicorn backend.main:app --reload
```

### 5. Open in Browser

Navigate to `http://localhost:8000`

## API Endpoints

- `GET /api/sports` - List available sports
- `GET /api/scan/{sport}` - Scan a specific sport for arbitrage
- `GET /api/scan/all` - Scan all sports
- `GET /api/bookmakers` - List supported bookmakers
- `POST /api/calculate` - Calculate stakes for an opportunity

## How Arbitrage Works

For a 2-way market (e.g., moneyline):

```
Implied probability = 1 / decimal_odds
If sum of implied probabilities < 1, arbitrage exists

Example:
- Bookmaker A: Team 1 @ 2.10 (47.6% implied)
- Bookmaker B: Team 2 @ 2.05 (48.8% implied)
- Total: 96.4% → 3.6% profit margin

Stake calculation for $1000 total:
- Stake on Team 1 = $1000 × (47.6% / 96.4%) = $494
- Stake on Team 2 = $1000 × (48.8% / 96.4%) = $506
- Guaranteed return: ~$1036 regardless of outcome
```

## Tech Stack

- **Backend:** Python 3.11+ with FastAPI
- **Frontend:** HTML, CSS, vanilla JavaScript
- **API:** The Odds API
- **Database:** SQLite (caching and history)

## License

MIT
