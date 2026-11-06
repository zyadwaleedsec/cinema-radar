"""Cinema Radar entry point: long polling, background jobs, graceful shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import sys
import time
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent, MenuButtonCommands

import i18n
import strings
from broadcaster import Broadcaster
from cache import Cache
from config import settings
from db import Database
from discovery import DiscoveryJob
from feedback import FeedbackService
from handlers import routers
from http_client import HttpClient
from imax import load_default_service
from metadata import TmdbMetadataService
from middleware import LanguageMiddleware, RateLimitMiddleware
from notifier import Notifier, TelegramSender
from posters import TmdbPosterService
from providers import (
    PremiereProvider,
    ProviderRegistry,
    RenaissanceProvider,
    VoxProvider,
)
from scheduler import Scheduler
from stats import StatsService
from support import SupportService
from timeutil import local_now
from tmdb import TmdbClient
from ui.render import set_freshness_state
from version import __version__
from watcher import Watcher

logger = logging.getLogger(__name__)

_BOT_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")


def _redact(text: str) -> str:
    """Hide bot tokens that can appear inside request URLs or exceptions."""

    return _BOT_TOKEN_RE.sub("bot<redacted>", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def _commands(pairs: tuple[tuple[str, str], ...]) -> list[BotCommand]:
    return [BotCommand(command=name, description=description) for name, description in pairs]


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def run() -> None:
    setup_logging(settings.log_level)
    if not settings.bot_token:
        logger.error("BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")
        raise SystemExit(1)
    if not settings.admin_id:
        logger.warning("ADMIN_ID is missing: admin alerts and admin commands will be disabled.")

    db = Database(settings.db_path)
    await db.connect()
    await db.init_schema()
    cache = Cache(db, max_stale=settings.cache_stale_ttl)
    loaded = await cache.load()
    logger.info("Cache loaded from SQLite: %s entries", loaded)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sender = TelegramSender(bot, settings)
    tmdb = TmdbClient(
        settings.tmdb_read_token,
        timeout=settings.tmdb_timeout,
        user_agent=settings.tmdb_user_agent,
    )
    metadata = TmdbMetadataService(tmdb, cache)
    notifier = Notifier(sender, db, settings, metadata=metadata)
    http = HttpClient(settings, cache, on_admin_message=notifier.send_admin)
    posters = TmdbPosterService(tmdb, cache, ttl=settings.cache_poster_ttl)
    imax = None
    if "vox" in settings.providers:
        try:
            imax = load_default_service(cache)
        except Exception:
            logger.exception("IMAX snapshot could not be loaded; the indicator is disabled")
            imax = None

    def _provider(name: str) -> Any:
        if name == "renaissance":
            return RenaissanceProvider(http, cache, settings, posters=posters)
        if name == "premiere":
            return PremiereProvider(http, cache, settings, posters=posters)
        return VoxProvider(http, cache, settings, posters=posters)

    provider_objs = [_provider(name) for name in settings.providers]
    provider = provider_objs[0]
    providers = ProviderRegistry(provider_objs)
    scheduler = Scheduler(settings, time.time)
    broadcaster = Broadcaster(settings, db, sender, posters=posters, metadata=metadata)
    stats = StatsService(
        db,
        settings,
        http=http,
        cache=cache,
        scheduler=scheduler,
        broadcaster=broadcaster,
    )
    broadcaster.stats = stats
    discovery = DiscoveryJob(
        settings,
        db,
        cache,
        providers,
        broadcaster=broadcaster,
        http=http,
        on_admin_message=notifier.send_admin,
    )
    stats.discovery = discovery
    watcher = Watcher(
        settings,
        db,
        cache,
        scheduler,
        providers,
        http,
        notifier=notifier,
        stats=stats,
        on_admin_message=notifier.send_admin,
    )
    support = SupportService(db, settings, sender, bot)
    feedback = FeedbackService(db, settings, notifier)

    dp = Dispatcher(storage=MemoryStorage())
    for router in routers:
        dp.include_router(router)
    language_gate = LanguageMiddleware(db, settings)
    rate_limiter = RateLimitMiddleware(settings)
    for observer in (dp.message, dp.callback_query):
        observer.middleware(language_gate)
        observer.middleware(rate_limiter)

    dp["db"] = db
    dp["cache"] = cache
    dp["settings"] = settings
    dp["scheduler"] = scheduler
    dp["support"] = support
    dp["feedback"] = feedback
    dp["stats"] = stats
    dp["provider"] = provider
    dp["providers"] = providers
    dp["discovery"] = discovery
    dp["imax"] = imax
    dp["http"] = http
    dp["notifier"] = notifier
    dp["metadata"] = metadata

    tasks: list[asyncio.Task[Any]] = []

    async def apply_watch_limits() -> None:
        if await db.get_meta("watch_limits_v2") == "done":
            return
        trimmed = await db.trim_watches_to_limits(
            settings.free_watch_limit, settings.supporter_watch_limit
        )
        for row in trimmed:
            try:
                with i18n.use(row.get("lang")):
                    text = strings.watches_trimmed(row["removed"], row["limit"])
                await sender.send(row["telegram_id"], text)
            except Exception:
                logger.warning("Could not tell %s about trimmed watches", row["telegram_id"])
        await db.set_meta("watch_limits_v2", "done")
        await notifier.send_admin(
            lambda: strings.admin_limits_applied(
                len(trimmed), sum(int(row["removed"]) for row in trimmed)
            )
        )

    async def freshness_loop() -> None:
        while True:
            try:
                age = http.seconds_since_success
                if age is None:
                    set_freshness_state(0, False)
                else:
                    minutes = int(age // 60)
                    if http.incident_open:
                        set_freshness_state(max(minutes, 1), True)
                    else:
                        set_freshness_state(minutes, False)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Freshness loop error")
            await asyncio.sleep(30)

    async def health_loop() -> None:
        """Probe once a minute only while VOX is marked as down."""

        while True:
            await asyncio.sleep(60)
            if not http.incident_open or not http.breaker.allow():
                continue
            with contextlib.suppress(Exception):
                await http.get(
                    settings.http_base_url,
                    "health:home",
                    ttl=0,
                    force_refresh=True,
                    conditional=False,
                    allow_stale=False,
                )

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled update error: %s", event.exception)
        await notifier.send_admin(
            lambda: strings.admin_unexpected_error(type(event.exception).__name__)
        )
        update = event.update
        try:
            if update.callback_query:
                await update.callback_query.answer(strings.error_generic(), show_alert=True)
            elif update.message:
                await update.message.answer(strings.error_generic())
        except Exception:
            pass
        return True

    async def watcher_loop() -> None:
        while True:
            try:
                sent = await watcher.run_once()
                if sent:
                    logger.info("Watcher sent %s alerts", sent)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Watcher loop error")
            await asyncio.sleep(settings.watcher_tick)

    async def discovery_loop() -> None:
        while True:
            try:
                if settings.discovery_enabled:
                    await discovery.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Discovery loop error")
            await asyncio.sleep(30)

    async def stats_loop() -> None:
        last_day = None
        while True:
            try:
                now = local_now(settings.timezone)
                today = now.date().isoformat()
                if today != last_day and now.hour >= settings.stats_update_hour:
                    await stats.record_daily(today)
                    last_day = today
                dropped = await cache.sweep()
                if dropped:
                    logger.info("Cache sweep removed %s stale entries", dropped)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Stats loop error")
            await asyncio.sleep(3600)

    async def on_startup() -> None:
        admin_row = await db.get_user(settings.admin_id) if settings.admin_id else None
        i18n.set_admin_language((admin_row or {}).get("lang") or i18n.DEFAULT_LANGUAGE)
        try:
            me = await bot.me()
            if me.username:
                notifier.bot_username = me.username
                dp["bot_username"] = me.username
        except Exception:
            logger.exception("Could not read the bot username; deep links are disabled")
        try:
            for lang in i18n.SUPPORTED_LANGUAGES:
                catalog = i18n.for_language(lang)
                language_code = "" if lang == i18n.DEFAULT_LANGUAGE else lang
                public = _commands(catalog.PUBLIC_COMMANDS)
                await bot.set_my_commands(public, language_code=language_code)
                if settings.admin_id:
                    await bot.set_my_commands(
                        public + _commands(catalog.ADMIN_COMMANDS),
                        scope=BotCommandScopeChat(chat_id=settings.admin_id),
                        language_code=language_code,
                    )
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception:
            logger.exception("Could not register commands / menu button")
        await broadcaster.start()
        await apply_watch_limits()
        tasks.append(asyncio.create_task(watcher_loop(), name="watcher-loop"))
        tasks.append(asyncio.create_task(discovery_loop(), name="discovery-loop"))
        tasks.append(asyncio.create_task(stats_loop(), name="stats-loop"))
        tasks.append(asyncio.create_task(freshness_loop(), name="freshness-loop"))
        tasks.append(asyncio.create_task(health_loop(), name="health-loop"))
        await watcher.sync_targets()
        logger.info("Cinema Radar started with %s active targets", len(scheduler))
        await notifier.send_admin(lambda: strings.admin_started())

    async def on_shutdown() -> None:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await broadcaster.stop()
        await http.close()
        await db.close()
        logger.info("Cinema Radar stopped.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Cinema Radar v%s starting", __version__)

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        with contextlib.suppress(Exception):
            await bot.session.close()


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    main()
