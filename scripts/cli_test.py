"""CLI smoke test for the VOX provider.

Examples:
    python -m scripts.cli_test
    python -m scripts.cli_test --branch city-centre-almaza
    python -m scripts.cli_test --branch city-centre-almaza --date 2026-12-16
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from cache import Cache
from config import Settings
from db import Database
from http_client import HttpClient
from providers.vox import VoxProvider


async def run(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.base_url:
        object.__setattr__(settings, "http_base_url", args.base_url)
    db = Database(":memory:")
    await db.connect()
    await db.init_schema()
    cache = Cache(db)
    http = HttpClient(settings, cache)
    provider = VoxProvider(http, cache, settings)
    try:
        branches = await provider.get_branches(force_refresh=True)
        print(f"\nBranches ({len(branches)}):")
        for branch in branches:
            print(f"  {branch.id:28} {branch.name}")
        if not branches:
            print("No branches returned.")
            return 1

        branch_id = args.branch or branches[0].id
        branch = next((b for b in branches if b.id == branch_id), None)
        if branch is None:
            print(f"Unknown branch: {branch_id}")
            return 2

        dates = await provider.get_dates(branch_id, force_refresh=True)
        print(f"\nDates for {branch.name} ({len(dates)}): {', '.join(dates[:14])}")
        if not dates:
            print("No dates returned.")
            return 0
        date = args.date or dates[0]
        if date not in dates:
            print(f"Warning: {date} is not in the date strip; trying it anyway.")

        movies = await provider.get_movies(branch_id, date, force_refresh=True)
        print(f"\nMovies on {date} ({len(movies)}):")
        for movie in movies:
            print(f"  {movie.id:16} {movie.name}  ({movie.slug})")

        selected = movies
        if args.movie:
            needle = args.movie.lower()
            selected = [m for m in movies if needle in m.name.lower() or needle in m.slug.lower()]
        print(f"\nShowtimes on {date}:")
        for movie in selected:
            showtimes = await provider.get_showtimes(branch_id, date, movie.id, force_refresh=True)
            print(f"\n  {movie.name} [{movie.id}]")
            if not showtimes:
                print("    (none)")
            for showtime in showtimes:
                seats = (
                    f", {showtime.seats_available} seats"
                    if showtime.seats_available is not None
                    else ""
                )
                print(
                    f"    {showtime.time:>5}  {showtime.hall_type:<10} "
                    f"{showtime.status}{seats}  {showtime.booking_url or ''}"
                )
        return 0
    finally:
        await http.close()
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cinema Radar VOX CLI test")
    parser.add_argument("--branch", help="branch slug, e.g. city-centre-almaza")
    parser.add_argument("--date", help="ISO date, e.g. 2026-12-16")
    parser.add_argument("--movie", help="movie name or slug filter")
    parser.add_argument("--base-url", help="override VOX base URL")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
