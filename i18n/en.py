"""American English copy for every user-facing surface.

This catalog mirrors :mod:`i18n.ar` name for name and signature for signature;
``tests/test_i18n.py`` fails the build if the two drift apart.  Keep sentences
short and plain: the audience is a general cinema-goer, not a developer.

Dynamic values are HTML-escaped because messages are sent with parse_mode=HTML.
"""

from __future__ import annotations

from datetime import date as date_cls

from i18n.base import esc
from imax import CERTIFIED_DIGITAL, FULL_70MM, PARTIAL_70MM, PARTIAL_DIGITAL, UNKNOWN
from models import AVAILABLE, NOT_AVAILABLE, SOLD_OUT
from models import format_key as _format_key
from version import __version__

CODE = "en"
NAME = "English"
RTL = False

STATUS_LABELS_EN = {
    AVAILABLE: "Available",
    SOLD_OUT: "Sold out",
    NOT_AVAILABLE: "Not on sale yet",
    UNKNOWN: "Unknown",
}

FORMAT_LABELS_EN = {
    "IMAX": "IMAX",
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
    "THEATRE": "Theatre",
    "3D": "3D",
    "2D": "2D",
}

_WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _plural(value: int, singular: str, plural: str | None = None) -> str:
    return singular if value == 1 else (plural or f"{singular}s")


def _count(value: int, singular: str, plural: str | None = None) -> str:
    return f"{value} {_plural(value, singular, plural)}"


def _seats(value: int) -> str:
    return _count(value, "seat")


def format_time(value: str) -> str:
    """``10:45`` / ``10:45am`` / ``22:00`` -> ``10:45 AM`` / ``10:45 AM`` / ``10:00 PM``."""

    raw = (value or "").strip().lower().replace(".", "")
    suffix = ""
    if raw.endswith("pm"):
        suffix = "pm"
        raw = raw[:-2].strip()
    elif raw.endswith("am"):
        suffix = "am"
        raw = raw[:-2].strip()
    parts = raw.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        hour = int(parts[0])
        minute = int(parts[1][:2])
        if suffix:
            # Input carried am/pm; normalize it to 24 hours first.
            if suffix == "pm" and hour < 12:
                hour += 12
            if suffix == "am" and hour == 12:
                hour = 0
        display_suffix = "PM" if hour >= 12 else "AM"
        hour12 = hour % 12 or 12
        return f"{hour12}:{minute:02d} {display_suffix}"
    return esc(value)


def format_date(value: str) -> str:
    if value == "*":
        return "All days"
    try:
        d = date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return esc(value)
    return f"{d.strftime('%b')} {d.day}"


def relative_date(value: str, today: date_cls | None = None) -> str:
    if value == "*":
        return "Every available day"
    today = today or date_cls.today()
    try:
        d = date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return format_date(value)
    delta = (d - today).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if delta == -1:
        return "Yesterday"
    return f"{_WEEKDAYS_EN[d.weekday()]} {d.day}/{d.month:02d}"


# --------------------------------------------------------------------- buttons
BTN_ADD_WATCH = "➕ Add a watch"
BTN_SEARCH = "🔎 Find a movie"
BTN_SEARCH_MOVIE = "🔎 Search by name"
BTN_SEARCH_AGAIN = "🔎 Search again"
BTN_ALL_MOVIES = "📋 All movies"
BTN_MY_WATCHES = "🎟️ My watches"
BTN_SETTINGS = "⚙️ Settings"
BTN_SUPPORT = "💛 Support the project"
BTN_FEEDBACK = "✍️ Send feedback"
BTN_BACK = "⬅️ Back"
BTN_HOME = "🏠 Home"
BTN_CANCEL = "Cancel"
BTN_NEXT = "Next"
BTN_PREV = "Previous"
BTN_RETRY = "🔄 Try again"
BTN_ONBOARD_NEXT = "Next ➡️"
BTN_ONBOARD_SKIP = "Skip"
BTN_ONBOARD_START = "Let's start 🎬"
BTN_CONFIRM = "Confirm watch ✅"
BTN_DELETE_ALL = "🗑️ Delete all"
BTN_CONFIRM_DELETE_ALL = "Yes, delete all"
BTN_OPEN_BOOKING = "🎟️ Open booking"
BTN_WATCH_MOVIE = "Watch this movie"
BTN_STOP_ALERTS = "Stop these alerts"
BTN_REMOVE_WATCH = "❌ Remove watch"
BTN_CONFIRM_REMOVE_WATCH = "Yes, remove it"
BTN_SNOOZE = "⏰ Remind me in an hour"
BTN_UNSNOOZE = "🔕 Resume alerts"
BTN_MODE_ALL = "🔔 Everything"
BTN_MODE_SEATS = "🪑 Seats came back"
BTN_MODE_OPENING = "🎟️ Booking opens only"
BTN_WATCH_SETTINGS = "⚙️ Alert settings"
BTN_WATCH_ALL_SHOWTIMES = "🔔 Watch every showtime that day"
BTN_WATCH_ALL_DATES = "📅 Watch every available date"
BTN_I_PAID = "I paid ✅"
BTN_YES_DELETE = "Yes, delete my data"
BTN_NO = "No, take me back"
BTN_DONE = "Done ✅"
BTN_ALL_SHOWTIMES = "All showtimes"
BTN_ALL_HALLS = "All halls"
BTN_ALL_FORMATS = "🎭 All formats"
BTN_MOVIE_INFO = "ℹ️ Movie info"
BTN_TRAILER = "▶️ Watch trailer"
BTN_BACK_TO_SHOWTIMES = "🔙 Back to showtimes"
BTN_VODAFONE_CASH = "Vodafone Cash"
BTN_INSTAPAY = "InstaPay"
BTN_CANCELLATIONS = "Seat alerts"
BTN_QUIET_HOURS = "🕰️ Quiet hours"
BTN_QUIET_CUSTOM = "🕰️ Custom time"
BTN_DISCOVERY_ALERTS = "New movie alerts"
BTN_BRANCHES_FILTER = "🎯 Alert branches"
BTN_TYPES_FILTER = "📌 Alert types"
BTN_HALL_FILTER = "🎭 Hall type"
BTN_QUIET_WATCHES = "Watch alerts respect quiet hours"
BTN_DELETE_MY_DATA = "🗑️ Delete my data"
BTN_COPY_PHONE = "📋 Copy number"
BTN_MANAGE_WATCH = "⚙️ Manage watch"
BTN_LANGUAGE = "🌐 Language"
BTN_ARABIC = "العربية"
BTN_ENGLISH = "English"

