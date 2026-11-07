"""American English copy for every user-facing surface.

This catalog mirrors :mod:`i18n.ar` name for name and signature for signature;
``tests/test_i18n.py`` fails the build if the two drift apart.  Keep sentences
short and plain: the audience is a general cinema-goer, not a developer.

Dynamic values are HTML-escaped because messages are sent with parse_mode=HTML.
"""

from __future__ import annotations

from datetime import date as date_cls

from config import settings as _app_settings
from i18n.base import esc, get_provider
from imax import CERTIFIED_DIGITAL, FULL_70MM, PARTIAL_70MM, PARTIAL_DIGITAL, UNKNOWN
from models import AVAILABLE, NOT_AVAILABLE, SOLD_OUT
from models import format_key as _format_key
from ui.theme import DIVIDER, progress
from version import __version__

CODE = "en"
NAME = "English"
RTL = False


def cinema_name(provider: str | None = None) -> str:
    code = (provider or get_provider() or _app_settings.provider).lower()
    if code == "renaissance":
        return "Renaissance"
    if code == "premiere":
        return "Premiere"
    return "VOX"


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
    "DBOX": "DBOX",
    "BALCONE": "Balcone",
    "SPECIAL": "Special",
    "THEATRE": "Theatre",
    "LUXE": "LUXE",
    "CINECOMFORT": "CineComfort",
    "PLUS": "Plus",
    "MX4D": "MX4D",
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


def _needed_seats(value: int) -> str:
    value = max(1, int(value))
    return _seats(value)


def choose_seats(context: str = "") -> str:
    path = context or "Seat count"
    return (
        f"{step_header(5, 6, path)}\n\n"
        "<b>How many seats do you need?</b> 🪑\n\n"
        "I'll alert you once that many seats are available or more.\n"
        "Pick one below, or type a custom number."
    )


def seats_custom_prompt() -> str:
    return (
        f"{step_header(5, 6, 'Custom count')}\n\n"
        "<b>Type the seat count</b> 🪑\n\n"
        "Send a number from <b>1</b> to <b>10</b>."
    )


def seats_custom_invalid() -> str:
    return "Send a whole number from 1 to 10, for example: 3"


def required_seats_line(seats: int) -> str:
    return f"🪑 Needs {_needed_seats(seats)}"


def seats_updated(seats: int) -> str:
    return f"Done ✅ I'll alert you when {_needed_seats(seats)} or more are free."


def seats_button(seats: int) -> str:
    return f"🪑 Seats: {_needed_seats(seats)}"


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
BTN_ALL_MOVIES = "🎞️ All movies"
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
BTN_MOVIE_PAGE = "🎬 Movie page"
BTN_CINEMA_PAGE = "🏢 Cinema page"
BTN_WATCH_MOVIE = "🔔 Watch a movie from these updates"
BTN_STOP_ALERTS = "🔕 Stop all movie alerts"
BTN_TURN_ON_ALERTS = "🔔 Turn alerts back on"
BTN_REMOVE_WATCH = "❌ Remove watch"
BTN_CONFIRM_REMOVE_WATCH = "Yes, remove it"
BTN_SNOOZE = "⏰ Remind me in an hour"
BTN_UNSNOOZE = "🔔 Turn alerts back on"
BTN_MODE_ALL = "🔔 Everything"
BTN_MODE_SEATS = "🪑 Seats came back"
BTN_MODE_OPENING = "🎟️ Booking opens only"
BTN_WATCH_SETTINGS = "⚙️ Watch settings"
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
BTN_BACK_TO_SHOWTIMES = "⬅️ Back to showtimes"
BTN_VODAFONE_CASH = "Vodafone Cash"
BTN_INSTAPAY = "InstaPay"
BTN_CANCELLATIONS = "🪑 Seats back"
BTN_QUIET_HOURS = "🕰️ Quiet hours"
BTN_QUIET_CUSTOM = "🕰️ Custom time"
BTN_DISCOVERY_ALERTS = "🎬 Movie and showtime alerts"
BTN_BRANCHES_FILTER = "🎯 Alert branches"
BTN_TYPES_FILTER = "📌 Alert types"
BTN_HALL_FILTER = "🎭 Hall type"
BTN_QUIET_WATCHES = "Watch alerts respect quiet hours"
BTN_DELETE_MY_DATA = "🗑️ Delete my data"
BTN_COPY_PHONE = "📋 Copy number"
BTN_MANAGE_WATCH = "⚙️ Manage watch"
BTN_SEATS_CUSTOM = "✍️ Custom number"
BTN_LANGUAGE = "🌐 Language"
BTN_ARABIC = "🇪🇬 العربية"
BTN_ENGLISH = "🇺🇸 English"
BTN_ALL_CINEMAS = "🌍 All cinemas"
BTN_CONSENT_ACCEPT = "✅ I agree, start"
BTN_CONSENT_DECLINE = "❌ I don't agree"
BTN_CONSENT_REVIEW = "🔐 Review consent again"


# ------------------------------------------------------------ keyboard labels
def all_dates_label() -> str:
    return "📅 Every available date"


def donation_amount_label(amount: int) -> str:
    return f"{amount} EGP"


def donation_custom_label() -> str:
    return "Another amount"


def donation_approve_label() -> str:
    return "✅ Approve"


def donation_reject_label() -> str:
    return "❌ Reject"


def feedback_category_button(kind: str) -> str:
    return {
        "idea": "💡 Idea",
        "bug": "🐞 Bug",
        "movie": "🎬 Missing movie",
        "other": "💬 Something else",
    }.get(kind, kind)


# Public commands are registered in the default scope.  Admin commands are
# registered only in the admin's private chat scope, so they never appear in
# the public menu.
PUBLIC_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Home"),
    ("add", "Add a watch"),
    ("search", "Find a movie"),
    ("watches", "My watches"),
    ("settings", "Settings"),
    ("help", "Help"),
    ("privacy", "Privacy and data"),
    ("delete_me", "Delete my data"),
    ("cancel", "Cancel the current step"),
)

ADMIN_COMMANDS: tuple[tuple[str, str], ...] = (
    ("admin", "Admin panel"),
    ("status", "Cinema connection status"),
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
        f"🎬 <b>Cinema Radar</b>\n{DIVIDER}",
        "<i>Your front-row friend 🍿</i>",
        f"Welcome{who} 👋",
    ]
    if active_watches:
        lines.append(
            f"You have <b>{active_watches}</b> active {_plural(active_watches, 'watch', 'watches')}."
        )
    else:
        lines.append("No watches yet — shall we start with one? 🍿")
    if next_watch:
        lines += ["⏭️ <b>Next show</b>", next_watch]
    if limit:
        lines.append(f"<i>🎟️ Your limit: {_count(limit, 'watch', 'watches')}.</i>")
    lines.append("Pick an option below 👇")
    return _blocks(*lines)


