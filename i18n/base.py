"""Language-neutral text helpers shared by every catalog.

Only formatting utilities live here.  Anything a user reads belongs in
``i18n/ar.py`` or ``i18n/en.py`` so translators can find it.
"""

from __future__ import annotations

import html


def esc(value: object) -> str:
    """Escape dynamic values for messages sent with ``parse_mode=HTML``."""

    return html.escape(str(value), quote=False)


def truncate(value: str, limit: int = 1000) -> str:
    """Cut long HTML without leaving a half-written tag or entity behind."""

    if len(value) <= limit:
        return value
    cut = value[: max(0, limit - 1)]
    open_angle = cut.rfind("<")
    close_angle = cut.rfind(">")
    if open_angle > close_angle:
        cut = cut[:open_angle]
    amp = cut.rfind("&")
    semi = cut.rfind(";")
    if amp > semi:
        cut = cut[:amp]
    return cut.rstrip() + "…"
