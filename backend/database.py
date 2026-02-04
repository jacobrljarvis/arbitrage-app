"""SQLite database operations for caching and history."""

import json
import aiosqlite
from datetime import datetime
from typing import Optional
from pathlib import Path

from .config import DATABASE_PATH
from .models import ArbitrageOpportunity, ScanResult


class Database:
    """SQLite database for caching odds and storing scan history."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._initialized = False

    async def initialize(self):
        """Create database tables if they don't exist."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Scan history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sport_key TEXT NOT NULL,
                    sport_title TEXT NOT NULL,
                    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    events_scanned INTEGER DEFAULT 0,
                    opportunities_found INTEGER DEFAULT 0,
                    api_requests_used INTEGER DEFAULT 1
                )
            """)

            # Opportunities table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER,
                    event_id TEXT NOT NULL,
                    sport_key TEXT NOT NULL,
                    sport_title TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    commence_time TIMESTAMP,
                    market_key TEXT DEFAULT 'h2h',
                    profit_margin REAL NOT NULL,
                    outcomes_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
                )
            """)

            # API usage tracking table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    endpoint TEXT NOT NULL,
                    requests_used INTEGER DEFAULT 1,
                    requests_remaining INTEGER
                )
            """)

            # Odds cache table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS odds_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            await db.commit()
            self._initialized = True

    async def save_scan_result(self, result: ScanResult) -> int:
        """Save scan result to database."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO scan_history (
                    sport_key, sport_title, scan_time,
                    events_scanned, opportunities_found, api_requests_used
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result.sport_key,
                result.sport_title,
                result.scan_time.isoformat(),
                result.events_scanned,
                result.opportunities_found,
                result.api_requests_used,
            ))

            scan_id = cursor.lastrowid

            # Save opportunities
            for opp in result.opportunities:
                outcomes_json = json.dumps([
                    {"name": o.name, "price": o.price, "bookmaker": o.bookmaker}
                    for o in opp.outcomes
                ])

                await db.execute("""
                    INSERT INTO opportunities (
                        scan_id, event_id, sport_key, sport_title,
                        home_team, away_team, commence_time, market_key,
                        profit_margin, outcomes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_id,
                    opp.event_id,
                    opp.sport_key,
                    opp.sport_title,
                    opp.home_team,
                    opp.away_team,
                    opp.commence_time.isoformat(),
                    opp.market_key,
                    opp.profit_margin,
                    outcomes_json,
                ))

            await db.commit()
            return scan_id

    async def get_recent_scans(self, limit: int = 10) -> list[dict]:
        """Get recent scan history."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM scan_history
                ORDER BY scan_time DESC
                LIMIT ?
            """, (limit,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_opportunities_by_scan(self, scan_id: int) -> list[dict]:
        """Get opportunities for a specific scan."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM opportunities
                WHERE scan_id = ?
                ORDER BY profit_margin DESC
            """, (scan_id,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def log_api_usage(
        self,
        endpoint: str,
        requests_used: int = 1,
        requests_remaining: Optional[int] = None
    ):
        """Log API usage for tracking."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO api_usage (endpoint, requests_used, requests_remaining)
                VALUES (?, ?, ?)
            """, (endpoint, requests_used, requests_remaining))
            await db.commit()

    async def get_api_usage_today(self) -> dict:
        """Get API usage for today."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    SUM(requests_used) as total_used,
                    MIN(requests_remaining) as remaining
                FROM api_usage
                WHERE date(timestamp) = date('now')
            """)

            row = await cursor.fetchone()
            return {
                "total_used_today": row[0] or 0,
                "requests_remaining": row[1],
            }

    async def get_api_usage_month(self) -> dict:
        """Get API usage for the current month."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT
                    SUM(requests_used) as total_used,
                    MIN(requests_remaining) as remaining
                FROM api_usage
                WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
            """)

            row = await cursor.fetchone()
            return {
                "total_used_month": row[0] or 0,
                "requests_remaining": row[1],
            }

    async def cleanup_expired_cache(self):
        """Remove expired cache entries."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM odds_cache
                WHERE expires_at < datetime('now')
            """)
            await db.commit()


# Singleton instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get or create the singleton Database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
