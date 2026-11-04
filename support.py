"""Voluntary support: one-off manual Vodafone Cash / InstaPay donations.

Telegram Stars are intentionally not supported.  A donation is recorded as
``pending`` and only becomes a supporter grant after the admin taps Approve.
"""

from __future__ import annotations

import logging
from typing import Any

import i18n
import strings
from config import Settings
from db import Database
from notifier import TelegramSender

logger = logging.getLogger(__name__)


class SupportService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        sender: TelegramSender,
        bot: Any | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.sender = sender
        self.bot = bot

    # ------------------------------------------------------------------ manual
    async def create_manual(
        self,
        telegram_id: int,
        method: str,
        note: str,
        file_id: str | None = None,
        amount: float | None = None,
    ) -> int:
        user = await self.db.get_or_create_user(
            telegram_id, watch_limit=self.settings.free_watch_limit
        )
        below_minimum = bool(amount is not None and amount < self.settings.donation_min_amount)
        donation_id = await self.db.create_donation(
            user_id=int(user["id"]),
            method=method,
            amount=amount,
            status="pending",
            note=note,
            file_id=file_id,
            below_minimum=below_minimum,
        )
        await self._notify_admin_donation(
            donation_id, telegram_id, method, amount, note, file_id, below_minimum
        )
        return donation_id

    async def _notify_admin_donation(
        self,
        donation_id: int,
        telegram_id: int,
        method: str,
        amount: float | None,
        note: str,
        file_id: str | None,
        below_minimum: bool = False,
    ) -> None:
        from keyboards import donation_admin_keyboard

        with i18n.use(i18n.admin_language()):
            text = strings.support_admin_new(
                donation_id,
                telegram_id,
                method,
                amount,
                note,
                self.settings.donation_min_amount,
                below_minimum,
            )
        if not self.settings.admin_id:
            return
        keyboard = donation_admin_keyboard(donation_id)
        if file_id and self.bot is not None:
            try:
                await self.bot.send_photo(
                    chat_id=self.settings.admin_id,
                    photo=file_id,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                return
            except Exception:
                logger.exception("Could not forward donation proof")
        try:
            await self.sender.send(self.settings.admin_id, text, reply_markup=keyboard)
        except Exception:
            logger.exception("Could not notify admin about donation")

    # ----------------------------------------------------------------- decision
    async def approve(self, donation_id: int, admin_id: int) -> tuple[bool, int | None]:
        changed, telegram_id = await self.db.approve_donation(
            donation_id, admin_id, self.settings.supporter_watch_limit
        )
        if changed and telegram_id is not None:
            donation = await self.db.get_donation(donation_id)
            amount = donation.get("amount") if donation else None
            user = await self.db.get_user(telegram_id)
            with i18n.use((user or {}).get("lang")):
                text = strings.support_approved(amount, self.settings.supporter_watch_limit)
            try:
                await self.sender.send(telegram_id, text)
            except Exception:
                logger.exception("Could not thank the supporter")
        return changed, telegram_id

    async def reject(self, donation_id: int, admin_id: int) -> tuple[bool, int | None]:
        changed, telegram_id = await self.db.reject_donation(donation_id, admin_id)
        if changed and telegram_id is not None:
            user = await self.db.get_user(telegram_id)
            with i18n.use((user or {}).get("lang")):
                text = strings.support_rejected()
            try:
                await self.sender.send(telegram_id, text)
            except Exception:
                logger.exception("Could not inform a rejected donor")
        return changed, telegram_id

    # ------------------------------------------------------------------- admin
    async def grant(self, telegram_id: int) -> bool:
        user = await self.db.get_user(telegram_id)
        if not user:
            return False
        await self.db.set_user_supporter(telegram_id, True, self.settings.supporter_watch_limit)
        return True

    async def revoke(self, telegram_id: int) -> bool:
        user = await self.db.get_user(telegram_id)
        if not user:
            return False
        await self.db.set_user_supporter(telegram_id, False, self.settings.free_watch_limit)
        return True
