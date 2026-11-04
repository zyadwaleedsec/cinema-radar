"""Egyptian Arabic copy for every user-facing surface.

Keeping copy in one file makes it easy to edit without touching logic.
Dynamic values are HTML-escaped because messages are sent with parse_mode=HTML.
The English catalog in :mod:`i18n.en` mirrors every public name here; a test
enforces that the two never drift apart.
"""

from __future__ import annotations

from datetime import date as date_cls

from i18n.base import esc
from imax import CERTIFIED_DIGITAL, FULL_70MM, PARTIAL_70MM, PARTIAL_DIGITAL, UNKNOWN
from models import (
    AVAILABLE,
    NOT_AVAILABLE,
    SOLD_OUT,
    STATUS_LABELS_AR,
)
from models import (
    format_label as _format_label,
)
from version import __version__

CODE = "ar"
NAME = "العربية"
RTL = True


def format_time(value: str) -> str:
    """``10:45`` / ``10:45am`` / ``22:00`` -> ``10:45 ص`` / ``10:45 ص`` / ``10:00 م``."""

    raw = (value or "").strip().lower().replace(".", "")
    suffix = ""
    if raw.endswith("pm"):
        suffix = "م"
        raw = raw[:-2].strip()
    elif raw.endswith("am"):
        suffix = "ص"
        raw = raw[:-2].strip()
    parts = raw.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        hour = int(parts[0])
        minute = int(parts[1][:2])
        if suffix:
            # Input carried am/pm; normalise it to 24 hours first.
            if suffix == "م" and hour < 12:
                hour += 12
            if suffix == "ص" and hour == 12:
                hour = 0
        display_suffix = "م" if hour >= 12 else "ص"
        hour12 = hour % 12 or 12
        return f"{hour12}:{minute:02d} {display_suffix}"
    return esc(value)


def format_date(value: str) -> str:
    if value == "*":
        return "كل الأيام"
    try:
        d = date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return esc(value)
    return d.strftime("%d/%m")


_WEEKDAYS_AR = (
    "الاثنين",
    "الثلاثاء",
    "الأربعاء",
    "الخميس",
    "الجمعة",
    "السبت",
    "الأحد",
)


def relative_date(value: str, today: date_cls | None = None) -> str:
    if value == "*":
        return "كل الأيام المتاحة"
    today = today or date_cls.today()
    try:
        d = date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return format_date(value)
    delta = (d - today).days
    if delta == 0:
        return "النهاردة"
    if delta == 1:
        return "بكرة"
    if delta == -1:
        return "امبارح"
    return f"{_WEEKDAYS_AR[d.weekday()]} {d.day}/{d.month:02d}"


# --------------------------------------------------------------------- buttons
BTN_ADD_WATCH = "➕ ضيف مراقبة"
BTN_SEARCH = "🔎 دوّر على فيلم"
BTN_SEARCH_MOVIE = "🔎 دوّر بالاسم"
BTN_SEARCH_AGAIN = "🔎 بحث تاني"
BTN_ALL_MOVIES = "📋 كل الأفلام"
BTN_MY_WATCHES = "🎟️ مراقباتي"
BTN_SETTINGS = "⚙️ الإعدادات"
BTN_SUPPORT = "💛 ادعم المشروع"
BTN_FEEDBACK = "✍️ ابعتلنا رأيك"
BTN_BACK = "⬅️ رجوع"
BTN_HOME = "🏠 الرئيسية"
BTN_CANCEL = "إلغاء"
BTN_NEXT = "التالي"
BTN_PREV = "السابق"
BTN_RETRY = "🔄 جرّب تاني"
BTN_ONBOARD_NEXT = "التالي ➡️"
BTN_ONBOARD_SKIP = "تخطي"
BTN_ONBOARD_START = "يلا نبدأ 🎬"
BTN_CONFIRM = "أكد المراقبة ✅"
BTN_DELETE_ALL = "🗑️ امسح الكل"
BTN_CONFIRM_DELETE_ALL = "أيوه امسح الكل"
BTN_OPEN_BOOKING = "🎟️ افتح الحجز"
BTN_WATCH_MOVIE = "راقب الفيلم ده"
BTN_STOP_ALERTS = "إيقاف التنبيهات دي"
BTN_REMOVE_WATCH = "❌ شيل المراقبة"
BTN_CONFIRM_REMOVE_WATCH = "أيوه شيلها"
BTN_SNOOZE = "⏰ فكّرني بعد ساعة"
BTN_UNSNOOZE = "🔕 رجّع التنبيه"
BTN_MODE_ALL = "🔔 كل حاجة"
BTN_MODE_SEATS = "🪑 كراسي رجعت"
BTN_MODE_OPENING = "🎟️ فتح الحجز بس"
BTN_WATCH_SETTINGS = "⚙️ إعدادات التنبيه"
BTN_WATCH_ALL_SHOWTIMES = "🔔 راقب كل حفلات اليوم"
BTN_WATCH_ALL_DATES = "📅 راقب كل الأيام المتاحة"
BTN_I_PAID = "حوّلت ✅"
BTN_YES_DELETE = "أيوه امسح بياناتي"
BTN_NO = "لا، رجعني"
BTN_DONE = "تم ✅"
BTN_ALL_SHOWTIMES = "كل الحفلات"
BTN_ALL_HALLS = "كل القاعات"
BTN_ALL_FORMATS = "🎭 كل الفورمات"
BTN_MOVIE_INFO = "ℹ️ معلومات الفيلم"
BTN_TRAILER = "▶️ شوف التريلر"
BTN_BACK_TO_SHOWTIMES = "🔙 رجوع للحفلات"
BTN_VODAFONE_CASH = "فودافون كاش"
BTN_INSTAPAY = "إنستاباي"
BTN_CANCELLATIONS = "تنبيه الإلغاء"
BTN_QUIET_HOURS = "🕰️ ساعات الهدوء"
BTN_QUIET_CUSTOM = "🕰️ وقت مخصص"
BTN_DISCOVERY_ALERTS = "تنبيهات الأفلام الجديدة"
BTN_BRANCHES_FILTER = "🎯 فروع التنبيهات"
BTN_TYPES_FILTER = "📌 أنواع التنبيهات"
BTN_HALL_FILTER = "🎭 نوع القاعة"
BTN_QUIET_WATCHES = "تنبيهات المراقبات بتحترم الهدوء"
BTN_DELETE_MY_DATA = "🗑️ حذف بياناتي"
BTN_COPY_PHONE = "📋 نسخ الرقم"
BTN_MANAGE_WATCH = "⚙️ إدارة المراقبة"
BTN_LANGUAGE = "🌐 اللغة"
BTN_ARABIC = "العربية"
BTN_ENGLISH = "English"

