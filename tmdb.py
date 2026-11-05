"""Small TMDB client for canonical titles and poster images.

TMDB is not the source of truth for the IMAX indicator: its keywords do not
reliably mark films shot with IMAX cameras.  It is asked for the canonical
title/year so the local Wikipedia snapshot can be matched more accurately, and
for official poster artwork so the bot never hotlinks images scraped from a
cinema site.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"


@dataclass(frozen=True)
class TmdbMovie:
    title: str
    year: int | None
    poster_path: str | None = None


class TmdbClient:
    def __init__(
        self,
        token: str,
        timeout: float = 10.0,
        user_agent: str | None = None,
    ) -> None:
        self._token = (token or "").strip()
        self._timeout = timeout
        self._user_agent = (user_agent or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def resolve(self, title: str, year: int | None = None) -> TmdbMovie | None:
        if not self.enabled or not title.strip():
            return None
        result = await self._search(title, year)
        if result is None and year is not None:
            result = await self._search(title, None)
        return result

    async def poster(self, title: str, year: int | None = None) -> str | None:
        """Return a TMDB-hosted poster URL, or ``None`` when there is no match."""

        found = await self.resolve(title, year)
        if found is None or not found.poster_path:
            return None
        path = found.poster_path.strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{POSTER_BASE_URL}{path if path.startswith('/') else '/' + path}"

    async def _search(self, title: str, year: int | None) -> TmdbMovie | None:
        params = {
            "query": title,
            "language": "en-US",
            "include_adult": "false",
            "page": "1",
        }
        if year is not None:
            params["year"] = str(year)
        headers = {"Authorization": f"Bearer {self._token}"}
        if self._user_agent:
            headers["User-Agent"] = self._user_agent
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
            ) as client:
                response = await client.get(f"{BASE_URL}/search/movie", params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            logger.warning("TMDB title lookup failed for %r", title)
            return None
        results = payload.get("results") or []
        if not results or not isinstance(results[0], dict):
            return None
        first = results[0]
        name = str(first.get("title") or first.get("original_title") or "").strip()
        if not name:
            return None
        release = str(first.get("release_date") or "")
        release_year = int(release[:4]) if release[:4].isdigit() else None
        poster_path = str(first.get("poster_path") or "").strip() or None
        return TmdbMovie(name, release_year, poster_path)
