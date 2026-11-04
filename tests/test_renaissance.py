"""Renaissance Cinemas parser regression tests."""

from __future__ import annotations

from models import AVAILABLE, SOLD_OUT, Movie
from providers.renaissance import (
    from_rns_date,
    normalize_time,
    parse_branches,
    parse_coming_soon,
    parse_dates,
    parse_movie_details,
    parse_movies,
    parse_showtimes,
    to_rns_date,
)

BRANCHES = """
<div class="row">
  <a class="venulink" href="https://rnscinemas.com/en/cinemas/madinty">
    <div class="venuelocation">Open Air Mall - Madinaty - New Cairo</div>
    <div class="venuename">Madinaty</div>
  </a>
  <a class="venulink" href="https://rnscinemas.com/en/cinemas/dandy_mall">
    <div class="venuelocation">6th of October - Alex Desert Road</div>
    <div class="venuename">Dandy Mall</div>
  </a>
</div>
"""

DAY = """
<html><body>
<div class="eventsDays"><ul>
  <li class="active"><a href="https://rnscinemas.com/en/cinemas/madinty/04-11-2026">Wed 04 Nov</a></li>
  <li><a href="https://rnscinemas.com/en/cinemas/madinty/05-11-2026">Thu 05 Nov</a></li>
</ul></div>

<div class="row showtimes_data">
  <div class="col-md-12 veneu_item">
    <div class="showtimes_location">
      <div class="showtimes_data">
        <div>
          <div class="msd_mob">
            <a href="https://rnscinemas.com/en/movie/clayface">
              <img src="https://rnscinemas.com/image/clayface.jpg">
            </a>
          </div>
          <a href="https://rnscinemas.com/en/movie/clayface">
            <div class="venuelocation">Action - Thriller</div>
          </a>
          <a href="https://rnscinemas.com/en/movie/clayface">
            <div class="venuename">Clayface</div>
          </a>
        </div>

        <div class="venuenameseats">
          <div class="bullitsdiv"><span class="bullitsdivitem">VIP</span></div>
        </div>
        <div class="show_time_dates">
          <ul>
            <li class="vip">
              <a class="js-booking-confirm-link"
                 data-booking-url="https://rnscinemas.com/en/booking/abc123"
                 data-event-time="04:30 PM"
                 data-is-3d="0"
                 data-movie-name-en="Clayface"
                 href="https://rnscinemas.com/en/booking/abc123">
                04:30 PM <span class="watch_exprince">(2D)</span>
              </a>
            </li>
          </ul>
        </div>

        <div class="venuenameseats">
          <div class="bullitsdiv">
            <span class="bullitsdivitem">Regular</span>
            <span class="bullitsdivstop">•</span>
            <span class="bullitsdivitem">Premium</span>
          </div>
        </div>
        <div class="show_time_dates">
          <ul>
            <li>
              <a class="disabled" href="javascript:void(0);showMesg();"
                 data-event-time="07:00 PM" data-movie-name-en="Clayface">
                07:00 PM <span class="watch_exprince">(2D)</span>
              </a>
            </li>
            <li>
              <a data-booking-url="https://rnscinemas.com/en/booking/def456"
                 data-event-time="10:00 PM" data-is-3d="1"
                 data-movie-name-en="Clayface"
                 href="https://rnscinemas.com/en/booking/def456">
                10:00 PM <span class="watch_exprince">(3D)</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>

  <div class="col-md-12 veneu_item">
    <div class="showtimes_location">
      <div class="showtimes_data">
        <div>
          <a href="https://rnscinemas.com/en/movie/whalefall">
            <div class="venuename">Whalefall</div>
          </a>
        </div>
        <div class="venuenameseats">
          <div class="bullitsdiv"><span class="bullitsdivitem">Regular</span></div>
        </div>
        <div class="show_time_dates">
          <ul>
            <li>
              <a data-booking-url="https://rnscinemas.com/en/booking/ghi789"
                 data-event-time="09:30 PM" data-movie-name-en="Whalefall"
                 href="https://rnscinemas.com/en/booking/ghi789">
                09:30 PM <span class="watch_exprince">(2D)</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>
"""