# Public commands are registered in the default scope.  Admin commands are
# registered only in the admin's private chat scope, so they never appear in
# the public menu.
PUBLIC_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "القائمة الرئيسية"),
    ("add", "ضيف مراقبة جديدة"),
    ("search", "دوّر على فيلم بالاسم"),
    ("watches", "مراقباتي"),
    ("settings", "الإعدادات"),
    ("help", "المساعدة"),
    ("privacy", "الخصوصية والبيانات"),
    ("delete_me", "امسح بياناتي"),
    ("cancel", "إلغاء أي خطوة"),
)

ADMIN_COMMANDS: tuple[tuple[str, str], ...] = (
    ("admin", "لوحة الأدمن"),
    ("status", "حالة الاتصال بـ VOX"),
    ("grant", "تفعيل دعم مستخدم"),
    ("revoke", "إلغاء دعم مستخدم"),
    ("imax", "ضبط حالة IMAX لفيلم"),
)


# ----------------------------------------------------------------------- start


def dashboard(
    name: str = "",
    active_watches: int = 0,
    next_watch: str | None = None,
    limit: int | None = None,
) -> str:
    who = f" يا {esc(name)}" if name else ""
    lines = [
        "🎬 <b>سينما رادار</b>",
        f"أهلاً بيك{who} 👋",
        "",
    ]
    if active_watches:
        lines.append(f"عندك <b>{active_watches}</b> مراقبة نشطة.")
    else:
        lines.append("مفيش مراقبات نشطة لسه — ابدأ بضغطة من تحت.")
    if next_watch:
        lines.append(f"⏭️ أقرب مراقبة: {next_watch}")
    if limit:
        lines.append(f"<i>حدك الحالي {limit} مراقبة.</i>")
    lines += ["", "اختار من تحت 👇"]
    return "\n".join(lines)


def version_line() -> str:
    return f"<i>الإصدار v{esc(__version__)}</i>"


def language_screen() -> str:
    return (
        "🌐 <b>اختار لغتك</b> · <b>Choose your language</b>\n\n"
        "تقدر تغيّرها في أي وقت من الإعدادات.\n"
        "You can change it anytime from Settings."
    )


def language_saved(name: str = "") -> str:
    return f"تمام ✅ لغتك بقت <b>{esc(name or NAME)}</b>."


def dashboard_next(movie: str, branch: str, date: str, showtime: str, scope: str | None) -> str:
    when = relative_date(date)
    if (scope or "showtime") == "movie_all_dates":
        detail = "كل الأيام"
    elif (scope or "showtime") == "movie":
        detail = "كل الحفلات"
    elif showtime and showtime != "*":
        detail = format_time(showtime)
    else:
        detail = "كل الحفلات"
    return f"<b>{esc(movie)}</b> — {esc(branch)} — {when} · {esc(detail)}"


def step_header(step: int, total: int, path: str) -> str:
    return f"<i>{step}/{total} · {esc(path)}</i>"


def page_label(page: int, pages: int) -> str:
    if pages <= 1:
        return ""
    return f"<i>صفحة {page + 1} من {pages}</i>"


# ------------------------------------------------------------------ onboarding
def onboard_intro(name: str = "") -> str:
    who = f" يا {esc(name)}" if name else ""
    return (
        f"أهلاً بيك{who} في <b>سينما رادار</b> 🎬\n\n"
        "أنا بتابع حفلات VOX في مصر وأبعتلك تنبيه أول ما الحجز يفتح "
        "أو كرسي يرجع متاح.\n\n"
        "يعني مش هتحتاج تفضل تفتح الموقع كل شوية — أنا هعمل ده عنك."
    )


def onboard_alerts() -> str:
    return (
        "<b>إيه اللي هيوصلك؟</b> 🔔\n\n"
        "• <b>فتح الحجز</b> — أول ما حفلة جديدة تبقى متاحة.\n"
        "• <b>كراسي رجعت</b> — لو الحفلة كانت مكتملة وفضل كرسي.\n"
        "• <b>أيام جديدة</b> — لو راقبت كل الأيام والفيلم نزل في يوم جديد.\n\n"
        "تقدر تختار نوع التنبيه لكل مراقبة لوحدها من "
        "<b>⚙️ إعدادات التنبيه</b>، وتأجل التنبيهات وقت ما تحب."
    )


def onboard_safety() -> str:
    return (
        "<b>قبل ما نبدأ — كام حاجة مهمة</b> 🙏\n\n"
        "• البوت مجاني وبس بيبعتلك لينك الحجز — مش بيحجز ولا بيدفع مكانك.\n"
        "• مش بطلب منك اسمك ولا رقمك ولا أي بيانات دفع.\n"
        "• البوت غير رسمي وغير تابع لـ VOX Cinemas، والبيانات ممكن تتأخر "
        "أو تكون غلط.\n\n"
        "كل ده تفاصيله في /privacy، وتقدر تمسح بياناتك في أي وقت "
        "بـ /delete_me."
    )


def onboard_progress(step: int) -> str:
    return f"<i>خطوة {step + 1} من 3</i>"


def help_text() -> str:
    return (
        "<b>إزاي تستخدم سينما رادار؟</b>\n\n"
        "1. اضغط <b>➕ ضيف مراقبة</b>.\n"
        "2. اختار الفرع، اليوم، الفيلم، والحفلة — أو راقب كل حفلات اليوم/كل الأيام، "
        "واختار الفورمات لو عايز (IMAX، 4DX، VIP…).\n"
        "3. أول ما الحجز يفتح أو ترجع كراسي هتوصلك رسالة فيها لينك الحجز.\n\n"
        "من جوه التنبيه تقدر تفتح الحجز، تشيل المراقبة، أو تأجلها ساعة. "
        "ومن <b>🎟️ مراقباتي</b> تظبط نوع التنبيه: كل حاجة، كراسي رجعت، أو فتح الحجز بس.\n\n"
        "مش لاقي الفيلم؟ اضغط <b>🔎 دوّر بالاسم</b> واكتب جزء من الاسم "
        "بالعربي أو الإنجليزي — البوت بيفهم الأخطاء الإملائية كمان.\n\n"
        "<b>أوامر مفيدة</b>\n"
        "/start القائمة الرئيسية\n"
        "/add ضيف مراقبة جديدة\n"
        "/search دوّر على فيلم بالاسم\n"
        "/watches مراقباتي\n"
        "/settings الإعدادات\n"
        "/help المساعدة\n"
        "/privacy إيه البيانات اللي بنحفظها\n"
        "/delete_me مسح بياناتك\n"
        "/cancel إلغاء أي خطوة\n\n"
        "⚠️ البوت غير رسمي وغير تابع لـ VOX Cinemas. البيانات ممكن تتأخر "
        "أو تكون غلط، والحجز بيتم على موقع السينما نفسه.\n\n"
        f"{version_line()}"
    )


