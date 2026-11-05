"""Regenerate ``data/imax_films.json`` from Wikipedia's List of IMAX films.

The bot never scrapes Wikipedia at runtime.  This small maintenance script is
run by hand (or by a weekly cron) whenever the list changes, and the generated
JSON is committed with the project.

Usage::

    python scripts/update_imax_list.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

URL = "https://en.wikipedia.org/wiki/List_of_IMAX_films"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "imax_films.json"
LICENSE = "CC BY-SA 4.0 (Wikipedia contributors)"

SECTIONS = {
    "Films shot entirely with IMAX 70mm cameras": "FULL_70MM",
    "Films shot partially with IMAX 70mm cameras": "PARTIAL_70MM",
    "Films shot entirely with IMAX-certified digital cameras": "CERTIFIED_DIGITAL",
    "Films shot partially with IMAX-certified digital cameras": "PARTIAL_DIGITAL",
}

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_CITE_RE = re.compile(r"\[\d+\]")
_SPACE_RE = re.compile(r"\s+")


def _clean(value: str) -> str:
    return _SPACE_RE.sub(" ", _CITE_RE.sub("", value)).strip()


def _year(value: str) -> int | None:
    match = _YEAR_RE.search(value)
    return int(match.group(0)) if match else None


def parse(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, object]] = []
    current: str | None = None
    for node in soup.select("h2, h3, table.wikitable"):
        if node.name in {"h2", "h3"}:
            heading = _clean(node.get_text(" "))
            current = next(
                (
                    category
                    for label, category in SECTIONS.items()
                    if label.lower() in heading.lower()
                ),
                None,
            )
            continue
        if current is None:
            continue
        for row in node.select("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            title = _clean(cells[0].get_text(" "))
            if not title or title.casefold() == "title":
                continue
            year = _year(_clean(cells[1].get_text(" ")))
            entries.append({"title": title, "year": year, "category": current})

    deduped: dict[tuple[str, int | None, str], dict[str, object]] = {}
    for item in entries:
        key = (str(item["title"]).casefold(), item["year"], str(item["category"]))
        deduped[key] = item
    return sorted(
        deduped.values(),
        key=lambda item: (str(item["title"]).casefold(), int(item["year"] or 0)),
    )


def main() -> None:
    from config import DEFAULT_USER_AGENT

    headers = {"User-Agent": DEFAULT_USER_AGENT}
    response = httpx.get(URL, headers=headers, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    entries = parse(response.text)
    if not entries:
        raise SystemExit("No IMAX films parsed; Wikipedia markup probably changed.")

    payload = {
        "source": URL,
        "license": LICENSE,
        "generated_at": datetime.now(UTC).date().isoformat(),
        "films": entries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} films to {OUTPUT}")


if __name__ == "__main__":
    main()
