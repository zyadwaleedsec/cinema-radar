"""Resolve whether a movie was actually shot with IMAX cameras.

The source of truth is a local snapshot of Wikipedia's *List of IMAX films*
(``data/imax_films.json``).  Wikipedia is never fetched at runtime.  TMDB is an
optional fallback used only to normalise an ambiguous VOX title; it is not used
to decide whether a film is an IMAX film.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FULL_70MM = "FULL_70MM"
PARTIAL_70MM = "PARTIAL_70MM"
CERTIFIED_DIGITAL = "CERTIFIED_DIGITAL"
PARTIAL_DIGITAL = "PARTIAL_DIGITAL"
UNKNOWN = "UNKNOWN"

IMAX_CATEGORIES = (FULL_70MM, PARTIAL_70MM, CERTIFIED_DIGITAL, PARTIAL_DIGITAL)

_NON_WORD_RE = re.compile(r"[^0-9a-z\u0600-\u06ff]+")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(value: object) -> str:
    """Normalise a movie title for matching across VOX and Wikipedia."""

    text = html.unescape(str(value or ""))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold().replace("&", " and ")
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    return text


@dataclass(frozen=True)
class ImaxFilm:
    title: str
    year: int | None
    category: str


class ImaxService:
    """Look up a movie title in the local IMAX snapshot."""

    def __init__(
        self,
        films: list[ImaxFilm],
        tmdb: Any | None = None,
        cache: Any | None = None,
    ) -> None:
        self._films = films
        self._tmdb = tmdb
        self._cache = cache
        self._index: dict[str, list[ImaxFilm]] = {}
        self._memo: dict[str, str] = {}
        self._overrides: dict[str, str] = {}
        for film in films:
            self._index.setdefault(normalize_title(film.title), []).append(film)

    @classmethod
    def from_path(
        cls, path: str | Path, tmdb: Any | None = None, cache: Any | None = None
    ) -> ImaxService:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        films = [
            ImaxFilm(
                title=str(item.get("title") or ""),
                year=int(item["year"]) if item.get("year") else None,
                category=str(item.get("category") or UNKNOWN),
            )
            for item in payload.get("films", [])
            if item.get("title")
        ]
        return cls(films, tmdb=tmdb, cache=cache)

    def match(self, title: str, year: int | None = None) -> ImaxFilm | None:
        candidates = self._index.get(normalize_title(title))
        if not candidates:
            return None
        if year is not None:
            exact = [film for film in candidates if film.year == year]
            if exact:
                return exact[0]
            nearby = [film for film in candidates if film.year and abs(film.year - year) <= 1]
            if nearby:
                return nearby[0]
            return None
        # Without a year, prefer the newest listed film with this title.  The
        # snapshot only contains titles that are actually IMAX films, so this
        # cannot invent a match for a film that is not in the list.
        return max(candidates, key=lambda film: film.year or 0)

    def remember(self, title: str, status: str) -> None:
        """Apply an admin override for future watches of this title."""

        normalized = normalize_title(title)
        self._overrides[normalized] = status
        prefix = f"{normalized}|"
        self._memo = {key: value for key, value in self._memo.items() if not key.startswith(prefix)}

    async def lookup(self, title: str, year: int | None = None, cache: Any | None = None) -> str:
        override = self._overrides.get(normalize_title(title))
        if override:
            return override
        key = f"{normalize_title(title)}|{year or ''}"
        if key in self._memo:
            return self._memo[key]
        store = cache or self._cache
        cache_key = f"imax:status:{key}"
        if store is not None:
            cached = await store.get_json(cache_key)
            if cached:
                self._memo[key] = str(cached)
                return str(cached)

        film = self.match(title, year)
        if film is None and self._tmdb is not None:
            resolved = await self._tmdb.resolve(title, year)
            if resolved is not None:
                film = self.match(resolved.title, resolved.year)

        status = film.category if film is not None else UNKNOWN
        self._memo[key] = status
        if store is not None:
            await store.put_json(cache_key, status, ttl=30 * 24 * 3600)
        return status


def load_default_service(cache: Any | None = None) -> ImaxService:
    """Build the process-wide service from the configured snapshot and token."""

    from config import settings
    from tmdb import TmdbClient

    path = Path(settings.imax_data_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    tmdb = TmdbClient(
        settings.tmdb_read_token,
        timeout=settings.tmdb_timeout,
        user_agent=settings.http_user_agent,
    )
    return ImaxService.from_path(path, tmdb=tmdb, cache=cache)