def privacy_text() -> str:
    return (
        "<b>الخصوصية باختصار — واطمن</b>\n\n"
        "مش محتاج تديني اسمك ولا رقم تليفونك ولا إيميلك. البوت بيعرفك "
        "برقم تليجرام بس، وده اللي بيخليني أقدر أبعتلك التنبيه.\n\n"
        "<b>اللي بحفظه:</b>\n"
        "• المراقبات اللي إنت اختارتها (الفرع، اليوم، الفيلم، الحفلة).\n"
        "• إعداداتك البسيطة، وإنك دعمت المشروع ولا لأ.\n"
        "• لو بعت فيدباك، النص واسم المستخدم عشان أقدر أرد عليك.\n\n"
        "<b>اللي مش بحفظه أبدًا:</b>\n"
        "• أرقام كروت أو أي بيانات بنكية.\n"
        "• رقم تليفونك أو إيميلك.\n"
        "• محادثاتك مع أي حد تاني.\n\n"
        "صور إثبات التحويل بتوصل للأدمن بس، وبتتشال مع بياناتك لو استخدمت /delete_me. "
        "ومفيش حد بيشوف بياناتك غيرك — مش ببيعها ولا بشاركها مع أي طرف.\n\n"
        "ولو حبيت تبدأ من الأول، /delete_me بيمسح كل حاجة عنك في ثانية."
    )


# ------------------------------------------------------------------ add watch
def choose_branch() -> str:
    return f"{step_header(1, 5, 'الفرع')}\nاختار الفرع 🏢"


def choose_date(branch: str) -> str:
    return f"{step_header(2, 5, branch)}\nاختار اليوم 📅"


