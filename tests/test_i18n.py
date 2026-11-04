"""The bilingual interface: catalog parity, the gate, and versioning."""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from aiogram.types import Chat, Message, User

import deeplinks
import i18n
import strings
import version
from middleware import LanguageMiddleware
from ui import render
from ui.screen import Screen

ARABIC = re.compile(r"[\u0600-\u06FF]")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


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


# --------------------------------------------------------------------- catalogs


def test_catalogs_expose_the_same_public_functions():
    ar = i18n.for_language("ar")
    en = i18n.for_language("en")
    public = {
        name
        for name, value in vars(ar).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }
    mirror = {
        name
        for name, value in vars(en).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }
    assert public == mirror


def test_catalog_signatures_never_drift():
    ar = i18n.for_language("ar")
    en = i18n.for_language("en")
    for name in sorted(vars(ar)):
        if name.startswith("_"):
            continue
        left = getattr(ar, name)
        if not inspect.isfunction(left):
            continue
        assert inspect.signature(left) == inspect.signature(getattr(en, name)), name


def test_both_catalogs_declare_their_identity():
    assert i18n.for_language("ar").CODE == "ar"
    assert i18n.for_language("en").CODE == "en"
    assert i18n.for_language("ar").RTL is True
    assert i18n.for_language("en").RTL is False
    assert i18n.LANGUAGE_NAMES == {"ar": "العربية", "en": "English"}


def test_english_copy_has_no_arabic_except_the_bilingual_picker():
    en = i18n.for_language("en")
    for name, value in vars(en).items():
        if name.startswith("_") or name in {"NAME", "BTN_ARABIC"}:
            continue
        if isinstance(value, str):
            assert not ARABIC.search(value), f"{name} leaks Arabic"
        elif isinstance(value, (tuple, list)):
            for item in value:
                items = item if isinstance(item, tuple) else (item,)
                for part in items:
                    if isinstance(part, str):
                        assert not ARABIC.search(part), f"{name} leaks Arabic"

    # Every zero-argument screen is pure English; the picker is intentionally
    # bilingual so a brand-new user can recognize their own language.
    for name, value in vars(en).items():
        if name.startswith("_") or not inspect.isfunction(value):
            continue
        signature = inspect.signature(value)
        if any(
            parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        ):
            continue
        result = value()
        if name != "language_screen" and isinstance(result, str):
            assert not ARABIC.search(result), f"{name}() leaks Arabic"

    assert ARABIC.search(en.language_screen())


def test_normalize_handles_telegram_locales():
    assert i18n.normalize("ar") == "ar"
    assert i18n.normalize("ar-EG") == "ar"
    assert i18n.normalize("en") == "en"
    assert i18n.normalize("en-US") == "en"
    assert i18n.normalize("en_GB") == "en"
    assert i18n.normalize("fr") == "ar"
    assert i18n.normalize("") == "ar"
    assert i18n.normalize(None) == "ar"


def test_use_is_scoped_and_always_restored():
    i18n.set_language("ar")
    with i18n.use("en"):
        assert i18n.get_language() == "en"
        assert strings.BTN_BACK == i18n.for_language("en").BTN_BACK
    assert i18n.get_language() == "ar"
    assert strings.BTN_BACK == i18n.for_language("ar").BTN_BACK


def test_onboarding_copy_is_resolved_per_language():
    from handlers import common

    assert all(isinstance(name, str) for name in common.ONBOARD_SCREENS)
    i18n.set_language("en")
    try:
        for name in common.ONBOARD_SCREENS:
            screen = getattr(strings, name)
            text = screen("Tester") if name == "onboard_intro" else screen()
            assert not ARABIC.search(text), name
    finally:
        i18n.set_language("ar")


def test_admin_language_defaults_to_arabic():
    i18n.set_admin_language("en")
    try:
        assert i18n.admin_language() == "en"
        asser = i18n.for_language(i18n.admin_language())
        assert asser.CODE == "en"
    finally:
        i18n.set_admin_language("ar")
    assert i18n.admin_language() == "ar"


# ------------------------------------------------------------------------- gate


@pytest.mark.asyncio
async def test_first_message_is_blocked_by_the_language_picker(db, test_settings):
    deeplinks.clear()
    event = _message(5, "/start b12")
    visited = False
    answers: list[str] = []

    async def handler(event, data):
        nonlocal visited
        visited = True

    async def fake_answer(self, text, **kwargs):
        answers.append(text)

    gate = LanguageMiddleware(db, test_settings)
    with patch.object(Message, "answer", fake_answer):
        await gate(handler, event, {"event_from_user": event.from_user})

    assert visited is False
    assert answers and "Choose your language" in answers[0]
    assert deeplinks.take(5) == "b12"


@pytest.mark.asyncio
async def test_deep_link_payload_is_only_parked_until_language_is_chosen(db, test_settings):
    deeplinks.clear()
    event = _message(6, "/start w42")

    async def handler(event, data):
        pass

    async def fake_answer(self, text, **kwargs):
        pass

    gate = LanguageMiddleware(db, test_settings)
    with patch.object(Message, "answer", fake_answer):
        await gate(handler, event, {"event_from_user": event.from_user})

    await db.set_user_language(6, "en")
    seen: dict[str, object] = {}

    async def chosen(event, data):
        seen.update(data)

    with patch.object(Message, "answer", fake_answer):
        await gate(chosen, event, {"event_from_user": event.from_user})

    assert seen["lang"] == "en"
    assert i18n.get_language() == "en"
    assert deeplinks.take(6) == "w42"


@pytest.mark.asyncio
async def test_admin_skips_the_gate_and_uses_arabic(db, test_settings):
    event = _message(test_settings.admin_id)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    gate = LanguageMiddleware(db, test_settings)
    await gate(handler, event, {"event_from_user": event.from_user})

    assert called is True
    assert i18n.get_language() == "ar"


# ---------------------------------------------------------------------- render


def test_freshness_state_is_rendered_in_the_current_language():
    try:
        i18n.set_language("en")
        render.set_freshness_state(15, True)
        english = render._decorate(Screen(text="menu")).text
        assert "VOX is unavailable" in english

        i18n.set_language("ar")
        arabic = render._decorate(Screen(text="menu")).text
        assert "VOX مش متاح" in arabic
    finally:
        render.set_freshness_state(0, False)
        i18n.set_language("ar")


# --------------------------------------------------------------------- version


def test_version_is_semver():
    assert SEMVER.fullmatch(version.__version__)
    assert version.__version__ == version.VERSION
    assert version.RELEASE_NAME


def test_changelog_documents_the_current_version():
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    assert changelog.exists()
    assert f"## [{version.__version__}]" in changelog.read_text(encoding="utf-8")


def test_version_is_shown_to_users():
    i18n.set_language("en")
    try:
        assert version.__version__ in strings.version_line()
        assert version.__version__ in strings.settings_text(
            True, 0, 0, False, 0, [], None, True, "en"
        )
    finally:
        i18n.set_language("ar")
