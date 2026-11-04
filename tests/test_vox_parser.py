"""VOX parser regression tests based on the real showtimes markup."""

from __future__ import annotations

from bs4 import BeautifulSoup

import strings
from models import AVAILABLE, SOLD_OUT, Movie
from providers.vox import (
    parse_coming_soon,
    parse_dates,
    parse_movie_details,
    parse_movies,
    parse_showtimes,
)

HTML = """
<html><body>
  <nav class="date-filter"><ol>
    <li><a href="/showtimes?c=almaza&amp;d=20261216">Wed 16 Dec</a></li>
    <li><span>Fri 18 Dec</span></li>
    <li><a href="/showtimes?c=almaza&amp;d=20261219">Sat 19 Dec</a></li>
  </ol></nav>
  <form action="/showtimes" method="get">
    <input type="hidden" name="c" value="almaza">
    <input type="hidden" name="d" value="20261218">
  </form>

  <article class="movie-compare" data-slug="avengers-doomsday-infinity-vision"
           data-identifier="avengers-doomsday-infinity-vision">
    <aside class="movie-hero" data-slug="avengers-doomsday-infinity-vision">
      <img class="hero" src="https://assets.voxcinemas.com/heroes/B_HO00013676.jpg">
      <div>
        <h2>Avengers: Doomsday (Infinity Vision)</h2>
        <span class="tag">English</span>
        <a class="read-more" href="/movies/avengers-doomsday-infinity-vision">Info</a>
      </div>
    </aside>
    <div class="dates">
      <ol class="showtimes">
        <li>
          <strong>MAX</strong>
          <ol>
            <li data-id="0047-276898">
              <span class="action showtime unavailable">10:45am</span>
            </li>
            <li data-id="0047-276902">
              <a class="action showtime" href="https://egy.voxcinemas.com/booking/0047-276902">2:30pm</a>
            </li>
          </ol>
        </li>
        <li>
          <strong>Standard</strong>
          <ol>
            <li data-id="0047-276776">
              <span class="action showtime unavailable">6:45pm</span>
            </li>
          </ol>
        </li>
      </ol>
    </div>
  </article>

  <nav>
    <a href="/movies/whatson">MOVIES</a>
    <a href="/movies/comingsoon">COMING SOON</a>
  </nav>
</body></html>
"""


def test_selected_date_is_parsed_from_hidden_input():
    dates = parse_dates(HTML)
    assert "2026-12-18" in dates
    assert "2026-12-16" in dates


def test_movie_names_come_from_heading_not_info_link():
    movies = parse_movies(HTML)
    assert [m.name for m in movies] == ["Avengers: Doomsday (Infinity Vision)"]
    assert movies[0].id == "avengers-doomsday-infinity-vision"


def test_unavailable_sessions_are_kept_as_sold_out_with_hall():
    shows = parse_showtimes(HTML, "almaza", "2026-12-18")
    assert len(shows) == 3
    by_time = {s.time: s for s in shows}

    assert by_time["10:45"].hall_type == "MAX"
    assert by_time["10:45"].status == SOLD_OUT
    assert by_time["10:45"].booking_url is None

    assert by_time["14:30"].hall_type == "MAX"
    assert by_time["14:30"].status == AVAILABLE
    assert by_time["14:30"].booking_url

    assert by_time["18:45"].hall_type == "Standard"
    assert by_time["18:45"].status == SOLD_OUT


def test_parsers_accept_one_shared_soup():
    soup = BeautifulSoup(HTML, "lxml")

    assert parse_dates(soup) == parse_dates(HTML)
    assert parse_movies(soup) == parse_movies(HTML)
    assert parse_showtimes(soup, "almaza", "2026-12-18") == parse_showtimes(
        HTML, "almaza", "2026-12-18"
    )


def test_sold_out_button_is_not_labelled_as_not_open():
    label = strings.showtime_button("10:45", "MAX", SOLD_OUT, None)
    assert "🔴" in label
    assert "⚪" not in label


def test_day_without_sessions_says_booking_has_not_opened():
    message = strings.no_movies()
    assert "لسه مفتحش" in message


