"""Async client for The Odds API."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx

from .config import (
    ODDS_API_KEY,
    ODDS_API_BASE_URL,
    SUPPORTED_BOOKMAKERS,
    DEFAULT_MARKETS,
    CACHE_TTL_SECONDS,
)
from .models import Sport, Market, Outcome


class OddsAPIError(Exception):
    """Custom exception for Odds API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class CacheEntry:
    """Cache entry with TTL."""

    def __init__(self, data: any, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.data = data
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class OddsClient:
    """Async client for The Odds API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ODDS_API_KEY
        self.base_url = ODDS_API_BASE_URL
        self._cache: dict[str, CacheEntry] = {}
        self._requests_remaining: Optional[int] = None
        self._requests_used: Optional[int] = None

    @property
    def requests_remaining(self) -> Optional[int]:
        """Return remaining API requests."""
        return self._requests_remaining

    @property
    def requests_used(self) -> Optional[int]:
        """Return API requests used."""
        return self._requests_used

    def _get_cache(self, key: str) -> Optional[any]:
        """Get cached data if not expired."""
        entry = self._cache.get(key)
        if entry and not entry.is_expired:
            return entry.data
        return None

    def _set_cache(self, key: str, data: any):
        """Set cache entry."""
        self._cache[key] = CacheEntry(data)

    def _update_rate_limits(self, headers: httpx.Headers):
        """Update rate limit tracking from response headers."""
        remaining = headers.get("x-requests-remaining")
        used = headers.get("x-requests-used")

        if remaining is not None:
            self._requests_remaining = int(remaining)
        if used is not None:
            self._requests_used = int(used)

    async def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated request to the API."""
        if not self.api_key:
            raise OddsAPIError("API key not configured. Set ODDS_API_KEY in .env file.")

        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params["apiKey"] = self.api_key

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                self._update_rate_limits(response.headers)

                if response.status_code == 401:
                    raise OddsAPIError("Invalid API key", 401)
                elif response.status_code == 429:
                    raise OddsAPIError("Rate limit exceeded", 429)
                elif response.status_code != 200:
                    raise OddsAPIError(
                        f"API request failed: {response.text}",
                        response.status_code
                    )

                return response.json()

            except httpx.TimeoutException:
                raise OddsAPIError("Request timed out")
            except httpx.RequestError as e:
                raise OddsAPIError(f"Request failed: {str(e)}")

    async def get_sports(self, use_cache: bool = True) -> list[Sport]:
        """Fetch available sports from the API."""
        cache_key = "sports"

        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached

        data = await self._request("/sports")
        sports = [Sport(**s) for s in data]

        self._set_cache(cache_key, sports)
        return sports

    async def get_odds(
        self,
        sport_key: str,
        regions: str = "us,uk,eu,au",
        markets: Optional[list[str]] = None,
        bookmakers: Optional[list[str]] = None,
        use_cache: bool = True,
    ) -> list[Market]:
        """
        Fetch odds for a sport across all bookmakers.

        Args:
            sport_key: The sport key (e.g., 'basketball_nba')
            regions: Comma-separated regions (us, uk, eu, au)
            markets: List of market types (default: ['h2h'])
            bookmakers: Specific bookmakers to fetch (optional)
            use_cache: Whether to use cached data

        Returns:
            List of Market objects with outcomes
        """
        markets = markets or DEFAULT_MARKETS
        markets_str = ",".join(markets)

        cache_key = f"odds:{sport_key}:{regions}:{markets_str}"

        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached

        params = {
            "regions": regions,
            "markets": markets_str,
            "oddsFormat": "decimal",
        }

        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)

        data = await self._request(f"/sports/{sport_key}/odds", params)
        markets_list = self._parse_odds_response(data, sport_key)

        self._set_cache(cache_key, markets_list)
        return markets_list

    def _parse_odds_response(self, data: list[dict], sport_key: str) -> list[Market]:
        """Parse API response into Market objects."""
        markets = []

        for event in data:
            event_id = event.get("id", "")
            sport_title = event.get("sport_title", "")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence_time_str = event.get("commence_time", "")

            try:
                commence_time = datetime.fromisoformat(
                    commence_time_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                commence_time = datetime.utcnow()

            # Process each bookmaker's odds
            bookmakers_data = event.get("bookmakers", [])

            for bookmaker in bookmakers_data:
                bookmaker_key = bookmaker.get("key", "")
                bookmaker_title = bookmaker.get("title", bookmaker_key)

                for market_data in bookmaker.get("markets", []):
                    market_key = market_data.get("key", "h2h")

                    outcomes = []
                    for outcome_data in market_data.get("outcomes", []):
                        outcomes.append(Outcome(
                            name=outcome_data.get("name", ""),
                            price=outcome_data.get("price", 0),
                            bookmaker=bookmaker_title,
                        ))

                    markets.append(Market(
                        event_id=event_id,
                        sport_key=sport_key,
                        sport_title=sport_title,
                        home_team=home_team,
                        away_team=away_team,
                        commence_time=commence_time,
                        market_key=market_key,
                        outcomes=outcomes,
                    ))

        return markets

    async def get_bookmakers(self) -> dict[str, str]:
        """Return supported bookmakers."""
        return SUPPORTED_BOOKMAKERS.copy()

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()


# Singleton instance
_client: Optional[OddsClient] = None


def get_odds_client() -> OddsClient:
    """Get or create the singleton OddsClient instance."""
    global _client
    if _client is None:
        _client = OddsClient()
    return _client
