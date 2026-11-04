"""Multi-cinema behaviour: deep links, branch filters and migration."""

from __future__ import annotations

import pytest

from handlers.watches import _parse_branch_suffix
from keyboards import branches_filter_keyboard


class _FakeProviders:
    def __init__(self, names):
        self._names = names

    def names(self):
        return tuple(self._names)

    def get(self, name):
        return _FakeProvider(name)


class _FakeProvider:
    name = "vox"

    def __init__(self, name):
        self.name = name


def _settings():
    from config import Settings

    return Settings()


def _texts(markup):
    return [
        button.text
        for row in markup.inline_keyboard
        for button in row
        if button.text and not button.text.startswith("🏠")
    ]


def test_parse_branch_suffix_new_format():
    providers = _FakeProviders(["vox", "renaissance"])
    assert _parse_branch_suffix(
        "renaissance_madinty", providers, _FakeProvider("vox"), _settings()
    ) == (
        "renaissance",
        "madinty",
    )
    assert _parse_branch_suffix(
        "vox_mall-of-egypt", providers, _FakeProvider("vox"), _settings()
    ) == (
        "vox",
        "mall-of-egypt",
    )


def test_parse_branch_suffix_legacy_defaults_to_vox():
    providers = _FakeProviders(["vox", "renaissance"])
    assert _parse_branch_suffix("mall-of-egypt", providers, _FakeProvider("vox"), _settings()) == (
        "vox",
        "mall-of-egypt",
    )


def test_branches_filter_keyboard_prefixes_provider_label():
    branches = [{"id": "madinty", "name": "Madinaty", "provider": "renaissance"}]
    texts = _texts(branches_filter_keyboard(branches, []))
    assert any("Renaissance" in text for text in texts)
    assert _texts(branches_filter_keyboard(branches, ["renaissance:madinty"]))[0].startswith("✅")


@pytest.mark.asyncio
async def test_subscription_branch_ids_migration_prefixes_plain_ids(db):
    user = await db.get_or_create_user(42)
    await db.upsert_subscription(
        int(user["id"]),
        branch_ids=["mall-of-egypt", "city-centre-almaza"],
        event_types=["NEW_MOVIE"],
        hall_type=None,
        active=True,
    )
    # The migration ran during init_schema; reset its marker to run it again.
    await db.execute("DELETE FROM bot_meta WHERE key = 'branch_ids_v2'")
    await db._migrate_subscription_branch_ids()
    sub = await db.get_subscription(int(user["id"]))
    import json

    assert json.loads(sub["branch_ids"]) == ["vox:mall-of-egypt", "vox:city-centre-almaza"]


@pytest.mark.asyncio
async def test_subscription_branch_ids_migration_is_idempotent(db):
    user = await db.get_or_create_user(43)
    await db.upsert_subscription(
        int(user["id"]),
        branch_ids=["vox:mall-of-egypt"],
        event_types=["NEW_MOVIE"],
        hall_type=None,
        active=True,
    )
    await db.execute("DELETE FROM bot_meta WHERE key = 'branch_ids_v2'")
    await db._migrate_subscription_branch_ids()
    await db._migrate_subscription_branch_ids()
    sub = await db.get_subscription(int(user["id"]))
    import json

    assert json.loads(sub["branch_ids"]) == ["vox:mall-of-egypt"]
