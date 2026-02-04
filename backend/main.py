"""FastAPI application entry point."""

from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import SUPPORTED_SPORTS, SUPPORTED_BOOKMAKERS, MIN_PROFIT_MARGIN
from .models import (
    Sport,
    Bookmaker,
    ScanResult,
    ArbitrageOpportunity,
    CalculateStakesRequest,
    CalculateStakesResponse,
)
from .odds_client import get_odds_client, OddsAPIError
from .arbitrage import find_arbitrage_opportunities, calculate_stakes
from .database import get_database

app = FastAPI(
    title="Sports Betting Arbitrage Scanner",
    description="Scan multiple sportsbooks for arbitrage opportunities",
    version="1.0.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    db = get_database()
    await db.initialize()


@app.get("/")
async def root():
    """Serve the frontend."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Sports Betting Arbitrage Scanner API", "docs": "/docs"}


@app.get("/api/sports", response_model=list[dict])
async def get_sports(active_only: bool = True):
    """
    List available sports.

    Returns both API-available sports and locally configured sports.
    """
    client = get_odds_client()

    try:
        api_sports = await client.get_sports(use_cache=True)
        sports = []

        for sport in api_sports:
            if active_only and not sport.active:
                continue

            display_name = SUPPORTED_SPORTS.get(sport.key, sport.title)
            sports.append({
                "key": sport.key,
                "title": display_name,
                "group": sport.group,
                "active": sport.active,
                "has_outrights": sport.has_outrights,
            })

        return sorted(sports, key=lambda s: s["title"])

    except OddsAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)


@app.get("/api/bookmakers", response_model=list[Bookmaker])
async def get_bookmakers():
    """List supported bookmakers."""
    return [
        Bookmaker(key=key, title=title)
        for key, title in SUPPORTED_BOOKMAKERS.items()
    ]


@app.get("/api/scan/{sport_key}", response_model=ScanResult)
async def scan_sport(
    sport_key: str,
    min_profit: float = Query(default=MIN_PROFIT_MARGIN, ge=0, le=1),
):
    """
    Scan a specific sport for arbitrage opportunities.

    Args:
        sport_key: The sport to scan (e.g., 'basketball_nba')
        min_profit: Minimum profit margin to report (default 0.1%)

    Returns:
        ScanResult with found opportunities
    """
    client = get_odds_client()
    db = get_database()

    try:
        # Fetch odds from all bookmakers
        markets = await client.get_odds(sport_key, use_cache=False)

        # Find arbitrage opportunities
        opportunities = find_arbitrage_opportunities(markets, min_profit)

        # Get sport title
        sport_title = SUPPORTED_SPORTS.get(sport_key, sport_key)

        # Count unique events
        unique_events = set(m.event_id for m in markets)

        result = ScanResult(
            sport_key=sport_key,
            sport_title=sport_title,
            scan_time=datetime.utcnow(),
            events_scanned=len(unique_events),
            opportunities_found=len(opportunities),
            opportunities=opportunities,
            api_requests_used=1,
            api_requests_remaining=client.requests_remaining,
        )

        # Save to database
        await db.save_scan_result(result)
        await db.log_api_usage(
            f"/sports/{sport_key}/odds",
            requests_used=1,
            requests_remaining=client.requests_remaining,
        )

        return result

    except OddsAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)


@app.get("/api/scan/all", response_model=list[ScanResult])
async def scan_all_sports(
    min_profit: float = Query(default=MIN_PROFIT_MARGIN, ge=0, le=1),
):
    """
    Scan all supported sports for arbitrage opportunities.

    Warning: This uses multiple API requests.

    Args:
        min_profit: Minimum profit margin to report

    Returns:
        List of ScanResult for each sport
    """
    client = get_odds_client()
    results = []

    try:
        # Get available sports
        sports = await client.get_sports(use_cache=True)

        for sport in sports:
            if not sport.active:
                continue

            if sport.key not in SUPPORTED_SPORTS:
                continue

            try:
                markets = await client.get_odds(sport.key, use_cache=False)
                opportunities = find_arbitrage_opportunities(markets, min_profit)

                unique_events = set(m.event_id for m in markets)

                result = ScanResult(
                    sport_key=sport.key,
                    sport_title=SUPPORTED_SPORTS.get(sport.key, sport.title),
                    scan_time=datetime.utcnow(),
                    events_scanned=len(unique_events),
                    opportunities_found=len(opportunities),
                    opportunities=opportunities,
                    api_requests_used=1,
                    api_requests_remaining=client.requests_remaining,
                )
                results.append(result)

            except OddsAPIError:
                # Skip sports with errors
                continue

        return results

    except OddsAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=e.message)


@app.post("/api/calculate", response_model=CalculateStakesResponse)
async def calculate_opportunity_stakes(request: CalculateStakesRequest):
    """
    Calculate optimal stakes for an arbitrage opportunity.

    Args:
        request: Contains total stake and outcomes with best odds

    Returns:
        Stake recommendations for each outcome
    """
    return calculate_stakes(request.outcomes, request.total_stake)


@app.get("/api/usage")
async def get_api_usage():
    """Get API usage statistics."""
    client = get_odds_client()
    db = get_database()

    today = await db.get_api_usage_today()
    month = await db.get_api_usage_month()

    return {
        "today": today,
        "month": month,
        "current_remaining": client.requests_remaining,
    }


@app.get("/api/history")
async def get_scan_history(limit: int = Query(default=10, ge=1, le=100)):
    """Get recent scan history."""
    db = get_database()
    return await db.get_recent_scans(limit)


@app.get("/api/history/{scan_id}/opportunities")
async def get_scan_opportunities(scan_id: int):
    """Get opportunities for a specific scan."""
    db = get_database()
    return await db.get_opportunities_by_scan(scan_id)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
