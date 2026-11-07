"""Public cinema and movie pages used by alert links.

The URLs are built locally from data we already have.  Nothing here is fetched:
booking pages stay out of the bot entirely, and a link button only opens the
cinema's own public page in the user's browser.
"""

from __future__ import annotations

from urllib.parse import quote, urlsplit, urlunsplit

from models import Branch, Movie

#: Public movie page per provider.  ``{slug}`` is the identifier the provider
#: itself uses in its page URL, which is exactly what ``Movie.slug`` holds.
_MOVIE_PAGES = {
    "vox": "https://egy.voxcinemas.com/movies/{slug}",
    "renaissance": "https://rnscinemas.com/{lang}/movie/{slug}",
    "premiere": "https://www.premiere-cinemas.com/{lang}/movie-details/{slug}",
}

#: Fallback when a branch has no scraped page URL of its own.
_CINEMA_PAGES = {
    "premiere": "https://www.premiere-cinemas.com/{lang}/now-showing",
}

#: Sites that publish both languages under ``/<lang>/``.  A stored URL is
#: rewritten so an Arabic reader does not land on the English page.
_LOCALIZABLE_HOSTS = {"rnscinemas.com", "www.rnscinemas.com"}


def _site_language(lang: object) -> str:
    return "ar" if str(lang or "").strip().lower().startswith("ar") else "en"


def _localize_url(url: str, lang: str) -> str:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in _LOCALIZABLE_HOSTS:
        return url
    segments = parts.path.split("/")
    if len(segments) > 1 and segments[1] in {"ar", "en"}:
        segments[1] = _site_language(lang)
        return urlunsplit(
            (parts.scheme, parts.netloc, "/".join(segments), parts.query, parts.fragment)
        )
    return url


def movie_page_url(movie: Movie, lang: str = "en") -> str | None:
    """Public movie page, or ``None`` when the provider has no known pattern."""

    template = _MOVIE_PAGES.get(movie.provider)
    slug = (movie.slug or movie.id or "").strip()
    if not template or not slug:
        return None
    return template.format(
        slug=quote(slug, safe=".-_~"),
        lang=_site_language(lang),
    )


def cinema_page_url(branch: Branch, lang: str = "en") -> str | None:
    """The branch's own public page, with a provider listing as fallback."""

    if branch.url:
        return _localize_url(branch.url, lang)
    template = _CINEMA_PAGES.get(branch.provider)
    if not template:
        return None
    return template.format(lang=_site_language(lang))