# Public commands are registered in the default scope.  Admin commands are
# registered only in the admin's private chat scope, so they never appear in
# the public menu.
PUBLIC_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Main menu"),
    ("add", "Add a new watch"),
    ("search", "Search for a movie by name"),
    ("watches", "My watches"),
    ("settings", "Settings"),
    ("help", "Help"),
    ("privacy", "Privacy and data"),
    ("delete_me", "Delete my data"),
    ("cancel", "Cancel any step"),
)

ADMIN_COMMANDS: tuple[tuple[str, str], ...] = (
    ("admin", "Admin panel"),
    ("status", "(VOX) connection status"),
    ("grant", "Grant a user supporter access"),
    ("revoke", "Revoke supporter access"),
    ("imax", "Set a movie's IMAX status"),
)


# ----------------------------------------------------------------------- start
def dashboard(
    name: str = "",
    active_watches: int = 0,
    next_watch: str | None = None,
    limit: int | None = None,
) -> str:
    who = f", {esc(name)}" if name else ""
    lines = [
        "🎬 <b>Cinema Radar</b>",
        f"Welcome{who} 👋",
        "",
    ]
    if active_watches:
        lines.append(
            f"You have <b>{active_watches}</b> active {_plural(active_watches, 'watch', 'watches')}."
        )
    else:
        lines.append("No active watches yet — start with a tap below.")
    if next_watch:
        lines.append(f"⏭️ Next watch: {next_watch}")
    if limit:
        lines.append(f"<i>Your current limit is {_count(limit, 'watch', 'watches')}.</i>")
    lines += ["", "Pick an option below 👇"]
    return "\n".join(lines)


def version_line() -> str:
    return f"<i>Version v{esc(__version__)}</i>"


def language_screen() -> str:
    return (
        "🌐 <b>Choose your language</b> · <b>اختار لغتك</b>\n\n"
        "You can change it anytime from Settings.\n"
        "تقدر تغيّرها في أي وقت من الإعدادات."
    )


def language_saved(name: str = "") -> str:
    return f"Done ✅ Your language is now <b>{esc(name or NAME)}</b>."


def dashboard_next(movie: str, branch: str, date: str, showtime: str, scope: str | None) -> str:
    when = relative_date(date)
    if (scope or "showtime") == "movie_all_dates":
        detail = "All dates"
    elif (scope or "showtime") == "movie":
        detail = "All showtimes"
    elif showtime and showtime != "*":
        detail = format_time(showtime)
    else:
        detail = "All showtimes"
    return f"<b>{esc(movie)}</b> — {esc(branch)} — {when} · {esc(detail)}"


def step_header(step: int, total: int, path: str) -> str:
    return f"<i>{step}/{total} · {esc(path)}</i>"


def page_label(page: int, pages: int) -> str:
    if pages <= 1:
        return ""
    return f"<i>Page {page + 1} of {pages}</i>"


# ------------------------------------------------------------------ onboarding
def onboard_intro(name: str = "") -> str:
    who = f", {esc(name)}" if name else ""
    return (
        "🎬 <b>Cinema Radar</b>\n"
        f"Welcome{who} 👋\n\n"
        "I watch (VOX) showtimes in Egypt,\n"
        "and message you the moment booking opens\n"
        "or a seat frees up.\n\n"
        "No more refreshing the site yourself."
    )


def onboard_alerts() -> str:
    return (
        "🔔 <b>What you'll get</b>\n\n"
        "• <b>Booking opened</b> — when a showtime goes on sale.\n"
        "• <b>Seats came back</b> — when a sold-out show frees up.\n"
        "• <b>New dates</b> — when a movie opens a new day.\n\n"
        "Set the alert type for each watch in\n"
        "⚙️ Alert settings."
    )


def onboard_safety() -> str:
    return (
        "🙏 <b>Before we start</b>\n\n"
        "• The bot is free and only sends the booking link.\n"
        "• It never books or pays for you.\n"
        "• It never asks for your name, phone or payment details.\n"
        "• It is unofficial and not affiliated with (VOX).\n\n"
        "Full details: /privacy\n"
        "Erase your data anytime: /delete_me"
    )


def onboard_progress(step: int) -> str:
    return f"<i>Step {step + 1} of 3</i>"


def help_text() -> str:
    return (
        "<b>How to use Cinema Radar</b>\n\n"
        "1. Tap <b>➕ Add a watch</b>.\n"
        "2. Pick the branch, date, movie and showtime — or watch every showtime "
        "that day/every date, and filter by format if you want (IMAX, 4DX, VIP…).\n"
        "3. When booking opens or seats come back, you get a message with the booking link.\n\n"
        "From inside an alert you can open booking, remove the watch, or snooze it for an hour. "
        "From <b>🎟️ My watches</b> you can set the alert type: everything, seats back, "
        "or booking opens only.\n\n"
        "Can't find the movie? Tap <b>🔎 Search by name</b> and type part of the title "
        "in Arabic or English — the bot tolerates typos too.\n\n"
        "<b>Useful commands</b>\n"
        "/start Main menu\n"
        "/add Add a new watch\n"
        "/search Search for a movie by name\n"
        "/watches My watches\n"
        "/settings Settings\n"
        "/help Help\n"
        "/privacy What data we store\n"
        "/delete_me Delete your data\n"
        "/cancel Cancel any step\n\n"
        "⚠️ The bot is unofficial and not affiliated with (VOX Cinemas). Data may be "
        "delayed or wrong, and booking happens on the cinema's own site.\n\n"
        f"{version_line()}"
    )


