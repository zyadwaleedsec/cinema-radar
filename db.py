"""SQLite persistence layer (aiosqlite, parameterised SQL only)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    is_supporter INTEGER NOT NULL DEFAULT 0,
    watch_limit INTEGER NOT NULL DEFAULT 2,
    notify_cancellations INTEGER NOT NULL DEFAULT 1,
    quiet_start INTEGER,
    quiet_end INTEGER,
    quiet_watches INTEGER NOT NULL DEFAULT 1,
    onboarded INTEGER NOT NULL DEFAULT 0,
    lang TEXT,
    consent_at TEXT,
    consent_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    date TEXT NOT NULL,
    movie_id TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    poster_url TEXT,
    duration_minutes INTEGER,
    rating TEXT,
    language TEXT,
    synopsis TEXT,
    trailer_url TEXT,
    scope TEXT NOT NULL DEFAULT 'showtime',
    showtime TEXT NOT NULL,
    hall_type TEXT NOT NULL,
    booking_url TEXT,
    alert_mode TEXT NOT NULL DEFAULT 'all',
    snoozed_until TEXT,
    last_status TEXT,
    last_seats INTEGER,
    required_seats INTEGER NOT NULL DEFAULT 1,
    baseline_done INTEGER NOT NULL DEFAULT 0,
    imax_status TEXT,
    expires_at TEXT,
    deactivated_at TEXT,
    expiry_notified INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    last_alert_at TEXT,
    group_id TEXT,
    time_window TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, provider, branch_id, date, movie_id, showtime, hall_type)
);
CREATE INDEX IF NOT EXISTS idx_watches_active ON watches(active, provider, branch_id, date, movie_id);
CREATE INDEX IF NOT EXISTS idx_watches_user ON watches(user_id, active);

CREATE TABLE IF NOT EXISTS watch_baselines (
    watch_id INTEGER NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    status TEXT,
    PRIMARY KEY (watch_id, date)
);

CREATE TABLE IF NOT EXISTS state_cache (
    target_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    etag TEXT,
    last_modified TEXT,
    body_hash TEXT,
    fetched_at REAL NOT NULL,
    ttl REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    branch_ids TEXT NOT NULL DEFAULT '[]',
    event_types TEXT NOT NULL DEFAULT '["NEW_MOVIE","NEW_DATE_OPENED","NEW_SHOWTIMES","UPCOMING_MOVIE"]',
    hall_type TEXT,
    active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions(active);

CREATE TABLE IF NOT EXISTS known_state (
    branch_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS broadcast_log (
    event_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    method TEXT NOT NULL,
    amount REAL,
    status TEXT NOT NULL,
    note TEXT,
    file_id TEXT,
    approved_at TEXT,
    approved_by INTEGER,
    below_minimum INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status, created_at);

CREATE TABLE IF NOT EXISTS bot_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id, created_at);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    alerts_sent INTEGER NOT NULL DEFAULT 0,
    active_watches INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS discovery_alerts (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS imax_overrides (
    movie_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_actions (
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    branch_id TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    date TEXT NOT NULL,
    movie_id TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'vox',
    created_at TEXT NOT NULL
);
"""


class DuplicateWatch(Exception):
    pass


