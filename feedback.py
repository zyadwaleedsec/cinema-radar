"""One free-text feedback message per user per hour."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import i18n
import strings
from config import Settings
from db import Database
from notifier import Notifier


class FeedbackService:
    def __init__(self, db: Database, settings: Settings, notifier: Notifier) -> None:
        self.db = db
        self.settings = settings
        self.notifier = notifier

    async def submit(
        self,
        telegram_id: int,
        username: str | None,
        text: str,
        first_name: str | None = None,
    ) -> bool:
        user = await self.db.get_or_create_user(
            telegram_id, watch_limit=self.settings.free_watch_limit
        )
        last = await self.db.last_feedback_at(int(user["id"]))
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=UTC)
                if datetime.now(UTC) - last_dt < timedelta(hours=1):
                    return False
            except (TypeError, ValueError):
                pass
        await self.db.add_feedback(int(user["id"]), username, text.strip()[:4000])
        with i18n.use(i18n.admin_language()):
            notice = strings.feedback_admin(telegram_id, username, text, first_name)
        await self.notifier.send_admin(notice)
        return True
