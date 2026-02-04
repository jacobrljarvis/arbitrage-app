"""Pydantic models for data validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Outcome(BaseModel):
    """Represents odds for a single outcome (team/player)."""

    name: str = Field(..., description="Name of the team or player")
    price: float = Field(..., description="Decimal odds for this outcome")
    bookmaker: str = Field(..., description="Bookmaker offering these odds")

    @property
    def implied_probability(self) -> float:
        """Calculate implied probability from decimal odds."""
        return 1 / self.price if self.price > 0 else 0


class Market(BaseModel):
    """Collection of outcomes for an event."""

    event_id: str = Field(..., description="Unique identifier for the event")
    sport_key: str = Field(..., description="Sport key from The Odds API")
    sport_title: str = Field(..., description="Human-readable sport name")
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    commence_time: datetime = Field(..., description="Event start time")
    market_key: str = Field(default="h2h", description="Market type (e.g., h2h, spreads)")
    outcomes: list[Outcome] = Field(default_factory=list, description="All available outcomes")


class StakeRecommendation(BaseModel):
    """Recommended stake for a single outcome."""

    outcome_name: str = Field(..., description="Name of the outcome")
    bookmaker: str = Field(..., description="Bookmaker to place bet with")
    odds: float = Field(..., description="Decimal odds")
    stake: float = Field(..., description="Recommended stake amount")
    potential_return: float = Field(..., description="Potential return if this outcome wins")


class ArbitrageOpportunity(BaseModel):
    """Detected arbitrage opportunity with profit margin and stakes."""

    event_id: str = Field(..., description="Unique identifier for the event")
    sport_key: str = Field(..., description="Sport key")
    sport_title: str = Field(..., description="Human-readable sport name")
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    commence_time: datetime = Field(..., description="Event start time")
    market_key: str = Field(default="h2h", description="Market type")
    profit_margin: float = Field(..., description="Profit margin as decimal (e.g., 0.036 = 3.6%)")
    total_implied_probability: float = Field(..., description="Sum of implied probabilities")
    outcomes: list[Outcome] = Field(..., description="Best odds for each outcome")
    stakes: Optional[list[StakeRecommendation]] = Field(
        default=None,
        description="Stake recommendations (calculated on demand)"
    )

    @property
    def profit_percentage(self) -> float:
        """Return profit margin as percentage."""
        return self.profit_margin * 100

    @property
    def event_name(self) -> str:
        """Return formatted event name."""
        return f"{self.away_team} @ {self.home_team}"


class ScanResult(BaseModel):
    """Full scan response."""

    sport_key: str = Field(..., description="Sport that was scanned")
    sport_title: str = Field(..., description="Human-readable sport name")
    scan_time: datetime = Field(default_factory=datetime.utcnow)
    events_scanned: int = Field(..., description="Number of events scanned")
    opportunities_found: int = Field(..., description="Number of arbitrage opportunities found")
    opportunities: list[ArbitrageOpportunity] = Field(default_factory=list)
    api_requests_used: int = Field(default=1, description="API requests consumed by this scan")
    api_requests_remaining: Optional[int] = Field(
        default=None,
        description="Remaining API requests (from response header)"
    )


class CalculateStakesRequest(BaseModel):
    """Request to calculate optimal stakes for an opportunity."""

    total_stake: float = Field(..., description="Total amount to stake", gt=0)
    outcomes: list[Outcome] = Field(..., description="Outcomes with best odds")


class CalculateStakesResponse(BaseModel):
    """Response with calculated stakes."""

    total_stake: float = Field(..., description="Total stake amount")
    guaranteed_profit: float = Field(..., description="Guaranteed profit regardless of outcome")
    profit_percentage: float = Field(..., description="Profit as percentage of stake")
    stakes: list[StakeRecommendation] = Field(..., description="Stake for each outcome")


class Sport(BaseModel):
    """Sport available from The Odds API."""

    key: str = Field(..., description="Sport key for API calls")
    group: str = Field(..., description="Sport group/category")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(default="", description="Sport description")
    active: bool = Field(default=True, description="Whether sport is currently active")
    has_outrights: bool = Field(default=False, description="Whether sport has outright markets")


class Bookmaker(BaseModel):
    """Bookmaker information."""

    key: str = Field(..., description="Bookmaker key for API calls")
    title: str = Field(..., description="Human-readable name")
    region: str = Field(default="us", description="Region (us, uk, eu, au)")
