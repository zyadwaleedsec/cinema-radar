"""HTTP backoff and circuit-breaker behaviour."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

import pytest

from http_client import (
    CircuitBreaker,
    CircuitOpenError,
    HttpClient,
    UpstreamError,
    reason_for_exception,
)


class Response:
    def __init__(self, status_code: int, text: str = "", headers=None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def get(self, url, headers=None, timeout=None):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return Response(200, "<html>ok</html>")


@pytest.mark.asyncio
async def test_429_storm_opens_and_closes_breaker(db, cache, test_settings, clock):
    session = FakeSession([Response(429) for _ in range(3)])
    client = HttpClient(test_settings, cache, session=session, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        with pytest.raises(UpstreamError):
            await client.get("https://example.test/showtimes", "k", ttl=1)
    assert client.circuit_state == "open"
    assert client.slowdown_factor > 1.0

    with pytest.raises(CircuitOpenError):
        await client.get("https://example.test/showtimes", "k", ttl=1)

    clock.advance(11)
    result = await client.get("https://example.test/showtimes", "k", ttl=1)
    assert result.status_code == 200
    assert client.circuit_state == "closed"
    assert session.calls == 4


def test_stuck_half_open_probe_is_replaced_after_timeout(clock):
    breaker = CircuitBreaker(
        threshold=1,
        pause_min=10,
        pause_max=10,
        probe_timeout=5,
        clock=clock,
    )
    assert breaker.record_failure() is True
    assert breaker.state == "open"

    clock.advance(10)
    assert breaker.allow() is True
    assert breaker.state == "half_open"
    # A probe is in flight, so no second request is allowed yet.
    assert breaker.allow() is False

    clock.advance(5)
    # The first probe never reported back; let a fresh one through.
    assert breaker.allow() is True

    assert breaker.record_success() is True
    assert breaker.state == "closed"
    assert breaker.allow() is True


@pytest.mark.asyncio
async def test_outage_alerts_the_admin_once_then_recovery(db, cache, test_settings, clock):
    alerts: list[str] = []

    async def admin(text: str) -> None:
        alerts.append(text)

    session = FakeSession([Response(403) for _ in range(3)] + [Response(200, "<html>ok</html>")])
    client = HttpClient(
        test_settings,
        cache,
        session=session,
        clock=clock,
        sleep=clock.sleep,
        on_admin_message=admin,
    )

    for _ in range(3):
        with pytest.raises(UpstreamError):
            await client.get(
                "https://example.test/showtimes",
                "k",
                ttl=1,
                target_key="vox:almaza:2026-12-16",
                allow_stale=False,
            )

    assert len(alerts) == 1
    assert "VOX واقعة" in alerts[0]
    assert "403" in alerts[0]
    assert client.incident_open is True
    assert client.circuit_state == "open"

    clock.advance(11)
    result = await client.get("https://example.test/showtimes", "k", ttl=1, allow_stale=False)
    assert result.status_code == 200
    assert len(alerts) == 2
    assert "VOX رجعت" in alerts[1]
    assert client.incident_open is False
    assert client.circuit_state == "closed"


@pytest.mark.asyncio
async def test_successful_retry_does_not_alert_the_admin(db, cache, test_settings, clock):
    alerts: list[str] = []

    async def admin(text: str) -> None:
        alerts.append(text)

    class FlakySession:
        def __init__(self) -> None:
            self.calls = 0

        async def get(self, url, headers=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise OSError("connection reset by peer")
            return Response(200, "<html>ok</html>")

    session = FlakySession()
    settings = replace(test_settings, max_retries=1)
    client = HttpClient(
        settings,
        cache,
        session=session,
        clock=clock,
        sleep=clock.sleep,
        on_admin_message=admin,
    )

    result = await client.get("https://example.test/showtimes", "k", ttl=100, allow_stale=False)

    assert result.status_code == 200
    assert session.calls == 2
    assert alerts == []
    assert client.incident_open is False


def test_transport_errors_are_classified_for_the_admin():
    class CurlTimeout(OSError):
        pass

    class CurlTimeoutError(OSError):
        code = 28

    assert reason_for_exception(TimeoutError("slow")) == "timeout"
    assert reason_for_exception(CurlTimeout("timed out")) == "timeout"
    assert reason_for_exception(CurlTimeoutError("curl: (28)")) == "timeout"
    assert reason_for_exception(OSError("connection reset")) == "network"


@pytest.mark.asyncio
async def test_strict_fetch_refuses_stale_data_but_menus_may_read_it(
    db, cache, test_settings, clock
):
    session = FakeSession([Response(200, "<html>fresh</html>")] + [Response(500) for _ in range(3)])
    client = HttpClient(test_settings, cache, session=session, clock=clock, sleep=clock.sleep)
    url = "https://example.test/showtimes"

    first = await client.get(url, "k", ttl=100)
    assert first.text == "<html>fresh</html>"
    clock.advance(200)  # the cached body is now stale

    for _ in range(3):
        with pytest.raises(UpstreamError):
            await client.get(url, "k", ttl=100, allow_stale=False)

    # The breaker is open: an alerting caller must not get the old body...
    with pytest.raises(CircuitOpenError):
        await client.get(url, "k", ttl=100, allow_stale=False)
    # ...while a menu can still show it with an age label.
    stale = await client.get(url, "k", ttl=100, allow_stale=True)
    assert stale.text == "<html>fresh</html>"
    assert stale.stale is True


@pytest.mark.asyncio
async def test_last_success_age_uses_the_injected_clock(db, cache, test_settings, clock):
    session = FakeSession([Response(200, "<html>ok</html>")])
    client = HttpClient(test_settings, cache, session=session, clock=clock, sleep=clock.sleep)

    await client.get("https://example.test/x", "k", ttl=100)
    assert client.seconds_since_success == 0
    assert client.last_success_wall is not None
    assert abs(client.last_success_wall - time.time()) < 5

    clock.advance(90)
    assert client.seconds_since_success == 90


@pytest.mark.asyncio
async def test_outage_alert_reports_a_real_wall_clock_last_success(db, cache, test_settings, clock):
    alerts: list[str] = []

    async def admin(text: str) -> None:
        alerts.append(text)

    session = FakeSession([Response(200, "<html>ok</html>")] + [Response(403) for _ in range(3)])
    client = HttpClient(
        test_settings,
        cache,
        session=session,
        clock=clock,
        sleep=clock.sleep,
        on_admin_message=admin,
    )

    await client.get("https://example.test/x", "k1", ttl=100)
    clock.advance(200)
    for _ in range(3):
        with pytest.raises(UpstreamError):
            await client.get("https://example.test/x", "k2", ttl=100, allow_stale=False)

    assert len(alerts) == 1
    # The old bug formatted the monotonic clock, producing a 1970/2023 date.
    assert str(datetime.now().year) in alerts[0]
    assert "1970" not in alerts[0]
