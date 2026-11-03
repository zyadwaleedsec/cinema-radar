"""Fuzzy Arabic/English search for movie and branch names.

The goal is to be forgiving about how people actually type:

* Arabic spelling variants: ``أ / إ / آ / ا``, ``ة / ه``, ``ى / ي``,
  ``ؤ / و``, ``ئ / ي``, optional ``ال`` and tashkeel.
* English case, punctuation and spacing: ``Spider-Man`` == ``spider man``
  == ``spiderman``.
* Small typos: ``avengrs``, ``doomsdy``, ``clayfac``.
* Common Arabic transliterations: ``افنجرز`` -> ``avengers``,
  ``سبايدر مان`` -> ``spider man``.

Everything here is pure Python and has no Telegram or network dependency, so
it can be unit-tested without installing aiogram.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

# A hit below this score is almost always noise ("dune" vs "the dino family").
MIN_SCORE = 0.65
# Lower threshold used only for "did you mean?" suggestions.
SUGGEST_SCORE = 0.35
# Telegram messages can be 4096 characters; fuzzy matching is O(query x movies).
MAX_QUERY_LENGTH = 64


def clean_query(text: object) -> str:
    """Trim and bound user input before it reaches the fuzzy matcher."""

    return str(text or "").strip()[:MAX_QUERY_LENGTH]


_SPACES = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)
_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ئ": "ي",
        "ؤ": "و",
        "ة": "ه",
        # Persian letters occasionally used by Egyptian typists.
        "پ": "ب",
        "ڤ": "ف",
        "ک": "ك",
        "ی": "ي",
    }
)

# Arabic transliterations of popular titles, mapped to the Latin words VOX
# uses.  The list is intentionally small and easy to extend; it is only a
# bonus on top of fuzzy matching, never a requirement.
_ALIASES: dict[str, str] = {
    "افنجرز": "avengers",
    "افينجرز": "avengers",
    "افنجر": "avengers",
    "افنجرس": "avengers",
    "افينجر": "avengers",
    "افينجرس": "avengers",
    "افنجيرز": "avengers",
    "سبايدرمان": "spiderman",
    "اسبايدرمان": "spiderman",
    "سبيدرمان": "spiderman",
    "سبايدر": "spider",
    "مان": "man",
    "باتمان": "batman",
    "سوبرمان": "superman",
    "ديون": "dune",
    "جودزيلا": "godzilla",
    "دومزداي": "doomsday",
    "دومسداي": "doomsday",
    "دومزدي": "doomsday",
    "دومس": "dooms",
    "دومز": "dooms",
    "انفينيتي": "infinity",
    "انفنتي": "infinity",
    "انفينتي": "infinity",
    "اوديسي": "odyssey",
    "ذا": "the",
    "كلايفيس": "clayface",
    "كلاي": "clay",
    "فيس": "face",
    "ريزيدنت": "resident",
    "ايفل": "evil",
    "سمورفس": "smurfs",
    "سميرفس": "smurfs",
    "سمورفز": "smurfs",
    "مونجوس": "mongoose",
    "وايلدوود": "wildwood",
    "وايلد": "wild",
    "وود": "wood",
    "هانجر": "hunger",
    "جيمز": "games",
    "براند": "brand",
    "نيو": "new",
    "داي": "day",
    "محمود": "mahmoud",
    "التاني": "el tany",
    "تاني": "tany",
    "مينوس": "minus",
    "زيرو": "zero",
    "هوب": "hope",
    "موسكو": "moscow",
    "كايرو": "cairo",
    "نصيب": "naseeb",
    "ستريت": "street",
    "فايتر": "fighter",
    "سينس": "sense",
    "اند": "and",
    "سينسيبيليتي": "sensibility",
    "هيرت": "heart",
    "اوف": "of",
    "بيست": "beast",
    "فيريتي": "verity",
    "انفلوينسر": "influencer",
    "بروجكت": "project",
    "دينو": "dino",
    "فاميلي": "family",
    "ماجيك": "magic",
    "فاراوي": "faraway",
    "تري": "tree",
    "بارت": "part",
    "ثري": "three",
    "فيجن": "vision",
    "وولا": "wala",
    "كان": "kan",
    "علي": "ala",
    "البال": "el bal",
    "مطلوب": "matloub",
    "عايلتين": "3a2eleyain",
}


def normalize(text: object) -> str:
    """Lower-case, strip accents/tashkeel, unify Arabic letters, drop punctuation."""

    raw = unicodedata.normalize("NFKD", str(text or ""))
    # NFKD turns ``أ`` into ``ا`` + a combining hamza and separates Latin
    # accents; removing combining marks handles both in one pass.
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().translate(_DIGITS).translate(_LETTERS)
    raw = raw.replace("_", " ")
    raw = _NON_WORD.sub(" ", raw)
    return _SPACES.sub(" ", raw).strip()


def compact(text: object) -> str:
    """Normalised text with all spaces removed (``spider man`` -> ``spiderman``)."""

    return normalize(text).replace(" ", "")


def _alias_token(token: str) -> str:
    if token in _ALIASES:
        return _ALIASES[token]
    # Arabic definite article: الافنجرز -> افنجرز -> avengers.
    if token.startswith("ال") and len(token) > 4 and token[2:] in _ALIASES:
        return _ALIASES[token[2:]]
    return token


def expand_aliases(text: object) -> str:
    """Normalise and translate known Arabic transliterations to Latin words."""

    return " ".join(_alias_token(token) for token in normalize(text).split())


def _variants(token: str) -> tuple[str, ...]:
    if token.startswith("ال") and len(token) > 4:
        return (token, token[2:])
    return (token,)


def _pair_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) < 2 or len(right) < 2:
        return 0.0
    if right.startswith(left) or left.startswith(right):
        return 0.93
    if len(left) >= 3 and left in right:
        return 0.88
    if len(left) < 2 or len(right) < 2:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _token_score(left: str, right: str) -> float:
    return max(_pair_score(a, b) for a in _variants(left) for b in _variants(right))


def score(query: object, candidate: object) -> float:
    """Return 0..1 similarity between a user query and one candidate name."""

    query_text = expand_aliases(clean_query(query))
    candidate_text = expand_aliases(candidate)
    if len(query_text.replace(" ", "")) < 2 or not candidate_text:
        return 0.0

    query_compact = query_text.replace(" ", "")
    candidate_compact = candidate_text.replace(" ", "")
    if query_text == candidate_text or query_compact == candidate_compact:
        return 1.0

    query_tokens = query_text.split()
    candidate_tokens = candidate_text.split()

    per_token = [
        max((_token_score(token, other) for other in candidate_tokens), default=0.0)
        for token in query_tokens
    ]
    average = sum(per_token) / len(per_token)
    coverage = sum(1 for value in per_token if value >= 0.78) / len(per_token)
    compact_ratio = SequenceMatcher(None, query_compact, candidate_compact).ratio()

    result = 0.62 * average + 0.28 * coverage + 0.10 * compact_ratio
    if query_compact in candidate_compact:
        result = max(result, 0.90)
    if candidate_compact.startswith(query_compact):
        result = max(result, 0.94)
    return round(min(result, 1.0), 4)


@dataclass(frozen=True)
class Hit:
    item: Any
    score: float
    index: int


def _default_key(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "")
    return str(getattr(item, "name", item))


def rank(
    query: object,
    items: Iterable[Any],
    key: Callable[[Any], str] | None = None,
    limit: int | None = None,
    min_score: float = MIN_SCORE,
) -> list[Hit]:
    """Return matching items, best first, with their original list index."""

    query = clean_query(query)
    key = key or _default_key
    hits: list[Hit] = []
    for index, item in enumerate(items):
        value = score(query, key(item))
        if value >= min_score:
            hits.append(Hit(item=item, score=value, index=index))
    # Prefer the higher score, then the shorter (more specific) title.
    hits.sort(key=lambda hit: (-hit.score, len(normalize(key(hit.item))), hit.index))
    return hits[:limit] if limit is not None else hits


def suggest(
    query: object,
    items: Iterable[Any],
    key: Callable[[Any], str] | None = None,
    limit: int = 3,
) -> list[Hit]:
    """Closest names for a query that produced no results."""

    return rank(query, items, key=key, limit=limit, min_score=SUGGEST_SCORE)
