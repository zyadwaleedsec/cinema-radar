"""Router registry imported once by ``main``."""

from __future__ import annotations

from handlers import (
    admin,
    common,
    consent,
    discovery,
    feedback,
    language,
    settings,
    support,
    watches,
)

routers = [
    common.router,
    consent.router,
    language.router,
    watches.router,
    settings.router,
    support.router,
    feedback.router,
    admin.router,
    discovery.router,
]
