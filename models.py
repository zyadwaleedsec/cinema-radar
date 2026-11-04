"""Typed domain models shared by providers, watcher, discovery and the bot."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

# Showtime status values.  VOX renders a session only after its day is on
# sale; a grey session means sold out, while a day with no sessions is the
# "not on sale yet" case.
AVAILABLE = "AVAILABLE"
SOLD_OUT = "SOLD_OUT"
NOT_AVAILABLE = "NOT_AVAILABLE"
UNKNOWN = "UNKNOWN"

STATUS_LABELS_AR = {
    AVAILABLE: "متاح",
    SOLD_OUT: "الحجز مكتمل",
    NOT_AVAILABLE: "لسه مفتحش",
    UNKNOWN: "مش معروف",
}

# Canonical screening formats.  The order matters: the more specific labels
# come first so ``IMAX`` is never parsed as ``MAX``.
FORMAT_LABELS_AR = {
    "IMAX": "آيماكس IMAX",
    "SCREENX": "ScreenX",
    "PREMIUM": "Premium",
    "STANDARD": "Standard",
    "DOLBY": "Dolby",
    "4DX": "4DX",
    "GOLD": "Gold",
    "KIDS": "Kids",
    "ONYX": "Onyx",
    "MAX": "MAX",
    "VIP": "VIP",
    "DBOX": "DBOX",
    "BALCONE": "Balcone",
    "SPECIAL": "Special",
    "THEATRE": "Theatre",
    "3D": "3D",
    "2D": "2D",
}
CANONICAL_FORMATS = tuple(FORMAT_LABELS_AR)


def format_key(value: object) -> str:
    """Normalise a provider hall/experience label to a canonical key.

    VOX writes ``Standard``, ``MAX`` and ``IMAX`` in title case, while the
    subscription filter may have been stored in any case.  Centralising the
    mapping keeps the filter, the buttons and the alert text in sync.
    """

    text = str(value or "").strip().upper()
    if not text or text == "*":
        return "*"
    for token in CANONICAL_FORMATS:
        if token in text:
            return token
    return text


def format_label(value: object) -> str:
    key = format_key(value)
    if key == "*":
        return "كل الفورمات"
    return FORMAT_LABELS_AR.get(key, str(value or key))


@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    provider: str = "vox"
    url: str | None = None


@dataclass(frozen=True)
class Movie:
    id: str
    name: str
    slug: str
    provider: str = "vox"
    poster_url: str | None = None
    duration_minutes: int | None = None
    rating: str | None = None
    language: str | None = None
    synopsis: str | None = None
    trailer_url: str | None = None
    imax_status: str | None = None


@dataclass(frozen=True)
class Showtime:
    """One screening.

    ``time`` is normalised to 24h ``HH:MM``.  ``hall_type`` is the VOX
    experience (MAX, IMAX, GOLD, Standard, ...).  ``status`` is one of the
    module-level status constants.  ``seats_available`` is ``None`` when the
    upstream page does not expose a seat count.
    """

    provider: str
    branch_id: str
    date: str
    movie_id: str
    movie_name: str
    time: str
    hall_type: str
    status: str
    seats_available: int | None = None
    booking_url: str | None = None
    showtime_id: str | None = None

    @property
    def key(self) -> str:
        return f"{self.time}|{self.hall_type}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Showtime:
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class BranchOverview:
    """One branch as returned by the provider's whole-branch endpoint."""

    branch: Branch
    dates: tuple[str, ...] = ()
    movies: tuple[Movie, ...] = ()
    showtimes: tuple[Showtime, ...] = ()
    fetched_date: str | None = None


@dataclass(frozen=True)
class TargetKey:
    provider: str
    branch_id: str
    date: str
    movie_id: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.branch_id}:{self.date}:{self.movie_id}"

    @property
    def fetch_key(self) -> str:
        """Coalescing key: a whole branch+day page serves every movie."""

        return f"{self.provider}:{self.branch_id}:{self.date}"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.key


@dataclass(frozen=True)
class WatchEvent:
    kind: str  # BOOKING_OPENED | SEATS_AVAILABLE | NEW_SHOWTIMES
    showtime: Showtime
    previous_status: str | None = None
    previous_seats: int | None = None
    seats_available: int | None = None
    is_new: bool = False
    times: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryEvent:
    kind: str  # NEW_MOVIE | NEW_DATE_OPENED | NEW_SHOWTIMES | UPCOMING_MOVIE
    branch: Branch
    movie: Movie
    date: str | None = None
    showtime: Showtime | None = None
    booking_url: str | None = None
    event_key: str = ""
    times: tuple[str, ...] = ()
    released: bool = False


def showtime_map(showtimes: Iterable[Showtime]) -> dict[str, Showtime]:
    return {st.key: st for st in showtimes}
