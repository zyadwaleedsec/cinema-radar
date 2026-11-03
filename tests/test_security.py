"""Regression tests for the security review fixes."""

from __future__ import annotations

import search
from broadcaster import _event_line
from http_client import MAX_RETRY_AFTER_SECONDS, _retry_after_seconds
from models import Branch, DiscoveryEvent, Movie


class Response:
    def __init__(self, status_code: int, headers=None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


def test_discovery_digest_lines_escape_movie_names():
    event = DiscoveryEvent(
        kind="NEW_MOVIE",
        branch=Branch("b1", "Branch"),
        movie=Movie("m1", "<b>Bad</b> & Co", "m1"),
    )

    line = _event_line(event)

    assert "<b>Bad</b>" not in line
    assert "&lt;b&gt;Bad&lt;/b&gt; &amp; Co" in line


def test_retry_after_is_capped():
    response = Response(429, headers={"retry-after": "999999"})

    assert _retry_after_seconds(response) == MAX_RETRY_AFTER_SECONDS


def test_search_query_is_bounded_before_matching():
    long_query = "a" * 5000

    assert len(search.clean_query(long_query)) == search.MAX_QUERY_LENGTH
    assert search.clean_query("  spider man  ") == "spider man"
