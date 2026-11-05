"""Network probe for a deployed bot.

Run it inside the Fly machine:

    python -m scripts.probe

It reports proxy/impersonation env vars, DNS resolution, then calls the VOX and
Renaissance entry pages twice: once with plain httpx and once with curl_cffi's
Chrome impersonation. That tells a TLS block apart from a geo/datacenter block.
"""

from __future__ import annotations

import os
import socket
import time

TARGETS = {
    "vox": "https://egy.voxcinemas.com/cinemas",
    "renaissance": "https://rnscinemas.com/",
}


def print_env() -> None:
    print("== Environment ==")
    for key in ("HTTP_IMPERSONATE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        print(f"{key:16} = {os.getenv(key) or '(unset)'}")


def print_dns() -> None:
    print("== DNS ==")
    for name, url in TARGETS.items():
        host = url.split("/")[2]
        try:
            print(f"{name:12} {host} -> {socket.gethostbyname(host)}")
        except OSError as exc:
            print(f"{name:12} {host} -> DNS FAILED: {exc}")


def plain(url: str) -> None:
    import httpx

    print("  httpx      ... ", end="", flush=True)
    started = time.monotonic()
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = client.get(url)
        elapsed = time.monotonic() - started
        print(f"{response.status_code} {len(response.content)} bytes in {elapsed:.1f}s")
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"FAILED in {elapsed:.1f}s: {type(exc).__name__}: {str(exc)[:160]}")


def impersonated(url: str) -> None:
    from curl_cffi import requests

    print("  curl_cffi  ... ", end="", flush=True)
    started = time.monotonic()
    try:
        response = requests.get(url, impersonate="chrome124", timeout=30)
        elapsed = time.monotonic() - started
        print(f"{response.status_code} {len(response.content)} bytes in {elapsed:.1f}s")
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"FAILED in {elapsed:.1f}s: {type(exc).__name__}: {str(exc)[:160]}")


def main() -> None:
    print_env()
    print_dns()
    for name, url in TARGETS.items():
        print(f"== {name}: {url} ==")
        plain(url)
        impersonated(url)


if __name__ == "__main__":
    main()
