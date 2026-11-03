"""The renderer-independent description of one Telegram screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Screen:
    """Everything a renderer needs, and nothing Telegram-specific.

    ``text`` is HTML so both renderers can share it.  Rich messages simply
    wrap the same markup in ``InputRichMessage(html=..., is_rtl=True)``.
    """

    text: str
    keyboard: Any = None
    photo_url: str | None = None
    is_rtl: bool = True
