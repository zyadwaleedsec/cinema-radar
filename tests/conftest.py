"""Shared fixtures for the test suite."""

from __future__ import annotations

from dataclasses import replace

import pytest
import pytest_asyncio

from cache import Cache
from config import Settings
from db import Database


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    async def sleep(self, seconds: float) -> None:
        self.value += max(0.0, seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    return replace(
        Settings(),
        db_path=str(tmp_path / "test.sqlite3"),
        bot_token="test",
        admin_id=1,
        donation_phone="01000000000",
        global_rate_limit=1000.0,
        max_connections=10,
        request_timeout=1.0,
        max_retries=0,
        circuit_failure_threshold=3,
        circuit_pause_min=10,
        circuit_pause_max=10,
        watch_confirm_delay=0.0,
        discovery_confirm_delay=0.0,
        discovery_interval=100,
        discovery_jitter=0.0,
        discovery_flap_window=300,
        discovery_confirm_network=False,
        discovery_daily_cap=10,
        quiet_start=0,
        quiet_end=0,
        telegram_rate_per_second=25.0,
        telegram_per_chat_per_second=1.0,
        free_watch_limit=2,
        supporter_watch_limit=10,
        donation_min_amount=50,
    )


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.sqlite3"))
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def cache(db, clock):
    value = Cache(db, now=clock)
    await value.load()
    return value
