"""Daily snapshots and bounded history tables."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from db import utc_now_iso
from stats import StatsService


async def test_record_daily_prunes_old_broadcast_keys(db, test_settings):
    old = (datetime.now(UTC) - timedelta(days=200)).isoformat(timespec="seconds")
    fresh = utc_now_iso()
    await db.execute(
        "INSERT INTO broadcast_log (event_key, created_at) VALUES (?, ?), (?, ?)",
        ("old", old, "fresh", fresh),
    )

    await StatsService(db, test_settings).record_daily()

    rows = await db.fetchall("SELECT event_key FROM broadcast_log")
    assert [row["event_key"] for row in rows] == ["fresh"]