COMING_SOON_HTML = """
<html><body>
  <section class="coming-soon">
    <article class="movie-card">
      <a href="/movies/dune-part-three"><img src="/media/dune.jpg" alt="Dune"></a>
      <h3>Dune: Part Three</h3>
    </article>
    <article class="movie-card">
      <a href="/movies/avengers-secret-wars"><img src="/media/avengers.jpg"></a>
      <h3>Avengers: Secret Wars</h3>
    </article>
  </section>
</body></html>
"""

DETAILS_HTML = """
<html><head>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Movie",
    "name": "Dune: Part Three | VOX Cinemas Egypt",
    "image": "https://assets.voxcinemas.com/posters/dune.jpg",
    "duration": "PT2H46M",
    "contentRating": "PG-13",
    "inLanguage": "en"
  }
  </script>
</head><body><h1>Dune: Part Three</h1></body></html>
"""


def test_coming_soon_parses_plain_movie_cards():
    movies = parse_coming_soon(COMING_SOON_HTML)
    names = {m.name for m in movies}
    assert names == {"Dune: Part Three", "Avengers: Secret Wars"}
    dune = next(m for m in movies if m.name == "Dune: Part Three")
    assert dune.slug == "dune-part-three"
    assert dune.poster_url.endswith("/media/dune.jpg")


def test_movie_details_read_jsonld_and_strip_site_suffix():
    details = parse_movie_details(DETAILS_HTML, Movie("HO1", "Dune", "dune-part-three"))
    assert details.name == "Dune: Part Three"
    assert details.poster_url == "https://assets.voxcinemas.com/posters/dune.jpg"
    assert details.duration_minutes == 166
    assert details.rating == "PG-13"
    assert details.language == "English"


def test_movie_details_fall_back_to_listing_fields():
    fallback = Movie(
        "HO2",
        "Avengers",
        "avengers",
        poster_url="https://assets/avengers.jpg",
        duration_minutes=120,
    )
    details = parse_movie_details("<html><body><h1>Avengers</h1></body></html>", fallback)
    assert details.poster_url == "https://assets/avengers.jpg"
    assert details.duration_minutes == 120


def test_movie_details_read_text_duration_rating_and_language():
    html = (
        '<html><body><h1>Film</h1><p>2h 5m · 15+</p><span class="tag">Arabic</span></body></html>'
    )
    details = parse_movie_details(html, Movie("HO3", "Film", "film"))
    assert details.duration_minutes == 125
    assert details.rating == "15+"
    assert details.language == "العربية"


def test_movie_details_read_synopsis_and_normalise_youtube_trailer():
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@type": "Movie",
        "name": "Dune: Part Three",
        "description": "Paul Atreides unites with the Fremen.",
        "trailer": {
          "@type": "VideoObject",
          "embedUrl": "https://www.youtube.com/embed/dQw4w9WgXcQ"
        }
      }
      </script>
    </head><body><h1>Dune: Part Three</h1></body></html>
    """
    details = parse_movie_details(html, Movie("HO4", "Dune", "dune"))
    assert details.synopsis == "Paul Atreides unites with the Fremen."
    assert details.trailer_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_movie_details_fall_back_to_open_graph_text_and_video():
    html = """
    <html><head>
      <meta property="og:description" content="A short synopsis.">
      <meta property="og:video" content="https://youtu.be/abc123XYZ">
    </head><body><h1>Film</h1></body></html>
    """
    details = parse_movie_details(html, Movie("HO5", "Film", "film"))
    assert details.synopsis == "A short synopsis."
    assert details.trailer_url == "https://www.youtube.com/watch?v=abc123XYZ"


def test_movie_details_reject_non_http_trailer_links():
    html = """
    <html><head>
      <meta property="og:video" content="javascript:alert(1)">
      <script type="application/ld+json">
      {"@type": "Movie", "name": "Film", "trailer": "data:text/html,boom"}
      </script>
    </head><body><h1>Film</h1></body></html>
    """
    details = parse_movie_details(html, Movie("HO6", "Film", "film"))
    assert details.trailer_url is None


def test_movie_details_keep_fallback_synopsis_and_trailer():
    fallback = Movie(
        "HO7",
        "Film",
        "film",
        synopsis="Old synopsis",
        trailer_url="https://www.youtube.com/watch?v=keepme123",
    )
    details = parse_movie_details("<html><body><h1>Film</h1></body></html>", fallback)
    assert details.synopsis == "Old synopsis"
    assert details.trailer_url == "https://www.youtube.com/watch?v=keepme123"