class WatchLimitReached(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Database:
    def __init__(self, path: str = "cinemaradar.sqlite3") -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA cache_size=-20000")
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._conn.commit()

    async def init_schema(self) -> None:
        assert self._conn is not None
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        # ``CREATE TABLE IF NOT EXISTS`` never adds columns to an existing
        # database, so upgrade older installs in place.
        await self._ensure_column("users", "quiet_watches", "INTEGER NOT NULL DEFAULT 1")
        await self._ensure_column("users", "lang", "TEXT")
        await self._ensure_column("users", "consent_at", "TEXT")
        await self._ensure_column("users", "consent_version", "INTEGER NOT NULL DEFAULT 0")
        onboarded_added = await self._ensure_column(
            "users", "onboarded", "INTEGER NOT NULL DEFAULT 0"
        )
        if onboarded_added:
            # Existing users should not be shown first-run onboarding again.
            await self.execute("UPDATE users SET onboarded = 1")
        await self._ensure_column("watches", "booking_url", "TEXT")
        await self._ensure_column("watches", "scope", "TEXT NOT NULL DEFAULT 'showtime'")
        await self._ensure_column("watches", "alert_mode", "TEXT NOT NULL DEFAULT 'all'")
        await self._ensure_column("watches", "snoozed_until", "TEXT")
        await self._ensure_column("watches", "poster_url", "TEXT")
        await self._ensure_column("watches", "duration_minutes", "INTEGER")
        await self._ensure_column("watches", "rating", "TEXT")
        await self._ensure_column("watches", "language", "TEXT")
        await self._ensure_column("watches", "synopsis", "TEXT")
        await self._ensure_column("watches", "trailer_url", "TEXT")
        await self._ensure_column("watches", "baseline_done", "INTEGER NOT NULL DEFAULT 0")
        await self._ensure_column("watches", "imax_status", "TEXT")
        await self._ensure_column("watches", "expires_at", "TEXT")
        deactivated_added = await self._ensure_column("watches", "deactivated_at", "TEXT")
        expiry_notified_added = await self._ensure_column(
            "watches", "expiry_notified", "INTEGER NOT NULL DEFAULT 0"
        )
        await self._ensure_column("watches", "group_id", "TEXT")
        await self._ensure_column("watches", "time_window", "TEXT")
        await self._ensure_column("watches", "required_seats", "INTEGER NOT NULL DEFAULT 1")
        if deactivated_added:
            # Give watches that were already closed a short grace period
            # instead of deleting them the moment the feature ships, and never
            # send a late cleanup notice for them.
            await self.execute(
                "UPDATE watches SET deactivated_at = ?, expiry_notified = 1 "
                "WHERE active = 0 AND deactivated_at IS NULL",
                (utc_now_iso(),),
            )
        elif expiry_notified_added:
            await self.execute("UPDATE watches SET expiry_notified = 1 WHERE active = 0")
        # Created after the columns above exist: a legacy ``watches`` table
        # would make ``SCHEMA`` fail if the index were declared there.
        await self.execute(
            "CREATE INDEX IF NOT EXISTS idx_watches_expiry ON watches(active, expires_at)"
        )
        await self._ensure_column("discovery_actions", "user_id", "INTEGER")
        await self._ensure_column("discovery_actions", "provider", "TEXT NOT NULL DEFAULT 'vox'")
        await self._ensure_column("donations", "approved_at", "TEXT")
        await self._ensure_column("donations", "approved_by", "INTEGER")
        await self._ensure_column("donations", "below_minimum", "INTEGER NOT NULL DEFAULT 0")
        await self.execute(
            "CREATE INDEX IF NOT EXISTS idx_watches_target "
            "ON watches(provider, branch_id, date, movie_id, active)"
        )
        await self.execute(
            "CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status, created_at)"
        )
        await self.execute("DROP TABLE IF EXISTS movie_waits")
        # Artwork scraped from a cinema site is no longer used; existing watches
        # keep working and simply render text-only until a TMDB poster is known.
        await self.execute(
            "UPDATE watches SET poster_url = NULL "
            "WHERE poster_url LIKE '%voxcinemas.com%' "
            "OR poster_url LIKE '%rnscinemas.com%' "
            "OR poster_url LIKE '%rnscinemas.net%'"
        )
        await self._migrate_subscription_event_types()
        await self._migrate_subscription_branch_ids()

    async def _migrate_subscription_event_types(self) -> None:
        """Add the Coming Soon release event to rows holding the old default.

        Only the exact previous "all types" list is upgraded, so a user who
        deliberately chose a subset is never opted into a new alert silently.
        """

        old_default = {"NEW_MOVIE", "NEW_DATE_OPENED", "NEW_SHOWTIMES"}
        rows = await self.fetchall("SELECT id, event_types FROM subscriptions")
        for row in rows:
            try:
                types = json.loads(row["event_types"] or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(types, list) or set(types) != old_default:
                continue
            types.append("UPCOMING_MOVIE")
            await self.execute(
                "UPDATE subscriptions SET event_types = ? WHERE id = ?",
                (json.dumps(types, ensure_ascii=False), row["id"]),
            )

    async def _migrate_subscription_branch_ids(self) -> None:
        """Prefix legacy branch filters with ``vox:`` once.

        Before multi-cinema support the branch filter stored plain branch ids
        (all of which belonged to VOX).  New rows store ``provider:branch``
        keys; upgrade existing rows in place behind a one-time marker.
        """

        if await self.get_meta("branch_ids_v2") == "done":
            return
        rows = await self.fetchall("SELECT id, branch_ids FROM subscriptions")
        for row in rows:
            try:
                ids = json.loads(row["branch_ids"] or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(ids, list):
                continue
            migrated = [
                item if (isinstance(item, str) and ":" in item) else f"vox:{item}" for item in ids
            ]
            if migrated != ids:
                await self.execute(
                    "UPDATE subscriptions SET branch_ids = ? WHERE id = ?",
                    (json.dumps(migrated, ensure_ascii=False), row["id"]),
                )
        await self.set_meta("branch_ids_v2", "done")

    async def _ensure_column(self, table: str, column: str, ddl: str) -> bool:
        columns = await self.fetchall(f"PRAGMA table_info({table})")
        if column in {row["name"] for row in columns}:
            return False
        await self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        return True

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        async with self._write_lock:
            cur = await self.conn.execute(sql, params)
            await self.conn.commit()
            return cur

    async def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        async with self._write_lock:
            await self.conn.executemany(sql, rows)
            await self.conn.commit()

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        cur = await self.conn.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return _row(row)

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cur = await self.conn.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return [dict(r) for r in rows]

    async def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = 0) -> Any:
        cur = await self.conn.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        if row is None:
            return default
        value = row[0]
        return default if value is None else value

    # ------------------------------------------------------------------ users
    async def get_or_create_user(self, telegram_id: int, watch_limit: int = 2) -> dict[str, Any]:
        existing = await self.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        if existing:
            return existing
        await self.execute(
            "INSERT OR IGNORE INTO users (telegram_id, watch_limit, created_at) VALUES (?, ?, ?)",
            (telegram_id, watch_limit, utc_now_iso()),
        )
        user = await self.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        assert user is not None
        return user

    async def get_user(self, telegram_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

    async def set_user_supporter(self, telegram_id: int, supporter: bool, limit: int) -> None:
        await self.execute(
            "UPDATE users SET is_supporter = ?, watch_limit = ? WHERE telegram_id = ?",
            (1 if supporter else 0, limit, telegram_id),
        )

    async def mark_user_onboarded(self, telegram_id: int) -> None:
        await self.execute("UPDATE users SET onboarded = 1 WHERE telegram_id = ?", (telegram_id,))

    async def set_user_language(self, telegram_id: int, lang: str) -> None:
        """Persist the interface language chosen in onboarding or settings."""

        await self.execute("UPDATE users SET lang = ? WHERE telegram_id = ?", (lang, telegram_id))

    async def record_user_consent(
        self,
        telegram_id: int,
        lang: str,
        watch_limit: int,
        version: int,
    ) -> dict[str, Any]:
        """Create or update the user only after explicit, informed consent."""

        await self.execute(
            """
            INSERT INTO users (telegram_id, watch_limit, lang, consent_at, consent_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                lang = excluded.lang,
                consent_at = excluded.consent_at,
                consent_version = excluded.consent_version
            """,
            (telegram_id, watch_limit, lang, utc_now_iso(), int(version), utc_now_iso()),
        )
        user = await self.get_user(telegram_id)
        assert user is not None
        return user

    async def update_user_settings(self, user_id: int, **fields: Any) -> None:
        allowed = {
            "notify_cancellations",
            "quiet_start",
            "quiet_end",
            "quiet_watches",
        }
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        assignments = ", ".join(f"{k} = ?" for k in clean)
        await self.execute(
            f"UPDATE users SET {assignments} WHERE id = ?", (*clean.values(), user_id)
        )

    async def count_supporters(self) -> int:
        return int(
            await self.scalar("SELECT COUNT(*) FROM users WHERE is_supporter = 1", default=0)
        )

    async def delete_user(self, telegram_id: int) -> bool:
        user = await self.get_user(telegram_id)
        if not user:
            return False
        async with self._write_lock:
            await self.conn.execute("DELETE FROM discovery_alerts WHERE user_id = ?", (user["id"],))
            await self.conn.execute("DELETE FROM feedback WHERE user_id = ?", (user["id"],))
            await self.conn.execute("DELETE FROM donations WHERE user_id = ?", (user["id"],))
            await self.conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user["id"],))
            await self.conn.execute("DELETE FROM watches WHERE user_id = ?", (user["id"],))
            await self.conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
            await self.conn.commit()
        return True

    # ----------------------------------------------------------------- watches
    async def trim_watches_to_limits(
        self, free_limit: int, supporter_limit: int
    ) -> list[dict[str, Any]]:
        """Apply new watch limits to existing users.

        Every user keeps their soonest screenings; anything above the new limit
        is deactivated silently (``expiry_notified`` set, so no cleanup notice).
        Returns one row per affected user with the removed count.
        """

        await self.execute(
            "UPDATE users SET watch_limit = CASE WHEN is_supporter = 1 THEN ? ELSE ? END",
            (supporter_limit, free_limit),
        )
        users = await self.fetchall("SELECT id, telegram_id, is_supporter, lang FROM users")
        now = utc_now_iso()
        trimmed: list[dict[str, Any]] = []
        for user in users:
            limit = supporter_limit if int(user["is_supporter"] or 0) else free_limit
            rows = await self.fetchall(
                """
                SELECT id FROM watches
                WHERE user_id = ? AND active = 1
                ORDER BY (expires_at IS NULL), expires_at, date, showtime, id
                """,
                (user["id"],),
            )
            excess = [int(row["id"]) for row in rows[limit:]]
            if not excess:
                continue
            placeholders = ",".join("?" for _ in excess)
            await self.execute(
                f"""
                UPDATE watches
                SET active = 0, deactivated_at = ?, expiry_notified = 1
                WHERE id IN ({placeholders})
                """,
                (now, *excess),
            )
            trimmed.append(
                {
                    "telegram_id": int(user["telegram_id"]),
                    "removed": len(excess),
                    "limit": limit,
                }
            )
        return trimmed

    async def count_active_watches(self, user_id: int) -> int:
        """Number of active logical watches.  Rows sharing a ``group_id`` (the
        cross-cinema window flow creates one per branch) count as a single watch."""

        return int(
            await self.scalar(
                "SELECT COUNT(DISTINCT COALESCE(group_id, 'id:' || id)) "
                "FROM watches WHERE user_id = ? AND active = 1",
                (user_id,),
                default=0,
            )
        )

    async def add_watch(
        self,
        user_id: int,
        provider: str,
        branch_id: str,
        branch_name: str,
        date: str,
        movie_id: str,
        movie_name: str,
        showtime: str,
        hall_type: str,
        watch_limit: int,
        booking_url: str | None = None,
        alert_mode: str = "all",
        scope: str = "showtime",
        poster_url: str | None = None,
        duration_minutes: int | None = None,
        rating: str | None = None,
        language: str | None = None,
        synopsis: str | None = None,
        trailer_url: str | None = None,
        imax_status: str | None = None,
        expires_at: str | None = None,
        required_seats: int = 1,
    ) -> int:
        count = await self.count_active_watches(user_id)
        if count >= watch_limit:
            raise WatchLimitReached
        return await self._insert_watch(
            user_id=user_id,
            provider=provider,
            branch_id=branch_id,
            branch_name=branch_name,
            date=date,
            movie_id=movie_id,
            movie_name=movie_name,
            showtime=showtime,
            hall_type=hall_type,
            booking_url=booking_url,
            alert_mode=alert_mode,
            scope=scope,
            poster_url=poster_url,
            duration_minutes=duration_minutes,
            rating=rating,
            language=language,
            synopsis=synopsis,
            trailer_url=trailer_url,
            imax_status=imax_status,
            expires_at=expires_at,
            required_seats=required_seats,
        )

    async def add_watch_group(
        self, user_id: int, watch_limit: int, entries: list[dict[str, Any]]
    ) -> list[int]:
        """Insert a cross-cinema window watch as one logical watch.

        Each entry is one branch's row; they share a ``group_id`` so the limit
        counts them as a single watch.
        """

        count = await self.count_active_watches(user_id)
        if count >= watch_limit:
            raise WatchLimitReached
        ids: list[int] = list(
            await asyncio.gather(
                *(self._insert_watch(user_id=user_id, **entry) for entry in entries)
            )
        )
        return ids

    async def _insert_watch(
        self,
        *,
        user_id: int,
        provider: str,
        branch_id: str,
        branch_name: str,
        date: str,
        movie_id: str,
        movie_name: str,
        showtime: str,
        hall_type: str,
        booking_url: str | None = None,
        alert_mode: str = "all",
        scope: str = "showtime",
        poster_url: str | None = None,
        duration_minutes: int | None = None,
        rating: str | None = None,
        language: str | None = None,
        synopsis: str | None = None,
        trailer_url: str | None = None,
        imax_status: str | None = None,
        expires_at: str | None = None,
        group_id: str | None = None,
        time_window: str | None = None,
        required_seats: int = 1,
    ) -> int:
        try:
            cur = await self.execute(
                """
                INSERT INTO watches (
                    user_id, provider, branch_id, branch_name, date, movie_id,
                    movie_name, poster_url, duration_minutes, rating, language,
                    synopsis, trailer_url, imax_status, expires_at,
                    scope, showtime, hall_type, booking_url,
                    alert_mode, group_id, time_window, required_seats, active, created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?
                )
                """,
                (
                    user_id,
                    provider,
                    branch_id,
                    branch_name,
                    date,
                    movie_id,
                    movie_name,
                    poster_url,
                    duration_minutes,
                    rating,
                    language,
                    synopsis,
                    trailer_url,
                    imax_status,
                    expires_at,
                    scope,
                    showtime,
                    hall_type,
                    booking_url,
                    alert_mode,
                    group_id,
                    time_window,
                    required_seats,
                    utc_now_iso(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateWatch from exc
        return int(cur.lastrowid or 0)

    async def list_watches(self, user_id: int, active_only: bool = True) -> list[dict[str, Any]]:
        clause = "AND active = 1" if active_only else ""
        return await self.fetchall(
            f"SELECT * FROM watches WHERE user_id = ? {clause} ORDER BY date, showtime, id",
            (user_id,),
        )

    async def get_watch(self, watch_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM watches WHERE id = ?", (watch_id,))

    async def deactivate_watch(self, watch_id: int, user_id: int | None = None) -> bool:
        now = utc_now_iso()
        if user_id is None:
            cur = await self.execute(
                "UPDATE watches SET active = 0, deactivated_at = ?, expiry_notified = 1 "
                "WHERE id = ? AND active = 1",
                (now, watch_id),
            )
        else:
            cur = await self.execute(
                "UPDATE watches SET active = 0, deactivated_at = ?, expiry_notified = 1 "
                "WHERE id = ? AND user_id = ? AND active = 1",
                (now, watch_id, user_id),
            )
        return cur.rowcount > 0

    async def deactivate_all_watches(self, user_id: int) -> int:
        cur = await self.execute(
            "UPDATE watches SET active = 0, deactivated_at = ?, expiry_notified = 1 "
            "WHERE user_id = ? AND active = 1",
            (utc_now_iso(), user_id),
        )
        return cur.rowcount

    async def deactivate_watches_for_telegram(self, telegram_id: int) -> int:
        cur = await self.execute(
            """
            UPDATE watches SET active = 0, deactivated_at = ?, expiry_notified = 1
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?) AND active = 1
            """,
            (utc_now_iso(), telegram_id),
        )
        return cur.rowcount

    async def set_watch_expires_at(self, watch_id: int, expires_at: str) -> None:
        await self.execute(
            "UPDATE watches SET expires_at = ? WHERE id = ? AND active = 1",
            (expires_at, watch_id),
        )

    async def active_watches_missing_expiry(self, limit: int = 500) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT * FROM watches
            WHERE active = 1 AND expires_at IS NULL AND date <> '*'
            ORDER BY id LIMIT ?
            """,
            (limit,),
        )

    async def active_expired_watches(self, now_iso: str) -> list[dict[str, Any]]:
        """Due watches plus earlier closures whose notice never went out."""

        return await self.fetchall(
            """
            SELECT w.*, u.telegram_id, u.lang
            FROM watches w JOIN users u ON u.id = w.user_id
            WHERE w.expiry_notified = 0
              AND (
                  (w.active = 1 AND w.expires_at IS NOT NULL AND w.expires_at <= ?)
                  OR (w.active = 0 AND w.deactivated_at IS NOT NULL AND w.deactivated_at <= ?)
              )
            ORDER BY w.user_id, w.id
            """,
            (now_iso, now_iso),
        )

    async def expire_watch(self, watch_id: int, now_iso: str) -> bool:
        """Close one watch when its event has passed, keeping the first time it closed."""

        cur = await self.execute(
            """
            UPDATE watches
            SET active = 0, deactivated_at = COALESCE(deactivated_at, ?)
            WHERE id = ? AND active = 1
            """,
            (now_iso, watch_id),
        )
        return cur.rowcount > 0

    async def mark_watch_expiry_notified(self, watch_id: int) -> None:
        await self.execute("UPDATE watches SET expiry_notified = 1 WHERE id = ?", (watch_id,))

    async def delete_inactive_watches(self, cutoff_iso: str) -> int:
        """Hard-delete closed watches after the retention window.

        ``watch_baselines`` rows disappear through ``ON DELETE CASCADE``.
        """

        cur = await self.execute(
            """
            DELETE FROM watches
            WHERE active = 0 AND COALESCE(deactivated_at, created_at) <= ?
            """,
            (cutoff_iso,),
        )
        return cur.rowcount

    async def close_past_date_watches(self, today_iso: str, now_iso: str) -> int:
        cur = await self.execute(
            """
            UPDATE watches
            SET active = 0, deactivated_at = COALESCE(deactivated_at, ?),
                expiry_notified = 1
            WHERE active = 1 AND date < ? AND date <> '*'
            """,
            (now_iso, today_iso),
        )
        return cur.rowcount

    async def movie_names_for_id(self, movie_id: str) -> list[str]:
        rows = await self.fetchall(
            "SELECT DISTINCT movie_name FROM watches WHERE movie_id = ?", (movie_id,)
        )
        return [str(row["movie_name"]) for row in rows if row.get("movie_name")]

    async def count_movie_watchers(self, provider: str, movie_id: str) -> int:
        """How many distinct users are tracking this movie at a cinema chain.

        Only ``active`` watches count, so the number reflects people who would
        currently receive an alert.  The same user watching three showtimes of
        the same movie counts once.
        """

        return int(
            await self.scalar(
                """
                SELECT COUNT(DISTINCT user_id) FROM watches
                WHERE active = 1 AND provider = ? AND movie_id = ?
                """,
                (provider, movie_id),
                default=0,
            )
        )

    async def set_movie_imax_status(self, movie_id: str, status: str) -> int:
        cur = await self.execute(
            "UPDATE watches SET imax_status = ? WHERE movie_id = ? AND active = 1",
            (status, movie_id),
        )
        return cur.rowcount

    async def set_imax_override(self, movie_id: str, status: str) -> None:
        """Persist an admin override for watches created after a restart."""

        await self.execute(
            """
            INSERT INTO imax_overrides (movie_id, status, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(movie_id) DO UPDATE SET status = excluded.status
            """,
            (movie_id, status, utc_now_iso()),
        )

    async def get_imax_override(self, movie_id: str) -> str | None:
        row = await self.fetchone(
            "SELECT status FROM imax_overrides WHERE movie_id = ?", (movie_id,)
        )
        return str(row["status"]) if row else None

    async def active_watches_for_target(
        self, provider: str, branch_id: str, date: str, movie_id: str
    ) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT w.*, u.telegram_id, u.quiet_start, u.quiet_end,
                   u.notify_cancellations, u.quiet_watches, u.lang
            FROM watches w JOIN users u ON u.id = w.user_id
            WHERE w.active = 1 AND w.provider = ?
              AND (w.branch_id = ? OR w.branch_id = '*')
              AND (w.date = ? OR w.date = '*')
              AND w.movie_id = ?
            ORDER BY w.id
            """,
            (provider, branch_id, date, movie_id),
        )

    async def active_watch_targets(self) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT provider, branch_id, date, movie_id, branch_name, movie_name,
                   COUNT(*) AS watch_count
            FROM watches WHERE active = 1 AND date <> '*'
            GROUP BY provider, branch_id, date, movie_id
            """
        )

    async def active_all_dates_watches(self) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT * FROM watches
            WHERE active = 1 AND date = '*' AND scope = 'movie_all_dates'
            ORDER BY id
            """
        )

    async def get_watch_baseline(self, watch_id: int, date: str) -> dict[str, Any] | None:
        return await self.fetchone(
            "SELECT * FROM watch_baselines WHERE watch_id = ? AND date = ?",
            (watch_id, date),
        )

    async def set_watch_baseline(self, watch_id: int, date: str, status: str | None) -> None:
        await self.execute(
            """
            INSERT INTO watch_baselines (watch_id, date, status) VALUES (?, ?, ?)
            ON CONFLICT(watch_id, date) DO UPDATE SET status = excluded.status
            """,
            (watch_id, date, status),
        )

    async def mark_watch_baseline_done(self, watch_id: int) -> None:
        await self.execute(
            "UPDATE watches SET baseline_done = 1 WHERE id = ? AND baseline_done = 0",
            (watch_id,),
        )

    async def count_watch_baselines(self, watch_id: int) -> int:
        return int(
            await self.scalar(
                "SELECT COUNT(*) FROM watch_baselines WHERE watch_id = ?",
                (watch_id,),
                default=0,
            )
        )

    async def prune_watch_baselines(self, before_date: str) -> None:
        await self.execute("DELETE FROM watch_baselines WHERE date < ?", (before_date,))

    async def count_all_active_watches(self) -> int:
        return int(await self.scalar("SELECT COUNT(*) FROM watches WHERE active = 1", default=0))

    async def update_watch_state(
        self, watch_id: int, status: str | None, seats: int | None
    ) -> None:
        await self.execute(
            "UPDATE watches SET last_status = ?, last_seats = ? WHERE id = ?",
            (status, seats, watch_id),
        )

    async def mark_watch_alert(self, watch_id: int, at: str | None = None) -> None:
        await self.execute(
            "UPDATE watches SET last_alert_at = ? WHERE id = ?",
            (at or utc_now_iso(), watch_id),
        )

    async def set_watch_alert_mode(self, watch_id: int, user_id: int, mode: str) -> bool:
        cur = await self.execute(
            "UPDATE watches SET alert_mode = ? WHERE id = ? AND user_id = ? AND active = 1",
            (mode, watch_id, user_id),
        )
        return cur.rowcount > 0

    async def set_watch_required_seats(self, watch_id: int, user_id: int, seats: int) -> bool:
        cur = await self.execute(
            "UPDATE watches SET required_seats = ? WHERE id = ? AND user_id = ? AND active = 1",
            (seats, watch_id, user_id),
        )
        return cur.rowcount > 0

    async def snooze_watch(self, watch_id: int, user_id: int, until: str) -> bool:
        cur = await self.execute(
            "UPDATE watches SET snoozed_until = ? WHERE id = ? AND user_id = ? AND active = 1",
            (until, watch_id, user_id),
        )
        return cur.rowcount > 0

    async def clear_watch_snooze(self, watch_id: int) -> None:
        await self.execute(
            "UPDATE watches SET snoozed_until = NULL WHERE id = ? AND snoozed_until IS NOT NULL",
            (watch_id,),
        )

    async def list_due_snoozes(self, now_iso: str) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT w.*, u.telegram_id, u.quiet_start, u.quiet_end, u.quiet_watches, u.lang
            FROM watches w JOIN users u ON u.id = w.user_id
            WHERE w.active = 1 AND w.snoozed_until IS NOT NULL AND w.snoozed_until <= ?
            ORDER BY w.id
            """,
            (now_iso,),
        )

    # ------------------------------------------------------------ subscriptions
    async def get_subscription(self, user_id: int) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))

    async def upsert_subscription(
        self,
        user_id: int,
        branch_ids: list[str],
        event_types: list[str],
        hall_type: str | None,
        active: bool,
    ) -> None:
        await self.execute(
            """
            INSERT INTO subscriptions (user_id, branch_ids, event_types, hall_type, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                branch_ids = excluded.branch_ids,
                event_types = excluded.event_types,
                hall_type = excluded.hall_type,
                active = excluded.active
            """,
            (
                user_id,
                json.dumps(branch_ids, ensure_ascii=False),
                json.dumps(event_types, ensure_ascii=False),
                hall_type,
                1 if active else 0,
                utc_now_iso(),
            ),
        )

    async def set_subscription_active(self, user_id: int, active: bool) -> None:
        await self.execute(
            "UPDATE subscriptions SET active = ? WHERE user_id = ?",
            (1 if active else 0, user_id),
        )

    async def deactivate_subscription_for_telegram(self, telegram_id: int) -> None:
        await self.execute(
            """
            UPDATE subscriptions SET active = 0
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?)
            """,
            (telegram_id,),
        )

    async def list_active_subscriptions(self) -> list[dict[str, Any]]:
        return await self.fetchall(
            """
            SELECT s.*, u.telegram_id, u.quiet_start, u.quiet_end, u.is_supporter, u.lang
            FROM subscriptions s JOIN users u ON u.id = s.user_id
            WHERE s.active = 1
            """
        )

    # -------------------------------------------------------------------- cache
    async def set_cache_row(
        self,
        key: str,
        payload: str,
        etag: str | None,
        last_modified: str | None,
        body_hash: str | None,
        fetched_at: float,
        ttl: float,
    ) -> None:
        await self.execute(
            """
            INSERT INTO state_cache (target_key, payload, etag, last_modified, body_hash, fetched_at, ttl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_key) DO UPDATE SET
                payload = excluded.payload,
                etag = excluded.etag,
                last_modified = excluded.last_modified,
                body_hash = excluded.body_hash,
                fetched_at = excluded.fetched_at,
                ttl = excluded.ttl
            """,
            (key, payload, etag, last_modified, body_hash, fetched_at, ttl),
        )

    # -------------------------------------------------------------- known state
    async def get_known_state(self, branch_id: str) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM known_state WHERE branch_id = ?", (branch_id,))

    async def set_known_state(self, branch_id: str, payload: str, updated_at: float) -> None:
        await self.execute(
            """
            INSERT INTO known_state (branch_id, payload, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(branch_id) DO UPDATE SET
                payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (branch_id, payload, updated_at),
        )

    # ------------------------------------------------------------ broadcast log
    async def mark_broadcast(self, event_key: str) -> bool:
        """Return True if this call inserted the key (i.e. first time)."""

        cur = await self.execute(
            "INSERT OR IGNORE INTO broadcast_log (event_key, created_at) VALUES (?, ?)",
            (event_key, utc_now_iso()),
        )
        return cur.rowcount > 0

    # ---------------------------------------------------------------- donations
    async def create_donation(
        self,
        user_id: int,
        method: str,
        amount: float | None,
        status: str,
        note: str | None = None,
        file_id: str | None = None,
        below_minimum: bool = False,
    ) -> int:
        cur = await self.execute(
            """
            INSERT INTO donations
                (user_id, method, amount, status, note, file_id,
                 below_minimum, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                method,
                amount,
                status,
                note,
                file_id,
                1 if below_minimum else 0,
                utc_now_iso(),
            ),
        )
        return int(cur.lastrowid or 0)

    async def get_donation(self, donation_id: int) -> dict[str, Any] | None:
        return await self.fetchone(
            """
            SELECT d.*, u.telegram_id, u.is_supporter
            FROM donations d JOIN users u ON u.id = d.user_id
            WHERE d.id = ?
            """,
            (donation_id,),
        )

    async def approve_donation(
        self, donation_id: int, admin_id: int, supporter_limit: int
    ) -> tuple[bool, int | None]:
        """Mark a pending donation approved and grant the supporter limit once.

        Returns ``(changed, telegram_id)``.  ``changed`` is False when the row is
        missing or was already handled, which makes a double tap harmless.
        """

        async with self._write_lock:
            cur = await self.conn.execute(
                """
                SELECT d.status, u.telegram_id, u.id AS internal_id
                FROM donations d JOIN users u ON u.id = d.user_id
                WHERE d.id = ?
                """,
                (donation_id,),
            )
            row = await cur.fetchone()
            await cur.close()
            if row is None or row["status"] != "pending":
                return False, int(row["telegram_id"]) if row is not None else None
            await self.conn.execute(
                """
                UPDATE donations
                SET status = 'approved', approved_at = ?, approved_by = ?
                WHERE id = ? AND status = 'pending'
                """,
                (utc_now_iso(), admin_id, donation_id),
            )
            await self.conn.execute(
                "UPDATE users SET is_supporter = 1, watch_limit = ? WHERE id = ?",
                (supporter_limit, row["internal_id"]),
            )
            await self.conn.commit()
        return True, int(row["telegram_id"])

    async def reject_donation(self, donation_id: int, admin_id: int) -> tuple[bool, int | None]:
        async with self._write_lock:
            cur = await self.conn.execute(
                """
                SELECT d.status, u.telegram_id
                FROM donations d JOIN users u ON u.id = d.user_id
                WHERE d.id = ?
                """,
                (donation_id,),
            )
            row = await cur.fetchone()
            await cur.close()
            if row is None or row["status"] != "pending":
                return False, int(row["telegram_id"]) if row is not None else None
            await self.conn.execute(
                """
                UPDATE donations
                SET status = 'rejected', approved_at = ?, approved_by = ?
                WHERE id = ? AND status = 'pending'
                """,
                (utc_now_iso(), admin_id, donation_id),
            )
            await self.conn.commit()
        return True, int(row["telegram_id"])

    # --------------------------------------------------------------------- meta
    async def get_meta(self, key: str) -> str | None:
        row = await self.fetchone("SELECT value FROM bot_meta WHERE key = ?", (key,))
        return str(row["value"]) if row else None

    async def set_meta(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO bot_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ----------------------------------------------------------------- feedback
    async def add_feedback(self, user_id: int, username: str | None, text: str) -> int:
        cur = await self.execute(
            "INSERT INTO feedback (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, text, utc_now_iso()),
        )
        return int(cur.lastrowid or 0)

    async def last_feedback_at(self, user_id: int) -> str | None:
        row = await self.fetchone(
            "SELECT created_at FROM feedback WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return row["created_at"] if row else None

    # -------------------------------------------------------------- daily stats
    async def increment_alerts_sent(self, day: str | None = None) -> None:
        day = day or date_cls.today().isoformat()
        await self.execute(
            """
            INSERT INTO daily_stats (date, alerts_sent, active_watches, active_users)
            VALUES (?, 1, 0, 0)
            ON CONFLICT(date) DO UPDATE SET alerts_sent = alerts_sent + 1
            """,
            (day,),
        )

    async def set_daily_snapshot(
        self, day: str, alerts_sent: int, active_watches: int, active_users: int
    ) -> None:
        await self.execute(
            """
            INSERT INTO daily_stats (date, alerts_sent, active_watches, active_users)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                alerts_sent = excluded.alerts_sent,
                active_watches = excluded.active_watches,
                active_users = excluded.active_users
            """,
            (day, alerts_sent, active_watches, active_users),
        )

    async def get_daily_stats(self, day: str) -> dict[str, Any] | None:
        return await self.fetchone("SELECT * FROM daily_stats WHERE date = ?", (day,))

    async def count_active_users(self) -> int:
        return int(
            await self.scalar(
                "SELECT COUNT(DISTINCT user_id) FROM watches WHERE active = 1", default=0
            )
        )

    # ------------------------------------------------------------ discovery cap
    async def get_discovery_count(self, user_id: int, day: str) -> int:
        return int(
            await self.scalar(
                "SELECT count FROM discovery_alerts WHERE user_id = ? AND date = ?",
                (user_id, day),
                default=0,
            )
        )

    async def increment_discovery_count(self, user_id: int, day: str) -> int:
        await self.execute(
            """
            INSERT INTO discovery_alerts (user_id, date, count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
            """,
            (user_id, day),
        )
        return await self.get_discovery_count(user_id, day)

    # -------------------------------------------------------- discovery actions
    async def add_discovery_action(
        self,
        token: str,
        user_id: int,
        branch_id: str,
        branch_name: str,
        date: str,
        movie_id: str,
        movie_name: str,
        provider: str = "vox",
    ) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat(timespec="seconds")
        await self.execute("DELETE FROM discovery_actions WHERE created_at < ?", (cutoff,))
        await self.execute(
            """
            INSERT OR REPLACE INTO discovery_actions
                (token, user_id, branch_id, branch_name, date, movie_id, movie_name, provider, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                user_id,
                branch_id,
                branch_name,
                date,
                movie_id,
                movie_name,
                provider,
                utc_now_iso(),
            ),
        )

    async def get_discovery_action(self, token: str) -> dict[str, Any] | None:
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat(timespec="seconds")
        return await self.fetchone(
            "SELECT * FROM discovery_actions WHERE token = ? AND created_at >= ?",
            (token, cutoff),
        )
