"""Classic HTML renderer: the always-working path."""

from __future__ import annotations

from typing import Any

from ui.screen import Screen


def text_payload(screen: Screen) -> dict[str, Any]:
    return {
        "text": screen.text,
        "reply_markup": screen.keyboard,
        "disable_web_page_preview": True,
    }


def photo_payload(screen: Screen) -> dict[str, Any]:
    return {
        "photo": screen.photo_url,
        "caption": screen.text,
        "reply_markup": screen.keyboard,
        "parse_mode": "HTML",
    }