def privacy_text() -> str:
    return (
        "<b>Privacy in short — you're safe</b>\n\n"
        "You don't need to give me your name, phone number or email. I know you by your "
        "Telegram ID only, and that's how I can send you alerts.\n\n"
        "<b>What I store:</b>\n"
        "• The watches you chose (branch, date, movie, showtime).\n"
        "• Your simple settings, and whether you supported the project.\n"
        "• If you send feedback, the text and your username so I can reply.\n\n"
        "<b>What I never store:</b>\n"
        "• Card numbers or any banking details.\n"
        "• Your phone number or email.\n"
        "• Your chats with anyone else.\n\n"
        "Transfer screenshots reach the admin only, and they are deleted with your data "
        "if you use /delete_me. Nobody else sees your data — I never sell or share it.\n\n"
        "If you want a clean slate, /delete_me erases everything in a second."
    )


# ------------------------------------------------------------------ add watch
def choose_branch() -> str:
    return f"{step_header(1, 5, 'Branch')}\nPick a branch 🏢"


def choose_date(branch: str) -> str:
    return f"{step_header(2, 5, branch)}\nPick a date 📅"


def choose_movie(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return (
        f"{step_header(3, 5, path)}\nPick a movie 🎞️\nCan't find it? Tap <b>🔎 Search by name</b>."
    )


def search_choose_branch(query: str = "") -> str:
    head = f"{step_header(2, 5, 'Search')}\n"
    if query:
        return f"{head}Searching for “<b>{esc(query)}</b>” 🔎\nPick the branch first:"
    return f"{head}Movie search 🔎\nPick the branch first:"


def search_prompt(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return (
        f"{step_header(3, 5, path)}\n\n"
        "Type the movie name in Arabic or English 🔎\n"
        "Typos are fine — part of the name is enough."
    )


def search_too_short() -> str:
    return "Type at least two letters so I can search 🔎"


def search_results(query: str, count: int, total: int) -> str:
    return (
        f"Results for “<b>{esc(query)}</b>” — "
        f"<b>{count}</b> of {total} movies\n"
        "Pick the movie you want:"
    )


def search_no_results(query: str, suggestions: list[str] | None = None) -> str:
    lines = [f"No movie close to “<b>{esc(query)}</b>” on that date."]
    if suggestions:
        lines.append("Did you mean one of these? Tap it 👇")
    else:
        lines.append("Try part of the name, the English title, or browse all movies.")
    return "\n".join(lines)


def choose_showtime(movie: str, date: str, extra: str = "") -> str:
    path = f"{relative_date(date)} › {movie}"
    lines = [
        step_header(4, 5, path),
        "Pick the showtime you want to watch 🎟️",
        "“Available” = you can book now, “Sold out” = fully booked.",
        "Want a specific format (IMAX, 4DX, VIP…)? Pick it from the buttons above.",
    ]
    if extra:
        lines.insert(1, extra)
    return "\n".join(lines)


def format_label(value: object) -> str:
    key = _format_key(value)
    if key == "*":
        return "All formats"
    return FORMAT_LABELS_EN.get(key, str(value or key))


def format_filtered(value: str | None) -> str:
    if value is None:
        return "Showing all formats 🎭"
    return f"Showing {esc(value)} only 🎭"


def format_not_found() -> str:
    return "That format isn't available for the showtimes shown. Try another one."


def showtime_button(time: str, hall: str, status: str, seats: int | None) -> str:
    if status == AVAILABLE:
        mark = "Available"
        if seats is not None:
            mark = f"Available · {_seats(seats)}"
    elif status == SOLD_OUT:
        mark = "Sold out"
    else:
        mark = "Not on sale yet"
    return f"{format_time(time)} · {esc(hall)} · {mark}"


def confirm_watch(
    branch: str, date: str, movie: str, time: str, hall: str, status: str = ""
) -> str:
    if status == SOLD_OUT:
        note = "This show is sold out right now. I'll watch it and message you as soon as seats come back."
    elif status == NOT_AVAILABLE:
        note = "I'll message you as soon as booking opens."
    elif status == AVAILABLE:
        note = "This show is available now — you can book right away, and I'll watch it if seats run out."
    else:
        note = "I'll watch this show and message you when anything changes."
    return (
        f"{step_header(5, 5, 'Confirm')}\n\n"
        "<b>Confirm watch</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} ({format_date(date)})\n"
        f"🎞️ {esc(movie)}\n"
        f"🎟️ {format_time(time)} — {esc(hall)}\n\n"
        f"{note}"
    )


def no_data() -> str:
    return (
        "Still fetching data from the cinema. Try again in a minute 🙏\n"
        "I don't send requests to the cinema site while you browse, to keep the bot running."
    )


def no_dates() -> str:
    return "No dates are available for this branch right now. Try another branch or wait a bit."


def no_movies() -> str:
    return (
        "Booking isn't open for that date yet. Try another date or wait for it to open.\n"
        "When showtimes appear, they'll be right here."
    )


def no_showtimes() -> str:
    return "Booking isn't open for this movie on that date yet. Try another movie or date."


IMAX_LINES_EN = {
    FULL_70MM: "🎥 Shot entirely on IMAX 70mm cameras — worth IMAX",
    PARTIAL_70MM: "🎥 Parts shot on IMAX 70mm cameras — worth IMAX",
    CERTIFIED_DIGITAL: "🎥 Shot on certified IMAX cameras — worth IMAX",
    PARTIAL_DIGITAL: "🎥 Parts shot on certified IMAX cameras",
    UNKNOWN: "🎥 Not known — not on the IMAX film list",
}


def imax_line(status: str | None) -> str:
    """English line for the movie card, or an empty string when not looked up."""

    if not status:
        return ""
    return IMAX_LINES_EN.get(status, "🎥 Not on the IMAX film list — likely an upscale")


def movie_info(name: str, synopsis: str | None, facts: str = "", extra: str = "") -> str:
    lines = [f"🎬 <b>{esc(name)}</b>"]
    if facts:
        lines.append(facts)
    if extra:
        lines.append(extra)
    if synopsis:
        lines.append("")
        lines.append(esc(synopsis))
    else:
        lines.append("")
        lines.append("No synopsis is available for this movie yet.")
    return "\n".join(lines)


def confirm_movie_watch(
    branch: str,
    date: str,
    movie: str,
    count: int,
    statuses: list[str] | None = None,
    hall: str | None = None,
) -> str:
    states = statuses or []
    if states and all(state == "AVAILABLE" for state in states):
        note = "Shows are available now, and I'll watch each one in case seats come back."
    elif states and all(state == "SOLD_OUT" for state in states):
        note = "Every show is sold out right now. I'll watch them and message you as soon as seats come back."
    else:
        note = "I'll watch every showtime for this movie that day, and message you when booking opens or seats come back."
    ticket = f"🎟️ All showtimes ({_count(count, 'showtime')})"
    if hall:
        ticket = f"🎭 {esc(hall)} — all showtimes ({_count(count, 'showtime')})"
    return (
        f"{step_header(5, 5, 'Confirm')}\n\n"
        "<b>Confirm full-day watch</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} ({format_date(date)})\n"
        f"🎞️ {esc(movie)}\n"
        f"{ticket}\n\n"
        f"{note}"
    )


def watch_created_movie(
    branch: str, date: str, movie: str, count: int, hall: str | None = None
) -> str:
    format_text = f" — {esc(hall)}" if hall else ""
    return (
        "All set ✅\n"
        f"Watching <b>{esc(movie)}</b> — {relative_date(date)} — "
        f"{_count(count, 'showtime')}{format_text} — {esc(branch)}.\n"
        "As soon as any booking opens or seats come back, you'll get a message.\n\n"
        "From <b>⚙️ Alert settings</b> you can choose: everything, seats back, "
        "or booking opens only."
    )


def watch_created(branch: str, date: str, movie: str, time: str, hall: str) -> str:
    return (
        "All set ✅\n"
        f"Watching <b>{esc(movie)}</b> — {relative_date(date)} — "
        f"{format_time(time)} — {esc(hall)} — {esc(branch)}.\n"
        "You'll get a message when anything changes.\n\n"
        "From <b>⚙️ Alert settings</b> you can choose: everything, seats back, "
        "or booking opens only."
    )


def confirm_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        f"{step_header(5, 5, 'Confirm')}\n\n"
        "<b>Confirm watch on every date</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"🎞️ {esc(movie)}\n"
        f"📅 Every date available now ({_count(count, 'day')}){format_text}\n\n"
        "I'll watch every day this movie plays at this branch, plus any new date that opens.\n"
        "When booking opens or seats come back, you'll get a message."
    )


def watch_created_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f" — {esc(hall)}" if hall else ""
    return (
        "All set ✅\n"
        f"Watching <b>{esc(movie)}</b> at <b>{esc(branch)}</b>{format_text} — "
        f"every available date ({_count(count, 'day')} for now).\n"
        "If a new date opens or seats come back, you'll get a message.\n\n"
        "From <b>⚙️ Alert settings</b> you can pick the alert type."
    )


def all_dates_unavailable() -> str:
    return "No dates are available for this branch right now. Try a specific date or wait for booking to open."


def watch_limit_reached(
    limit: int,
    supporter_limit: int = 10,
    min_amount: int = 50,
    is_supporter: bool = False,
) -> str:
    if is_supporter:
        return (
            f"You've reached the maximum ({_count(limit, 'watch', 'watches')}).\n\n"
            "Remove an old watch from <b>My watches</b> to add a new one."
        )
    return (
        f"You've reached the free limit ({_count(limit, 'watch', 'watches')}).\n\n"
        f"To reach <b>{supporter_limit} watches</b>, you can support the project "
        f"<b>once</b> with a minimum of {min_amount} EGP from <b>Support the project</b> 💛\n"
        "Or remove an old watch from <b>My watches</b>."
    )


def watches_trimmed(removed: int, limit: int) -> str:
    return (
        f"I trimmed {removed} of your watches because the new limit is "
        f"<b>{_count(limit, 'watch', 'watches')}</b>.\n"
        "The watches with the nearest dates stayed with you; you can add more from "
        "<b>Support the project</b> or remove and add again."
    )


def duplicate_watch() -> str:
    return "You already have this watch 👌"


# ------------------------------------------------------------------- my watches
def no_watches() -> str:
    return "No watches yet. Tap <b>Add a watch</b> and get started 🎬"


def watches_retention_note(days: int) -> str:
    return (
        f"<i>Watches are removed automatically {_count(days, 'day')} after their show starts.</i>"
    )


def watches_group(date: str) -> str:
    if date == "*":
        return "📅 <b>Every available date</b>"
    return f"📅 <b>{relative_date(date)}</b>"


def confirm_delete_all(count: int) -> str:
    return (
        "🗑️ <b>Are you sure?</b>\n\n"
        f"I'll delete <b>{_count(count, 'active watch', 'active watches')}</b>. "
        "This can't be undone, and you'd start over to watch them again."
    )


def confirm_remove_watch(movie: str, when: str) -> str:
    return (
        "❌ <b>Remove this watch?</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"📅 {esc(when)}\n\n"
        "You won't get alerts about it anymore."
    )


def watches_page_title(count: int) -> str:
    return f"<b>🎟️ My watches</b> — {_count(count, 'active watch', 'active watches')}"


def watch_mode_label(mode: str | None) -> str:
    return {
        "seats": "Seats came back 🪑",
        "opening": "Booking opens only 🎟️",
    }.get(mode or "all", "Everything 🔔")


def watch_row(
    branch: str,
    date: str,
    movie: str,
    time: str,
    hall: str,
    status: str,
    seats: int | None,
    mode: str | None = "all",
    snoozed_until: str | None = None,
    scope: str | None = "showtime",
) -> str:
    state = STATUS_LABELS_EN.get(status, status)
    if seats is not None:
        state = f"{state} · {_seats(seats)}"
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 Every available date · all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text} · {esc(state)}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)} · {esc(state)}"
    lines = [
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {esc(branch)} — {relative_date(date)}",
        ticket,
        f"🔔 {watch_mode_label(mode)}",
    ]
    if snoozed_until:
        lines.append("⏰ Alerts are snoozed for now")
    return "\n".join(lines)


