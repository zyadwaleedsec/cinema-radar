"""Shared visual tokens so every screen looks like one product.

Everything here is renderer-agnostic: box-drawing characters and block glyphs
look the same in rich messages and in the classic HTML fallback.
"""

from __future__ import annotations

#: A thin rule used under titles and between cards.
DIVIDER = "──────────"

_FILLED = "▰"
_EMPTY = "▱"


def progress(step: int, total: int) -> str:
    """Return ``▰▰▱ 2/3`` for a one-based step inside ``total``."""

    total = max(1, int(total))
    step = min(max(int(step), 1), total)
    return f"{_FILLED * step}{_EMPTY * (total - step)} {step}/{total}"
