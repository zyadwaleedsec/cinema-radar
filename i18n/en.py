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
    return "Renaissance" if code == "renaissance" else "VOX"


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
BTN_WATCH_MOVIE = "🔔 Watch this movie"
BTN_STOP_ALERTS = "🔕 Stop these alerts"
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
BTN_SEATS_CUSTOM = "✍️ Custom number"
BTN_LANGUAGE = "🌐 Language"
BTN_ARABIC = "🇪🇬 العربية"
BTN_ENGLISH = "🇺🇸 English"
BTN_ALL_CINEMAS = "🌍 All cinemas"
BTN_SHARE = "🔗 Share booking"
BTN_CONSENT_ACCEPT = "✅ I agree, start"
BTN_CONSENT_DECLINE = "❌ I don't agree"
BTN_CONSENT_REVIEW = "🔐 Review consent again"

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
        "🎬 <b>Cinema Radar</b>",
        DIVIDER,
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
        lines += ["", "⏭️ <b>Next watch</b>", next_watch]
    if limit:
        lines += ["", f"<i>Your current limit is {_count(limit, 'watch', 'watches')}.</i>"]
    lines += ["", "Pick an option below 👇"]
    return "\n".join(lines)


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
    return (
        "🎬 <b>Cinema Radar</b>\n"
        f"{DIVIDER}\n"
        f"Welcome{who} 👋\n\n"
        "I watch VOX and Renaissance showtimes in Egypt,\n"
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
        "• It is unofficial and not affiliated with any cinema.\n\n"
        "Full details: /privacy\n"
        "Erase your data anytime: /delete_me"
    )


def onboard_progress(step: int) -> str:
    return f"<i>{progress(step + 1, 3)}</i>"