def choose_movie(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return f"{step_header(3, 5, path)}\nاختار الفيلم 🎞️\nمش لاقيه؟ اضغط <b>🔎 دوّر بالاسم</b>."


def search_choose_branch(query: str = "") -> str:
    head = f"{step_header(2, 5, 'بحث')}\n"
    if query:
        return f"{head}هندور على «<b>{esc(query)}</b>» 🔎\nاختار الفرع الأول:"
    return f"{head}بحث عن فيلم 🔎\nاختار الفرع الأول:"


def search_prompt(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return (
        f"{step_header(3, 5, path)}\n\n"
        "اكتب اسم الفيلم بالعربي أو الإنجليزي 🔎\n"
        "مش مشكلة لو فيه غلطة إملائية — جرّب جزء من الاسم بس."
    )


def search_too_short() -> str:
    return "اكتب حرفين على الأقل عشان أقدر أدور 🔎"


def search_results(query: str, count: int, total: int) -> str:
    return (
        f"نتائج البحث عن «<b>{esc(query)}</b>» — "
        f"<b>{count}</b> من {total} فيلم\n"
        "اختار الفيلم اللي عايزه:"
    )


def search_no_results(query: str, suggestions: list[str] | None = None) -> str:
    lines = [f"مفيش فيلم قريب من «<b>{esc(query)}</b>» في اليوم ده."]
    if suggestions:
        lines.append("قصدك واحدة من دول؟ اضغط عليها 👇")
    else:
        lines.append("جرّب جزء من الاسم، أو اكتبه بالإنجليزي، أو شوف كل الأفلام.")
    return "\n".join(lines)


def choose_showtime(movie: str, date: str, extra: str = "") -> str:
    path = f"{relative_date(date)} › {movie}"
    lines = [
        step_header(4, 5, path),
        "اختار الحفلة اللي عايز تراقبها 🎟️",
        "«متاح» = ينفع تحجز دلوقتي، «الحجز مكتمل» = كله محجوز.",
        "لو عايز فورمات معيّن (IMAX، 4DX، VIP…) اختار من الأزرار اللي فوق.",
    ]
    if extra:
        lines.insert(1, extra)
    return "\n".join(lines)


def format_label(value: object) -> str:
    return _format_label(value)


def format_filtered(value: str | None) -> str:
    if value is None:
        return "بنعرض كل الفورمات 🎭"
    return f"بنعرض {esc(value)} بس 🎭"


def format_not_found() -> str:
    return "الفورمات ده مش متاح للحفلات المعروضة. جرّب فورمات تاني."


def showtime_button(time: str, hall: str, status: str, seats: int | None) -> str:
    if status == AVAILABLE:
        mark = "متاح"
        if seats is not None:
            mark = f"متاح · {seats} كرسي"
    elif status == SOLD_OUT:
        mark = "الحجز مكتمل"
    else:
        mark = "لسه مفتحش"
    return f"{format_time(time)} · {esc(hall)} · {mark}"


def confirm_watch(
    branch: str, date: str, movie: str, time: str, hall: str, status: str = ""
) -> str:
    if status == SOLD_OUT:
        note = "الحفلة دي حجوزاتها مكتملة دلوقتي. هنراقبها ونبعتلك أول ما ترجع كراسي."
    elif status == NOT_AVAILABLE:
        note = "هنبعتلك أول ما الحجز يفتح."
    elif status == AVAILABLE:
        note = "الحفلة متاحة دلوقتي — تقدر تحجز على طول، وهنراقبها كمان لو الكراسي فضيت."
    else:
        note = "هنراقب الحفلة ونبعتلك أول ما يحصل جديد."
    return (
        f"{step_header(5, 5, 'تأكيد')}\n\n"
        "<b>تأكيد المراقبة</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"📅 {relative_date(date)} ({format_date(date)})\n"
        f"🎞️ {esc(movie)}\n"
        f"🎟️ {format_time(time)} — {esc(hall)}\n\n"
        f"{note}"
    )


def no_data() -> str:
    return (
        "لسه بنجيب البيانات من السينما. جرّب تاني بعد دقيقة 🙏\n"
        "مش بنعمل طلبات لموقع السينما وانت بتتصفح، عشان نحافظ على البوت شغال."
    )


def no_dates() -> str:
    return "مفيش أيام متاحة للفرع ده دلوقتي. جرّب فرع تاني أو استنى شوية."


def no_movies() -> str:
    return (
        "الحجز لسه مفتحش لليوم ده. جرّب يوم تاني أو استنى لما ينزل.\n"
        "لو الحفلات ظهرت، هتلاقيها هنا على طول."
    )


def no_showtimes() -> str:
    return "الحجز لسه مفتحش للفيلم ده في اليوم ده. جرّب فيلم أو يوم تاني."


IMAX_LINES_AR = {
    FULL_70MM: "🎥 متصور بالكامل بكاميرات IMAX 70mm — يستاهل IMAX",
    PARTIAL_70MM: "🎥 أجزاء منه متصورة بكاميرات IMAX 70mm — يستاهل IMAX",
    CERTIFIED_DIGITAL: "🎥 متصور بكاميرات IMAX المعتمدة — يستاهل IMAX",
    PARTIAL_DIGITAL: "🎥 أجزاء منه متصورة بكاميرات IMAX المعتمدة",
    UNKNOWN: "🎥 مش معروف — مش في قائمة أفلام IMAX",
}


def imax_line(status: str | None) -> str:
    """Arabic line for the movie card, or an empty string when not looked up."""

    if not status:
        return ""
    return IMAX_LINES_AR.get(status, "🎥 مش في قائمة أفلام IMAX — غالبًا تكبير بس")


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
        lines.append("مفيش قصة متاحة للفيلم ده دلوقتي.")
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
        note = "الحفلات متاحة دلوقتي، وهنراقب كل حفلة عشان لو كراسي ترجع."
    elif states and all(state == "SOLD_OUT" for state in states):
        note = "كل الحفلات محجوزة دلوقتي. هنراقبهم ونبعتلك أول ما ترجع كراسي."
    else:
        note = "هنراقب كل حفلات الفيلم ده في اليوم، ونبعتلك أول ما حجز يفتح أو ترجع كراسي."
    ticket = f"🎟️ كل الحفلات ({count} حفلة)"
    if hall:
        ticket = f"🎭 {esc(hall)} — كل الحفلات ({count} حفلة)"
    return (
        f"{step_header(5, 5, 'تأكيد')}\n\n"
        "<b>تأكيد مراقبة اليوم كامل</b>\n\n"
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
        "تمام ✅\n"
        f"بنراقب <b>{esc(movie)}</b> — {relative_date(date)} — "
        f"<b>{count}</b> حفلة{format_text} — {esc(branch)}.\n"
        "أول ما أي حجز يفتح أو كراسي ترجع هتوصلك رسالة.\n\n"
        "من <b>⚙️ إعدادات التنبيه</b> تقدر تختار: كل حاجة، كراسي رجعت، "
        "أو فتح الحجز بس."
    )


def watch_created(branch: str, date: str, movie: str, time: str, hall: str) -> str:
    return (
        "تمام ✅\n"
        f"بنراقب <b>{esc(movie)}</b> — {relative_date(date)} — "
        f"{format_time(time)} — {esc(hall)} — {esc(branch)}.\n"
        "أول ما يحصل جديد هتوصلك رسالة.\n\n"
        "من <b>⚙️ إعدادات التنبيه</b> تقدر تختار: كل حاجة، كراسي رجعت، "
        "أو فتح الحجز بس."
    )


def confirm_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return (
        f"{step_header(5, 5, 'تأكيد')}\n\n"
        "<b>تأكيد مراقبة كل الأيام</b>\n\n"
        f"🏢 {esc(branch)}\n"
        f"🎞️ {esc(movie)}\n"
        f"📅 كل الأيام المتاحة دلوقتي ({count} يوم){format_text}\n\n"
        "هنراقب كل يوم يفتح فيه الفيلم في الفرع ده، "
        "وكمان أي يوم جديد ينزل للحجز.\n"
        "أول ما حجز يفتح أو كراسي ترجع هتوصلك رسالة."
    )


def watch_created_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f" — {esc(hall)}" if hall else ""
    return (
        "تمام ✅\n"
        f"بنراقب <b>{esc(movie)}</b> في <b>{esc(branch)}</b>{format_text} — "
        f"كل الأيام المتاحة ({count} يوم دلوقتي).\n"
        "أي يوم جديد ينزل أو كراسي ترجع، هتوصلك رسالة.\n\n"
        "من <b>⚙️ إعدادات التنبيه</b> تقدر تختار نوع التنبيه."
    )


def all_dates_unavailable() -> str:
    return "مفيش أيام متاحة للفرع ده دلوقتي. جرّب يوم معيّن أو استنى لما الحجز يفتح."


def watch_limit_reached(
    limit: int,
    supporter_limit: int = 10,
    min_amount: int = 50,
    is_supporter: bool = False,
) -> str:
    if is_supporter:
        return (
            f"وصلت للحد الأقصى ({limit} مراقبة).\n\n"
            "امسح مراقبة قديمة من <b>مراقباتي</b> عشان تضيف واحدة جديدة."
        )
    return (
        f"وصلت للحد المجاني ({limit} مراقبة).\n\n"
        f"لو عايز توصل لـ <b>{supporter_limit} مراقبات</b>، تقدر تدعم المشروع "
        f"<b>مرة واحدة</b> بحد أدنى {min_amount} جنيه من <b>ادعم المشروع</b> 💛\n"
        "أو امسح مراقبة قديمة من <b>مراقباتي</b>."
    )


def watches_trimmed(removed: int, limit: int) -> str:
    return (
        f"قلّلنا مراقباتك بـ {removed} عشان الحد الجديد بقى <b>{limit}</b> "
        "مراقبات.\n"
        "المراقبات الأقرب في المواعيد فضلت معاك، وتقدر تضيف غيرها من "
        "<b>ادعم المشروع</b> أو تمسح وتضيف من جديد."
    )


def duplicate_watch() -> str:
    return "المراقبة دي موجودة عندك بالفعل 👌"


# ------------------------------------------------------------------- my watches
def no_watches() -> str:
    return "مفيش مراقبات لسه. اضغط <b>ضيف مراقبة جديدة</b> وابدأ 🎬"


def watches_retention_note(days: int) -> str:
    return f"<i>المراقبات اللي حفلاتها بدأت بتتشال تلقائيًا بعد {days} أيام.</i>"


def watches_group(date: str) -> str:
    if date == "*":
        return "📅 <b>كل الأيام المتاحة</b>"
    return f"📅 <b>{relative_date(date)}</b>"


def confirm_delete_all(count: int) -> str:
    label = "مراقبة" if count == 1 else "مراقبات"
    return (
        "🗑️ <b>متأكد؟</b>\n\n"
        f"هنمسح <b>{count}</b> {label} نشطة. مش هنقدر نرجّعهم، "
        "ولو عايز تراقب تاني هتبدأ من الأول."
    )


def confirm_remove_watch(movie: str, when: str) -> str:
    return (
        "❌ <b>متأكد إنك عايز تشيل المراقبة دي؟</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"📅 {esc(when)}\n\n"
        "مش هتوصلك تنبيهات عنها تاني."
    )


def watches_page_title(count: int) -> str:
    label = "مراقبة" if count == 1 else "مراقبات"
    return f"<b>🎟️ مراقباتي</b> — {count} {label} نشطة"


def watch_mode_label(mode: str | None) -> str:
    return {
        "seats": "كراسي رجعت 🪑",
        "opening": "فتح الحجز بس 🎟️",
    }.get(mode or "all", "كل حاجة 🔔")


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
    state = STATUS_LABELS_AR.get(status, status)
    if seats is not None:
        state = f"{state} · {seats} كرسي"
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 كل الأيام المتاحة · كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text} · {esc(state)}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)} · {esc(state)}"
    lines = [
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {esc(branch)} — {relative_date(date)}",
        ticket,
        f"🔔 {watch_mode_label(mode)}",
    ]
    if snoozed_until:
        lines.append("⏰ التنبيهات متأجلة مؤقتاً")
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
    snooze = f"⏰ متأجل لحد {esc(snoozed_until_text)}" if snoozed_until_text else "⏰ مفيش تأجيل"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 كل الأيام المتاحة — كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)}"
    return (
        "<b>إعدادات المراقبة ⚙️</b>\n\n"
        f"🎬 <b>{esc(movie)}</b>\n"
        f"🏢 {esc(branch)} — {relative_date(date)}\n"
        f"{ticket}\n\n"
        f"🔔 التنبيهات: <b>{watch_mode_label(mode)}</b>\n"
        f"{snooze}\n\n"
        "اختار نوع التنبيه اللي يناسبك:"
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
    state = STATUS_LABELS_AR.get(status, status)
    if seats is not None:
        state = f"{state} · {seats} كرسي"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"🎟️ كل الأيام المتاحة — كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text}"
    else:
        ticket = f"🎟️ {format_time(time)} · {esc(hall)}"
    lines = [
        "⏰ <b>فكّرتك بالمراقبة دي</b>",
        "",
        f"🎬 <b>{esc(movie)}</b>",
        f"🏢 {esc(branch)} — {relative_date(date)}",
        ticket,
    ]
    if scope != "movie_all_dates":
        lines.append(f"الحالة دلوقتي: {esc(state)}")
    lines += ["", "افتح صفحة الحجز وشوف المتاح."]
    return "\n".join(lines)


def watch_snoozed(until_text: str) -> str:
    return f"تمام ⏰ هسكت التنبيهات لحد {esc(until_text)}، وبعدها هفكّرك."


def watch_unsnoozed() -> str:
    return "رجّعنا التنبيهات ✅"


def watch_removed_from_alert() -> str:
    return "✅ شيلنا المراقبة دي. مش هتوصلك تنبيهات عنها تاني."


def watch_mode_set(mode: str | None) -> str:
    return f"تم ✅ التنبيهات بقت: {watch_mode_label(mode)}"


def watch_removed() -> str:
    return "شيلنا المراقبة ✅"


def all_watches_removed() -> str:
    return "مسحنا كل المراقبات ✅"


def watch_expired_summary(items: list[str], more: int = 0) -> str:
    total = len(items) + more
    label = "مراقبة" if total == 1 else "مراقبات"
    lines = [f"🧹 <b>شيلنا {total} {label} خلصت</b>", ""]
    lines.extend(f"• {item}" for item in items)
    if more:
        lines.append(f"• وغيرها {more} مراقبة")
    lines += [
        "",
        "المراقبات دي حفلاتها بدأت، فمش هينفع نبعتك عنها تنبيهات تاني.",
        "لو حابب تراقب حفلة جديدة، اضغط «ضيف مراقبة».",
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
    seat_text = f" · {seats} كرسي متاح" if seats else ""
    return (
        "🎟️ <b>فيه حجز اتفتح!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b>\n"
        f"{esc(hall)} — {format_time(time)} — {esc(branch)} — {relative_date(date)}"
        f"{seat_text}\n\n"
        "الحق احجز قبل ما يتكمل!"
    )


def alert_seats_available(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = f"{seats} كرسي" if seats else "كرسي"
    return (
        "🪑 <b>رجعت كراسي!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b>\n"
        f"{esc(hall)} — {format_time(time)} — {esc(branch)} — {relative_date(date)}\n"
        f"بقى فيه {seat_text} متاح دلوقتي.\n\n"
        "الحق احجز 🏃"
    )


def alert_movie_booking_opened(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    seats: int | None = None,
) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    seat_text = f" · {seats} كرسي متاح" if seats else ""
    return (
        "🎟️ <b>الحجز اتفتح لحفلات الفيلم!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"الحفلات: {joined}{more}{seat_text}\n\n"
        "الحق احجز قبل ما يتكمل!"
    )


def alert_movie_seats_available(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    seats: int | None = None,
) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    seat_text = f" · بقى فيه {seats} كرسي" if seats else ""
    return (
        "🪑 <b>رجعت كراسي في حفلات الفيلم!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"الحفلات: {joined}{more}{seat_text}\n\n"
        "الحق احجز 🏃"
    )


def alert_new_date(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    hall: str | None = None,
) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🎬 <b>الفيلم نزل في يوم جديد!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}{hall_text}\n"
        f"المواعيد: {joined}{more}\n\n"
        "افتح صفحة الحجز وشوف المتاح."
    )


def alert_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    return (
        "🎬 <b>حفلات جديدة ظهرت!</b>\n\n"
        f"فيلم <b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"المواعيد: {joined}{more}\n\n"
        "افتح صفحة الحجز وشوف المتاح."
    )


def duration_label(minutes: int | None) -> str:
    if not minutes:
        return ""
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{_hours_label(hours)} و{mins} دقيقة"
    if hours:
        return _hours_label(hours)
    return f"{mins} دقيقة"


def _hours_label(hours: int) -> str:
    if hours == 1:
        return "ساعة"
    if hours == 2:
        return "ساعتين"
    if 3 <= hours <= 10:
        return f"{hours} ساعات"
    return f"{hours} ساعة"


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
    return "سينما رادار — تنبيه بس، الحجز على موقع السينما."


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
    types = "، ".join(event_type_label(t) for t in event_types) or "كل الأنواع"
    branches = "كل الفروع" if branch_count == 0 else f"{branch_count} فرع"
    hall = hall_type or "كل القاعات"
    watch_quiet = "بتشمل المراقبات ✅" if quiet_watches else "المراقبات شغالة دايماً 🔔"
    return (
        "<b>⚙️ الإعدادات</b>\n\n"
        "<b>الإشعارات</b>\n"
        f"• رجوع الكراسي: {'مفعل ✅' if notify_cancellations else 'مقفول ⛔'}\n"
        f"• ساعات الهدوء: {format_time(f'{quiet_start}:00')} ← {format_time(f'{quiet_end}:00')} ({watch_quiet})\n"
        f"• أفلام وحجوزات جديدة: {'مفعلة ✅' if discovery_enabled else 'مقفولة ⛔'}\n\n"
        "<b>فلاتر التنبيهات الجديدة</b>\n"
        f"• الفروع: {esc(branches)}\n"
        f"• الأنواع: {esc(types)}\n"
        f"• القاعة: {esc(hall)}\n"
        f"• اللغة: {'العربية' if (language or 'ar') == 'ar' else 'English'}"
        f"\n\n{version_line()}"
    )


def quiet_hours_text(start: int, end: int, quiet_watches: bool = True) -> str:
    watches = (
        "وتنبيهات المراقبات بتحترم الوقت ده كمان ✅"
        if quiet_watches
        else "لكن تنبيهات المراقبات شغالة حتى في الوقت ده 🔔"
    )
    return (
        "<b>🕰️ ساعات الهدوء</b>\n\n"
        f"من <b>{format_time(f'{start}:00')}</b> لـ <b>{format_time(f'{end}:00')}</b>.\n"
        "مش هنبعت تنبيهات في الوقت ده، إلا لو الحفلة النهاردة أو بكرة.\n"
        f"{watches}\n\n"
        "اختار وقت جاهز، أو اضغط <b>وقت مخصص</b> وابعت مثلًا <code>23-8</code>."
    )


def quiet_custom_prompt() -> str:
    return (
        "<b>🕰️ وقت مخصص</b>\n\n"
        "ابعت البداية والنهاية بالساعات فقط، مثلًا: <code>23-8</code> "
        "(من 11 م لـ 8 ص).\n"
        "الساعة بنظام 24 ساعة (0 = 12 بالليل)."
    )


def quiet_custom_invalid() -> str:
    return "مش فاهم الوقت. ابعت مثلًا <code>23-8</code> (من 11 م لـ 8 ص)."


def choose_branches_text() -> str:
    return "اختار الفروع اللي عايز تنبيهات منها (تقدر تختار أكتر من فرع):"


def choose_event_types_text() -> str:
    return "اختار أنواع التنبيهات:"


def choose_hall_text() -> str:
    return "اختار نوع القاعة:"


def event_type_label(kind: str) -> str:
    return {
        "NEW_MOVIE": "فيلم جديد",
        "NEW_DATE_OPENED": "حجز يوم جديد",
        "NEW_SHOWTIMES": "حفلات جديدة",
        "UPCOMING_MOVIE": "قولّي لما ينزل",
    }.get(kind, kind)


# -------------------------------------------------------------------- support
def support_text(limit: int = 10, min_amount: int = 50) -> str:
    return (
        "سينما رادار مجاني للكل، وكل مستخدم عنده <b>مراقبتين</b> مجانًا 💛\n\n"
        "لو عايز تتابع أكتر، تقدر تدعم المشروع <b>مرة واحدة</b> "
        f"بحد أدنى <b>{min_amount} جنيه</b> — وحدك يبقى <b>{limit} مراقبات</b> "
        "على طول، مش اشتراك شهري.\n\n"
        "التحويل فودافون كاش أو إنستاباي، وبعدها تبعت صورة الإثبات. "
        "الأدمن بيراجع الإثبات ويوافق.\n\n"
        "اختار طريقة الدعم:"
    )


def support_manual_text(method: str, phone: str, min_amount: int = 50) -> str:
    name = "فودافون كاش" if method == "vodafone_cash" else "إنستاباي"
    return (
        f"<b>دعم عن طريق {name}</b>\n\n"
        f"حوّل على الرقم ده:\n<code>{esc(phone)}</code>\n\n"
        f"الحد الأدنى <b>{min_amount} جنيه</b> — مرة واحدة مش اشتراك.\n"
        "بعد التحويل اضغط <b>حوّلت ✅</b> وابعت صورة التحويل أو رقم العملية. "
        "الأدمن هيراجع الإثبات، ولو اتقبل حدك هيبقى 10 مراقبات.\n\n"
        "⚠️ التحويل مش بيتفعل تلقائيًا."
    )


def support_ask_amount(min_amount: int = 50) -> str:
    return (
        "المبلغ اللي حوّلته كام؟ 💰\n"
        f"الحد الأدنى {min_amount} جنيه.\n"
        "اختار المبلغ أو اكتبه بالأرقام (مثال: 75)."
    )


def support_amount_invalid() -> str:
    return "اكتب مبلغ صحيح بالأرقام، مثال: 50"


def support_ask_proof(method: str) -> str:
    name = "فودافون كاش" if method == "vodafone_cash" else "إنستاباي"
    return f"ابعت صورة إثبات تحويل {name} أو اكتب رقم العملية 📸\nلو مش عايز تكمل اضغط إلغاء."


def support_proof_received() -> str:
    return "تم إرسال الإثبات للأدمن ✅\nمستني موافقة الأدمن — هتوصلك رسالة أول ما يتراجع."


def support_approved(amount: float | None = None, limit: int = 10) -> str:
    amount_text = f" ({amount:g} جنيه)" if amount else ""
    return f"تم تأكيد دعمك{amount_text} ✅\nشكراً من قلبنا 💛 حد المراقبات بقى <b>{limit}</b>."


def support_rejected() -> str:
    return (
        "للأسف إثبات التحويل مش واضح أو التحويل مش مكتمل ❌\n"
        "تقدر تبعته تاني من شاشة <b>ادعم المشروع</b>."
    )


def support_already_handled() -> str:
    return "الطلب ده اتراجع قبل كده ✅"


def support_admin_new(
    donation_id: int,
    user_id: int,
    method: str,
    amount: float | None,
    note: str,
    min_amount: int = 50,
    below_minimum: bool = False,
) -> str:
    name = "فودافون كاش" if method == "vodafone_cash" else "إنستاباي"
    amount_text = f"{amount:g} جنيه" if amount else "غير محدد"
    warning = f"\n⚠️ <b>أقل من الحد الأدنى ({min_amount} جنيه)</b>" if below_minimum else ""
    return (
        f"<b>إثبات دعم جديد #{donation_id}</b>{warning}\n"
        f"المستخدم: <code>{user_id}</code>\n"
        f"الطريقة: {name}\n"
        f"المبلغ: {esc(amount_text)}\n"
        f"ملاحظة: {esc(note or '—')}\n\n"
        "راجع الإثبات وبعدين قرر:"
    )


def support_admin_decided(donation_id: int, approved: bool) -> str:
    state = "تمت الموافقة ✅" if approved else "تم الرفض ❌"
    return f"الطلب #{donation_id}: {state}"


def support_not_configured() -> str:
    return "الدعم اليدوي مش متظبط دلوقتي. كلّم الأدمن."


# ------------------------------------------------------------------- feedback
def feedback_categories_text() -> str:
    return (
        "✍️ <b>ابعتلنا رأيك</b>\n\n"
        "اختار نوع الرسالة الأول، وبعدها اكتب تفاصيلك في رسالة واحدة.\n"
        "كل رسالة بتوصل للأدمن، وبتساعدنا نطوّر البوت."
    )


def feedback_category_label(category: str) -> str:
    return {
        "idea": "اقتراح",
        "bug": "مشكلة",
        "movie": "فيلم ناقص",
        "other": "حاجة تانية",
    }.get(category, "حاجة تانية")


def feedback_text(category: str | None = None) -> str:
    label = feedback_category_label(category) if category else "رأي"
    return (
        f"✍️ <b>{esc(label)}</b>\n\n"
        "اكتب رأيك أو اقتراحك في رسالة واحدة.\n"
        "كل رسالة بتوصل للأدمن، وبتساعدنا نطوّر البوت."
    )


def feedback_thanks() -> str:
    return "شكراً! وصلنا رأيك ✅"


def feedback_too_soon() -> str:
    return "وصلنا رأيك قريب. جرّب تاني بعد ساعة 🙏"


def feedback_admin(user_id: int, username: str | None, text: str) -> str:
    who = f"@{esc(username)}" if username else f"<code>{user_id}</code>"
    return f"<b>فيدباك جديد</b> من {who}:\n\n{esc(text)}"


# ------------------------------------------------------------------ discovery
def discovery_new_movie(movie: str, branch: str, date: str | None, hall: str | None) -> str:
    date_text = f" — من يوم {relative_date(date)}" if date else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🎬 <b>فيلم جديد اتفتح له حجز!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)}{date_text}{hall_text}"
    )


