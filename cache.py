"""Two-level cache: in-process memory backed by SQLite.

The SQLite copy is important: after a restart the bot must not stampede VOX
with requests just because memory is empty.  Menus read only from this cache.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from db import Database


@dataclass
class CacheEntry:
    key: str
    payload: str
    fetched_at: float
    ttl: float
    etag: str | None = None
    last_modified: str | None = None
    body_hash: str | None = None

    def age(self, now: float | None = None) -> float:
        return (now if now is not None else time.time()) - self.fetched_at

    def is_fresh(self, now: float | None = None) -> bool:
        return self.age(now) < self.ttl

    def json(self) -> Any:
        return json.loads(self.payload)


class Cache:
    def __init__(self, db: Database, now=time.time, max_stale: float = 7 * 24 * 3600) -> None:
        self.db = db
        self._memory: dict[str, CacheEntry] = {}
        self._now = now
        self.max_stale = max_stale
        self.hits = 0
        self.misses = 0
        self.stale_hits = 0

    async def load(self) -> int:
        """Restore the SQLite cache after a restart.

        Entries that expired longer than ``max_stale`` ago are deleted first:
        they can never be served, and loading them would waste memory.
        """

        await self.sweep()
        rows = await self.db.fetchall("SELECT * FROM state_cache")
        for row in rows:
            self._memory[row["target_key"]] = CacheEntry(
                key=row["target_key"],
                payload=row["payload"],
                fetched_at=float(row["fetched_at"]),
                ttl=float(row["ttl"]),
                etag=row["etag"],
                last_modified=row["last_modified"],
                body_hash=row["body_hash"],
            )
        return len(rows)

    async def sweep(self) -> int:
        """Drop entries expired more than ``max_stale`` seconds ago."""

        cutoff = self._now() - self.max_stale
        for key, entry in list(self._memory.items()):
            if entry.fetched_at + entry.ttl < cutoff:
                del self._memory[key]
        cur = await self.db.execute("DELETE FROM state_cache WHERE fetched_at + ttl < ?", (cutoff,))
        return max(int(cur.rowcount or 0), 0)

    async def get(
        self, key: str, ttl: float | None = None, allow_stale: bool = False
    ) -> CacheEntry | None:
        entry = self._memory.get(key)
        if entry is None:
            self.misses += 1
            return None
        effective_ttl = entry.ttl if ttl is None else ttl
        if entry.age(self._now()) < effective_ttl:
            self.hits += 1
            return entry
        if allow_stale:
            if entry.age(self._now()) <= effective_ttl + self.max_stale:
                self.stale_hits += 1
                return entry
            self.misses += 1
            return None
        self.misses += 1
        return None

    async def get_json(
        self, key: str, ttl: float | None = None, allow_stale: bool = False
    ) -> Any | None:
        entry = await self.get(key, ttl=ttl, allow_stale=allow_stale)
        if entry is None:
            return None
        try:
            return entry.json()
        except (TypeError, ValueError):
            return None

    async def put(
        self,
        key: str,
        payload: str,
        ttl: float,
        etag: str | None = None,
        last_modified: str | None = None,
        body_hash: str | None = None,
        fetched_at: float | None = None,
    ) -> CacheEntry:
        now = self._now() if fetched_at is None else fetched_at
        entry = CacheEntry(
            key=key,
            payload=payload,
            fetched_at=now,
            ttl=ttl,
            etag=etag,
            last_modified=last_modified,
            body_hash=body_hash,
        )
        self._memory[key] = entry
        await self.db.set_cache_row(
            key=key,
            payload=payload,
            etag=etag,
            last_modified=last_modified,
            body_hash=body_hash,
            fetched_at=now,
            ttl=ttl,
        )
        return entry

    async def put_json(self, key: str, value: Any, ttl: float, **meta: Any) -> CacheEntry:
        return await self.put(key, json.dumps(value, ensure_ascii=False), ttl, **meta)

    async def touch(self, key: str, fetched_at: float | None = None) -> None:
        entry = self._memory.get(key)
        if entry is None:
            return
        entry.fetched_at = self._now() if fetched_at is None else fetched_at
        await self.db.set_cache_row(
            key=key,
            payload=entry.payload,
            etag=entry.etag,
            last_modified=entry.last_modified,
            body_hash=entry.body_hash,
            fetched_at=entry.fetched_at,
            ttl=entry.ttl,
        )

    async def clear(self) -> None:
        self._memory.clear()
        await self.db.execute("DELETE FROM state_cache")

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0

    def __len__(self) -> int:
        return len(self._memory)


# Cache-key helpers shared by provider, watcher and bot menus.
# Bump this when the parsed shape changes so old entries are ignored instead
# of being served with missing sessions or stale movie names.
_PARSER_VERSION = "v4"


def branches_key(provider: str) -> str:
    return f"{provider}:branches"


def dates_key(provider: str, branch_id: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:dates:{branch_id}"


def movies_key(provider: str, branch_id: str, date: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:movies:{branch_id}:{date}"


def showtimes_key(provider: str, branch_id: str, date: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:showtimes:{branch_id}:{date}"


def overview_key(provider: str, branch_id: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:overview:{branch_id}"


def snapshot_key(provider: str, branch_id: str, date: str, movie_id: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:snapshot:{branch_id}:{date}:{movie_id}"


def coming_soon_key(provider: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:comingsoon"


def prebook_dates_key(provider: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:prebook"


def prebook_movies_key(provider: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:prebookmovies"


def movie_details_key(provider: str, slug: str) -> str:
    return f"{provider}:{_PARSER_VERSION}:movie:{slug}"


def alert_key(target_key: str, event: str, showtime_key: str) -> str:
    return f"alert:{target_key}:{event}:{showtime_key}"
