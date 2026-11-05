"""Consent gate, safe/identified User-Agents and TMDB poster behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from aiogram.types import Chat, Message, User

import consent
import i18n
from config import (
    BOT_CONTACT_EMAIL,
    BOT_NAME,
    DEFAULT_USER_AGENT,
    IDENTIFIED_USER_AGENT,
    Settings,
    upstream_user_agent,
)
from handlers import consent as consent_handler
from http_client import HttpClient
from middleware import LanguageMiddleware
from models import Movie
from posters import TmdbPosterService
from tmdb import TmdbClient


@pytest.fixture(autouse=True)
def _reset_consent_state():
    consent.clear_all()
    yield
    consent.clear_all()


def _message(user_id: int, text: str = "/start", language_code: str = "en") -> Message:
    return Message(
        message_id=1,
        date=datetime.fromtimestamp(0, UTC),
        chat=Chat(id=user_id, type="private"),
        from_user=User(
            id=user_id,
            is_bot=False,
            first_name="Tester",
            language_code=language_code,
        ),
        text=text,
    )


class _FakeCallback:
    def __init__(self, user_id: int, data: str) -> None:
        self.data = data
        self.message = object()
        self.from_user = User(id=user_id, is_bot=False, first_name="Tester")


class _FakeState:
    async def clear(self) -> None:
        pass


# --------------------------------------------------------------------- gate


@pytest.mark.asyncio
async def test_language_choice_does_not_create_a_user_before_consent(db, test_settings):
    from handlers import language

    seen: list[str] = []

    async def fake_edit(callback, text, keyboard=None, photo_url=None):
        seen.append(text)

    async def fake_answer(callback, text=None, alert=False):
        pass

    with (
        patch.object(language, "edit", fake_edit),
        patch.object(language, "answer", fake_answer),
    ):
        await language.language_chosen(
            _FakeCallback(21, "lang:set:en"), _FakeState(), db, test_settings
        )

    assert await db.get_user(21) is None
    assert seen and "Consent to store your data" in seen[0]
    assert consent.pending_language(21) == "en"


@pytest.mark.asyncio
async def test_consent_accept_creates_the_user_with_a_version(db, test_settings):
    consent.remember_pending_language(22, "en")
    i18n.set_language("en")

    edits: list[str] = []

    async def fake_edit(callback, text, keyboard=None, photo_url=None):
        edits.append(text)

    async def fake_answer(callback, text=None, alert=False):
        pass

    with (
        patch.object(consent_handler, "edit", fake_edit),
        patch.object(consent_handler, "answer", fake_answer),
    ):
        await consent_handler.consent_accepted(_FakeCallback(22, "consent:yes"), db, test_settings)

    user = await db.get_user(22)
    assert user is not None
    assert user["lang"] == "en"
    assert user["consent_version"] == consent.CONSENT_VERSION
    assert user["consent_at"]
    assert user["onboarded"] == 0
    assert consent.pending_language(22) is None
    assert edits and "Welcome, Tester" in edits[0]
    i18n.set_language("ar")


@pytest.mark.asyncio
async def test_existing_pre_consent_user_keeps_the_new_language_until_agreeing(db, test_settings):
    from handlers import language

    await db.get_or_create_user(26, watch_limit=test_settings.free_watch_limit)
    await db.set_user_language(26, "ar")

    async def fake_edit(callback, text, keyboard=None, photo_url=None):
        pass

    async def fake_answer(callback, text=None, alert=False):
        pass

    with (
        patch.object(language, "edit", fake_edit),
        patch.object(language, "answer", fake_answer),
    ):
        await language.language_chosen(
            _FakeCallback(26, "lang:set:en"), _FakeState(), db, test_settings
        )

    stored = await db.get_user(26)
    assert stored is not None and stored["lang"] == "ar"
    assert stored["consent_version"] == 0
    assert consent.pending_language(26) == "en"

    async def fake_consent_edit(callback, text, keyboard=None, photo_url=None):
        pass

    with (
        patch.object(consent_handler, "edit", fake_consent_edit),
        patch.object(consent_handler, "answer", fake_answer),
    ):
        await consent_handler.consent_accepted(_FakeCallback(26, "consent:yes"), db, test_settings)

    stored = await db.get_user(26)
    assert stored is not None
    assert stored["lang"] == "en"
    assert stored["consent_version"] == consent.CONSENT_VERSION
    i18n.set_language("ar")


@pytest.mark.asyncio
async def test_consent_decline_stores_nothing(db, test_settings):
    consent.remember_pending_language(23, "en")
    i18n.set_language("en")

    async def fake_edit(callback, text, keyboard=None, photo_url=None):
        pass

    async def fake_answer(callback, text=None, alert=False):
        pass

    with (
        patch.object(consent_handler, "edit", fake_edit),
        patch.object(consent_handler, "answer", fake_answer),
    ):
        await consent_handler.consent_declined(_FakeCallback(23, "consent:no"))

    assert await db.get_user(23) is None
    # The in-memory language stays so "review consent" can re-open the screen.
    assert consent.pending_language(23) == "en"
    i18n.set_language("ar")


@pytest.mark.asyncio
async def test_existing_user_without_consent_is_blocked(db, test_settings):
    await db.get_or_create_user(24, watch_limit=test_settings.free_watch_limit)
    await db.set_user_language(24, "en")
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    event = _message(24, "/add")

    async def fake_answer(self, text, **kwargs):
        pass

    gate = LanguageMiddleware(db, test_settings)
    with patch.object(Message, "answer", fake_answer):
        await gate(handler, event, {"event_from_user": event.from_user})

    assert called is False
    assert i18n.get_language() == "en"


@pytest.mark.asyncio
async def test_privacy_stays_available_before_consent(db, test_settings):
    await db.get_or_create_user(25, watch_limit=test_settings.free_watch_limit)
    await db.set_user_language(25, "en")
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    gate = LanguageMiddleware(db, test_settings)
    await gate(handler, _message(25, "/privacy"), {"event_from_user": _message(25).from_user})

    assert called is True


def test_consent_version_gate():
    assert consent.has_consent({"consent_version": consent.CONSENT_VERSION})
    assert not consent.has_consent({"consent_version": 0})
    assert not consent.has_consent(None)


# ----------------------------------------------------------------- user agent


def test_default_user_agent_is_safe_for_cinema_wafs():
    # VOX resets any UA containing '@', '://' or 'bot'; keep it browser-shaped.
    assert Settings().http_user_agent == DEFAULT_USER_AGENT
    assert "CinemaRadar" in DEFAULT_USER_AGENT
    assert "@" not in DEFAULT_USER_AGENT
    assert "://" not in DEFAULT_USER_AGENT
    assert "bot" not in DEFAULT_USER_AGENT.lower()


def test_identified_user_agent_names_the_bot_and_contact():
    assert BOT_NAME in IDENTIFIED_USER_AGENT
    assert BOT_CONTACT_EMAIL in IDENTIFIED_USER_AGENT
    assert Settings().tmdb_user_agent == IDENTIFIED_USER_AGENT


def test_unsafe_user_agent_override_falls_back_to_the_safe_default():
    assert upstream_user_agent(IDENTIFIED_USER_AGENT) == DEFAULT_USER_AGENT
    assert upstream_user_agent("MyBot/1.0") == DEFAULT_USER_AGENT
    assert upstream_user_agent(DEFAULT_USER_AGENT) == DEFAULT_USER_AGENT


@pytest.mark.asyncio
async def test_http_client_sends_safe_headers_and_contact(cache, test_settings):
    client = HttpClient(test_settings, cache)
    try:
        headers = client.session.headers
        assert headers["User-Agent"] == test_settings.http_user_agent
        # The contact still travels with every request, just not in the UA.
        assert headers["From"] == BOT_CONTACT_EMAIL
        assert headers["X-Bot-Name"] == BOT_NAME
        assert headers["X-Bot-Contact"] == BOT_CONTACT_EMAIL
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tmdb_client_sends_the_identified_user_agent():
    sent: dict[str, str] = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "Dune", "release_date": "2021-09-15"}]}

    class _Client:
        def __init__(self, headers, timeout):
            sent.update(headers)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return _Response()

    with patch("tmdb.httpx.AsyncClient", _Client):
        await TmdbClient("token", user_agent=IDENTIFIED_USER_AGENT).resolve("Dune")

    assert sent["User-Agent"] == IDENTIFIED_USER_AGENT


def test_imax_tmdb_client_uses_the_identified_user_agent(monkeypatch):
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    import imax
    import tmdb

    monkeypatch.setattr(tmdb, "TmdbClient", _Client)
    imax.load_default_service()

    # The IMAX normaliser talks to TMDB, so it must identify the bot and the
    # contact address; only cinema requests need the browser-shaped UA.
    assert captured["user_agent"] == Settings().tmdb_user_agent


# --------------------------------------------------------------------- posters


@pytest.mark.asyncio
async def test_poster_service_caches_tmdb_lookups(cache):
    calls: list[str] = []

    class _Client:
        enabled = True

        async def poster(self, title, year=None):
            calls.append(title)
            return f"https://image.tmdb.org/t/p/w500/{title}.jpg"

    service = TmdbPosterService(_Client(), cache)
    first = await service.url("Dune")
    second = await service.url("dune")

    assert first == "https://image.tmdb.org/t/p/w500/Dune.jpg"
    assert second == first
    assert calls == ["Dune"]


@pytest.mark.asyncio
async def test_poster_service_is_disabled_without_a_token(cache):
    service = TmdbPosterService(TmdbClient(""), cache)
    assert await service.url("Dune") is None


def test_provider_drops_scraped_artwork():
    from providers.vox import _without_scraped_posters

    movie = Movie("HO1", "Dune", "dune", poster_url="https://assets.voxcinemas.com/p1.jpg")
    assert _without_scraped_posters([movie])[0].poster_url is None


@pytest.mark.asyncio
async def test_movie_movies_get_a_tmdb_poster():
    from providers.vox import VoxProvider

    class _Posters:
        async def url(self, title, year=None):
            return f"https://image.tmdb.org/t/p/w500/{title}.jpg"

    provider = VoxProvider(object(), object(), Settings(), posters=_Posters())
    movie = Movie("HO1", "Dune", "dune", poster_url="https://assets.voxcinemas.com/p1.jpg")
    official = await provider._official_poster(movie)

    assert official.poster_url == "https://image.tmdb.org/t/p/w500/Dune.jpg"


@pytest.mark.asyncio
async def test_tmdb_poster_url_is_built_from_the_path():
    class _Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "title": "Dune",
                        "release_date": "2021-09-15",
                        "poster_path": "/dune.jpg",
                    }
                ]
            }

    class _Client:
        def __init__(self, headers, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return _Response()

    with patch("tmdb.httpx.AsyncClient", _Client):
        url = await TmdbClient("token").poster("Dune")

    assert url == "https://image.tmdb.org/t/p/w500/dune.jpg"
