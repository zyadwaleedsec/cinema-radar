"""Small dependency-free helpers shared across modules.

Keeping these out of ``handlers.utils`` lets background services (broadcaster,
discovery) reuse them without importing Telegram-specific code.
"""

from __future__ import annotations

import json
from typing import Any


def json_list(raw: Any) -> list[str]:
    """Decode a JSON array (or pass through a list) as a list of strings."""

    if isinstance(raw, list):
        return [str(item) for item in raw]
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []
