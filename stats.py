"""Internal counters and the admin dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_cls
from typing import Any

import strings
from config import Settings
from db import Database
from timeutil import today_iso


class StatsService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        http: Any | None = None,
        cache: Any | None = None,
        scheduler: Any | None = None,
        discovery: Any | None = None,
        broadcaster: Any | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.http = http
        self.cache = cache
        self.scheduler = scheduler
        self.discovery = discovery
        self.broadcaster = broadcaster
        self._alerts_today = 0
        self._alerts_day = today_iso(settings.timezone)

    def _roll_day(self) -> None:
        today = today_iso(self.settings.timezone)
        if today != self._alerts_day:
            self._alerts_day = today
            self._alerts_today = 0

    def note_alert(self) -> None:
        self._roll_day()
        self._alerts_today += 1

    def note_broadcast(self) -> None:
        self._roll_day()
        self._alerts_today += 1

    async def record_daily(self, day: str | None = None) -> None:
        day = day or today_iso(self.settings.timezone)
        row = await self.db.get_daily_stats(day)
        alerts = int(row["alerts_sent"]) if row else self._alerts_today
        if self._alerts_today > alerts:
            alerts = self._alerts_today
        await self.db.set_daily_snapshot(
            day,
            alerts_sent=alerts,
            active_watches=await self.db.count_all_active_watches(),
            active_users=await self.db.count_active_users(),
        )
        cutoff = (
            date_cls.fromisoformat(day) - timedelta(days=self.settings.daily_stats_days)
        ).isoformat()
        await self.db.execute("DELETE FROM daily_stats WHERE date < ?", (cutoff,))
        broadcast_cutoff = (
            datetime.now(UTC) - timedelta(days=self.settings.broadcast_log_days)
        ).isoformat(timespec="seconds")
        await self.db.execute("DELETE FROM broadcast_log WHERE created_at < ?", (broadcast_cutoff,))

    async def admin_metrics(self) -> dict[str, Any]:
        last_poll = "—"
        if self.http is not None:
            if self.http.last_error:
                last_poll = f"{self.http.last_status or 'ERR'} / {self.http.last_error}"
            elif self.http.last_status:
                last_poll = str(self.http.last_status)
        discovery_last = "—"
        if self.discovery is not None and self.discovery.last_run:
            latest = max(self.discovery.last_run.values())
            discovery_last = datetime.fromtimestamp(latest, tz=UTC).strftime("%Y-%m-%d %H:%M")
        return {
            "active_users": await self.db.count_active_users(),
            "active_watches": await self.db.count_all_active_watches(),
            "supporters": await self.db.count_supporters(),
            "requests_per_minute": self.http.requests_per_minute if self.http else 0.0,
            "cache_hit_ratio": self.cache.hit_ratio if self.cache else 0.0,
            "active_targets": len(self.scheduler) if self.scheduler else 0,
            "slowdown_factor": self.http.slowdown_factor if self.http else 1.0,
            "circuit_state": self.http.circuit_state if self.http else "closed",
            "last_poll_status": last_poll,
            "discovery_last_run": discovery_last,
            "events_today": self.discovery.events_today if self.discovery else 0,
            "broadcasts_sent": self.broadcaster.sent if self.broadcaster else 0,
            "queue_length": self.broadcaster.queue_length if self.broadcaster else 0,
        }

    async def admin_text(self) -> str:
        return strings.admin_text(await self.admin_metrics())