def watch_detail(
    branch: str,
    date: str,
    movie: str,
    time: str,
    hall: str,
    mode: str | None,
    snoozed_until_text: str | None = None,
    scope: str | None = "showtime",
) -> str:
    snooze = (
        f"⏰ Snoozed until {esc(snoozed_until_text)}" if snoozed_until_text else "⏰ Not snoozed"
    )
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 Every available date — all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)}"
    return (
        "<b>Watch settings ⚙️</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)} — {relative_date(date)}\n"
        f"{ticket}\n\n"
        f"🔔 Alerts: <b>{watch_mode_label(mode)}</b>\n"
        f"{snooze}\n\n"
        "Pick the alert type that suits you:"
    )


def watch_reminder(
    movie: str,
    branch: str,
    date: str,
    time: str,
    hall: str,
    status: str,
    seats: int | None,
    scope: str | None = "showtime",
) -> str:
    state = STATUS_LABELS_EN.get(status, status)
    if seats is not None:
        state = f"{state} · {_seats(seats)}"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"🎟️ Every available date — all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)}"
    lines = [
        "⏰ <b>Here's the watch you asked about</b>",
        "",
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {esc(branch)} — {relative_date(date)}",
        ticket,
    ]
    if scope != "movie_all_dates":
        lines.append(f"Status now: {esc(state)}")
    lines += ["", "Open the booking page and see what's available."]
    return "\n".join(lines)


