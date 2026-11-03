"""Arabic/English fuzzy search: normalisation, aliases and typo tolerance."""

from __future__ import annotations

import search

MOVIES = [
    {"id": "avengers-doomsday", "name": "Avengers: Doomsday"},
    {"id": "avengers-doomsday-infinity-vision", "name": "Avengers: Doomsday (Infinity Vision)"},
    {"id": "spider-man-brand-new-day", "name": "Spider-Man: Brand New Day"},
    {"id": "dune-part-three", "name": "Dune: Part Three"},
    {"id": "the-dino-family", "name": "The Dino Family"},
    {"id": "clayface", "name": "Clayface"},
    {"id": "mahmoud-el-tany", "name": "Mahmoud El Tany (Arabic)"},
]


def _names(query: str) -> list[str]:
    return [hit.item["name"] for hit in search.rank(query, MOVIES, key=lambda m: m["name"])]


def test_normalize_unifies_arabic_letters_and_removes_tashkeel():
    assert search.normalize("أَفْلامٌ") == "افلام"
    assert search.normalize("حفلة") == search.normalize("حفله")
    assert search.normalize("مصطفى") == search.normalize("مصطفي")
    assert search.normalize("مؤمن") == search.normalize("مومن")
    assert search.normalize("ساعة") == search.normalize("ساعه")


def test_normalize_handles_latin_accents_punctuation_and_digits():
    assert search.normalize("Amélie") == "amelie"
    assert search.normalize("Spider-Man: Brand New Day!") == "spider man brand new day"
    assert search.normalize("٢٠٢٦") == "2026"


def test_english_exact_and_spacing_variants():
    assert _names("spider man")[0] == "Spider-Man: Brand New Day"
    assert _names("SPIDER-MAN")[0] == "Spider-Man: Brand New Day"
    assert _names("spiderman")[0] == "Spider-Man: Brand New Day"


def test_english_typos_are_tolerated():
    assert _names("avengrs")[0] == "Avengers: Doomsday"
    assert _names("avangers doomsday")[0] == "Avengers: Doomsday"
    assert _names("doomsdy")[0] == "Avengers: Doomsday"
    assert _names("clayfac")[0] == "Clayface"
    assert _names("spider mn")[0] == "Spider-Man: Brand New Day"
    assert _names("spidr man")[0] == "Spider-Man: Brand New Day"


def test_arabic_transliteration_aliases():
    assert _names("افنجرز")[0] == "Avengers: Doomsday"
    assert _names("الافنجرز")[0] == "Avengers: Doomsday"
    assert _names("سبايدر مان")[0] == "Spider-Man: Brand New Day"
    assert _names("ديون")[0] == "Dune: Part Three"
    assert _names("كلايفيس")[0] == "Clayface"


def test_arabic_phrase_aliases_and_spacing():
    assert search.expand_aliases("دومس داي") == "dooms day"
    assert search.expand_aliases("كلاي فيس") == "clay face"
    assert search.score("دومس داي", "Avengers: Doomsday") >= 0.90
    assert search.score("كلاي فيس", "Clayface") == 1.0


def test_arabic_word_with_optional_article():
    assert _names("محمود التاني")[0] == "Mahmoud El Tany (Arabic)"
    assert _names("محمود تاني")[0] == "Mahmoud El Tany (Arabic)"


def test_partial_title_ranks_the_specific_movie_first():
    assert _names("infinity vision")[0] == "Avengers: Doomsday (Infinity Vision)"
    assert _names("dune")[0] == "Dune: Part Three"


def test_no_false_positive_for_unrelated_title():
    assert "The Dino Family" not in _names("dune")
    assert search.rank("zzzzzz", MOVIES, key=lambda m: m["name"]) == []


def test_suggestions_are_offered_when_nothing_matches():
    hits = search.suggest("avengrs", MOVIES, key=lambda m: m["name"])
    assert hits
    assert hits[0].item["name"].startswith("Avengers")


def test_score_orders_exact_above_typo_above_noise():
    exact = search.score("clayface", "Clayface")
    typo = search.score("clayfac", "Clayface")
    noise = search.score("clayfac", "The Dino Family")
    assert exact > typo > noise
