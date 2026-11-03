"""Router registry imported once by ``main``."""

from __future__ import annotations

from handlers import admin, common, discovery, feedback, settings, support, watches

routers = [
    common.router,
    watches.router,
    settings.router,
    support.router,
    feedback.router,
    admin.router,
    discovery.router,
]
