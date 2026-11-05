"""Watch diffing for seats, booking openings and movie scope."""

from __future__ import annotations

from models import AVAILABLE, NOT_AVAILABLE, SOLD_OUT, Showtime
from watcher import BOOKING_OPENED, NEW_SHOWTIMES, SEATS_AVAILABLE, compute_watch_events


def showtime(
    status: str, time: str = "10:45", hall: str = "MAX", seats=None, mid="HO1"
) -> Showtime:
    return Showtime(
        provider="vox",
        branch_id="almaza",
        date="2026-12-16",
        movie_id=mid,
        movie_name="Avengers",
        time=time,
        hall_type=hall,
        status=status,
        seats_available=seats,
        booking_url="https://egy.voxcinemas.com/booking/0047-1",
        showtime_id="0047-1",
    )


def watch(time: str = "10:45", hall: str = "MAX", mid="HO1", wid=1):
    return {
        "id": wid,
        "showtime": time,
        "hall_type": hall,
        "movie_id": mid,
    }


def movie_watch(mid="HO1", wid=1):
    return {
        "id": wid,
        "showtime": "*",
        "hall_type": "*",
        "movie_id": mid,
        "scope": "movie",
    }


def test_booking_opened() -> None:
    events = compute_watch_events([showtime(NOT_AVAILABLE)], [showtime(AVAILABLE)], [watch()])
    assert len(events) == 1
    assert events[0][1].kind == BOOKING_OPENED


def test_sold_out_to_seats() -> None:
    events = compute_watch_events(
        [showtime(SOLD_OUT, seats=0)],
        [showtime(AVAILABLE, seats=4)],
        [watch()],
    )
    assert len(events) == 1
    assert events[0][1].kind == SEATS_AVAILABLE
    assert events[0][1].seats_available == 4


def test_seat_requirement_is_respected() -> None:
    watch_with_four = {**watch(), "required_seats": 4}
    too_few = compute_watch_events(
        [showtime(SOLD_OUT, seats=0)],
        [showtime(AVAILABLE, seats=2)],
        [watch_with_four],
    )
    assert too_few == []

    enough = compute_watch_events(
        [showtime(SOLD_OUT, seats=0)],
        [showtime(AVAILABLE, seats=4)],
        [watch_with_four],
    )
    assert [event[1].kind for event in enough] == [SEATS_AVAILABLE]


def test_seat_requirement_alerts_when_the_count_rises() -> None:
    required = {**watch(), "required_seats": 4}
    rising = compute_watch_events(
        [showtime(AVAILABLE, seats=2)],
        [showtime(AVAILABLE, seats=4)],
        [required],
    )
    assert [event[1].kind for event in rising] == [SEATS_AVAILABLE]
    assert rising[0][1].previous_seats == 2
    assert rising[0][1].seats_available == 4

    already_enough = compute_watch_events(
        [showtime(AVAILABLE, seats=4)],
        [showtime(AVAILABLE, seats=6)],
        [required],
    )
    assert already_enough == []

    default_watch = compute_watch_events(
        [showtime(AVAILABLE, seats=1)],
        [showtime(AVAILABLE, seats=2)],
        [watch()],
    )
    assert default_watch == []


def test_unknown_seats_fail_open() -> None:
    events = compute_watch_events(
        [showtime(SOLD_OUT, seats=0)],
        [showtime(AVAILABLE, seats=None)],
        [{**watch(), "required_seats": 4}],
    )
    assert [event[1].kind for event in events] == [SEATS_AVAILABLE]


def test_movie_watch_alerts_when_one_hall_rises() -> None:
    previous = [
        showtime(AVAILABLE, time="10:45", seats=2),
        showtime(AVAILABLE, time="13:30", hall="STANDARD", seats=0),
    ]
    current = [
        showtime(AVAILABLE, time="10:45", seats=4),
        showtime(AVAILABLE, time="13:30", hall="STANDARD", seats=0),
    ]
    events = compute_watch_events(previous, current, [{**movie_watch(), "required_seats": 4}])
    assert [event[1].kind for event in events] == [SEATS_AVAILABLE]
    assert events[0][1].seats_available == 4


