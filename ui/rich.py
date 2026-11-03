"""Rich-message renderer (Bot API 10.3), with a lazy import for safety."""

from __future__ import annotations

from typing import Any

from ui.screen import Screen

try:  # pragma: no cover - exercised in production
    from aiogram.types import InputRichMessage
except Exception:  # pragma: no cover - lets core tests run without aiogram
    InputRichMessage = None  # type: ignore[assignment]


def build(screen: Screen) -> Any | None:
    """Return an ``InputRichMessage``, or ``None`` when unsupported."""

    if InputRichMessage is None:
        return None
    return InputRichMessage(html=screen.text, is_rtl=screen.is_rtl)