def watch_snoozed(until_text: str) -> str:
    return f"Done ⏰ I'll hold alerts until {esc(until_text)}, then remind you."


def watch_unsnoozed() -> str:
    return "Alerts are back ✅"


def watch_removed_from_alert() -> str:
    return "✅ Watch removed. You won't get alerts about it anymore."


def watch_mode_set(mode: str | None) -> str:
    return f"Done ✅ Alerts are now: {watch_mode_label(mode)}"


def watch_removed() -> str:
    return "Watch removed ✅"


def all_watches_removed() -> str:
    return "All watches deleted ✅"


def watch_expired_summary(items: list[str], more: int = 0) -> str:
    total = len(items) + more
    lines = [f"🧹 <b>Removed {_count(total, 'finished watch', 'finished watches')}</b>", ""]
    lines.extend(f"• {item}" for item in items)
    if more:
        lines.append(f"• and {_count(more, 'more watch', 'more watches')}")
    lines += [
        "",
        "Their shows have already started, so I can't send alerts about them anymore.",
        "To watch a new show, tap “Add a watch”.",
    ]
    return "\n".join(lines)


def watch_expired_row(movie: str, branch: str, date: str, showtime: str) -> str:
    when = relative_date(date)
    if showtime and showtime != "*":
        when = f"{when} — {format_time(showtime)}"
    return f"<b>{esc(movie)}</b> — {esc(branch)} — {when}"


# --------------------------------------------------------------------- alerts
def alert_booking_opened(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f" · {_seats(seats)} available" if seats else ""
    return (
        "🎟️ <b>Booking just opened!</b>\n\n"
        f"<b>{esc(movie)}</b>\n"
        f"{esc(hall)} — {format_time(time)} — {esc(branch)} — {relative_date(date)}"
        f"{seat_text}\n\n"
        "Book before it fills up!"
    )


def alert_seats_available(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f"{_seats(seats)} available now." if seats else "Seats are available now."
    return (
        "🪑 <b>Seats are back!</b>\n\n"
        f"<b>{esc(movie)}</b>\n"
        f"{esc(hall)} — {format_time(time)} — {esc(branch)} — {relative_date(date)}\n"
        f"{seat_text}\n\n"
        "Go grab them 🏃"
    )


def alert_movie_booking_opened(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    seats: int | None = None,
) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    seat_text = f" · {_seats(seats)} available" if seats else ""
    return (
        "🎟️ <b>Booking opened for this movie's showtimes!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"Showtimes: {joined}{more}{seat_text}\n\n"
        "Book before it fills up!"
    )


def alert_movie_seats_available(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    seats: int | None = None,
) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    seat_text = f" · {_seats(seats)} now available" if seats else ""
    return (
        "🪑 <b>Seats are back for this movie's showtimes!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"Showtimes: {joined}{more}{seat_text}\n\n"
        "Go grab them 🏃"
    )


def alert_new_date(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    hall: str | None = None,
) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🎬 <b>A new date just opened!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}{hall_text}\n"
        f"Times: {joined}{more}\n\n"
        "Open the booking page and see what's available."
    )


def alert_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    return (
        "🎬 <b>New showtimes just appeared!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"Times: {joined}{more}\n\n"
        "Open the booking page and see what's available."
    )