def test_movie_watch_applies_the_requirement_per_showtime() -> None:
    previous = [
        showtime(SOLD_OUT, time="10:45", seats=0),
        showtime(SOLD_OUT, time="13:30", hall="STANDARD", seats=0),
    ]
    split_two = [
        showtime(AVAILABLE, time="10:45", seats=2),
        showtime(AVAILABLE, time="13:30", hall="STANDARD", seats=2),
    ]
    required = {**movie_watch(), "required_seats": 4}
    assert compute_watch_events(previous, split_two, [required]) == []

    one_hall = [
        showtime(AVAILABLE, time="10:45", seats=4),
        showtime(AVAILABLE, time="13:30", hall="STANDARD", seats=0),
    ]
    events = compute_watch_events(previous, one_hall, [required])
    assert [event[1].kind for event in events] == [SEATS_AVAILABLE]
    assert events[0][1].seats_available == 4


def test_no_change_no_event() -> None:
    assert compute_watch_events([showtime(AVAILABLE)], [showtime(AVAILABLE)], [watch()]) == []


def test_new_showtime_grouped_once_per_watch() -> None:
    events = compute_watch_events(
        [showtime(AVAILABLE, time="10:45")],
        [showtime(AVAILABLE, time="10:45"), showtime(AVAILABLE, time="13:30")],
        [watch(), watch(wid=2)],
    )
    new = [e for e in events if e[1].kind == NEW_SHOWTIMES]
    assert len(new) == 2  # one grouped event per watcher
    assert new[0][1].times == ("13:30",)


def test_unknown_showtime_does_not_alert() -> None:
    events = compute_watch_events([showtime("UNKNOWN")], [showtime("UNKNOWN")], [watch()])
    assert events == []


def test_movie_watch_aggregates_booking_opened_across_halls() -> None:
    previous = [
        showtime(NOT_AVAILABLE, time="10:45", hall="MAX"),
        showtime(NOT_AVAILABLE, time="13:30", hall="Standard"),
    ]
    current = [
        showtime(AVAILABLE, time="10:45", hall="MAX", seats=20),
        showtime(AVAILABLE, time="13:30", hall="Standard", seats=30),
    ]
    events = compute_watch_events(previous, current, [movie_watch()])
    assert len(events) == 1
    watch_row, event = events[0]
    assert watch_row["id"] == 1
    assert event.kind == BOOKING_OPENED
    assert event.times == ("10:45", "13:30")
    assert event.seats_available == 50


def test_movie_watch_aggregates_freed_seats() -> None:
    previous = [
        showtime(SOLD_OUT, time="10:45", hall="MAX", seats=0),
        showtime(SOLD_OUT, time="13:30", hall="Standard", seats=0),
    ]
    current = [
        showtime(AVAILABLE, time="10:45", hall="MAX", seats=2),
        showtime(AVAILABLE, time="13:30", hall="Standard", seats=4),
    ]
    events = compute_watch_events(previous, current, [movie_watch()])
    assert [(e[1].kind, e[1].times) for e in events] == [(SEATS_AVAILABLE, ("10:45", "13:30"))]
    assert events[0][1].seats_available == 6


def test_movie_watch_does_not_duplicate_single_hall_changes() -> None:
    previous = [showtime(NOT_AVAILABLE, time="10:45", hall="MAX")]
    current = [showtime(AVAILABLE, time="10:45", hall="MAX", seats=5)]
    events = compute_watch_events(previous, current, [movie_watch()])
    assert len(events) == 1
    assert events[0][1].kind == BOOKING_OPENED
    assert events[0][1].times == ("10:45",)


def test_showtime_scope_ignores_other_halls() -> None:
    previous = [
        showtime(NOT_AVAILABLE, time="10:45", hall="MAX"),
        showtime(NOT_AVAILABLE, time="13:30", hall="Standard"),
    ]
    current = [
        showtime(AVAILABLE, time="10:45", hall="MAX", seats=5),
        showtime(AVAILABLE, time="13:30", hall="Standard", seats=9),
    ]
    events = compute_watch_events(previous, current, [watch(time="10:45", hall="MAX")])
    assert len(events) == 1
    assert events[0][1].showtime.hall_type == "MAX"
