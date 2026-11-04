"""User-facing copy, resolved to the language of the current context.

Historically this module held every Arabic string.  It is now a facade over
:mod:`i18n.ar` and :mod:`i18n.en` so existing code keeps using
``strings.something(...)`` while the active catalog follows the user's choice.

The language is set per update by :class:`middleware.LanguageMiddleware`; background
senders use ``with i18n.use(lang):``.  See :mod:`i18n` for the details.
"""

from __future__ import annotations

from typing import Any

import i18n
from i18n.base import esc, truncate

__all__ = ["catalog", "command_list", "esc", "truncate"]


def __getattr__(name: str) -> Any:
    """Resolve copy from the active catalog at call time.

    Module-level ``__getattr__`` keeps ``strings.dashboard(...)`` working for
    the ~340 existing call sites without importing a frozen copy of the
    active language.
    """

    return getattr(i18n.catalog(), name)


def catalog(lang: object = None) -> Any:
    """Explicit catalog for code that runs outside a request context."""

    return i18n.catalog(lang)


def command_list(kind: str, lang: object = None) -> tuple[tuple[str, str], ...]:
    """Command menu for ``kind`` (``public`` / ``admin``) in ``lang``."""

    source = "PUBLIC_COMMANDS" if kind == "public" else "ADMIN_COMMANDS"
    return getattr(i18n.catalog(lang), source)