def discovery_new_date(movie: str, branch: str, date: str) -> str:
    return (
        "📅 <b>يوم جديد اتفتح حجزه!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — من يوم {relative_date(date)}"
    )


def discovery_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    return (
        "🎟️ <b>حفلات جديدة ظهرت!</b>\n\n"
        f"<b>{esc(movie)}</b> — {esc(branch)} — {relative_date(date)}\n"
        f"المواعيد: {joined}{more}"
    )


def discovery_upcoming_released(
    movie: str, branch: str, date: str | None, hall: str | None = None
) -> str:
    date_text = f" — من {relative_date(date)}" if date else ""
    hall_text = f" — {esc(hall)}" if hall else ""
    return (
        "🍿 <b>الفيلم اللي كنت مستنيه نزل!</b>\n\n"
        f"<b>{esc(movie)}</b> اتفتح حجزه في {esc(branch)}{date_text}{hall_text}\n\n"
        "الحق احجز قبل ما يتكمل."
    )


def discovery_digest(branch: str, count: int, lines: list[str]) -> str:
    body = "\n".join(f"• {line}" for line in lines[:6])
    more = f"\nو{count - 6} حاجات كمان" if count > 6 else ""
    return (
        f"🎬 <b>{count} حاجات جديدة في فرع {esc(branch)}</b>\n\n"
        f"{body}{more}\n\n"
        "افتح الحجز أو راقب الفيلم بضغطة."
    )


