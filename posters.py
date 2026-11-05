"""TMDB poster lookup with a long-lived cache.

Cinema sites serve their own marketing artwork under their own terms.  The bot
therefore keeps only TMDB-hosted images and falls back to a text-only card when
TMDB has no match or no token is configured.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from cache import Cache
from tmdb import TmdbClient

logger = logging.getLogger(__name__)


def _key(title: str, year: int | None) -> str:
    raw = f"{year or ''}:{title.strip().casefold()}"
    digest = hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:32]
    return f"poster:tmdb:{digest}"


class TmdbPosterService:
    def __init__(
        self,
        client: TmdbClient,
        cache: Cache | None = None,
        ttl: int = 30 * 24 * 3600,
    ) -> None:
        self._client = client
        self._cache = cache
        self._ttl = ttl

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    async def url(self, title: str, year: int | None = None) -> str | None:
        """Return the TMDB poster for *title* (cached, including misses)."""

        name = (title or "").strip()
        if not name or not self.enabled:
            return None
        cache_key = _key(name, year)
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key, ttl=self._ttl)
            if cached is not None and isinstance(cached, dict):
                value = cached.get("url")
                return str(value) if value else None
        try:
            value = await self._client.poster(name, year)
        except Exception:
            logger.warning("TMDB poster lookup failed for %r", name)
            return None
        if self._cache is not None:
            # A negative result may be a temporary outage, so retry it sooner
            # than a confirmed poster.
            ttl = self._ttl if value else min(self._ttl, 24 * 3600)
            await self._cache.put_json(cache_key, {"url": value}, ttl)
        return value

    async def for_movie(self, movie: Any) -> str | None:
        """Convenience wrapper for a :class:`models.Movie` instance."""

        return await self.url(getattr(movie, "name", "") or "")
