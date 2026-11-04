"""Central configuration for Cinema Radar.

Every tunable interval, limit and secret lives here.  Secrets are read from the
environment (see ``.env.example``) and are never hard-coded in the source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = _env(name, default).lower()
    return value if value in allowed else default


def _parse_providers(raw: str) -> tuple[str, ...]:
    """Parse the comma-separated ``PROVIDERS`` list; both cinemas by default."""

    values = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    return values or ("vox", "renaissance")


@dataclass(frozen=True)
class Settings:
    # ------------------------------------------------------------------ secrets
    bot_token: str = ""
    admin_id: int = 0
    donation_phone: str = ""
    channel_id: str | None = None
    bot_username: str = ""

    # ------------------------------------------------------------------ general
    db_path: str = "cinemaradar.sqlite3"
    log_level: str = "INFO"
    timezone: str = "Africa/Cairo"
    provider: str = "vox"
    providers: tuple[str, ...] = ("vox", "renaissance")
    # auto: rich messages with automatic classic fallback; rich: always try;
    # classic: HTML + inline keyboards only.
    ui_renderer: str = "auto"

    # ------------------------------------------------------------------ upstream
    http_base_url: str = "https://egy.voxcinemas.com"
    renaissance_base_url: str = "https://rnscinemas.com"
    http_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # VOX resets plain TLS clients.  When curl_cffi is installed and this is set
    # (for example "chrome124"), requests are sent with a Chrome TLS fingerprint.
    http_impersonate: str = ""
    global_rate_limit: float = 1.0  # requests / second
    max_connections: int = 2
    request_timeout: float = 12.0
    max_retries: int = 1

    # ------------------------------------------------------------------- caching
    cache_static_ttl: int = 18 * 3600  # branches / halls
    cache_listings_ttl: int = 12 * 60  # movies / dates
    cache_showtimes_ttl: int = 150  # default; watcher passes its own TTL
    cache_coming_soon_ttl: int = 3600  # /movies/comingsoon listing
    cache_movie_details_ttl: int = 7 * 24 * 3600  # poster / duration / rating / language
    cache_stale_ttl: int = 7 * 24 * 3600  # keep stale data for restarts / outages
    # Pre-book dates for Renaissance come from the movie pages, beyond the
    # branch page's ten-day strip.  Refreshed in the background, not per request.
    prebook_dates_ttl: int = 3 * 3600  # how often we re-scan movie pages
    prebook_dates_max_days: int = 120  # horizon for bookable Coming Soon dates

    # ------------------------------------------------------------------ polling
    poll_open_with_seats: int = 100
    poll_waiting_for_open: int = 60
    poll_sold_out: int = 120
    poll_far_min: int = 480
    poll_far_max: int = 720
    poll_burst: int = 12
    poll_opening_window_minutes: int = 90
    poll_jitter: float = 0.20
    watch_confirm_delay: float = 3.0
    watch_alert_cooldown: int = 600
    watcher_tick: float = 1.0
    far_date_days: int = 7
    all_dates_max: int = 21
    all_dates_refresh: int = 1200

    # --------------------------------------------------------------- discovery
    discovery_enabled: bool = True
    discovery_interval: int = 8 * 60
    discovery_jitter: float = 0.20
    discovery_confirm_delay: float = 3.0
    discovery_confirm_network: bool = False
    discovery_daily_cap: int = 10
    discovery_flap_window: int = 30 * 60
    coming_soon_interval: int = 3600

    # ------------------------------------------------------------------- limits
    free_watch_limit: int = 2
    supporter_watch_limit: int = 10
    user_rate_limit_per_minute: int = 20

    # ----------------------------------------------------------------- telegram
    telegram_rate_per_second: float = 25.0
    telegram_per_chat_per_second: float = 1.0

    # ---------------------------------------------------------- circuit breaker
    circuit_failure_threshold: int = 3
    circuit_pause_min: int = 120
    circuit_pause_max: int = 240
    circuit_probe_timeout: int = 20
    backoff_global_max: float = 8.0
    backoff_recovery_step: float = 0.15

    # ------------------------------------------------------------------ support
    # One-off donation, approved manually by the admin.
    donation_min_amount: int = 50

    # --------------------------------------------------------------- quiet hours
    quiet_start: int = 23
    quiet_end: int = 8

    # -------------------------------------------------------------------- imax
    # Local snapshot generated by scripts/update_imax_list.py.  TMDB is only
    # used to normalise ambiguous titles, never as the IMAX source of truth.
    imax_data_path: str = "data/imax_films.json"
    tmdb_read_token: str = ""
    tmdb_timeout: float = 10.0

    # --------------------------------------------------------------------- misc
    watch_retention_days: int = 3
    stats_update_hour: int = 0
    daily_stats_days: int = 30
    broadcast_log_days: int = 90
    # Cross-cinema watch: showtimes before this hour are "morning", at/after are
    # "evening".
    morning_end_hour: int = 17

    @classmethod
    def from_env(cls) -> Settings:
        channel = _env("CHANNEL_ID") or None
        return cls(
            bot_token=_env("BOT_TOKEN"),
            admin_id=_env_int("ADMIN_ID", 0),
            donation_phone=_env("DONATION_PHONE"),
            channel_id=channel,
            bot_username=_env("BOT_USERNAME").lstrip("@"),
            db_path=_env("DB_PATH", "cinemaradar.sqlite3"),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            timezone=_env("TIMEZONE", "Africa/Cairo"),
            provider=_env("PROVIDER", "vox").lower(),
            providers=_parse_providers(_env("PROVIDERS", "")),
            ui_renderer=_env_choice("UI_RENDERER", "auto", {"auto", "rich", "classic"}),
            http_base_url=_env("VOX_BASE_URL", "https://egy.voxcinemas.com"),
            renaissance_base_url=_env("RENAISSANCE_BASE_URL", "https://rnscinemas.com"),
            http_user_agent=_env(
                "HTTP_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            ),
            http_impersonate=_env("HTTP_IMPERSONATE"),
            global_rate_limit=_env_float("GLOBAL_RATE_LIMIT", 1.0),
            max_connections=_env_int("MAX_CONNECTIONS", 2),
            request_timeout=_env_float("REQUEST_TIMEOUT", 12.0),
            max_retries=_env_int("MAX_RETRIES", 1),
            cache_static_ttl=_env_int("CACHE_STATIC_TTL", 18 * 3600),
            cache_listings_ttl=_env_int("CACHE_LISTINGS_TTL", 12 * 60),
            cache_showtimes_ttl=_env_int("CACHE_SHOWTIMES_TTL", 150),
            cache_coming_soon_ttl=_env_int("CACHE_COMING_SOON_TTL", 3600),
            cache_movie_details_ttl=_env_int("CACHE_MOVIE_DETAILS_TTL", 7 * 24 * 3600),
            cache_stale_ttl=_env_int("CACHE_STALE_TTL", 7 * 24 * 3600),
            prebook_dates_ttl=_env_int("PREBOOK_DATES_TTL", 3 * 3600),
            prebook_dates_max_days=_env_int("PREBOOK_DATES_MAX_DAYS", 120),
            poll_open_with_seats=_env_int("POLL_OPEN_WITH_SEATS", 100),
            poll_waiting_for_open=_env_int("POLL_WAITING_FOR_OPEN", 60),
            poll_sold_out=_env_int("POLL_SOLD_OUT", 120),
            poll_far_min=_env_int("POLL_FAR_MIN", 480),
            poll_far_max=_env_int("POLL_FAR_MAX", 720),
            poll_burst=_env_int("POLL_BURST", 12),
            poll_opening_window_minutes=_env_int("POLL_OPENING_WINDOW_MINUTES", 90),
            poll_jitter=_env_float("POLL_JITTER", 0.20),
            watch_confirm_delay=_env_float("WATCH_CONFIRM_DELAY", 3.0),
            watch_alert_cooldown=_env_int("WATCH_ALERT_COOLDOWN", 600),
            watcher_tick=_env_float("WATCHER_TICK", 1.0),
            far_date_days=_env_int("FAR_DATE_DAYS", 7),
            all_dates_max=_env_int("ALL_DATES_MAX", 21),
            all_dates_refresh=_env_int("ALL_DATES_REFRESH", 1200),
            discovery_enabled=_env_bool("DISCOVERY_ENABLED", True),
            discovery_interval=_env_int("DISCOVERY_INTERVAL", 8 * 60),
            discovery_jitter=_env_float("DISCOVERY_JITTER", 0.20),
            discovery_confirm_delay=_env_float("DISCOVERY_CONFIRM_DELAY", 3.0),
            discovery_confirm_network=_env_bool("DISCOVERY_CONFIRM_NETWORK", False),
            discovery_daily_cap=_env_int("DISCOVERY_DAILY_CAP", 10),
            discovery_flap_window=_env_int("DISCOVERY_FLAP_WINDOW", 30 * 60),
            coming_soon_interval=_env_int("COMING_SOON_INTERVAL", 3600),
            free_watch_limit=_env_int("FREE_WATCH_LIMIT", 2),
            supporter_watch_limit=_env_int("SUPPORTER_WATCH_LIMIT", 10),
            user_rate_limit_per_minute=_env_int("USER_RATE_LIMIT_PER_MINUTE", 20),
            telegram_rate_per_second=_env_float("TELEGRAM_RATE_PER_SECOND", 25.0),
            telegram_per_chat_per_second=_env_float("TELEGRAM_PER_CHAT_PER_SECOND", 1.0),
            circuit_failure_threshold=_env_int("CIRCUIT_FAILURE_THRESHOLD", 3),
            circuit_pause_min=_env_int("CIRCUIT_PAUSE_MIN", 120),
            circuit_pause_max=_env_int("CIRCUIT_PAUSE_MAX", 240),
            circuit_probe_timeout=_env_int("CIRCUIT_PROBE_TIMEOUT", 20),
            backoff_global_max=_env_float("BACKOFF_GLOBAL_MAX", 8.0),
            backoff_recovery_step=_env_float("BACKOFF_RECOVERY_STEP", 0.15),
            donation_min_amount=_env_int("DONATION_MIN_AMOUNT", 50),
            quiet_start=_env_int("QUIET_START", 23),
            quiet_end=_env_int("QUIET_END", 8),
            imax_data_path=_env("IMAX_DATA_PATH", "data/imax_films.json"),
            tmdb_read_token=_env("TMDB_READ_TOKEN"),
            tmdb_timeout=_env_float("TMDB_TIMEOUT", 10.0),
            watch_retention_days=_env_int("WATCH_RETENTION_DAYS", 3),
            stats_update_hour=_env_int("STATS_UPDATE_HOUR", 0),
            daily_stats_days=_env_int("DAILY_STATS_DAYS", 30),
            broadcast_log_days=_env_int("BROADCAST_LOG_DAYS", 90),
            morning_end_hour=_env_int("MORNING_END_HOUR", 17),
        )

    @property
    def channel_chat_id(self) -> int | str | None:
        if not self.channel_id:
            return None
        value = self.channel_id.strip()
        try:
            return int(value)
        except ValueError:
            return value


settings = Settings.from_env()