def discovery_channel(event_text: str) -> str:
    return f"{event_text}\n\n#سينما_رادار"


# ---------------------------------------------------------------------- admin
def admin_text(data: dict[str, object]) -> str:
    return (
        "<b>لوحة الأدمن 🛠️</b>\n\n"
        f"مستخدمين نشطين: <b>{data.get('active_users', 0)}</b>\n"
        f"مراقبات نشطة: <b>{data.get('active_watches', 0)}</b>\n"
        f"داعمين: <b>{data.get('supporters', 0)}</b>\n"
        f"طلبات/دقيقة: <b>{data.get('requests_per_minute', 0):.1f}</b>\n"
        f"نسبة الكاش: <b>{data.get('cache_hit_ratio', 0):.0%}</b>\n"
        f"أهداف نشطة: <b>{data.get('active_targets', 0)}</b>\n"
        f"معامل التباطؤ: <b>{data.get('slowdown_factor', 1):.2f}</b>\n"
        f"قاطع الدائرة: <b>{esc(data.get('circuit_state', 'closed'))}</b>\n"
        f"آخر طلب: <b>{esc(data.get('last_poll_status', '—'))}</b>\n"
        f"آخر اكتشاف: <b>{esc(data.get('discovery_last_run', '—'))}</b>\n"
        f"أحداث النهاردة: <b>{data.get('events_today', 0)}</b>\n"
        f"بثوث: <b>{data.get('broadcasts_sent', 0)}</b>\n"
        f"طول الطابور: <b>{data.get('queue_length', 0)}</b>\n"
        f"الإصدار: <b>v{esc(__version__)}</b>"
    )