def duration_label(minutes: int | None) -> str:
    if not minutes:
        return ""
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{_hours_label(hours)} {mins} min"
    if hours:
        return _hours_label(hours)
    return f"{mins} min"


def _hours_label(hours: int) -> str:
    if hours == 1:
        return "1 hr"
    return f"{hours} hr"


def movie_facts(
    duration_minutes: int | None = None,
    rating: str | None = None,
    language: str | None = None,
) -> str:
    parts: list[str] = []
    duration = duration_label(duration_minutes)
    if duration:
        parts.append(f"⏱️ {duration}")
    if rating:
        parts.append(f"🔞 {esc(rating)}")
    if language:
        parts.append(f"🗣️ {esc(language)}")
    return " · ".join(parts)


def alert_footer() -> str:
    return "Cinema Radar — alerts only, booking happens on the cinema site."


# ------------------------------------------------------------------- settings
def settings_text(
    notify_cancellations: bool,
    quiet_start: int,
    quiet_end: int,
    discovery_enabled: bool,
    branch_count: int,
    event_types: list[str],
    hall_type: str | None,
    quiet_watches: bool = True,
    language: str | None = None,
) -> str:
    types = ", ".join(event_type_label(t) for t in event_types) or "All types"
    branches = "All branches" if branch_count == 0 else _count(branch_count, "branch", "branches")
    hall = hall_type or "All halls"
    watch_quiet = "includes watches ✅" if quiet_watches else "watches always alert 🔔"
    return (
        "<b>⚙️ Settings</b>\n\n"
        "<b>Notifications</b>\n"
        f"• Seats back: {'on ✅' if notify_cancellations else 'off ⛔'}\n"
        f"• Quiet hours: {format_time(f'{quiet_start}:00')} → {format_time(f'{quiet_end}:00')} ({watch_quiet})\n"
        f"• New movies and bookings: {'on ✅' if discovery_enabled else 'off ⛔'}\n\n"
        "<b>New-alert filters</b>\n"
        f"• Branches: {esc(branches)}\n"
        f"• Types: {esc(types)}\n"
        f"• Hall: {esc(hall)}\n"
        f"• Language: {'العربية' if (language or 'en') == 'ar' else 'English'}"
        f"\n\n{version_line()}"
    )


def quiet_hours_text(start: int, end: int, quiet_watches: bool = True) -> str:
    watches = (
        "and watch alerts respect these hours too ✅"
        if quiet_watches
        else "but watch alerts still arrive during these hours 🔔"
    )
    return (
        "<b>🕰️ Quiet hours</b>\n\n"
        f"From <b>{format_time(f'{start}:00')}</b> to <b>{format_time(f'{end}:00')}</b>.\n"
        "No alerts during these hours, unless the show is today or tomorrow.\n"
        f"{watches}\n\n"
        "Pick a preset, or tap <b>Custom time</b> and send something like <code>23-8</code>."
    )


def quiet_custom_prompt() -> str:
    return (
        "<b>🕰️ Custom time</b>\n\n"
        "Send the start and end hours only, for example: <code>23-8</code> "
        "(11 PM to 8 AM).\n"
        "24-hour clock (0 = midnight)."
    )


def quiet_custom_invalid() -> str:
    return "I didn't catch that time. Send something like <code>23-8</code> (11 PM to 8 AM)."


def choose_branches_text() -> str:
    return "Pick the branches you want alerts from (you can pick more than one):"


def choose_event_types_text() -> str:
    return "Pick the alert types:"


def choose_hall_text() -> str:
    return "Pick the hall type:"


def event_type_label(kind: str) -> str:
    return {
        "NEW_MOVIE": "New movie",
        "NEW_DATE_OPENED": "New date opened",
        "NEW_SHOWTIMES": "New showtimes",
        "UPCOMING_MOVIE": "Tell me when it's out",
    }.get(kind, kind)


# -------------------------------------------------------------------- support
def support_text(limit: int = 10, min_amount: int = 50) -> str:
    return (
        "Cinema Radar is free for everyone, and every user gets <b>2 watches</b> for free 💛\n\n"
        "If you want more, you can support the project <b>once</b> with a minimum of "
        f"<b>{min_amount} EGP</b> — then your limit becomes <b>{limit} watches</b> "
        "for good, not a monthly subscription.\n\n"
        "Pay with Vodafone Cash or InstaPay, then send a screenshot. "
        "The admin reviews the proof and approves it.\n\n"
        "Pick how you'd like to support:"
    )


def support_manual_text(method: str, phone: str, min_amount: int = 50) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    return (
        f"<b>Support via {name}</b>\n\n"
        f"Send to this number:\n<code>{esc(phone)}</code>\n\n"
        f"Minimum <b>{min_amount} EGP</b> — one time, not a subscription.\n"
        "After paying, tap <b>I paid ✅</b> and send the transfer screenshot or transaction ID. "
        "The admin reviews it; once approved your limit becomes 10 watches.\n\n"
        "⚠️ Transfers are not activated automatically."
    )


def support_ask_amount(min_amount: int = 50) -> str:
    return (
        "How much did you send? 💰\n"
        f"The minimum is {min_amount} EGP.\n"
        "Pick an amount or type it in digits (example: 75)."
    )


def support_amount_invalid() -> str:
    return "Type a valid amount in digits, for example: 50"


def support_ask_proof(method: str) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    return (
        f"Send a screenshot of your {name} transfer, or type the transaction ID 📸\n"
        "If you'd rather stop, tap Cancel."
    )


def support_proof_received() -> str:
    return (
        "Proof sent to the admin ✅\n"
        "Waiting for review — you'll get a message as soon as it's checked."
    )