def version_line() -> str:
    return f"<i>🎬 Cinema Radar · v{esc(__version__)}</i>"


def language_screen() -> str:
    return (
        f"🌐 <b>Choose your language</b> · <b>اختار لغتك</b>\n{DIVIDER}\n\n"
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
    return f"<b>{esc(movie)}</b>\n{esc(branch)} · {when} · {esc(detail)}"


def step_header(step: int, total: int, path: str) -> str:
    return f"{progress(step, total)} · {esc(path)}\n{DIVIDER}"


def page_label(page: int, pages: int) -> str:
    if pages <= 1:
        return ""
    return f"Page {page + 1} / {pages}"


# ------------------------------------------------------------------ onboarding
def onboard_intro(name: str = "") -> str:
    who = f", {esc(name)}" if name else ""
    return _blocks(
        f"🎬 <b>Cinema Radar</b>\n{DIVIDER}",
        "<i>Your front-row friend 🍿</i>",
        f"Welcome{who} 👋",
        "I watch VOX, Renaissance and Premiere showtimes in Egypt,\n"
        "and message you the moment booking opens\n"
        "or a seat frees up — before the good ones go.",
        "No more refreshing the site yourself.",
    )


def onboard_alerts() -> str:
    return _blocks(
        f"🔔 <b>What you'll get</b>\n{DIVIDER}",
        "🎟️ <b>Booking opened</b>\nThe moment a showtime goes on sale.",
        "🪑 <b>Seats came back</b>\nWhen a sold-out show frees up.",
        "📅 <b>New date</b>\nWhen a movie opens another day.",
        "🍿 <b>A new movie or showtime</b>\nWhen a movie arrives or fresh slots open,\n"
        "if you turn on <b>Movie and showtime alerts</b>.",
        "⚙️ Set each type and switch alerts on in <b>Settings</b>.",
    )


def onboard_safety() -> str:
    return _blocks(
        f"🙏 <b>Before we start</b>\n{DIVIDER}",
        "✅ The bot is free and only sends the booking link.",
        "🙅 It never books or pays for you.",
        "🔒 It never asks for your name, phone or payment details.",
        "⚠️ It is unofficial and not affiliated with any cinema.",
        "📄 Full details: /privacy\n🗑️ Erase your data: /delete_me",
    )


def onboard_progress(step: int) -> str:
    return f"<i>{progress(step + 1, 3)}</i>"


def help_text() -> str:
    return (
        f"🎬 <b>How to use Cinema Radar</b>\n{DIVIDER}\n"
        "<i>Three steps, then we take it from there.</i>\n\n"
        "<b>1 · Add a watch</b>\n"
        "Tap <b>➕ Add a watch</b> and pick:\n"
        "• Branch\n"
        "• Date\n"
        "• Movie\n"
        "• Showtime\n\n"
        "Or watch every showtime that day, or every available date.\n"
        "You can also filter by format (IMAX, 4DX, VIP…).\n\n"
        "<b>Nothing to watch yet?</b>\n"
        "Turn on <b>🎬 Movie and showtime alerts</b> in Settings,\n"
        "and you'll hear about every new movie, date or showtime the moment it drops.\n\n"
        "<b>2 · Wait for the alert</b>\n"
        "When booking opens or a seat comes back,\n"
        "you get a message with the booking link.\n\n"
        "<b>3 · Stay in control</b>\n"
        "From <b>🎟️ My watches</b> you can:\n"
        "• Change the alert type\n"
        "• Snooze for an hour\n"
        "• Remove the watch\n\n"
        "<b>Can't find a movie?</b>\n"
        "Tap <b>🔎 Search by name</b> and type part of the title\n"
        "in Arabic or English.\n"
        "The bot tolerates typos too.\n\n"
        "<b>Quick commands</b>\n"
        "/start — Main menu\n"
        "/add — Add a watch\n"
        "/search — Search for a movie\n"
        "/watches — My watches\n"
        "/settings — Settings\n"
        "/help — Help\n"
        "/privacy — Privacy\n"
        "/delete_me — Delete my data\n"
        "/cancel — Cancel the current step\n\n"
        "⚠️ <i>The bot is unofficial and not affiliated with VOX, Renaissance or Premiere Cinemas.\n"
        "Data may be delayed or wrong,\n"
        "and booking happens on the cinema's own site.</i>\n\n"
        f"{version_line()}"
    )


def privacy_text() -> str:
    return (
        f"🔐 <b>Privacy in short</b>\n{DIVIDER}\n\n"
        "The bot knows you by your Telegram ID only,\n"
        "and never asks for your name or email.\n\n"
        "<b>What is stored</b>\n"
        "• Your language and settings.\n"
        "• Your watches: branch, date, movie, showtime.\n"
        "• If you supported the project:\n"
        "  the method, amount, and any note or proof you sent.\n"
        "• If you send feedback: the text and your username, if present.\n\n"
        "<b>What we never ask for</b>\n"
        "• Card or banking details.\n"
        "• Your phone number or email.\n\n"
        "If you type any of those yourself in a donation note or feedback,\n"
        "it is stored exactly as you wrote it.\n\n"
        "<b>Who sees it?</b>\n"
        "The admin only, to reply to feedback and review donation proof.\n"
        "Your data is never sold or shared with any third party.\n\n"
        "<b>Deleting your data</b>\n"
        "/delete_me removes everything stored in the bot's database.\n"
        "Messages and photos already sent in Telegram\n"
        "remain in the chats.\n\n"
        "<b>Images</b>\n"
        f"{tmdb_attribution()}\n\n"
        "<b>Contact</b>\n"
        "zyad.waleed.sec@gmail.com\n\n"
        f"{version_line()}"
    )


def tmdb_attribution() -> str:
    return (
        "Movie posters are provided by TMDB. "
        "This product uses the TMDB API but is not endorsed or certified by TMDB."
    )


def consent_text() -> str:
    return (
        f"🔐 <b>Consent to store your data</b>\n{DIVIDER}\n\n"
        "Before we start, we need your explicit consent.\n"
        "If you decline, nothing about you is stored.\n\n"
        "<b>What is stored</b>\n"
        "• Your Telegram ID — no name or email.\n"
        "• Your language and alert settings.\n"
        "• The watches you add:\n"
        "  cinema, branch, date, movie and showtime.\n"
        "• If you send feedback: the text and username, if present.\n"
        "• If you support the project: the transfer method and amount,\n"
        "  plus any note or proof image you send.\n\n"
        "<b>Why</b>\n"
        "To send booking and seat alerts,\n"
        "reply to feedback and verify support.\n\n"
        "<b>What we never ask for</b>\n"
        "Card or banking details, or your phone number or email.\n\n"
        "<b>Retention and control</b>\n"
        "Data is kept while your account is active.\n"
        "You can erase everything anytime with /delete_me,\n"
        "and read the full details with /privacy.\n\n"
        f"<b>Contact:</b> zyad.waleed.sec@gmail.com\n\n"
        f"{tmdb_attribution()}"
    )


def consent_declined() -> str:
    return (
        "Understood — nothing was stored ✅\n\n"
        "Without consent we cannot send you alerts.\n"
        "If you change your mind, use the button below."
    )


# ------------------------------------------------------------------ add watch
def choose_cinema() -> str:
    return _blocks(
        f"🎬 <b>Choose a cinema</b>\n{DIVIDER}",
        "Where do you want to watch?",
        "Pick one cinema,\nor <b>All cinemas</b> to watch the movie across every branch at once.",
    )


def BTN_MORNING(count: int) -> str:
    return f"🌅 Morning shows ({count})"


def BTN_EVENING(count: int) -> str:
    return f"🌙 Evening shows ({count})"


def window_cutoff_text(hour: int) -> str:
    """Render the morning/evening split hour in 12-hour form."""

    period = "PM" if hour % 24 >= 12 else "AM"
    value = hour % 12 or 12
    return f"{value} {period}"


def window_label(window: str, morning_end_hour: int = 17) -> str:
    cutoff = window_cutoff_text(morning_end_hour)
    return (
        f"Morning shows (before {cutoff})"
        if window == "morning"
        else f"Evening shows (from {cutoff})"
    )


def choose_window(movie: str, date: str, morning_end_hour: int = 17) -> str:
    cutoff = window_cutoff_text(morning_end_hour)
    return _blocks(
        f"🎬 <b>{esc(movie)}</b> · 📅 {relative_date(date)}\n{DIVIDER}",
        "Morning or evening?",
        f"🌅 <b>Morning</b> — before {cutoff}",
        f"🌙 <b>Evening</b> — from {cutoff}",
    )


def confirm_window(
    movie: str,
    date: str,
    window: str,
    branch_count: int,
    morning_end_hour: int = 17,
    required_seats: int = 1,
) -> str:
    return _blocks(
        f"🎬 <b>{esc(movie)}</b> · 📅 {relative_date(date)}\n{DIVIDER}",
        f"{window_label(window, morning_end_hour)}\n"
        f"{_count(branch_count, 'branch', 'branches')}\n"
        f"{required_seats_line(required_seats)}",
        "I'll watch every show in this period across all cinemas,\n"
        "and message you when a new show opens or a seat comes back.",
        "Confirm the watch?",
    )


def watch_created_window(
    movie: str, date: str, window: str, branch_count: int, morning_end_hour: int = 17
) -> str:
    return _blocks(
        f"✅ <b>Watch active</b>\n{DIVIDER}",
        f"{esc(movie)}\n"
        f"{relative_date(date)} · 🕐 {window_label(window, morning_end_hour)}\n"
        f"All cinemas ({_count(branch_count, 'branch', 'branches')})",
        "I'll message you when a new show opens in this period.",
    )


def no_showtimes_window(movie: str, date: str) -> str:
    return (
        f"🍿 <b>No shows</b>\n\n"
        f"No shows for «<b>{esc(movie)}</b>» on {relative_date(date)} at any cinema.\n"
        "Try another day or period."
    )


def choose_branch() -> str:
    return _blocks(
        step_header(1, 5, "Branch"),
        "🏢 <b>Pick a branch</b>",
        "Where should we start?",
    )


def choose_date(branch: str) -> str:
    return _blocks(
        step_header(2, 5, branch),
        "📅 <b>Pick a date</b>",
        "Choose the day that works for you.",
    )


def choose_movie(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return _blocks(
        step_header(3, 5, path),
        "🎞️ <b>Pick a movie</b>",
        "Can't find it? Tap <b>🔎 Search by name</b>.",
    )


def search_choose_branch(query: str = "") -> str:
    head = step_header(2, 5, "Search")
    if query:
        return _blocks(
            head,
            f"🔎 <b>Searching for “{esc(query)}”</b>",
            "Pick the branch first:",
        )
    return _blocks(head, "🔎 <b>Movie search</b>", "Pick the branch first:")


def search_prompt(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return _blocks(
        step_header(3, 5, path),
        "🔎 <b>Type the movie name</b>",
        "In Arabic or English.",
        "Typos are fine — part of the name is enough.",
    )


def search_too_short() -> str:
    return "Type at least two letters so I can search 🔎"


def search_results(query: str, count: int, total: int) -> str:
    return _blocks(
        "🔎 <b>Search results</b>",
        f"“<b>{esc(query)}</b>”",
        f"Found <b>{count}</b> of {_count(total, 'movie')}.",
        "Pick the movie you want:",
    )


def search_no_results(query: str, suggestions: list[str] | None = None) -> str:
    lines = [
        "🍿 <b>No results</b>",
        f"No movie close to “<b>{esc(query)}</b>” on that date.",
    ]
    if suggestions:
        lines.append("Did you mean one of these? Tap it 👇")
    else:
        lines.append("Try part of the name,\nthe English title,\nor browse all movies.")
    return _blocks(*lines)


def choose_showtime(movie: str, date: str, extra: str = "") -> str:
    path = f"{relative_date(date)} › {movie}"
    lines = [step_header(4, 5, path)]
    if extra:
        lines.append(extra)
    lines += [
        "🎟️ <b>Pick the showtime you want to watch</b>",
        "🟢 Available — book now\n"
        "🔴 Sold out — fully booked\n"
        "⚪ Not on sale yet — wait for the alert",
        "Want a specific format (IMAX, 4DX, VIP…)?\nPick it from the buttons above.",
    ]
    return _blocks(*lines)


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
        icon = "🟢"
    elif status == SOLD_OUT:
        icon = "🔴"
    else:
        icon = "⚪"
    label = f"{icon} {format_time(time)} · {esc(hall)}"
    if status == AVAILABLE and seats is not None:
        label += f" · {_seats(seats)}"
    return label


def confirm_watch(
    branch: str,
    date: str,
    movie: str,
    time: str,
    hall: str,
    status: str = "",
    required_seats: int = 1,
) -> str:
    if status == SOLD_OUT:
        note = "This show is sold out right now. I'll watch it and message you as soon as seats come back."
    elif status == NOT_AVAILABLE:
        note = "I'll message you as soon as booking opens."
    elif status == AVAILABLE:
        note = "This show is available now — you can book right away, and I'll watch it if seats run out."
    else:
        note = "I'll watch this show and message you when anything changes."
    return _blocks(
        step_header(6, 6, "Confirm"),
        "🎬 <b>Review your watch</b>",
        f"{esc(movie)}\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} ({format_date(date)})\n"
        f"{format_time(time)} · {esc(hall)}\n"
        f"{required_seats_line(required_seats)}",
        note,
        "Looks good? Confirm below ✅",
    )


def no_data() -> str:
    return _blocks(
        f"⏳ <b>Still fetching data</b>\n{DIVIDER}",
        "The cinema isn't responding right now.\nTry again in a minute 🙏",
        "<i>I don't send requests to the cinema site while you browse,\n"
        "so the bot stays reliable.</i>",
    )


def loading_branches() -> str:
    return _blocks("⏳ <b>Loading branches…</b>", "One moment 🙏")


def loading_showtimes() -> str:
    return _blocks(
        "⏳ <b>Loading shows from all cinemas…</b>",
        "This can take a few seconds 🙏",
    )


def window_movie_prompt() -> str:
    return _blocks(
        "🔎 <b>Type the movie name</b>",
        "Type the movie you want to watch across all cinemas (Arabic or English).",
    )


def choose_date_all_cinemas() -> str:
    return _blocks(
        "📅 <b>Pick a day</b>",
        "Pick the day you want to watch across all cinemas.",
    )


def no_dates() -> str:
    return _blocks(
        f"📅 <b>No dates available</b>\n{DIVIDER}",
        "This branch hasn't opened any dates yet.",
        "Try another branch, or wait a bit.",
    )


def no_movies() -> str:
    return _blocks(
        f"🎬 <b>Booking isn't open yet</b>\n{DIVIDER}",
        "No movies are available on that date right now.",
        "Try another date,\nand when showtimes appear they'll be right here.",
    )


def no_showtimes() -> str:
    return _blocks(
        f"🎟️ <b>No showtimes</b>\n{DIVIDER}",
        "Booking isn't open for this movie on that date yet.",
        "Try another movie or date.",
    )


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
    lines = [f"🎬 <b>{esc(name)}</b>\n{DIVIDER}"]
    if facts:
        lines.append(facts)
    if extra:
        lines.append(extra)
    if synopsis:
        lines.append(f"<i>{esc(synopsis)}</i>")
    else:
        lines.append("<i>No synopsis is available for this movie yet.</i>")
    return _blocks(*lines)


def confirm_movie_watch(
    branch: str,
    date: str,
    movie: str,
    count: int,
    statuses: list[str] | None = None,
    hall: str | None = None,
    required_seats: int = 1,
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
    return _blocks(
        step_header(6, 6, "Confirm"),
        "🎬 <b>Review your full-day watch</b>",
        f"{esc(movie)}\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} ({format_date(date)})\n"
        f"{ticket}\n"
        f"{required_seats_line(required_seats)}",
        note,
        "Looks good? Confirm below ✅",
    )


def watch_created_movie(
    branch: str, date: str, movie: str, count: int, hall: str | None = None
) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"✅ <b>Watch active</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)}{format_text}\n"
        f"🎟️ Every showtime ({_count(count, 'showtime')})",
        "As soon as any booking opens or seats come back,\nyou'll get a message.",
        "Set the alert type in <b>⚙️ Alert settings</b>.",
    )


def watch_created(branch: str, date: str, movie: str, time: str, hall: str) -> str:
    return _blocks(
        f"✅ <b>Watch active</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}",
        "You'll get a message when anything changes.",
        "Set the alert type in <b>⚙️ Alert settings</b>.",
    )


def confirm_all_dates(
    branch: str,
    movie: str,
    count: int,
    hall: str | None = None,
    required_seats: int = 1,
) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        step_header(6, 6, "Confirm"),
        "🎬 <b>Review your every-date watch</b>",
        f"{esc(branch)}\n"
        f"{esc(movie)}\n"
        f"Every date available now ({_count(count, 'day')}){format_text}\n"
        f"{required_seats_line(required_seats)}",
        "I'll watch every day this movie plays at this branch,\n"
        "plus any new date that opens.\n"
        "When booking opens or seats come back, you'll get a message.",
        "Looks good? Confirm below ✅",
    )


def watch_created_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"✅ <b>Watch active</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}{format_text}\n"
        f"Every available date ({_count(count, 'day')})",
        "If a new date opens or seats come back,\nyou'll get a message.",
        "Set the alert type in <b>⚙️ Alert settings</b>.",
    )


def all_dates_unavailable() -> str:
    return _blocks(
        f"📅 <b>No dates available</b>\n{DIVIDER}",
        "This branch hasn't opened any dates yet.",
        "Try a specific date,\nor wait for booking to open.",
    )


def watch_limit_reached(
    limit: int,
    supporter_limit: int = 10,
    min_amount: int = 50,
    is_supporter: bool = False,
) -> str:
    if is_supporter:
        return _blocks(
            f"⚠️ <b>You've reached the maximum</b>\n{DIVIDER}",
            f"You have <b>{_count(limit, 'watch', 'watches')}</b>.",
            "Remove an old watch from <b>My watches</b>\nto add a new one.",
        )
    return _blocks(
        f"⚠️ <b>You've reached the free limit</b>\n{DIVIDER}",
        f"You have <b>{_count(limit, 'watch', 'watches')}</b>, which is the free limit.",
        f"To reach <b>{_count(supporter_limit, 'watch', 'watches')}</b>,\n"
        "you can support the project <b>once</b>\n"
        f"with a minimum of <b>{min_amount} EGP</b> from <b>Support the project</b> 💛",
        "Or remove an old watch from <b>My watches</b>.",
    )


def watches_trimmed(removed: int, limit: int) -> str:
    return _blocks(
        f"✂️ <b>Your watches were trimmed</b>\n{DIVIDER}",
        f"I removed {removed} watch{'es' if removed != 1 else ''} "
        f"because the new limit is <b>{_count(limit, 'watch', 'watches')}</b>.",
        "The watches with the nearest dates stayed with you;\n"
        "you can add more from <b>Support the project</b> or remove and add again.",
    )


def duplicate_watch() -> str:
    return "You already have this watch 👌 I'll message you when something changes."


# ------------------------------------------------------------------- my watches
def no_watches() -> str:
    return _blocks(
        f"🍿 <b>No watches yet</b>\n{DIVIDER}",
        "Shall we start with one?",
        "Pick a movie and a showtime,\nand we'll keep an eye on them.",
        "When booking opens or a seat comes back,\nyou'll get a message right away.",
        "Tap <b>➕ Add a watch</b> below.",
    )


def watches_retention_note(days: int) -> str:
    return (
        f"<i>🧹 Watches are removed automatically "
        f"{_count(days, 'day')} after their show starts.</i>"
    )


def watches_group(date: str) -> str:
    if date == "*":
        return "📅 <b>Every available date</b>"
    return f"📅 <b>{relative_date(date)}</b>"


def confirm_delete_all(count: int) -> str:
    return _blocks(
        f"🗑️ <b>Are you sure?</b>\n{DIVIDER}",
        f"I'll delete <b>{_count(count, 'active watch', 'active watches')}</b> — "
        "and they can't be restored.",
        "If you want them back, you'd start from scratch.",
    )


def confirm_remove_watch(movie: str, when: str) -> str:
    return _blocks(
        f"❌ <b>Remove this watch?</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(when)}",
        "You won't get alerts about it anymore.",
    )


def watches_page_title(count: int) -> str:
    return f"🎟️ <b>My watches</b> · {_count(count, 'active watch', 'active watches')}"


def watch_mode_label(mode: str | None) -> str:
    return {
        "seats": "Seats came back",
        "opening": "Booking opens only",
    }.get(mode or "all", "Everything")


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
    provider: str = "vox",
    required_seats: int = 1,
) -> str:
    state = STATUS_LABELS_EN.get(str(status or "").upper(), "Unknown")
    if seats not in (None, ""):
        state = f"{state} · {_seats(int(seats))}"
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 Every available date · all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text} · {esc(state)}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text} · {esc(state)}"
    lines = [
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {cinema_name(provider)} · {esc(branch)} · {relative_date(date)}",
        ticket,
        f"🔔 {watch_mode_label(mode)}",
    ]
    if int(required_seats) > 1:
        lines[-1] += f" · 🪑 {_needed_seats(required_seats)}"
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
    provider: str = "vox",
    required_seats: int = 1,
) -> str:
    snooze = f"Snoozed until {esc(snoozed_until_text)}" if snoozed_until_text else "Not snoozed"
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 Every available date · all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text}"
    return _blocks(
        f"⚙️ <b>Watch settings</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{cinema_name(provider)} · {esc(branch)} · {relative_date(date)}\n"
        f"{ticket}",
        f"Alerts: <b>{watch_mode_label(mode)}</b>\n"
        f"Alert me at: <b>{_needed_seats(required_seats)} or more</b>\n"
        f"{snooze}",
        "Pick the alert type that suits you:",
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
    state = STATUS_LABELS_EN.get(str(status or "").upper(), "Unknown")
    if seats not in (None, ""):
        state = f"{state} · {_seats(int(seats))}"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"🎟️ Every available date — all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text}"
    lines = [
        f"⏰ <b>Here's the watch you asked about</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)} · {relative_date(date)}\n{ticket}",
    ]
    if scope != "movie_all_dates":
        lines.append(f"📊 Status now: {esc(state)}")
    lines.append("Open the booking page and see what's available.")
    return _blocks(*lines)


def watch_snoozed(until_text: str) -> str:
    return f"Done ⏰ I'll hold alerts until <b>{esc(until_text)}</b>, then remind you."


def watch_unsnoozed() -> str:
    return "✅ Alerts are back on."


def watch_removed_from_alert() -> str:
    return "✅ Watch removed. You won't get alerts about it anymore."


def watch_mode_set(mode: str | None) -> str:
    return f"✅ Alerts are now: <b>{watch_mode_label(mode)}</b>"


def watch_removed() -> str:
    return "✅ Watch removed."


def all_watches_removed() -> str:
    return "✅ All watches deleted."


def watch_expired_summary(items: list[str], more: int = 0) -> str:
    total = len(items) + more
    lines = [f"🧹 <b>Removed {_count(total, 'finished watch', 'finished watches')}</b>\n{DIVIDER}"]
    lines.extend(f"• {item}" for item in items)
    if more:
        lines.append(f"• and {_count(more, 'more watch', 'more watches')}")
    lines += [
        "Their shows have already started, so I can't send alerts about them anymore.",
        "To watch a new show, tap <b>➕ Add a watch</b>.",
    ]
    return _blocks(*lines)


def watch_expired_row(movie: str, branch: str, date: str, showtime: str) -> str:
    when = relative_date(date)
    if showtime and showtime != "*":
        when = f"{when} — {format_time(showtime)}"
    return f"<b>{esc(movie)}</b> — {esc(branch)} — {when}"


# --------------------------------------------------------------------- alerts
def alert_booking_opened(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f"\n🪑 {_seats(seats)} available" if seats else ""
    return _blocks(
        f"🎟️ <b>Booking opened</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}{seat_text}",
        "Book before it fills up.",
    )


def alert_seats_available(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f"<b>{_seats(seats)}</b> available now." if seats else "Seats are available now."
    return _blocks(
        f"🪑 <b>Seats are back</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}",
        f"{seat_text}",
        "Go grab them.",
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
    seat_text = f"\n🪑 {_seats(seats)} available" if seats else ""
    return _blocks(
        f"🎟️ <b>Booking opened for this movie</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}{seat_text}",
        "Book before it fills up.",
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
    seat_text = f"\n🪑 {_seats(seats)} now available" if seats else ""
    return _blocks(
        f"🪑 <b>Seats are back for this movie</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}{seat_text}",
        "Go grab them.",
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
    hall_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"📅 <b>A new date just opened</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}{hall_text}\n{joined}{more}",
        "Open the booking page and see what's available.",
    )


def alert_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    return _blocks(
        f"🕐 <b>New showtimes appeared</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}",
        "Open the booking page and see what's available.",
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
    return "Cinema Radar · we only alert — booking happens on the cinema site."


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
    watch_quiet = "and watches are included ✅" if quiet_watches else "watches always alert 🔔"
    hint = (
        ""
        if discovery_enabled
        else "💡 <i>Turn on movie and showtime alerts to hear about every new movie, "
        "date or showtime the moment it drops.</i>"
    )
    return _blocks(
        f"⚙️ <b>Settings</b>\n{DIVIDER}",
        "<b>🔔 Notifications</b>\n"
        f"• Seats back: {'on ✅' if notify_cancellations else 'off ⛔'}\n"
        f"• Quiet hours: {format_time(f'{quiet_start}:00')} → {format_time(f'{quiet_end}:00')}\n"
        f"  <i>{watch_quiet}</i>\n"
        f"• New movies and showtimes: {'on ✅' if discovery_enabled else 'off ⛔'}",
        hint,
        "<b>🎯 New-alert filters</b>\n"
        f"• Branches: {esc(branches)}\n"
        f"• Types: {esc(types)}\n"
        f"• Hall: {esc(hall)}\n"
        f"• Language: {'العربية' if (language or 'en') == 'ar' else 'English'}",
        version_line(),
    )


def quiet_hours_text(start: int, end: int, quiet_watches: bool = True) -> str:
    watches = (
        "Watch alerts respect these hours too ✅"
        if quiet_watches
        else "Watch alerts still arrive during these hours 🔔"
    )
    return _blocks(
        f"🕰️ <b>Quiet hours</b>\n{DIVIDER}",
        f"From <b>{format_time(f'{start}:00')}</b> to <b>{format_time(f'{end}:00')}</b>.",
        "No alerts during these hours,\nunless the show is today or tomorrow.",
        watches,
        "Pick a preset, or tap <b>Custom time</b> and send something like <code>23-8</code>.",
    )


def quiet_custom_prompt() -> str:
    return _blocks(
        f"🕰️ <b>Custom time</b>\n{DIVIDER}",
        "Send the start and end hours only,\nfor example: <code>23-8</code> (11 PM to 8 AM).",
        "24-hour clock (0 = midnight).",
    )


def quiet_custom_invalid() -> str:
    return "I didn't catch that time 🤔 Send something like <code>23-8</code> (11 PM to 8 AM)."


def choose_branches_text() -> str:
    return _blocks(
        "🏢 <b>Pick your branches</b>",
        "Where should the alerts come from?\nYou can pick more than one.",
    )


def choose_event_types_text() -> str:
    return _blocks(
        "🎯 <b>Pick your alert types</b>",
        "What do you want to hear about first?",
    )


def choose_hall_text() -> str:
    return _blocks(
        "🎭 <b>Pick a hall type</b>",
        "I'll only show formats your\nselected cinemas actually offer.",
    )


def format_not_offered() -> str:
    return "That format isn't offered by your selected cinemas 🙏"


def event_type_label(kind: str) -> str:
    return {
        "NEW_MOVIE": "New movie",
        "NEW_DATE_OPENED": "New date opened",
        "NEW_SHOWTIMES": "New showtimes",
        "UPCOMING_MOVIE": "Tell me when it's out",
    }.get(kind, kind)


# -------------------------------------------------------------------- support
def support_text(limit: int = 10, min_amount: int = 50) -> str:
    return _blocks(
        f"💛 <b>Support the project</b>\n{DIVIDER}",
        "Cinema Radar is free for everyone,\nand every user gets <b>2 watches</b> for free.",
        "Want more? You can support the project <b>once</b>\n"
        f"with a minimum of <b>{min_amount} EGP</b>,\n"
        f"and your limit becomes <b>{limit} watches</b> for good.\n"
        "Not a monthly subscription.",
        "Pay with Vodafone Cash or InstaPay,\n"
        "then send a screenshot of the transfer.\n"
        "The admin reviews the proof and approves it.",
        "How would you like to support?",
    )


def support_manual_text(method: str, phone: str, min_amount: int = 50) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    return _blocks(
        f"💛 <b>Support via {name}</b>\n{DIVIDER}",
        f"Send to this number:\n<code>{esc(phone)}</code>",
        f"Minimum <b>{min_amount} EGP</b> — one time, not a subscription.",
        "After paying, tap <b>I paid ✅</b>,\n"
        "then send the transfer screenshot or transaction ID.\n"
        "The admin reviews it,\n"
        "and once approved your limit becomes <b>10 watches</b>.",
        "⚠️ <i>Transfers are not activated automatically.</i>",
    )


def support_ask_amount(min_amount: int = 50) -> str:
    return _blocks(
        f"💰 <b>How much did you send?</b>\n{DIVIDER}",
        f"The minimum is <b>{min_amount} EGP</b>.",
        "Pick an amount below,\nor type it in digits (example: 75).",
    )


def support_amount_invalid() -> str:
    return "Type a valid amount in digits, for example: 50 🙏"


def support_custom_amount_prompt() -> str:
    return _blocks(
        "✍️ <b>Type the amount</b>",
        "How much did you send? Just the number (example: 75) 💰",
    )


def support_below_minimum_warning() -> str:
    return "⚠️ That's below the minimum — it goes to the admin, who decides."


def support_ask_proof(method: str) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    return _blocks(
        f"📸 <b>{name} transfer proof</b>",
        "Send the transfer screenshot or the transaction ID.",
        "If you'd rather stop, tap <b>Cancel</b>.",
    )


def support_proof_received() -> str:
    return _blocks(
        "✅ <b>Proof received</b>",
        "It's with the admin for review.\nYou'll get a message as soon as it's checked.",
    )


def support_approved(amount: float | None = None, limit: int = 10) -> str:
    amount_text = f" ({amount:g} EGP)" if amount else ""
    return _blocks(
        f"✅ <b>Your support is confirmed{amount_text}</b>",
        f"Thank you so much 💛\nYour limit is now <b>{_count(limit, 'watch', 'watches')}</b>.",
    )


def support_rejected() -> str:
    return _blocks(
        f"❌ <b>The proof isn't clear</b>\n{DIVIDER}",
        "The transfer isn't complete,\nor the screenshot is hard to read.",
        "You can send it again from <b>Support the project</b>.",
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
    return _blocks(
        f"<b>New support proof #{donation_id}</b>{warning}\n{DIVIDER}",
        f"User: <code>{user_id}</code>\n"
        f"Method: {name}\n"
        f"Amount: {esc(amount_text)}\n"
        f"Note: {esc(note or '—')}",
        "Review the proof, then decide:",
    )


def support_admin_decided(donation_id: int, approved: bool) -> str:
    state = "Approved ✅" if approved else "Rejected ❌"
    return f"Request #{donation_id}: {state}"


def support_not_configured() -> str:
    return "Manual support isn't configured right now. Contact the admin."


# ------------------------------------------------------------------- feedback
def feedback_categories_text() -> str:
    return _blocks(
        f"✍️ <b>Send us feedback</b>\n{DIVIDER}",
        "Pick the type first,\nthen write the details in one message.",
        "Every message reaches the admin\nand helps us improve the bot.",
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
    return _blocks(
        f"✍️ <b>Send feedback</b>\n{DIVIDER}",
        f"Type: <b>{esc(label)}</b>",
        "Write your feedback or idea in one message.",
        "Every message reaches the admin\nand helps us improve the bot.",
    )


def feedback_thanks() -> str:
    return _blocks(
        "✅ <b>We got your feedback</b>",
        "Thanks for helping us improve the bot 💛",
    )


def feedback_too_soon() -> str:
    return "We got feedback from you recently 🙏 Try again in an hour."


def feedback_admin(
    user_id: int, username: str | None, text: str, first_name: str | None = None
) -> str:
    if username:
        who = f"@{esc(username)}"
    elif first_name:
        who = esc(first_name)
    else:
        who = f"<code>{user_id}</code>"
    reference = f"\n\n<i>ID: <code>{user_id}</code></i>" if username or first_name else ""
    return f"<b>✍️ New feedback</b>\n{DIVIDER}\n\nFrom {who}:\n\n{esc(text)}{reference}"


# ------------------------------------------------------------------ discovery
def _blocks(*blocks: str) -> str:
    """Join non-empty blocks with a blank line so every fact can breathe."""

    return "\n\n".join(block for block in blocks if block)


def _cinema_line(branch: str, provider: str | None = None) -> str:
    """Cinema brand and branch on one readable line."""

    return f"🏢 <b>{cinema_name(provider)}</b> · {esc(branch)}"


def _place(movie: str, branch: str, provider: str | None) -> str:
    return _blocks(
        f"🎬 <b>{esc(movie)}</b>",
        _cinema_line(branch, provider),
    )


def discovery_new_movie(
    movie: str,
    branch: str,
    date: str | None,
    hall: str | None,
    provider: str | None = None,
) -> str:
    return _blocks(
        "🍿 <b>A new movie just opened</b>",
        DIVIDER,
        _place(movie, branch, provider),
        f"📅 From {relative_date(date)}" if date else "",
        f"🎭 {esc(hall)}" if hall else "",
        "✨ <i>First showtimes are live — book early.</i>",
    )


def discovery_new_date(
    movie: str,
    branch: str,
    date: str,
    provider: str | None = None,
) -> str:
    return _blocks(
        "📅 <b>A new date just opened</b>",
        DIVIDER,
        _place(movie, branch, provider),
        f"📅 From {relative_date(date)}",
        "🗓️ <i>The new dates are bookable now — pick your slot.</i>",
    )


def discovery_new_showtimes(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    provider: str | None = None,
) -> str:
    joined = " · ".join(format_time(t) for t in times[:6])
    more = " and more" if len(times) > 6 else ""
    return _blocks(
        "🎟️ <b>New showtimes just dropped</b>",
        DIVIDER,
        _place(movie, branch, provider),
        f"📅 {relative_date(date)}",
        f"🕘 {joined}{more}",
        "🍿 <i>Pick your show and go — before the good seats go.</i>",
    )


def discovery_upcoming_released(
    movie: str,
    branch: str,
    date: str | None,
    hall: str | None = None,
    provider: str | None = None,
) -> str:
    return _blocks(
        "🍿 <b>Finally — the movie you were waiting for is here</b>",
        DIVIDER,
        _place(movie, branch, provider),
        f"📅 From {relative_date(date)}" if date else "",
        f"🎭 {esc(hall)}" if hall else "",
        "🎬 <i>Book before it fills up.</i>",
    )


def discovery_digest(
    branch: str,
    count: int,
    lines: list[str],
    provider: str | None = None,
    hidden: int = 0,
) -> str:
    body = "\n".join(f"• {line}" for line in lines)
    more = f"➕ {_count(hidden, 'more update', 'more updates')}" if hidden > 0 else ""
    return _blocks(
        f"🍿 <b>{_count(count, 'new update', 'new updates')} at "
        f"{cinema_name(provider)} · {esc(branch)}</b>",
        DIVIDER,
        body,
        more,
        "👀 <i>Take a look and pick your favourite.</i>",
    )


def discovery_watch_prompt() -> str:
    return _blocks(
        "🔔 <b>Which movie do you want to watch?</b>",
        DIVIDER,
        "Pick a movie from the updates above:",
    )


def discovery_stopped() -> str:
    return _blocks(
        "🔕 <b>Movie and showtime alerts are off</b>",
        "You won't get alerts about new movies, dates or showtimes.",
        "Your regular watches are untouched.",
        "You can turn them back on anytime with the button below or in <b>Settings</b>.",
    )


def discovery_resumed() -> str:
    return _blocks(
        "🔔 <b>Alerts are back on</b>",
        "You'll hear about everything new from the branches you picked.",
    )


def discovery_alert_expired() -> str:
    return _blocks(
        "⌛ <b>This alert has expired</b>",
        "Alerts stay tappable for seven days.",
        "Open the latest alert or go to /settings.",
    )


def discovery_channel(event_text: str) -> str:
    return f"{event_text}\n\n#cinemaradar"


# ---------------------------------------------------------------------- admin
def admin_text(data: dict[str, object]) -> str:
    return _blocks(
        f"🛠️ <b>Admin panel</b>\n{DIVIDER}",
        "<b>👥 People</b>\n"
        f"• Active users: <b>{data.get('active_users', 0)}</b>\n"
        f"• Supporters: <b>{data.get('supporters', 0)}</b>\n"
        f"• Active watches: <b>{data.get('active_watches', 0)}</b>",
        "<b>🌐 Network</b>\n"
        f"• Requests/min: <b>{data.get('requests_per_minute', 0):.1f}</b>\n"
        f"• Cache hit ratio: <b>{data.get('cache_hit_ratio', 0):.0%}</b>\n"
        f"• Active targets: <b>{data.get('active_targets', 0)}</b>\n"
        f"• Slowdown factor: <b>{data.get('slowdown_factor', 1):.2f}</b>\n"
        f"• Circuit breaker: <b>{esc(data.get('circuit_state', 'closed'))}</b>\n"
        f"• Last request: <b>{esc(data.get('last_poll_status', '—'))}</b>",
        "<b>🛰️ Discovery and broadcast</b>\n"
        f"• Last discovery: <b>{esc(data.get('discovery_last_run', '—'))}</b>\n"
        f"• Events today: <b>{data.get('events_today', 0)}</b>\n"
        f"• Broadcasts: <b>{data.get('broadcasts_sent', 0)}</b>\n"
        f"• Queue length: <b>{data.get('queue_length', 0)}</b>",
        version_line(),
    )


def admin_only() -> str:
    return "🔒 This command is for the admin only."


def grant_done(telegram_id: int, limit: int) -> str:
    return f"✅ Supporter access granted to <code>{telegram_id}</code> — limit <b>{limit}</b>."


def revoke_done(telegram_id: int, limit: int) -> str:
    return f"✅ Supporter access revoked for <code>{telegram_id}</code> — limit <b>{limit}</b>."


# ------------------------------------------------------------ admin / system
def admin_started() -> str:
    return f"✅ <b>Cinema Radar is running</b> (v{esc(__version__)})."


def admin_limits_applied(users: int, watches: int) -> str:
    if not users:
        return "✅ Watch limits applied (2 free / 10 supporters)."
    return _blocks(
        "✅ Watch limits applied (2 free / 10 supporters).",
        f"<b>{users}</b> users affected,\nand <b>{watches}</b> extra watches removed.",
    )


def admin_unexpected_error(name: str) -> str:
    return f"⚠️ <b>Unexpected error</b>\n<i>{esc(name)}</i>"


REASON_LABELS_EN = {
    "http_403": "({cinema}) rejected the request (403) — protection or block",
    "http_429": "({cinema}) rate-limited the request (429)",
    "http_5xx": "({cinema}) server returned an error (5xx)",
    "timeout": "Timed out connecting to ({cinema})",
    "network": "Network / TLS / DNS problem",
    "http2": "({cinema}) reset the connection (HTTP/2 stream reset)",
    "parse": "({cinema}) page changed and the bot can't read it",
    "empty": "({cinema}) returned an empty page",
    "circuit": "Circuit breaker open after repeated failures",
    "unknown": "Unknown error",
}


def reason_label(reason: str, provider: str | None = None) -> str:
    template = REASON_LABELS_EN.get(reason, REASON_LABELS_EN["unknown"])
    return template.format(cinema=cinema_name(provider))


def format_place(place: str) -> str:
    """Show a technical place key with the localized cinema name."""

    if place.startswith("vox"):
        return f"({cinema_name('vox')})" + place[3:]
    if place.startswith("renaissance"):
        return f"({cinema_name('renaissance')})" + place[len("renaissance") :]
    if place.startswith("premiere"):
        return f"({cinema_name('premiere')})" + place[len("premiere") :]
    return place


def admin_upstream_down(
    reason: str,
    place: str,
    last_success: str,
    retry_seconds: int,
    affected: int = 0,
    opened: bool = False,
    provider: str | None = None,
) -> str:
    cinema = cinema_name(provider)
    title = (
        f"🚨 <b>({cinema}) is down</b>" if opened else f"⚠️ <b>Temporary problem with ({cinema})</b>"
    )
    blocks = [
        title,
        f"<b>Reason</b>\n{esc(reason_label(reason, provider))}",
        f"<b>Where</b>\n{esc(place or '—')}",
        f"<b>Last success</b>\n{esc(last_success or '—')}",
    ]
    if affected:
        blocks.append(f"👀 <b>Affected watches</b>\n{affected}")
    if opened:
        blocks.append("🛑 <b>Alerts are paused</b>\nNo alerts from stale data until it recovers.")
        blocks.append(f"🔁 Trying again in {retry_seconds}s.")
    else:
        blocks.append(f"🔁 Retrying in {retry_seconds}s.")
        blocks.append("<i>If this keeps happening, I'll pause alerts and tell you.</i>")
    return _blocks(*blocks)


def admin_upstream_recovered(minutes: int, provider: str | None = None) -> str:
    cinema = cinema_name(provider)
    title = f"✅ <b>({cinema}) is back</b>"
    if minutes > 0:
        title += f" after {minutes} min"
    return _blocks(title, "Data is updating again ✅")


def stale_notice(minutes: int, degraded: bool) -> str:
    if minutes <= 0:
        return ""
    if degraded:
        return (
            f"\n\n⚠️ <i>The cinema is unavailable right now. Last update {minutes} min ago — "
            "data may be stale.</i>"
        )
    if minutes >= 10:
        return f"\n\n<i>Last update {minutes} min ago.</i>"
    return ""


def admin_status(data: dict[str, object]) -> str:
    return _blocks(
        f"📡 <b>Connection status</b>\n{DIVIDER}",
        f"• State: <b>{esc(data.get('state', '—'))}</b>\n"
        f"• Last success: {esc(data.get('last_success', '—'))}\n"
        f"• Last error: {esc(data.get('last_error', '—'))}\n"
        f"• Circuit breaker: <b>{esc(data.get('breaker', 'closed'))}</b>",
        f"• Active targets: <b>{data.get('targets', 0)}</b>\n"
        f"• Affected watches: <b>{data.get('affected', 0)}</b>",
    )


def admin_status_multi(data: dict[str, object]) -> str:
    sections = data.get("sections") or []
    blocks = [
        (
            f"🎬 <b>{esc(section.get('cinema', ''))}</b>\n"
            f"• Last update: {esc(section.get('last_success', '—'))}\n"
            f"• Last error: {esc(section.get('last_error', '—'))}\n"
            f"• Events today: <b>{section.get('events', 0)}</b>"
        )
        for section in sections
    ]
    footer = (
        f"• Circuit breaker: <b>{esc(data.get('breaker', 'closed'))}</b>\n"
        f"• Active targets: <b>{data.get('targets', 0)}</b>\n"
        f"• Affected watches: <b>{data.get('affected', 0)}</b>"
    )
    return _blocks(
        f"📡 <b>Connection status</b>\n{DIVIDER}",
        *blocks,
        f"{DIVIDER}\n{footer}",
    )


def _short_error(error: object) -> str:
    """Keep an admin alert readable; raw transport errors can be huge."""

    text = esc(error).strip()
    if len(text) > 280:
        text = text[:277].rstrip() + "…"
    return text


def admin_discovery_branches_failed(error: object) -> str:
    return f"⚠️ <b>Discovery couldn't load branches</b>\n\n<i>{_short_error(error)}</i>"


def admin_discovery_branch_failed(branch: object, error: object) -> str:
    return f"⚠️ <b>Discovery failed at {esc(branch)}</b>\n\n<i>{_short_error(error)}</i>"


# ------------------------------------------------------------------ discovery
def discovery_line_upcoming(name: object) -> str:
    return f"🏁 Just released: {esc(name)}"


def discovery_line_new_movie(name: object) -> str:
    return f"🆕 New movie: {esc(name)}"


def discovery_line_new_date(name: object, date_text: str) -> str:
    return f"📅 New date open: {esc(name)} — {format_date(date_text)}"


def discovery_line_new_showtimes(name: object, times: tuple[str, ...]) -> str:
    shown = times[:6]
    formatted = ", ".join(format_time(value) for value in shown)
    if len(times) > len(shown):
        formatted += ", and more"
    return f"🕐 New showtimes: {esc(name)} — {formatted}"


# ---------------------------------------------------------------------- errors
def error_expired() -> str:
    return _blocks(
        "⌛ <b>This screen is out of date</b>",
        "The show changed or the page expired.\nTap /start and begin again.",
    )


def error_generic() -> str:
    return _blocks(
        "😅 <b>A small hiccup</b>",
        "Please try again in a moment 🙏",
    )


def rate_limited() -> str:
    return "Give it a moment between steps 🙏"


def cancelled() -> str:
    return _blocks(
        "Cancelled ✅",
        "To go back to the menu, tap /start.",
    )


def delete_me_confirm() -> str:
    return _blocks(
        f"🗑️ <b>Are you sure?</b>\n{DIVIDER}",
        "I'll delete everything:\nyour watches, alerts, feedback and support proofs.",
        "This can't be undone.",
    )


def delete_me_done() -> str:
    return _blocks(
        "✅ <b>All your data is deleted</b>",
        "You can come back anytime with /start.",
    )


def quiet_hours_set(start: int, end: int) -> str:
    return (
        f"✅ <b>Quiet hours set</b>\n"
        f"From {format_time(f'{start}:00')} to {format_time(f'{end}:00')}"
    )


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
    return "That user doesn't exist."