def admin_only() -> str:
    return "الأمر ده للأدمن بس."


def grant_done(telegram_id: int, limit: int) -> str:
    return f"تم تفعيل الدعم للمستخدم <code>{telegram_id}</code> — الحد {limit}."


def revoke_done(telegram_id: int, limit: int) -> str:
    return f"تم إلغاء الدعم للمستخدم <code>{telegram_id}</code> — الحد {limit}."


# ------------------------------------------------------------ admin / system
def admin_started() -> str:
    return f"✅ سينما رادار اشتغل (v{esc(__version__)})."


def admin_limits_applied(users: int, watches: int) -> str:
    if not users:
        return "✅ حدود المراقبات اتظبطت (2 مجاني / 10 للداعمين)."
    return (
        "✅ حدود المراقبات اتظبطت (2 مجاني / 10 للداعمين).\n"
        f"اتأثر {users} مستخدم، واتشال {watches} مراقبة زيادة."
    )


def admin_unexpected_error(name: str) -> str:
    return f"⚠️ خطأ غير متوقع: {esc(name)}"


REASON_LABELS_AR = {
    "http_403": "VOX رافض الطلب (403) — حماية أو بلوك",
    "http_429": "VOX محدّد الطلبات (429) — rate limit",
    "http_5xx": "سيرفر VOX بيرجع خطأ (5xx)",
    "timeout": "انتهت مهلة الاتصال بـ VOX",
    "network": "مشكلة شبكة / TLS / DNS",
    "parse": "صفحة VOX اتغيرت والبوت مش فاهمها",
    "empty": "VOX رجّع صفحة فاضية",
    "circuit": "قاطع الدائرة مفتوح بعد فشل متكرر",
    "unknown": "خطأ غير معروف",
}