def support_approved(amount: float | None = None, limit: int = 10) -> str:
    amount_text = f" ({amount:g} EGP)" if amount else ""
    return f"Your support is confirmed{amount_text} ✅\nThank you so much 💛 Your limit is now <b>{limit}</b>."


def support_rejected() -> str:
    return (
        "Sorry, the transfer proof isn't clear or the transfer isn't complete ❌\n"
        "You can send it again from <b>Support the project</b>."
    )


def support_already_handled() -> str:
    return "This request was already reviewed ✅"


def support_admin_new(
    donation_id: int,
    user_id: int,
    method: str,
    amount: float | None,
    note: str,
    min_amount: int = 50,
    below_minimum: bool = False,
) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    amount_text = f"{amount:g} EGP" if amount else "Not specified"
    warning = f"\n⚠️ <b>Below the minimum ({min_amount} EGP)</b>" if below_minimum else ""
    return (
        f"<b>New support proof #{donation_id}</b>{warning}\n"
        f"User: <code>{user_id}</code>\n"
        f"Method: {name}\n"
        f"Amount: {esc(amount_text)}\n"
        f"Note: {esc(note or '—')}\n\n"
        "Review the proof, then decide:"
    )


def support_admin_decided(donation_id: int, approved: bool) -> str:
    state = "Approved ✅" if approved else "Rejected ❌"
    return f"Request #{donation_id}: {state}"


def support_not_configured() -> str:
    return "Manual support isn't configured right now. Contact the admin."


# ------------------------------------------------------------------- feedback
def feedback_categories_text() -> str:
    return (
        "✍️ <b>Send us feedback</b>\n\n"
        "Pick the type first, then write the details in one message.\n"
        "Every message reaches the admin and helps us improve the bot."
    )


def feedback_category_label(category: str) -> str:
    return {
        "idea": "Idea",
        "bug": "Bug",
        "movie": "Missing movie",
        "other": "Something else",
    }.get(category, "Something else")


def feedback_text(category: str | None = None) -> str:
    label = feedback_category_label(category) if category else "Feedback"
    return (
        f"✍️ <b>{esc(label)}</b>\n\n"
        "Write your feedback or idea in one message.\n"
        "Every message reaches the admin and helps us improve the bot."
    )


def feedback_thanks() -> str:
    return "Thanks! We got your feedback ✅"


def feedback_too_soon() -> str:
    return "We got feedback from you recently. Try again in an hour 🙏"


def feedback_admin(user_id: int, username: str | None, text: str) -> str:
    who = f"@{esc(username)}" if username else f"<code>{user_id}</code>"
    return f"<b>New feedback</b> from {who}:\n\n{esc(text)}"


# ------------------------------------------------------------------ discovery
def discovery_new_movie(movie: str, branch: str, date: str | None, hall: str | None) -> str:
    date_text = f" — from {relative_date(date)}" if date else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🎬 <b>A new movie just opened for booking!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)}{date_text}{hall_text}"
    )


def discovery_new_date(movie: str, branch: str, date: str) -> str:
    return (
        "📅 <b>A new date just opened!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — from {relative_date(date)}"
    )


def discovery_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    return (
        "🎟️ <b>New showtimes just appeared!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"Times: {joined}{more}"
    )


def discovery_upcoming_released(
    movie: str, branch: str, date: str | None, hall: str | None = None
) -> str:
    date_text = f" — from {relative_date(date)}" if date else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🍿 <b>The movie you were waiting for is out!</b>\n\n"
        f"<b>{esc(movie)}</b> just opened for booking at {esc(branch)}{date_text}{hall_text}\n\n"
        "Book before it fills up."
    )


def discovery_digest(branch: str, count: int, lines: list[str]) -> str:
    body = "\n".join(f"• {line}" for line in lines[:6])
    more = f"\nand {count - 6} more" if count > 6 else ""
    return (
        f"🎬 <b>{count} new things at {esc(branch)}</b>\n\n"
        f"{body}{more}\n\n"
        "Open booking or watch the movie with one tap."
    )


def discovery_channel(event_text: str) -> str:
    return f"{event_text}\n\n#cinemaradar"


# ---------------------------------------------------------------------- admin
def admin_text(data: dict[str, object]) -> str:
    return (
        "<b>Admin panel 🛠️</b>\n\n"
        f"Active users: <b>{data.get('active_users', 0)}</b>\n"
        f"Active watches: <b>{data.get('active_watches', 0)}</b>\n"
        f"Supporters: <b>{data.get('supporters', 0)}</b>\n"
        f"Requests/min: <b>{data.get('requests_per_minute', 0):.1f}</b>\n"
        f"Cache hit ratio: <b>{data.get('cache_hit_ratio', 0):.0%}</b>\n"
        f"Active targets: <b>{data.get('active_targets', 0)}</b>\n"
        f"Slowdown factor: <b>{data.get('slowdown_factor', 1):.2f}</b>\n"
        f"Circuit breaker: <b>{esc(data.get('circuit_state', 'closed'))}</b>\n"
        f"Last request: <b>{esc(data.get('last_poll_status', '—'))}</b>\n"
        f"Last discovery: <b>{esc(data.get('discovery_last_run', '—'))}</b>\n"
        f"Events today: <b>{data.get('events_today', 0)}</b>\n"
        f"Broadcasts: <b>{data.get('broadcasts_sent', 0)}</b>\n"
        f"Queue length: <b>{data.get('queue_length', 0)}</b>\n"
        f"Version: <b>v{esc(__version__)}</b>"
    )


def admin_only() -> str:
    return "This command is for the admin only."


def grant_done(telegram_id: int, limit: int) -> str:
    return f"Supporter access granted to <code>{telegram_id}</code> — limit {limit}."


def revoke_done(telegram_id: int, limit: int) -> str:
    return f"Supporter access revoked for <code>{telegram_id}</code> — limit {limit}."


