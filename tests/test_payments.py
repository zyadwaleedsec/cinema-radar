"""Manual donations: pending proof, admin approval and rejection."""

from __future__ import annotations

from dataclasses import replace

import pytest

import i18n
from support import SupportService


class FakeSender:
    def __init__(self):
        self.sent = []

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))


class FakeBot:
    def __init__(self):
        self.photos = []
        self.documents = []

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)


def test_each_method_can_have_its_own_account(test_settings):
    settings = replace(
        test_settings,
        donation_phone="01000000000",
        donation_vodafone="01011111111",
        donation_instapay="donate@instapay",
    )

    assert settings.donation_account("vodafone_cash") == "01011111111"
    assert settings.donation_account("instapay") == "donate@instapay"


def test_shared_number_is_the_fallback(test_settings):
    settings = replace(
        test_settings,
        donation_phone="01000000000",
        donation_vodafone="",
        donation_instapay="",
    )

    assert settings.donation_account("vodafone_cash") == "01000000000"
    assert settings.donation_account("instapay") == "01000000000"


@pytest.mark.asyncio
async def test_manual_donation_starts_pending(db, test_settings):
    await db.get_or_create_user(559, watch_limit=test_settings.free_watch_limit)
    service = SupportService(db, test_settings, FakeSender())

    donation_id = await service.create_manual(
        559, "vodafone_cash", "proof 123", file_id="file-1", amount=75
    )

    donation = await db.get_donation(donation_id)
    assert donation is not None
    assert donation["id"] == donation_id
    assert donation["status"] == "pending"
    assert donation["file_id"] == "file-1"
    assert donation["below_minimum"] == 0


@pytest.mark.asyncio
async def test_below_minimum_is_flagged_but_allowed(db, test_settings):
    await db.get_or_create_user(560, watch_limit=test_settings.free_watch_limit)
    service = SupportService(db, test_settings, FakeSender())

    donation_id = await service.create_manual(560, "instapay", "proof", amount=20)

    donation = await db.get_donation(donation_id)
    assert donation is not None
    assert donation["below_minimum"] == 1
    assert donation["status"] == "pending"


@pytest.mark.asyncio
async def test_approval_grants_supporter_once(db, test_settings):
    await db.get_or_create_user(555, watch_limit=test_settings.free_watch_limit)
    sender = FakeSender()
    service = SupportService(db, test_settings, sender)
    donation_id = await service.create_manual(555, "vodafone_cash", "proof", amount=50)

    changed, telegram_id = await service.approve(donation_id, test_settings.admin_id)
    assert changed is True
    assert telegram_id == 555

    user = await db.get_user(555)
    assert user is not None
    assert user["is_supporter"] == 1
    assert user["watch_limit"] == test_settings.supporter_watch_limit

    # A second tap must not grant again or resend the thank-you message.
    again, _ = await service.approve(donation_id, test_settings.admin_id)
    assert again is False
    thanks = [msg for msg in sender.sent if msg[0][0] == 555]
    assert len(thanks) == 1


@pytest.mark.asyncio
async def test_rejection_does_not_grant(db, test_settings):
    await db.get_or_create_user(556, watch_limit=test_settings.free_watch_limit)
    sender = FakeSender()
    service = SupportService(db, test_settings, sender)
    donation_id = await service.create_manual(556, "instapay", "proof", amount=50)

    changed, telegram_id = await service.reject(donation_id, test_settings.admin_id)
    assert changed is True
    assert telegram_id == 556

    user = await db.get_user(556)
    assert user is not None
    assert user["is_supporter"] == 0
    assert user["watch_limit"] == test_settings.free_watch_limit
    assert (await db.get_donation(donation_id))["status"] == "rejected"
    notices = [msg for msg in sender.sent if msg[0][0] == 556]
    assert len(notices) == 1


@pytest.mark.asyncio
async def test_supporter_keeps_limit_after_new_donation(db, test_settings):
    await db.get_or_create_user(557, watch_limit=test_settings.free_watch_limit)
    await db.set_user_supporter(557, True, test_settings.supporter_watch_limit)
    service = SupportService(db, test_settings, FakeSender())

    donation_id = await service.create_manual(557, "vodafone_cash", "again", amount=100)
    changed, _ = await service.approve(donation_id, test_settings.admin_id)

    assert changed is True
    user = await db.get_user(557)
    assert user is not None
    assert user["is_supporter"] == 1
    assert user["watch_limit"] == test_settings.supporter_watch_limit


@pytest.mark.asyncio
async def test_repeat_donation_is_marked_for_the_admin(db, test_settings):
    await db.get_or_create_user(558, watch_limit=test_settings.free_watch_limit)
    await db.set_user_supporter(558, True, test_settings.supporter_watch_limit)
    sender = FakeSender()
    service = SupportService(db, test_settings, sender)
    previous = i18n.admin_language()
    i18n.set_admin_language("en")
    try:
        await service.create_manual(558, "instapay", "second time", amount=75)
    finally:
        i18n.set_admin_language(previous)

    admin_text = sender.sent[-1][0][1]
    assert "already a supporter" in admin_text


@pytest.mark.asyncio
async def test_document_proof_is_forwarded_as_a_document(db, test_settings):
    await db.get_or_create_user(561, watch_limit=test_settings.free_watch_limit)
    bot = FakeBot()
    service = SupportService(db, test_settings, FakeSender(), bot)

    donation_id = await service.create_manual(
        561,
        "instapay",
        "screenshot",
        file_id="doc-1",
        amount=50,
        file_type="document",
    )

    donation = await db.get_donation(donation_id)
    assert donation is not None
    assert donation["file_type"] == "document"
    assert bot.documents and bot.documents[0]["document"] == "doc-1"
    assert bot.photos == []