def help_text() -> str:
    return (
        f"🎬 <b>How to use Cinema Radar</b>\n{DIVIDER}\n\n"
        "<b>1 · Add a watch</b>\n"
        "Tap <b>➕ Add a watch</b>, then pick:\n"
        "• Branch\n"
        "• Date\n"
        "• Movie\n"
        "• Showtime\n\n"
        "Or watch every showtime that day, or every available date.\n"
        "You can also filter by format (IMAX, 4DX, VIP…).\n\n"
        "<b>2 · Wait for the alert</b>\n"
        "When booking opens or a seat comes back,\n"
        "you get a message with the booking link.\n\n"
        "<b>3 · Control your alerts</b>\n"
        "From <b>🎟️ My watches</b> you can:\n"
        "• Choose the alert type\n"
        "• Snooze for an hour\n"
        "• Remove the watch\n\n"
        "<b>Can't find a movie?</b>\n"
        "Tap <b>🔎 Search by name</b> and type part of the title\n"
        "in Arabic or English.\n"
        "The bot tolerates typos too.\n\n"
        "<b>Useful commands</b>\n"
        "/start — Main menu\n"
        "/add — Add a watch\n"
        "/search — Search for a movie\n"
        "/watches — My watches\n"
        "/settings — Settings\n"
        "/help — Help\n"
        "/privacy — Privacy\n"
        "/delete_me — Delete my data\n"
        "/cancel — Cancel the current step\n\n"
        "⚠️ The bot is unofficial and not affiliated with VOX or Renaissance Cinemas.\n"
        "Data may be delayed or wrong,\n"
        "and booking happens on the cinema's own site.\n\n"
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
    return (
        f"🎬 <b>Choose a cinema</b>\n{DIVIDER}\n\n"
        "Pick the cinema you want to watch at, or «All cinemas» to watch the movie "
        "across every branch at once."
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
    return (
        f"🎬 <b>{esc(movie)}</b> · 📅 {relative_date(date)}\n{DIVIDER}\n\n"
        "Choose the period to watch across all cinemas:\n"
        f"🌅 <b>Morning</b> — shows before {cutoff}\n"
        f"🌙 <b>Evening</b> — shows from {cutoff}"
    )


def confirm_window(
    movie: str,
    date: str,
    window: str,
    branch_count: int,
    morning_end_hour: int = 17,
    required_seats: int = 1,
) -> str:
    return (
        f"🎬 <b>{esc(movie)}</b>\n{DIVIDER}\n\n"
        f"📅 {relative_date(date)}\n"
        f"🕐 {window_label(window, morning_end_hour)}\n"
        f"🏢 {_count(branch_count, 'branch', 'branches')}\n"
        f"{required_seats_line(required_seats)}\n\n"
        "You'll watch every show in this period across all cinemas, and get a ping "
        "when a new show opens or a seat comes back.\n\n"
        "Confirm the watch?"
    )


def watch_created_window(
    movie: str, date: str, window: str, branch_count: int, morning_end_hour: int = 17
) -> str:
    return (
        "✅ <b>Watch active</b>\n\n"
        f"🎬 {esc(movie)}\n"
        f"📅 {relative_date(date)} · 🕐 {window_label(window, morning_end_hour)}\n"
        f"🏢 All cinemas ({_count(branch_count, 'branch', 'branches')})\n\n"
        "I'll alert you when a new show opens in this period."
    )


def no_showtimes_window(movie: str, date: str) -> str:
    return (
        f"🍿 <b>No shows</b>\n\n"
        f"No shows for «<b>{esc(movie)}</b>» on {relative_date(date)} at any cinema.\n"
        "Try another day or period."
    )


def choose_branch() -> str:
    return f"{step_header(1, 5, 'Branch')}\n\n<b>Pick a branch</b> 🏢"


def choose_date(branch: str) -> str:
    return f"{step_header(2, 5, branch)}\n\n<b>Pick a date</b> 📅"


def choose_movie(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return (
        f"{step_header(3, 5, path)}\n\n"
        "<b>Pick a movie</b> 🎞️\n"
        "Can't find it? Tap <b>🔎 Search by name</b>."
    )


def search_choose_branch(query: str = "") -> str:
    head = f"{step_header(2, 5, 'Search')}\n\n"
    if query:
        return f"{head}Searching for “<b>{esc(query)}</b>” 🔎\n\nPick the branch first:"
    return f"{head}<b>Movie search</b> 🔎\n\nPick the branch first:"


def search_prompt(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return (
        f"{step_header(3, 5, path)}\n\n"
        "<b>Type the movie name</b> 🔎\n"
        "In Arabic or English.\n"
        "Typos are fine — part of the name is enough."
    )


def search_too_short() -> str:
    return "Type at least two letters so I can search 🔎"


def search_results(query: str, count: int, total: int) -> str:
    return (
        f"🔎 <b>Search results</b>\n\n"
        f"“<b>{esc(query)}</b>”\n"
        f"<b>{count}</b> of {_count(total, 'movie')}\n\n"
        "Pick the movie you want:"
    )


def search_no_results(query: str, suggestions: list[str] | None = None) -> str:
    lines = [f"🍿 <b>No results</b>\n\nNo movie close to “<b>{esc(query)}</b>” on that date."]
    if suggestions:
        lines += ["", "Did you mean one of these? Tap it 👇"]
    else:
        lines += [
            "",
            "Try part of the name,\nthe English title,\nor browse all movies.",
        ]
    return "\n".join(lines)


def choose_showtime(movie: str, date: str, extra: str = "") -> str:
    path = f"{relative_date(date)} › {movie}"
    lines = [step_header(4, 5, path), ""]
    if extra:
        lines += [extra, ""]
    lines += [
        "<b>Pick the showtime you want to watch</b> 🎟️",
        "",
        "🟢 Available — you can book now",
        "🔴 Sold out — fully booked",
        "⚪ Not on sale yet — wait for the alert",
        "",
        "Want a specific format (IMAX, 4DX, VIP…)?\nPick it from the buttons above.",
    ]
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
    return (
        f"{step_header(6, 6, 'Confirm')}\n\n"
        "<b>Confirm watch</b>\n\n"
        f"🎬 {esc(movie)}\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} ({format_date(date)})\n"
        f"🕐 {format_time(time)} · {esc(hall)}\n"
        f"{required_seats_line(required_seats)}\n\n"
        f"{note}"
    )


def no_data() -> str:
    return (
        "⏳ <b>Still fetching data</b>\n\n"
        "The cinema isn't responding right now.\n"
        "Try again in a minute 🙏\n\n"
        "<i>I don't send requests to the cinema site while you browse,\n"
        "so the bot stays reliable.</i>"
    )


def loading_branches() -> str:
    return "⏳ <b>Loading branches…</b>\n\nOne moment."


def loading_showtimes() -> str:
    return "⏳ <b>Loading shows from all cinemas…</b>\n\nThis can take a few seconds."


def window_movie_prompt() -> str:
    return "🔎 <b>Type the movie name</b>\n\nType the movie you want to watch across all cinemas (Arabic or English)."


def choose_date_all_cinemas() -> str:
    return "📅 <b>Pick a day</b>\n\nPick the day you want to watch across all cinemas."


def no_dates() -> str:
    return (
        "📅 <b>No dates available</b>\n\n"
        "This branch hasn't opened any dates yet.\n\n"
        "Try another branch, or wait a bit."
    )


def no_movies() -> str:
    return (
        "🎬 <b>Booking isn't open yet</b>\n\n"
        "No movies are available on that date right now.\n\n"
        "Try another date,\n"
        "and when showtimes appear they'll be right here."
    )


def no_showtimes() -> str:
    return (
        "🎟️ <b>No showtimes</b>\n\n"
        "Booking isn't open for this movie on that date yet.\n\n"
        "Try another movie or date."
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
    return (
        f"{step_header(6, 6, 'Confirm')}\n\n"
        "<b>Confirm full-day watch</b>\n\n"
        f"🎬 {esc(movie)}\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} ({format_date(date)})\n"
        f"{ticket}\n"
        f"{required_seats_line(required_seats)}\n\n"
        f"{note}"
    )


def watch_created_movie(
    branch: str, date: str, movie: str, count: int, hall: str | None = None
) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        "✅ <b>Watch added</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)}{format_text}\n"
        f"🎟️ Every showtime ({_count(count, 'showtime')})\n\n"
        "As soon as any booking opens or seats come back,\n"
        "you'll get a message.\n\n"
        "Set the alert type in <b>⚙️ Alert settings</b>."
    )


def watch_created(branch: str, date: str, movie: str, time: str, hall: str) -> str:
    return (
        "✅ <b>Watch added</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} · {format_time(time)}\n"
        f"🎭 {esc(hall)}\n\n"
        "You'll get a message when anything changes.\n\n"
        "Set the alert type in <b>⚙️ Alert settings</b>."
    )


def confirm_all_dates(
    branch: str,
    movie: str,
    count: int,
    hall: str | None = None,
    required_seats: int = 1,
) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        f"{step_header(6, 6, 'Confirm')}\n\n"
        "<b>Confirm watch on every date</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"🎬 {esc(movie)}\n"
        f"📅 Every date available now ({_count(count, 'day')}){format_text}\n"
        f"{required_seats_line(required_seats)}\n\n"
        "I'll watch every day this movie plays at this branch, plus any new date that opens.\n"
        "When booking opens or seats come back, you'll get a message."
    )


def watch_created_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        "✅ <b>Watch added</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}{format_text}\n"
        f"📅 Every available date ({_count(count, 'day')})\n\n"
        "If a new date opens or seats come back,\n"
        "you'll get a message.\n\n"
        "Set the alert type in <b>⚙️ Alert settings</b>."
    )


def all_dates_unavailable() -> str:
    return (
        "📅 <b>No dates available</b>\n\n"
        "This branch hasn't opened any dates yet.\n\n"
        "Try a specific date,\n"
        "or wait for booking to open."
    )


def watch_limit_reached(
    limit: int,
    supporter_limit: int = 10,
    min_amount: int = 50,
    is_supporter: bool = False,
) -> str:
    if is_supporter:
        return (
            "⚠️ <b>You've reached the maximum</b>\n\n"
            f"You have <b>{_count(limit, 'watch', 'watches')}</b>.\n\n"
            "Remove an old watch from <b>My watches</b>\n"
            "to add a new one."
        )
    return (
        "⚠️ <b>You've reached the free limit</b>\n\n"
        f"You have <b>{_count(limit, 'watch', 'watches')}</b>, which is the free limit.\n\n"
        f"To reach <b>{_count(supporter_limit, 'watch', 'watches')}</b>,\n"
        "you can support the project <b>once</b>\n"
        f"with a minimum of <b>{min_amount} EGP</b> from <b>Support the project</b> 💛\n\n"
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
    return (
        "🍿 <b>No watches yet</b>\n\n"
        "Start with one movie,\n"
        "and I'll message you when booking opens\n"
        "or a seat comes back.\n\n"
        "Tap <b>➕ Add a watch</b> below."
    )


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
        f"🏢 ({cinema_name(provider)}) · {esc(branch)} · {relative_date(date)}",
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
    watchers: int | None = None,
) -> str:
    snooze = (
        f"⏰ Snoozed until {esc(snoozed_until_text)}" if snoozed_until_text else "⏰ Not snoozed"
    )
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 Every available date · all showtimes{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ All showtimes{format_text}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text}"
    crowd = f"{watchers_line(watchers)}\n" if watchers else ""
    return (
        f"⚙️ <b>Watch settings</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 ({cinema_name(provider)}) · {esc(branch)} · {relative_date(date)}\n"
        f"{ticket}\n\n"
        f"🔔 Alerts: <b>{watch_mode_label(mode)}</b>\n"
        f"🪑 Alert when: <b>{_needed_seats(required_seats)} or more</b>\n"
        f"{crowd}"
        f"{snooze}\n\n"
        "Pick the alert type that suits you:"
    )


def watchers_line(count: int | None) -> str:
    return f"👥 {int(count or 0)} people are watching this movie"


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
        "⏰ <b>Here's the watch you asked about</b>",
        "",
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {esc(branch)} · {relative_date(date)}",
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
    seat_text = f"\n🪑 {_seats(seats)} available" if seats else ""
    return (
        f"🎟️ <b>Booking opened</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} · {format_time(time)}\n"
        f"🎭 {esc(hall)}"
        f"{seat_text}\n\n"
        "Book before it fills up."
    )


def alert_seats_available(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f"<b>{_seats(seats)}</b> available now." if seats else "Seats are available now."
    return (
        f"🪑 <b>Seats are back</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} · {format_time(time)}\n"
        f"🎭 {esc(hall)}\n\n"
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
    seat_text = f"\n🪑 {_seats(seats)} available" if seats else ""
    return (
        f"🎟️ <b>Booking opened for this movie</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)}\n"
        f"🕐 {joined}{more}"
        f"{seat_text}\n\n"
        "Book before it fills up."
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
    return (
        f"🪑 <b>Seats are back for this movie</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)}\n"
        f"🕐 {joined}{more}"
        f"{seat_text}\n\n"
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
    hall_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        f"📅 <b>A new date just opened</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)}"
        f"{hall_text}\n"
        f"🕐 {joined}{more}\n\n"
        "Open the booking page and see what's available."
    )


def alert_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = ", ".join(format_time(t) for t in times[:8])
    more = " and more" if len(times) > 8 else ""
    return (
        f"🕐 <b>New showtimes appeared</b>\n{DIVIDER}\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)}\n"
        f"🕐 {joined}{more}\n\n"
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
        f"⚙️ <b>Settings</b>\n{DIVIDER}\n\n"
        "<b>Notifications</b>\n"
        f"• Seats back: {'on ✅' if notify_cancellations else 'off ⛔'}\n"
        f"• Quiet hours: {format_time(f'{quiet_start}:00')} to {format_time(f'{quiet_end}:00')}\n"
        f"  <i>{watch_quiet}</i>\n"
        f"• New movies and bookings: {'on ✅' if discovery_enabled else 'off ⛔'}\n\n"
        "<b>New-alert filters</b>\n"
        f"• Branches: {esc(branches)}\n"
        f"• Types: {esc(types)}\n"
        f"• Hall: {esc(hall)}\n"
        f"• Language: {'العربية' if (language or 'en') == 'ar' else 'English'}\n\n"
        f"{version_line()}"
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
    return "Pick a hall type that your selected cinemas actually offer:"


def format_not_offered() -> str:
    return "That format isn't offered by your selected cinemas."


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
        f"💛 <b>Support the project</b>\n{DIVIDER}\n\n"
        "Cinema Radar is free for everyone,\n"
        "and every user gets <b>2 watches</b> for free.\n\n"
        "If you want more, you can support the project <b>once</b>\n"
        f"with a minimum of <b>{min_amount} EGP</b>,\n"
        f"and your limit becomes <b>{limit} watches</b> for good.\n"
        "Not a monthly subscription.\n\n"
        "Pay with Vodafone Cash or InstaPay,\n"
        "then send a screenshot of the transfer.\n"
        "The admin reviews the proof and approves it.\n\n"
        "Pick how you'd like to support:"
    )


def support_manual_text(method: str, phone: str, min_amount: int = 50) -> str:
    name = "Vodafone Cash" if method == "vodafone_cash" else "InstaPay"
    return (
        f"💛 <b>Support via {name}</b>\n\n"
        "Send to this number:\n"
        f"<code>{esc(phone)}</code>\n\n"
        f"Minimum <b>{min_amount} EGP</b> — one time, not a subscription.\n\n"
        "After paying, tap <b>I paid ✅</b>,\n"
        "then send the transfer screenshot or transaction ID.\n"
        "The admin reviews it,\n"
        "and once approved your limit becomes <b>10 watches</b>.\n\n"
        "⚠️ Transfers are not activated automatically."
    )


def support_ask_amount(min_amount: int = 50) -> str:
    return (
        "💰 <b>How much did you send?</b>\n\n"
        f"The minimum is <b>{min_amount} EGP</b>.\n"
        "Pick an amount below,\n"
        "or type it in digits (example: 75)."
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
        "✍️ <b>Send feedback</b>\n\n"
        f"Type: <b>{esc(label)}</b>\n\n"
        "Write your feedback or idea in one message.\n"
        "Every message reaches the admin and helps us improve the bot."
    )


def feedback_thanks() -> str:
    return "Thanks! We got your feedback ✅"


def feedback_too_soon() -> str:
    return "We got feedback from you recently. Try again in an hour 🙏"


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
    return f"<b>New feedback</b> from {who}:\n\n{esc(text)}{reference}"


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
        f"📅 from {relative_date(date)}" if date else "",
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
        f"📅 from {relative_date(date)}",
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
        f"📅 from {relative_date(date)}" if date else "",
        f"🎭 {esc(hall)}" if hall else "",
        "🎬 <i>Book before it fills up.</i>",
    )


def discovery_digest(
    branch: str,
    count: int,
    lines: list[str],
    provider: str | None = None,
) -> str:
    body = "\n".join(f"• {line}" for line in lines[:6])
    more = f"\n<i>and {_count(count - 6, 'more update', 'more updates')}</i>" if count > 6 else ""
    return _blocks(
        f"🍿 <b>{_count(count, 'new update', 'new updates')} at "
        f"{cinema_name(provider)} · {esc(branch)}</b>",
        DIVIDER,
        body + more,
        "👀 <i>Take a look and pick your favourite.</i>",
    )


def discovery_channel(event_text: str) -> str:
    return f"{event_text}\n\n#cinemaradar"


# ---------------------------------------------------------------------- admin
def admin_text(data: dict[str, object]) -> str:
    return (
        f"🛠️ <b>Admin panel</b>\n{DIVIDER}\n\n"
        "<b>People</b>\n"
        f"• Active users: <b>{data.get('active_users', 0)}</b>\n"
        f"• Supporters: <b>{data.get('supporters', 0)}</b>\n"
        f"• Active watches: <b>{data.get('active_watches', 0)}</b>\n\n"
        "<b>Network</b>\n"
        f"• Requests/min: <b>{data.get('requests_per_minute', 0):.1f}</b>\n"
        f"• Cache hit ratio: <b>{data.get('cache_hit_ratio', 0):.0%}</b>\n"
        f"• Active targets: <b>{data.get('active_targets', 0)}</b>\n"
        f"• Slowdown factor: <b>{data.get('slowdown_factor', 1):.2f}</b>\n"
        f"• Circuit breaker: <b>{esc(data.get('circuit_state', 'closed'))}</b>\n"
        f"• Last request: <b>{esc(data.get('last_poll_status', '—'))}</b>\n\n"
        "<b>Discovery and broadcast</b>\n"
        f"• Last discovery: <b>{esc(data.get('discovery_last_run', '—'))}</b>\n"
        f"• Events today: <b>{data.get('events_today', 0)}</b>\n"
        f"• Broadcasts: <b>{data.get('broadcasts_sent', 0)}</b>\n"
        f"• Queue length: <b>{data.get('queue_length', 0)}</b>\n\n"
        f"{version_line()}"
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


def admin_self_check_failed(error: str) -> str:
    return (
        f"⚠️ <b>Post-deploy self-check failed</b>\n{DIVIDER}\n\n"
        "The bot started, but its first cinema request did not succeed:\n"
        f"<code>{esc(error)}</code>\n\n"
        "Check the logs; an incident alert follows automatically if it persists."
    )


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
        f"🔎 Reason: {esc(reason_label(reason, provider))}",
        f"📍 Where: {esc(place or '—')}",
        f"🕒 Last success: {esc(last_success or '—')}",
    ]
    if affected:
        blocks.append(f"👀 Affected watches: <b>{affected}</b>")
    if opened:
        blocks.append("🛑 Alerting is paused — no alerts based on stale data until it recovers.")
        blocks.append(f"🔁 Trying again in {retry_seconds}s.")
    else:
        blocks.append(f"🔁 Retrying in {retry_seconds}s.")
        blocks.append("<i>If this keeps happening, I'll pause alerts and tell you.</i>")
    return "\n\n".join(blocks)


def admin_upstream_recovered(minutes: int, provider: str | None = None) -> str:
    cinema = cinema_name(provider)
    if minutes <= 0:
        return f"✅ <b>({cinema}) is back</b>\n\nData is updating again."
    return f"✅ <b>({cinema}) is back</b> after {minutes} min\n\nData is updating again."


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
    return (
        "📡 <b>Connection status</b>\n{DIVIDER}\n\n"
        f"• State: <b>{esc(data.get('state', '—'))}</b>\n"
        f"• Last success: {esc(data.get('last_success', '—'))}\n"
        f"• Last error: {esc(data.get('last_error', '—'))}\n"
        f"• Circuit breaker: <b>{esc(data.get('breaker', 'closed'))}</b>\n\n"
        f"• Active targets: <b>{data.get('targets', 0)}</b>\n"
        f"• Affected watches: <b>{data.get('affected', 0)}</b>"
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
    return (
        "📡 <b>Connection status</b>\n{DIVIDER}\n\n"
        + "\n\n".join(blocks)
        + f"\n\n{DIVIDER}\n"
        + footer
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
