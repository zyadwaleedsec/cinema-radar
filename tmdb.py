"""Small TMDB client for canonical titles, posters and localised copy.

TMDB is not the source of truth for the IMAX indicator: its keywords do not
reliably mark films shot with IMAX cameras.  It is asked for the canonical
title/year so the local Wikipedia snapshot can be matched more accurately, for
official poster artwork so the bot never hotlinks images scraped from a cinema
site, and for Arabic display strings (title and overview).

Matching always stays in English (``en-US``).  Only the display copy is
localised, so the IMAX lookup, dedupe and provider matching keep working
exactly as before.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

#: The language used for Arabic display copy.  TMDB calls Saudi Arabic
#: ``ar-SA``; it is the closest match for Egyptian cinema listings.
ARABIC_LANGUAGE = "ar-SA"
ENGLISH_LANGUAGE = "en-US"


@dataclass(frozen=True)
class TmdbMovie:
    title: str
    year: int | None
    poster_path: str | None = None
    tmdb_id: int | None = None
    original_title: str | None = None
    overview: str | None = None


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

    async def search(
        self,
        query: str,
        language: str = ENGLISH_LANGUAGE,
        limit: int = 10,
    ) -> list[TmdbMovie]:
        """Return search results in ``language`` (used for Arabic name lookup)."""

        if not self.enabled or not query.strip():
            return []
        payload = await self._get(
            "/search/movie",
            {
                "query": query,
                "language": language,
                "include_adult": "false",
                "page": "1",
            },
        )
        if payload is None:
            return []
        results = payload.get("results") or []
        movies: list[TmdbMovie] = []
        for item in results:
            movie = _parse_movie(item)
            if movie is not None:
                movies.append(movie)
            if len(movies) >= max(limit, 1):
                break
        return movies

    async def details(self, tmdb_id: int, language: str = ARABIC_LANGUAGE) -> TmdbMovie | None:
        """Fetch one title in ``language`` (title + overview)."""

        if not self.enabled or not tmdb_id:
            return None
        payload = await self._get(f"/movie/{int(tmdb_id)}", {"language": language})
        if payload is None or not isinstance(payload, dict):
            return None
        return _parse_movie(payload)

    async def _search(self, title: str, year: int | None) -> TmdbMovie | None:
        params: dict[str, str] = {
            "query": title,
            "language": ENGLISH_LANGUAGE,
            "include_adult": "false",
            "page": "1",
        }
        if year is not None:
            params["year"] = str(year)
        payload = await self._get("/search/movie", params)
        if payload is None:
            return None
        results = payload.get("results") or []
        if not results or not isinstance(results[0], dict):
            return None
        return _parse_movie(results[0])

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        headers = {"Authorization": f"Bearer {self._token}"}
        if self._user_agent:
            headers["User-Agent"] = self._user_agent
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
            ) as client:
                response = await client.get(f"{BASE_URL}{path}", params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            logger.warning("TMDB request failed for %s", path)
            return None
        return payload if isinstance(payload, dict) else None


def _parse_movie(raw: Any) -> TmdbMovie | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("title") or raw.get("original_title") or "").strip()
    if not name:
        return None
    release = str(raw.get("release_date") or "")
    release_year = int(release[:4]) if release[:4].isdigit() else None
    poster_path = str(raw.get("poster_path") or "").strip() or None
    tmdb_id = raw.get("id")
    try:
        tmdb_id = int(tmdb_id) if tmdb_id is not None else None
    except (TypeError, ValueError):
        tmdb_id = None
    original = str(raw.get("original_title") or "").strip() or None
    overview = str(raw.get("overview") or "").strip() or None
    return TmdbMovie(
        name,
        release_year,
        poster_path,
        tmdb_id=tmdb_id,
        original_title=original,
        overview=overview,
    )