MOVIE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Movie",
  "name": "Clayface",
  "image": "https://rnscinemas.com/storage/app/movies/clayface.jpg",
  "description": "A dark psychological horror.",
  "duration": "PT120M"
}
</script>
</head><body>
<div class="movie_extra">
  Action/Thriller • Rated +18 • 120 Mins
  <a href="https://www.youtube.com/watch?v=abc">Watch Trailer</a>
</div>
</body></html>
"""

COMING = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ItemList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "url": "https://rnscinemas.com/en/movie/the-cat-in-the-hat",
          "name": "The Cat in the Hat",
          "description": "A family adventure.",
          "image": "https://rnscinemas.net/storage/app/movies/cat.jpg"
        }
      ]
    }
  ]
}
</script>
</head><body></body></html>
"""


def test_renaissance_date_conversion():
    assert to_rns_date("2026-11-04") == "04-11-2026"
    assert from_rns_date("04-11-2026") == "2026-11-04"
    assert normalize_time("04:30 PM") == "16:30"
    assert normalize_time("01:00 AM") == "01:00"


def test_parse_branches():
    branches = parse_branches(BRANCHES)
    assert [b.id for b in branches] == ["madinty", "dandy_mall"]
    assert branches[0].name == "Madinaty"
    assert branches[0].provider == "renaissance"


def test_parse_dates():
    assert parse_dates(DAY) == ["2026-11-04", "2026-11-05"]


def test_parse_movies():
    movies = parse_movies(DAY)
    assert [m.id for m in movies] == ["clayface", "whalefall"]
    assert movies[0].name == "Clayface"
    assert movies[0].poster_url == "https://rnscinemas.com/image/clayface.jpg"


def test_parse_showtimes_maps_status_and_formats():
    shows = parse_showtimes(DAY, "madinty", "2026-11-04")
    assert len(shows) == 4
    by_time = {(s.movie_id, s.time): s for s in shows}

    available = by_time[("clayface", "16:30")]
    assert available.status == AVAILABLE
    assert available.hall_type == "VIP"
    assert available.booking_url == "https://rnscinemas.com/en/booking/abc123"
    assert available.showtime_id == "abc123"
    assert available.seats_available is None

    closed = by_time[("clayface", "19:00")]
    assert closed.status == SOLD_OUT
    assert closed.booking_url is None
    assert closed.hall_type == "Standard"

    three_d = by_time[("clayface", "22:00")]
    assert three_d.status == AVAILABLE
    assert three_d.hall_type == "Standard 3D"
    assert three_d.showtime_id == "def456"

    other = by_time[("whalefall", "21:30")]
    assert other.movie_name == "Whalefall"
    assert other.status == AVAILABLE


def test_parse_movie_details():
    fallback = Movie("clayface", "Clayface", "clayface", "renaissance")
    details = parse_movie_details(MOVIE, fallback)
    assert details.duration_minutes == 120
    assert details.rating == "+18"
    assert details.poster_url == "https://rnscinemas.com/storage/app/movies/clayface.jpg"
    assert details.synopsis == "A dark psychological horror."
    assert details.trailer_url == "https://www.youtube.com/watch?v=abc"


def test_parse_coming_soon():
    movies = parse_coming_soon(COMING)
    assert [m.id for m in movies] == ["the-cat-in-the-hat"]
    assert movies[0].name == "The Cat in the Hat"
    assert movies[0].poster_url == "https://rnscinemas.net/storage/app/movies/cat.jpg"


def test_cinema_name_switches_to_renaissance():
    import config
    from i18n import ar, en

    original = config.settings.provider
    object.__setattr__(config.settings, "provider", "renaissance")
    try:
        assert ar.cinema_name() == "رينيسانس"
        assert en.cinema_name() == "Renaissance"
        assert "(رينيسانس)" in ar.onboard_intro("Zyad")
        assert "(Renaissance)" in en.onboard_intro("Zyad")
        assert ar.format_place("renaissance / madinty") == "(رينيسانس) / madinty"
        assert en.format_place("renaissance / madinty") == "(Renaissance) / madinty"
    finally:
        object.__setattr__(config.settings, "provider", original)
