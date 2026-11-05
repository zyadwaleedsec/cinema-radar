"""Localised TMDB metadata for cards and alerts.

Provider pages are written in English, but most users read the Arabic
interface.  This service keeps the *matching* language fixed (``en-US``) and
localises only the strings the user sees.

Caching mirrors :mod:`posters`:

* a positive answer is kept for 30 days;
* a miss is retried after one day, because it may be a temporary outage.

A tiny in-process memo avoids re-reading SQLite when one screen (or one alert
batch) asks about the same movie repeatedly.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from cache import Cache
from tmdb import ARABIC_LANGUAGE, TmdbClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalizedMovie:
    title: str
    overview: str | None = None
    tmdb_id: int | None = None
    original_title: str | None = None
    year: int | None = None
    poster_path: str | None = None


def _key(title: str, year: int | None, language: str) -> str:
    raw = f"{language}:{year or ''}:{title.strip().casefold()}"
    digest = hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:32]
    return f"meta:tmdb:{digest}"


def display_language(code: object) -> str | None:
    """TMDB language for a UI language, or ``None`` when no localisation is needed."""

    value = str(code or "").strip().lower()
    if value.startswith("ar"):
        return ARABIC_LANGUAGE
    return None


class TmdbMetadataService:
    def __init__(
        self,
        client: TmdbClient,
        cache: Cache | None = None,
        ttl: int = 30 * 24 * 3600,
        negative_ttl: int = 24 * 3600,
    ) -> None:
        self._client = client
        self._cache = cache
        self._ttl = ttl
        self._negative_ttl = negative_ttl
        self._memo: dict[tuple[str, int | None, str], LocalizedMovie | None] = {}

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    def for_language(self, code: object) -> str | None:
        return display_language(code)

    async def localize(
        self,
        title: str,
        year: int | None = None,
        language: str | None = ARABIC_LANGUAGE,
    ) -> LocalizedMovie | None:
        """Return the movie with a localised title/overview, or ``None``.

        ``language=None`` means "do not localise": callers use it to keep the
        provider copy when the active interface is English.
        """

        name = (title or "").strip()
        if not name or not language or not self.enabled:
            return None
        memo_key = (name.casefold(), year, language)
        if memo_key in self._memo:
            return self._memo[memo_key]

        cache_key = _key(name, year, language)
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key, ttl=self._ttl)
            if isinstance(cached, dict):
                if cached.get("missing"):
                    self._memo[memo_key] = None
                    return None
                movie = _from_dict(cached)
                if movie is not None:
                    self._memo[memo_key] = movie
                    return movie

        movie = await self._lookup(name, year, language)
        self._memo[memo_key] = movie
        if self._cache is not None:
            if movie is None:
                await self._cache.put_json(cache_key, {"missing": True}, self._negative_ttl)
            else:
                await self._cache.put_json(cache_key, _to_dict(movie), self._ttl)
        return movie

    async def aliases(self, query: str, language: str = ARABIC_LANGUAGE) -> list[str]:
        """English/original titles behind an Arabic search query.

        Every result contributes both its localized title (what the user typed,
        roughly) and its original English title, which is what provider pages
        use.  The caller ranks those against the real cinema listings, so a
        wrong TMDB match simply produces no provider hit.
        """

        text = (query or "").strip()
        if not text or not self.enabled:
            return []
        try:
            results = await self._client.search(text, language=language, limit=10)
        except Exception:
            logger.warning("TMDB Arabic search failed for %r", text)
            return []
        names: list[str] = []
        for result in results:
            for value in (result.original_title, result.title):
                if value and value not in names:
                    names.append(value)
        return names

    async def _lookup(self, name: str, year: int | None, language: str) -> LocalizedMovie | None:
        try:
            found = await self._client.resolve(name, year)
        except Exception:
            logger.warning("TMDB metadata lookup failed for %r", name)
            return None
        if found is None:
            return None
        details = found
        if found.tmdb_id and language:
            try:
                localized = await self._client.details(found.tmdb_id, language)
            except Exception:
                localized = None
            if localized is not None:
                details = localized
        title = (details.title or found.title or name).strip()
        if not title:
            return None
        return LocalizedMovie(
            title=title,
            overview=details.overview or found.overview,
            tmdb_id=found.tmdb_id,
            original_title=details.original_title or found.original_title,
            year=details.year or found.year,
            poster_path=details.poster_path or found.poster_path,
        )


def _to_dict(movie: LocalizedMovie) -> dict[str, Any]:
    return {
        "title": movie.title,
        "overview": movie.overview,
        "tmdb_id": movie.tmdb_id,
        "original_title": movie.original_title,
        "year": movie.year,
        "poster_path": movie.poster_path,
    }


def _from_dict(data: dict[str, Any]) -> LocalizedMovie | None:
    title = str(data.get("title") or "").strip()
    if not title:
        return None
    tmdb_id = data.get("tmdb_id")
    try:
        tmdb_id = int(tmdb_id) if tmdb_id is not None else None
    except (TypeError, ValueError):
        tmdb_id = None
    return LocalizedMovie(
        title=title,
        overview=str(data.get("overview") or "").strip() or None,
        tmdb_id=tmdb_id,
        original_title=str(data.get("original_title") or "").strip() or None,
        year=data.get("year"),
        poster_path=str(data.get("poster_path") or "").strip() or None,
    )
