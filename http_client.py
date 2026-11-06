"""Shared async HTTP client with pacing, conditional requests and protection.

All upstream requests (watcher, discovery, CLI) go through this module.  It
implements the strict rules from the brief:

* one persistent client, gzip, realistic UA;
* global token bucket (default 1 req/s) and at most two connections;
* ETag / If-Modified-Since plus body-hash comparison;
* AIMD slowdown and per-target penalties;
* circuit breaker with a single half-open probe;
* stale cached data can be served to menus, but callers that make alerting
  decisions pass ``allow_stale=False`` so they never diff old data.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

import i18n
import strings
from cache import Cache
from config import BOT_CONTACT_EMAIL, BOT_NAME, Settings, upstream_user_agent

logger = logging.getLogger(__name__)

# A malicious or broken upstream must not be able to park the shared client for
# hours by sending an absurd Retry-After value.
MAX_RETRY_AFTER_SECONDS = 120.0


class CircuitOpenError(RuntimeError):
    def __init__(self, message: str = "Circuit breaker is open") -> None:
        super().__init__(message)
        self.reason = "circuit"


class UpstreamError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        reason: str = "unknown",
        url: str | None = None,
        fetched_at: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.url = url
        self.fetched_at = fetched_at


@dataclass
class FetchResult:
    text: str | None
    status_code: int
    from_cache: bool = False
    stale: bool = False
    not_modified: bool = False
    unchanged: bool = False
    etag: str | None = None
    last_modified: str | None = None
    body_hash: str | None = None
    fetched_at: float = 0.0
    error: str | None = None


def reason_for_status(status: int) -> str:
    if status == 403:
        return "http_403"
    if status == 429:
        return "http_429"
    if 500 <= status < 600:
        return "http_5xx"
    return f"http_{status}" if status else "unknown"


def reason_for_exception(exc: BaseException) -> str:
    """Classify transport failures, including curl_cffi's own exception tree.

    curl_cffi's ``Timeout`` inherits ``OSError`` but not ``TimeoutError`` or
    ``httpx.TimeoutException``, so without the name/code check a timeout would
    be reported as a generic network problem.
    """

    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "timeout"
    code = getattr(exc, "code", None)
    message = str(exc)
    # curl 92: the edge accepted the connection then reset the HTTP/2 stream.
    # It is worth a fresh session over HTTP/1.1 instead of reporting an outage.
    if code == 92 or "HTTP/2 stream" in message:
        return "http2"
    if type(exc).__name__.endswith("Timeout") or code == 28:
        return "timeout"
    return "network"


def _place(target_key: str | None, url: str | None) -> str:
    if target_key:
        return target_key.replace(":", " / ")
    if url:
        return url
    return "—"


def _clock_text(value: float | None) -> str:
    if not value:
        return "—"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


class TokenBucket:
    """A small async token bucket with an injectable clock for tests."""

    def __init__(
        self, rate: float, capacity: float | None = None, clock=time.monotonic, sleep=asyncio.sleep
    ):
        self.rate = max(rate, 0.001)
        self.capacity = max(capacity if capacity is not None else rate, 1.0)
        self._tokens = self.capacity
        self._last = clock()
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                elapsed = max(now - self._last, 0.0)
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= 1.0 - 1e-9:
                    self._tokens = max(0.0, self._tokens - 1.0)
                    return
                need = (1.0 - self._tokens) / self.rate
                # A tiny margin keeps accumulated float error from putting two
                # sends inside the same exact one-second window.
                await self._sleep(need + 1e-6)
                # Credit the requested wait explicitly.  On coarse clocks (or
                # large monotonic timestamps) `now + need` may not change the
                # clock value at all, which would otherwise spin forever.
                self._last = self._clock()
                self._tokens = min(self.capacity, self._tokens + need * self.rate)


class CircuitBreaker:
    def __init__(
        self,
        threshold: int,
        pause_min: int,
        pause_max: int,
        probe_timeout: float = 30.0,
        clock=time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.threshold = max(threshold, 1)
        self.pause_min = pause_min
        self.pause_max = max(pause_max, pause_min)
        self.probe_timeout = max(float(probe_timeout), 0.0)
        self.state = "closed"
        self.failures = 0
        self.open_until = 0.0
        self._probe_in_flight = False
        self._probe_started = 0.0
        self._clock = clock
        self._rng = rng or random.Random()

    def allow(self) -> bool:
        now = self._clock()
        if self.state == "closed":
            return True
        if self.state == "open":
            if now >= self.open_until:
                self.state = "half_open"
                self._probe_in_flight = True
                self._probe_started = now
                return True
            return False
        # half-open: exactly one probe at a time.  If a probe hangs (cancelled
        # request, dead connection) allow a fresh one after probe_timeout so the
        # breaker can never stay stuck in half-open forever.
        if self._probe_in_flight and now - self._probe_started < self.probe_timeout:
            return False
        self._probe_in_flight = True
        self._probe_started = now
        return True

    def record_success(self) -> bool:
        """Return True when the breaker transitions back to closed."""

        was_open = self.state in {"open", "half_open"}
        self.failures = 0
        self.state = "closed"
        self._probe_in_flight = False
        return was_open

    def record_failure(self) -> bool:
        """Return True when the breaker just opened."""

        now = self._clock()
        if self.state == "half_open":
            self.state = "open"
            self.open_until = now + self._rng.uniform(self.pause_min, self.pause_max)
            self._probe_in_flight = False
            return True
        self.failures += 1
        if self.state == "closed" and self.failures >= self.threshold:
            self.state = "open"
            self.open_until = now + self._rng.uniform(self.pause_min, self.pause_max)
            return True
        return False

    @property
    def remaining_pause(self) -> float:
        return max(0.0, self.open_until - self._clock())


class HttpClient:
    def __init__(
        self,
        settings: Settings,
        cache: Cache,
        session: Any | None = None,
        clock=time.monotonic,
        sleep=asyncio.sleep,
        rng: random.Random | None = None,
        on_admin_message: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._clock = clock
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._session = session
        self._owns_session = session is None
        self._semaphore = asyncio.Semaphore(max(settings.max_connections, 1))
        self._bucket = TokenBucket(
            settings.global_rate_limit,
            capacity=max(settings.global_rate_limit, 1.0),
            clock=clock,
            sleep=sleep,
        )
        self.breaker = CircuitBreaker(
            settings.circuit_failure_threshold,
            settings.circuit_pause_min,
            settings.circuit_pause_max,
            probe_timeout=settings.circuit_probe_timeout,
            clock=clock,
            rng=self._rng,
        )
        self._on_admin_message = on_admin_message

        self.requests_total = 0
        self.failures_total = 0
        self.cache_hits = 0
        self.last_status: int | None = None
        self.last_error: str | None = None
        self.last_request_at: float | None = None
        self.last_success_at: float | None = None
        self.last_success_wall: float | None = None
        self.incident_open = False
        self.incident_started: float | None = None
        self.incident_reason = ""
        self.incident_place = ""
        self.incident_provider = ""
        self.incident_breaker_open = False
        self.affected_hint = 0
        self._request_times: list[float] = []
        self._global_slowdown = 1.0
        self._target_slowdown: dict[str, float] = {}
        self._probe_task: asyncio.Task[Any] | None = None
        # Set after a server-side HTTP/2 stream reset.  The next session pins
        # HTTP/1.1 so a WAF quirk cannot take the poller down permanently.
        self._force_http1 = False

    # ------------------------------------------------------------------ session
    def _headers(self) -> dict[str, str]:
        configured = self.settings.http_user_agent
        user_agent = upstream_user_agent(configured)
        if user_agent != configured.strip():
            logger.warning(
                "HTTP_USER_AGENT contains an email, URL or 'bot'; cinema WAFs "
                "reject it. Using a browser-safe UA and sending contact in headers."
            )
        return {
            "User-Agent": user_agent,
            # Standard header for the human responsible for the request.
            "From": BOT_CONTACT_EMAIL,
            "X-Bot-Name": BOT_NAME,
            "X-Bot-Contact": BOT_CONTACT_EMAIL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-EG,en;q=0.9,ar;q=0.8",
            "Cache-Control": "no-cache",
        }

    def _build_session(self) -> Any:
        headers = self._headers()
        if self.settings.http_impersonate:
            try:
                from curl_cffi.requests import AsyncSession  # type: ignore

                logger.info("Using curl_cffi TLS impersonation: %s", self.settings.http_impersonate)
                options: dict[str, Any] = {
                    "impersonate": self.settings.http_impersonate,
                    "headers": headers,
                    "timeout": self.settings.request_timeout,
                }
                if self._force_http1:
                    options["http_version"] = "v1"
                return AsyncSession(**options)
            except Exception:  # pragma: no cover - optional dependency
                logger.exception("curl_cffi unavailable; falling back to httpx")
        return httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self.settings.request_timeout),
            limits=httpx.Limits(
                max_connections=self.settings.max_connections,
                max_keepalive_connections=self.settings.max_connections,
            ),
            follow_redirects=True,
            http2=False,
        )

    @property
    def session(self) -> Any:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    async def close(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
        if self._session is not None and self._owns_session:
            close = getattr(self._session, "aclose", None) or getattr(self._session, "close", None)
            if close:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._session = None

    async def _discard_session(self) -> None:
        """Throw away a pooled session after a transport error.

        Keep-alive connections can be closed by the upstream after idle time;
        reusing one produces a spurious "network" failure.  The retry then
        starts a fresh connection instead of repeating the same dead socket.
        """

        if not self._owns_session or self._session is None:
            return
        session, self._session = self._session, None
        close = getattr(session, "aclose", None) or getattr(session, "close", None)
        if close is None:
            return
        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # pragma: no cover - closing must never mask the retry
            logger.debug("Could not close the failed HTTP session", exc_info=True)

    # ------------------------------------------------------------------ metrics
    @property
    def slowdown_factor(self) -> float:
        return self._global_slowdown

    def target_multiplier(self, target_key: str) -> float:
        return self._target_slowdown.get(target_key, 1.0)

    @property
    def requests_per_minute(self) -> float:
        cutoff = self._clock() - 60.0
        self._request_times = [t for t in self._request_times if t >= cutoff]
        return float(len(self._request_times))

    @property
    def circuit_state(self) -> str:
        if self.breaker.state == "open" and self.breaker.remaining_pause <= 0:
            return "half_open"
        return self.breaker.state

    @property
    def seconds_since_success(self) -> float | None:
        """Age of the last successful upstream response, using the same clock."""

        if self.last_success_at is None:
            return None
        return max(0.0, self._clock() - self.last_success_at)

    # --------------------------------------------------------------- protection
    async def _notify_admin(self, text: str) -> None:
        logger.warning("ADMIN: %s", text)
        if self._on_admin_message:
            try:
                await self._on_admin_message(text)
            except Exception:  # pragma: no cover - never let admin delivery break polling
                logger.exception("Failed to notify admin")

    @staticmethod
    def _provider_of(target_key: str | None) -> str | None:
        name = (target_key or "").split(":", 1)[0].strip()
        return name or None

    async def _send_down_alert(
        self,
        reason: str,
        place: str,
        provider: str | None,
        opened: bool,
    ) -> None:
        retry_seconds = int(self.breaker.remaining_pause) or self.settings.poll_waiting_for_open
        with i18n.use(i18n.admin_language()):
            alert = strings.admin_upstream_down(
                reason,
                strings.format_place(place),
                _clock_text(self.last_success_wall),
                retry_seconds,
                self.affected_hint,
                opened,
                provider,
            )
        await self._notify_admin(alert)

    async def _record_failure(
        self,
        target_key: str | None,
        reason: str,
        url: str | None = None,
    ) -> None:
        self.failures_total += 1
        self.last_error = reason
        multiplier = min(self._global_slowdown * 2.0, self.settings.backoff_global_max)
        self._global_slowdown = multiplier
        if target_key:
            self._target_slowdown[target_key] = min(
                self._target_slowdown.get(target_key, 1.0) * 2.0,
                self.settings.backoff_global_max,
            )
        opened = self.breaker.record_failure()
        place = _place(target_key, url)
        provider = self._provider_of(target_key)
        if not self.incident_open:
            self.incident_open = True
            self.incident_started = self._clock()
            self.incident_reason = reason
            self.incident_place = place
            self.incident_provider = provider or ""
            self.incident_breaker_open = opened
            await self._send_down_alert(reason, place, provider, opened)
        elif opened and not self.incident_breaker_open:
            # The breaker finally tripped: tell the admin that alerting is now
            # paused instead of leaving the first "retrying" note unqualified.
            self.incident_breaker_open = True
            self.incident_place = place
            self.incident_provider = provider or self.incident_provider
            await self._send_down_alert(reason, place, provider, True)

    async def report_failure(
        self, reason: str, target_key: str | None = None, url: str | None = None
    ) -> None:
        """Record a failure detected outside the HTTP layer (for example a parse)."""

        await self._record_failure(target_key, reason, url=url)

    async def _record_success(self, target_key: str | None) -> None:
        self.last_error = None
        # ``last_success_at`` uses the injected clock (monotonic by default) for
        # age arithmetic; ``last_success_wall`` is the real clock for display.
        self.last_success_at = self._clock()
        self.last_success_wall = time.time()
        self._global_slowdown = max(
            1.0, self._global_slowdown - self.settings.backoff_recovery_step
        )
        if target_key and target_key in self._target_slowdown:
            value = max(
                1.0, self._target_slowdown[target_key] - self.settings.backoff_recovery_step
            )
            if value <= 1.0:
                self._target_slowdown.pop(target_key, None)
            else:
                self._target_slowdown[target_key] = value
        was_open = self.breaker.record_success()
        if self.incident_open:
            started = self.incident_started or self._clock()
            provider = self.incident_provider or None
            # Do not claim "1 minute" for a blip that recovered in seconds.
            minutes = max(0, int((self._clock() - started) / 60))
            self.incident_open = False
            self.incident_started = None
            self.incident_reason = ""
            self.incident_place = ""
            self.incident_provider = ""
            self.incident_breaker_open = False
            with i18n.use(i18n.admin_language()):
                recovered = strings.admin_upstream_recovered(minutes, provider)
            await self._notify_admin(recovered)
        elif was_open:
            with i18n.use(i18n.admin_language()):
                recovered = strings.admin_upstream_recovered(0)
            await self._notify_admin(recovered)

    # ------------------------------------------------------------------- fetch
    async def get(
        self,
        url: str,
        cache_key: str,
        ttl: float,
        force_refresh: bool = False,
        conditional: bool = True,
        target_key: str | None = None,
        allow_stale: bool = True,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        cached = await self.cache.get(cache_key, allow_stale=True)

        if cached is not None and not force_refresh and cached.is_fresh():
            self.cache_hits += 1
            return FetchResult(
                text=cached.payload,
                status_code=200,
                from_cache=True,
                etag=cached.etag,
                last_modified=cached.last_modified,
                body_hash=cached.body_hash,
                fetched_at=cached.fetched_at,
            )

        if not self.breaker.allow():
            if cached is not None and allow_stale:
                self.cache_hits += 1
                return FetchResult(
                    text=cached.payload,
                    status_code=200,
                    from_cache=True,
                    stale=True,
                    etag=cached.etag,
                    last_modified=cached.last_modified,
                    body_hash=cached.body_hash,
                    fetched_at=cached.fetched_at,
                    error="circuit_open",
                )
            raise CircuitOpenError(
                "Circuit breaker is open"
                + ("" if cached is None else " and stale data is not allowed here")
            )

        request_headers: dict[str, str] = dict(headers or {})
        if cached is not None and conditional:
            if cached.etag:
                request_headers.setdefault("If-None-Match", cached.etag)
            if cached.last_modified:
                request_headers.setdefault("If-Modified-Since", cached.last_modified)

        last_exc: Exception | None = None
        attempts = max(0, self.settings.max_retries) + 1
        # One extra slot is only used by the HTTP/1.1 fallback below.
        for attempt in range(attempts + 1):
            try:
                async with self._semaphore:
                    await self._bucket.acquire()
                    self.requests_total += 1
                    now = self._clock()
                    self.last_request_at = now
                    self._request_times.append(now)
                    response = await self.session.get(
                        url, headers=request_headers, timeout=self.settings.request_timeout
                    )
                status = int(getattr(response, "status_code", 0))
                self.last_status = status

                if status == 304 and cached is not None:
                    await self.cache.touch(cache_key)
                    await self._record_success(target_key)
                    return FetchResult(
                        text=cached.payload,
                        status_code=304,
                        from_cache=True,
                        not_modified=True,
                        etag=cached.etag,
                        last_modified=cached.last_modified,
                        body_hash=cached.body_hash,
                        fetched_at=self._clock(),
                    )

                if status == 200:
                    text = response.text
                    body_hash = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
                    etag = _header(response, "etag")
                    last_modified = _header(response, "last-modified")
                    if cached is not None and cached.body_hash == body_hash:
                        await self.cache.touch(cache_key)
                        await self._record_success(target_key)
                        return FetchResult(
                            text=cached.payload,
                            status_code=200,
                            from_cache=True,
                            unchanged=True,
                            etag=etag or cached.etag,
                            last_modified=last_modified or cached.last_modified,
                            body_hash=body_hash,
                            fetched_at=self._clock(),
                        )
                    await self.cache.put(
                        cache_key,
                        text,
                        ttl=ttl,
                        etag=etag,
                        last_modified=last_modified,
                        body_hash=body_hash,
                        fetched_at=self._clock(),
                    )
                    await self._record_success(target_key)
                    return FetchResult(
                        text=text,
                        status_code=200,
                        etag=etag,
                        last_modified=last_modified,
                        body_hash=body_hash,
                        fetched_at=self._clock(),
                    )

                if status in {429, 403} or 500 <= status < 600:
                    retry_after = _retry_after_seconds(response)
                    reason = reason_for_status(status)
                    last_exc = UpstreamError(
                        f"HTTP {status}",
                        status,
                        reason=reason,
                        url=url,
                        fetched_at=cached.fetched_at if cached else None,
                    )
                    if attempt + 1 < attempts:
                        if retry_after:
                            await self._sleep(retry_after)
                        continue
                    # Count one failure per logical fetch, not per attempt: a
                    # transient error that succeeds on retry must not alert.
                    await self._record_failure(target_key, reason, url=url)
                    if cached is not None and allow_stale:
                        return FetchResult(
                            text=cached.payload,
                            status_code=status,
                            from_cache=True,
                            stale=True,
                            error=reason,
                            fetched_at=cached.fetched_at,
                        )
                    raise last_exc

                # Other 4xx: not a capacity signal, but still a failed fetch.
                reason = reason_for_status(status)
                await self._record_failure(target_key, reason, url=url)
                raise UpstreamError(
                    f"HTTP {status}",
                    status,
                    reason=reason,
                    url=url,
                    fetched_at=cached.fetched_at if cached else None,
                )

            except (httpx.TimeoutException, httpx.TransportError, OSError) as exc:
                last_exc = exc
                reason = reason_for_exception(exc)
                if reason == "http2" and not self._force_http1:
                    # The edge accepted the request then reset the HTTP/2
                    # stream.  A fresh HTTP/1.1 session avoids the reset and
                    # keeps the poller working even if the WAF changes again.
                    self._force_http1 = True
                    logger.warning("Upstream reset HTTP/2; retrying over HTTP/1.1")
                    await self._discard_session()
                    continue
                if attempt + 1 < attempts:
                    await self._discard_session()
                    continue
                # One failure per logical fetch: a retry that succeeds is not an
                # outage and must not page the admin.
                await self._record_failure(target_key, reason, url=url)
                if cached is not None and allow_stale:
                    return FetchResult(
                        text=cached.payload,
                        status_code=0,
                        from_cache=True,
                        stale=True,
                        error=reason,
                        fetched_at=cached.fetched_at,
                    )
                raise UpstreamError(
                    f"{type(exc).__name__}: {exc}",
                    reason=reason,
                    url=url,
                    fetched_at=cached.fetched_at if cached else None,
                ) from exc
            except (CircuitOpenError, UpstreamError):
                # Already classified and accounted for above; do not count the
                # failure twice (which would open the breaker prematurely).
                raise
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                await self._record_failure(target_key, "unknown", url=url)
                if cached is not None and allow_stale:
                    return FetchResult(
                        text=cached.payload,
                        status_code=0,
                        from_cache=True,
                        stale=True,
                        error="unknown",
                        fetched_at=cached.fetched_at,
                    )
                raise

        assert last_exc is not None
        raise last_exc


def _header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {}) or {}
    try:
        value = headers.get(name) or headers.get(name.title())
    except Exception:
        value = None
    return str(value) if value else None


def _retry_after_seconds(response: Any) -> float | None:
    value = _header(response, "retry-after")
    if not value:
        return None
    try:
        return min(MAX_RETRY_AFTER_SECONDS, max(0.0, float(value)))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return min(
                MAX_RETRY_AFTER_SECONDS,
                max(0.0, (dt - datetime.now(UTC)).total_seconds()),
            )
        except (TypeError, ValueError):
            return None