# ------------------------------------------------------------ admin / system
def admin_started() -> str:
    return f"✅ Cinema Radar is running (v{esc(__version__)})."


def admin_limits_applied(users: int, watches: int) -> str:
    if not users:
        return "✅ Watch limits applied (2 free / 10 supporters)."
    return (
        "✅ Watch limits applied (2 free / 10 supporters).\n"
        f"{users} users affected, {watches} extra watches removed."
    )


def admin_unexpected_error(name: str) -> str:
    return f"⚠️ Unexpected error: {esc(name)}"


REASON_LABELS_EN = {
    "http_403": "(VOX) rejected the request (403) — protection or block",
    "http_429": "(VOX) rate-limited the request (429)",
    "http_5xx": "(VOX) server returned an error (5xx)",
    "timeout": "Timed out connecting to (VOX)",
    "network": "Network / TLS / DNS problem",
    "parse": "(VOX) page changed and the bot can't read it",
    "empty": "(VOX) returned an empty page",
    "circuit": "Circuit breaker open after repeated failures",
    "unknown": "Unknown error",
}


def reason_label(reason: str) -> str:
    return REASON_LABELS_EN.get(reason, REASON_LABELS_EN["unknown"])


def format_place(place: str) -> str:
    """Show a technical place key with the localized cinema name."""

    if place.startswith("vox"):
        return "(VOX)" + place[3:]
    return place


def admin_upstream_down(
    reason: str,
    place: str,
    last_success: str,
    retry_seconds: int,
    affected: int = 0,
    opened: bool = False,
) -> str:
    breaker = (
        f"\n⛔ Circuit breaker opened — pausing {retry_seconds}s, then trying one request."
        if opened
        else f"\n🔁 Retrying in {retry_seconds}s."
    )
    affected_line = f"\nAffected watches: <b>{affected}</b>" if affected else ""
    return (
        "⚠️ <b>(VOX) is down</b>\n\n"
        f"Reason: {esc(reason_label(reason))}\n"
        f"Where: {esc(place or '—')}\n"
        f"Last success: {esc(last_success or '—')}"
        f"{affected_line}"
        f"{breaker}\n\n"
        "I won't send any alerts based on stale data until it recovers."
    )


def admin_upstream_recovered(minutes: int) -> str:
    if minutes <= 0:
        return "✅ <b>(VOX) is back</b> — data is updating again."
    return f"✅ <b>(VOX) is back</b> after {minutes} min — data is updating again."


def stale_notice(minutes: int, degraded: bool) -> str:
    if minutes <= 0:
        return ""
    if degraded:
        return (
            f"\n\n⚠️ <i>(VOX) is unavailable right now. Last update {minutes} min ago — "
            "data may be stale.</i>"
        )
    if minutes >= 10:
        return f"\n\n<i>Last update: {minutes} min ago.</i>"
    return ""


def admin_status(data: dict[str, object]) -> str:
    return (
        "<b>(VOX) connection status</b>\n\n"
        f"State: <b>{esc(data.get('state', '—'))}</b>\n"
        f"Last success: {esc(data.get('last_success', '—'))}\n"
        f"Last error: {esc(data.get('last_error', '—'))}\n"
        f"Circuit breaker: <b>{esc(data.get('breaker', 'closed'))}</b>\n"
        f"Active targets: <b>{data.get('targets', 0)}</b>\n"
        f"Affected watches: <b>{data.get('affected', 0)}</b>"
    )


def admin_discovery_branches_failed(error: object) -> str:
    return f"⚠️ Discovery couldn't load branches: {esc(error)}"


def admin_discovery_branch_failed(branch: object, error: object) -> str:
    return f"⚠️ Discovery failed at {esc(branch)}: {esc(error)}"


# ------------------------------------------------------------------ discovery
def discovery_line_upcoming(name: object) -> str:
    return f"Just released: {esc(name)}"


def discovery_line_new_movie(name: object) -> str:
    return f"New movie: {esc(name)}"


def discovery_line_new_date(name: object, date_text: str) -> str:
    return f"New date open: {esc(name)} — {format_date(date_text)}"


def discovery_line_new_showtimes(name: object, times: tuple[str, ...]) -> str:
    formatted = ", ".join(format_time(value) for value in times)
    return f"New showtimes: {esc(name)} — {formatted}"


# ---------------------------------------------------------------------- errors
def error_expired() -> str:
    return "This screen is out of date or the show changed. Tap /start and begin again."


def error_generic() -> str:
    return "Something went wrong. Please try again in a moment 🙏"


def rate_limited() -> str:
    return "Give it a moment between steps 🙏"


def cancelled() -> str:
    return "Cancelled. To go back to the menu, tap /start."


def delete_me_confirm() -> str:
    return (
        "<b>Are you sure?</b>\n\n"
        "I'll delete all your data: watches, alerts, feedback and support proofs. "
        "This can't be undone."
    )


def delete_me_done() -> str:
    return "All your data is deleted ✅\nYou can come back anytime with /start."


def quiet_hours_set(start: int, end: int) -> str:
    return f"Quiet hours set from {format_time(f'{start}:00')} to {format_time(f'{end}:00')} ✅"


def setting_saved() -> str:
    return "Saved ✅"


def admin_usage(command: str) -> str:
    return f"Usage: /{command} <telegram_id>"


def imax_override_usage() -> str:
    return (
        "Usage: /imax <movie_id> <status>\n"
        "Statuses: FULL_70MM, PARTIAL_70MM, CERTIFIED_DIGITAL, PARTIAL_DIGITAL, UNKNOWN"
    )


def imax_override_done(movie_id: str, status: str, updated: int) -> str:
    return (
        f"IMAX status for <code>{esc(movie_id)}</code> set to <b>{esc(status)}</b> "
        f"— {_count(updated, 'watch', 'watches')} updated."
    )


def user_not_found() -> str:
    return "User not found."
