"""Manual donations: pending proof, admin approval and rejection."""

from __future__ import annotations

import pytest

from support import SupportService


class FakeSender:
    def __init__(self):
        self.sent = []

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))


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