def reason_label(reason: str) -> str:
    return REASON_LABELS_AR.get(reason, REASON_LABELS_AR["unknown"])


def admin_upstream_down(
    reason: str,
    place: str,
    last_success: str,
    retry_seconds: int,
    affected: int = 0,
    opened: bool = False,
) -> str:
    breaker = (
        f"\n⛔ قاطع الدائرة اتفتح — هنوقف {retry_seconds} ثانية وبعدها نجرب طلب واحد."
        if opened
        else f"\n🔁 إعادة المحاولة خلال {retry_seconds} ثانية."
    )
    affected_line = f"\nمراقبات متأثرة: <b>{affected}</b>" if affected else ""
    return (
        "⚠️ <b>VOX واقعة</b>\n\n"
        f"السبب: {esc(reason_label(reason))}\n"
        f"المكان: {esc(place or '—')}\n"
        f"آخر نجاح: {esc(last_success or '—')}"
        f"{affected_line}"
        f"{breaker}\n\n"
        "مش هبعت أي تنبيهات مبنية على بيانات قديمة لحد ما ترجع."
    )


def admin_upstream_recovered(minutes: int) -> str:
    if minutes <= 0:
        return "✅ <b>VOX رجعت</b> — البيانات بتتحدث تاني."
    return f"✅ <b>VOX رجعت</b> بعد {minutes} دقيقة — البيانات بتتحدث تاني."


def stale_notice(minutes: int, degraded: bool) -> str:
    if minutes <= 0:
        return ""
    if degraded:
        return (
            f"\n\n⚠️ <i>VOX مش متاح دلوقتي. آخر تحديث من {minutes} دقيقة — "
            "البيانات ممكن تكون قديمة.</i>"
        )
    if minutes >= 10:
        return f"\n\n<i>آخر تحديث: من {minutes} دقيقة.</i>"
    return ""


def admin_status(data: dict[str, object]) -> str:
    return (
        "<b>حالة الاتصال بـ VOX</b>\n\n"
        f"الحالة: <b>{esc(data.get('state', '—'))}</b>\n"
        f"آخر نجاح: {esc(data.get('last_success', '—'))}\n"
        f"آخر خطأ: {esc(data.get('last_error', '—'))}\n"
        f"قاطع الدائرة: <b>{esc(data.get('breaker', 'closed'))}</b>\n"
        f"أهداف نشطة: <b>{data.get('targets', 0)}</b>\n"
        f"مراقبات متأثرة: <b>{data.get('affected', 0)}</b>"
    )


def admin_discovery_branches_failed(error: object) -> str:
    return f"⚠️ الاكتشاف مش قادر يجيب الفروع: {esc(error)}"


def admin_discovery_branch_failed(branch: object, error: object) -> str:
    return f"⚠️ الاكتشاف فشل في فرع {esc(branch)}: {esc(error)}"


# ------------------------------------------------------------------ discovery
def discovery_line_upcoming(name: object) -> str:
    return f"نزل أخيراً: {esc(name)}"


def discovery_line_new_movie(name: object) -> str:
    return f"فيلم جديد: {esc(name)}"


def discovery_line_new_date(name: object, date_text: str) -> str:
    return f"حجز يوم جديد: {esc(name)} — {format_date(date_text)}"


def discovery_line_new_showtimes(name: object, times: tuple[str, ...]) -> str:
    formatted = "، ".join(format_time(value) for value in times)
    return f"حفلات جديدة: {esc(name)} — {formatted}"


# ---------------------------------------------------------------------- errors
def error_expired() -> str:
    return "الشاشة دي قديمة أو الحفلة اتغيرت. اضغط /start وابدأ من الأول."


def error_generic() -> str:
    return "حصلت مشكلة صغيرة. جرّب تاني بعد شوية 🙏"


def rate_limited() -> str:
    return "استنى شوية بين كل خطوة والتانية 🙏"


def cancelled() -> str:
    return "تم الإلغاء. لو حابب ترجع للقائمة اضغط /start."


def delete_me_confirm() -> str:
    return (
        "<b>متأكد؟</b>\n\n"
        "هنمسح كل بياناتك: المراقبات، التنبيهات، الفيدباك، وإثباتات الدعم. "
        "مش هنقدر نرجّعها."
    )


def delete_me_done() -> str:
    return "تم مسح كل بياناتك ✅\nلو حابب ترجع استخدم /start في أي وقت."


def quiet_hours_set(start: int, end: int) -> str:
    return f"تم ضبط ساعات الهدوء من {format_time(f'{start}:00')} لـ {format_time(f'{end}:00')} ✅"


def setting_saved() -> str:
    return "تم الحفظ ✅"


def admin_usage(command: str) -> str:
    return f"استخدم: /{command} <telegram_id>"


def imax_override_usage() -> str:
    return (
        "استخدم: /imax <movie_id> <status>\n"
        "الحالات: FULL_70MM, PARTIAL_70MM, CERTIFIED_DIGITAL, PARTIAL_DIGITAL, UNKNOWN"
    )


def imax_override_done(movie_id: str, status: str, updated: int) -> str:
    return (
        f"تم ضبط حالة IMAX للفيلم <code>{esc(movie_id)}</code> على <b>{esc(status)}</b> "
        f"— اتحدّثت {updated} مراقبة."
    )


def user_not_found() -> str:
    return "المستخدم مش موجود."
