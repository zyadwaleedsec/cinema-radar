"""Egyptian Arabic copy for every user-facing surface.

Keeping copy in one file makes it easy to edit without touching logic.
Dynamic values are HTML-escaped because messages are sent with parse_mode=HTML.
The English catalog in :mod:`i18n.en` mirrors every public name here; a test
enforces that the two never drift apart.
"""

from __future__ import annotations

from datetime import date as date_cls

from config import settings as _app_settings
from i18n.base import esc, get_provider
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
from ui.theme import DIVIDER, progress
from version import __version__

CODE = "ar"
NAME = "العربية"
RTL = True


def _plural(value: int, one: str, two: str, few: str, many: str) -> str:
    """Pick the Egyptian-Arabic noun form for a count."""

    remainder = abs(int(value)) % 100
    if remainder == 1:
        return one
    if remainder == 2:
        return two
    if 3 <= remainder <= 10:
        return few
    return many


def _count(value: int, one: str, two: str, few: str, many: str) -> str:
    """Return ``5 فروع``, ``مراقبتين`` or ``12 مراقبة``."""

    value = int(value)
    noun = _plural(value, one, two, few, many)
    if abs(value) % 100 == 2:
        return noun
    return f"{value} {noun}"


def _watches(value: int) -> str:
    return _count(value, "مراقبة", "مراقبتين", "مراقبات", "مراقبة")


def _active_watches(value: int) -> str:
    return _count(value, "مراقبة نشطة", "مراقبتين نشطتين", "مراقبات نشطة", "مراقبة نشطة")


def _branches(value: int) -> str:
    return _count(value, "فرع", "فرعين", "فروع", "فرع")


def _seats(value: int) -> str:
    return _count(value, "كرسي", "كرسيين", "كراسي", "كرسي")


def _needed_seats(value: int) -> str:
    value = max(1, int(value))
    return "كرسي واحد" if value == 1 else _seats(value)


def _seats_state(value: int) -> str:
    return _count(
        value,
        "كرسي متاح",
        "كرسيين متاحين",
        "كراسي متاحة",
        "كرسي متاح",
    )


def _days(value: int) -> str:
    return _count(value, "يوم", "يومين", "أيام", "يوم")


def _movies(value: int) -> str:
    return _count(value, "فيلم", "فيلمين", "أفلام", "فيلم")


def _updates(value: int) -> str:
    return _count(
        value,
        "تحديث جديد",
        "تحديثين جديدين",
        "تحديثات جديدة",
        "تحديث جديد",
    )


def cinema_name(provider: str | None = None) -> str:
    code = (provider or get_provider() or _app_settings.provider).lower()
    return "رينيسانس" if code == "renaissance" else "فوكس"


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
BTN_SEARCH_AGAIN = "🔄 بحث تاني"
BTN_ALL_MOVIES = "🎞️ كل الأفلام"
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
BTN_CONFIRM_DELETE_ALL = "أيوه، امسح الكل"
BTN_OPEN_BOOKING = "🎟️ افتح الحجز"
BTN_WATCH_MOVIE = "🔔 راقب فيلم من التحديثات"
BTN_STOP_ALERTS = "🔕 وقّف التنبيهات دي"
BTN_REMOVE_WATCH = "❌ شيل المراقبة"
BTN_CONFIRM_REMOVE_WATCH = "أيوه، شيلها"
BTN_SNOOZE = "⏰ فكّرني بعد ساعة"
BTN_UNSNOOZE = "🔔 رجّع التنبيه"
BTN_MODE_ALL = "🔔 كل حاجة"
BTN_MODE_SEATS = "🪑 كراسي رجعت"
BTN_MODE_OPENING = "🎟️ فتح الحجز بس"
BTN_WATCH_SETTINGS = "⚙️ إعدادات المراقبة"
BTN_WATCH_ALL_SHOWTIMES = "🔔 راقب كل حفلات اليوم"
BTN_WATCH_ALL_DATES = "📅 راقب كل الأيام المتاحة"
BTN_I_PAID = "حوّلت ✅"
BTN_YES_DELETE = "أيوه، امسح بياناتي"
BTN_NO = "لا، رجعني"
BTN_DONE = "تم ✅"
BTN_ALL_SHOWTIMES = "كل الحفلات"
BTN_ALL_HALLS = "كل القاعات"
BTN_ALL_FORMATS = "🎭 كل الفورمات"
BTN_MOVIE_INFO = "ℹ️ معلومات الفيلم"
BTN_TRAILER = "▶️ شوف التريلر"
BTN_BACK_TO_SHOWTIMES = "⬅️ رجوع للحفلات"
BTN_VODAFONE_CASH = "فودافون كاش"
BTN_INSTAPAY = "إنستاباي"
BTN_CANCELLATIONS = "🪑 رجوع الكراسي"
BTN_QUIET_HOURS = "🕰️ ساعات الهدوء"
BTN_QUIET_CUSTOM = "🕰️ وقت مخصص"
BTN_DISCOVERY_ALERTS = "🎬 تنبيهات الأفلام الجديدة"
BTN_BRANCHES_FILTER = "🎯 فروع التنبيهات"
BTN_TYPES_FILTER = "📌 أنواع التنبيهات"
BTN_HALL_FILTER = "🎭 نوع القاعة"
BTN_QUIET_WATCHES = "تنبيهات المراقبات بتحترم الهدوء"
BTN_DELETE_MY_DATA = "🗑️ حذف بياناتي"
BTN_COPY_PHONE = "📋 نسخ الرقم"
BTN_MANAGE_WATCH = "⚙️ إدارة المراقبة"
BTN_SEATS_CUSTOM = "✍️ عدد معين"
BTN_LANGUAGE = "🌐 اللغة"
BTN_ARABIC = "🇪🇬 العربية"
BTN_ENGLISH = "🇺🇸 English"
BTN_ALL_CINEMAS = "🌍 كل السينمات"
BTN_CONSENT_ACCEPT = "✅ موافق، ابدأ"
BTN_CONSENT_DECLINE = "❌ مش موافق"
BTN_CONSENT_REVIEW = "🔐 راجع الموافقة تاني"


# ------------------------------------------------------------ keyboard labels
def all_dates_label() -> str:
    return "📅 كل الأيام المتاحة"


def donation_amount_label(amount: int) -> str:
    return f"{amount} جنيه"


def donation_custom_label() -> str:
    return "مبلغ تاني"


def donation_approve_label() -> str:
    return "✅ موافقة"


def donation_reject_label() -> str:
    return "❌ رفض"


def feedback_category_button(kind: str) -> str:
    return {
        "idea": "💡 اقتراح",
        "bug": "🐞 مشكلة",
        "movie": "🎬 فيلم ناقص",
        "other": "💬 حاجة تانية",
    }.get(kind, kind)


# Public commands are registered in the default scope.  Admin commands are
# registered only in the admin's private chat scope, so they never appear in
# the public menu.
PUBLIC_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "الرئيسية"),
    ("add", "ضيف مراقبة"),
    ("search", "دوّر على فيلم"),
    ("watches", "مراقباتي"),
    ("settings", "الإعدادات"),
    ("help", "المساعدة"),
    ("privacy", "الخصوصية والبيانات"),
    ("delete_me", "امسح بياناتي"),
    ("cancel", "إلغاء الخطوة الحالية"),
)

ADMIN_COMMANDS: tuple[tuple[str, str], ...] = (
    ("admin", "لوحة الأدمن"),
    ("status", "حالة الاتصال بالسينمات"),
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
        f"🎬 <b>سينما رادار</b>\n{DIVIDER}",
        "<i>رفيقك لحجز أول كرسي 🍿</i>",
        f"أهلاً بيك{who} 👋",
    ]
    if active_watches:
        lines.append(f"عندك <b>{_active_watches(active_watches)}</b>.")
    else:
        lines.append("لسه مفيش مراقبات — نبدأ بأول فيلم؟ 🍿")
    if next_watch:
        lines += ["⏭️ <b>أقرب حفلة</b>", next_watch]
    if limit:
        lines.append(f"<i>🎟️ حدك الحالي: {_watches(limit)}.</i>")
    lines.append("اختار من تحت 👇")
    return _blocks(*lines)


def version_line() -> str:
    return f"<i>🎬 Cinema Radar · v{esc(__version__)}</i>"


def language_screen() -> str:
    return (
        f"🌐 <b>اختار لغتك</b> · <b>Choose your language</b>\n{DIVIDER}\n\n"
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
    return f"<b>{esc(movie)}</b>\n{esc(branch)} · {when} · {esc(detail)}"


def step_header(step: int, total: int, path: str) -> str:
    return f"{progress(step, total)} · {esc(path)}\n{DIVIDER}"


def page_label(page: int, pages: int) -> str:
    if pages <= 1:
        return ""
    return f"صفحة {page + 1} / {pages}"


# ------------------------------------------------------------------ onboarding
def onboard_intro(name: str = "") -> str:
    who = f" يا {esc(name)}" if name else ""
    return _blocks(
        f"🎬 <b>سينما رادار</b>\n{DIVIDER}",
        "<i>رفيقك لحجز أول كرسي 🍿</i>",
        f"أهلاً بيك{who} 👋",
        "بتابع حفلات VOX ورينيسانس في مصر،\n"
        "وأبعتلك أول ما الحجز يفتح\n"
        "أو كرسي يرجع متاح — قبل ما الكراسي تطير.",
        "من غير ما تفضل تفتح الموقع كل شوية.",
    )


def onboard_alerts() -> str:
    return _blocks(
        f"🔔 <b>إيه اللي هيوصلك؟</b>\n{DIVIDER}",
        "🎟️ <b>الحجز فتح</b>\nأول ما الحفلة تنزل.",
        "🪑 <b>كراسي رجعت</b>\nلما كرسي يتفضى.",
        "📅 <b>يوم جديد</b>\nلما فيلم ينزل في يوم جديد.",
        "⚙️ تظبط كل نوع من <b>إعدادات التنبيه</b>.",
    )


def onboard_safety() -> str:
    return _blocks(
        f"🙏 <b>قبل ما نبدأ</b>\n{DIVIDER}",
        "✅ البوت مجاني، وبس بيبعتلك لينك الحجز.",
        "🙅 مش بيحجز ولا بيدفع مكانك.",
        "🔒 مش بيطلب اسمك ولا رقمك ولا بيانات دفع.",
        "⚠️ غير رسمي وغير تابع لأي سينما.",
        "📄 التفاصيل: /privacy\n🗑️ امسح بياناتك: /delete_me",
    )


def onboard_progress(step: int) -> str:
    return f"<i>{progress(step + 1, 3)}</i>"


def help_text() -> str:
    return (
        f"🎬 <b>إزاي تستخدم سينما رادار؟</b>\n{DIVIDER}\n"
        "<i>ثلاث خطوات، وبعدها إحنا نتولى الباقي.</i>\n\n"
        "<b>1 · ضيف مراقبة</b>\n"
        "اضغط <b>➕ ضيف مراقبة</b> واختار:\n"
        "• الفرع\n"
        "• اليوم\n"
        "• الفيلم\n"
        "• الحفلة\n\n"
        "أو راقب كل حفلات اليوم، أو كل الأيام المتاحة.\n"
        "وتقدر تحدد فورمات معيّن زي IMAX أو 4DX أو VIP.\n\n"
        "<b>2 · استنى التنبيه</b>\n"
        "أول ما الحجز يفتح أو كرسي يرجع،\n"
        "هتوصلك رسالة فيها لينك الحجز.\n\n"
        "<b>3 · تحكم في أي وقت</b>\n"
        "من <b>🎟️ مراقباتي</b> تقدر:\n"
        "• تغيّر نوع التنبيه\n"
        "• تأجل التنبيه ساعة\n"
        "• تشيل المراقبة\n\n"
        "<b>مش لاقي فيلم؟</b>\n"
        "اضغط <b>🔎 دوّر بالاسم</b> واكتب جزء من الاسم\n"
        "بالعربي أو الإنجليزي.\n"
        "البوت بيفهم الأخطاء الإملائية كمان.\n\n"
        "<b>أوامر سريعة</b>\n"
        "/start — الرئيسية\n"
        "/add — ضيف مراقبة\n"
        "/search — دوّر على فيلم\n"
        "/watches — مراقباتي\n"
        "/settings — الإعدادات\n"
        "/help — المساعدة\n"
        "/privacy — الخصوصية\n"
        "/delete_me — امسح بياناتي\n"
        "/cancel — إلغاء الخطوة\n\n"
        "⚠️ <i>البوت غير رسمي وغير تابع لـ VOX أو Renaissance Cinemas.\n"
        "البيانات ممكن تتأخر أو تكون غلط،\n"
        "والحجز بيتم على موقع السينما نفسه.</i>\n\n"
        f"{version_line()}"
    )


def privacy_text() -> str:
    return (
        f"🔐 <b>الخصوصية باختصار</b>\n{DIVIDER}\n\n"
        "البوت بيعرفك برقم تليجرام بس،\n"
        "ومش بيطلب منك اسمك ولا إيميلك.\n\n"
        "<b>اللي بيتحفظ</b>\n"
        "• لغتك وإعداداتك.\n"
        "• مراقباتك: الفرع، اليوم، الفيلم، الحفلة.\n"
        "• لو دعمت المشروع:\n"
        "  طريقة التحويل، المبلغ، وأي ملاحظة أو صورة إثبات.\n"
        "• لو بعت فيدباك: النص واسم المستخدم لو موجود.\n\n"
        "<b>اللي مش بنطلبه منك</b>\n"
        "• بيانات كروت أو بنوك.\n"
        "• رقم تليفون أو إيميل.\n\n"
        "لو كتبت حاجة منهم بنفسك في ملاحظة تبرع أو فيدباك،\n"
        "هتتحفظ زي ما كتبتها.\n\n"
        "<b>مين بيشوفها؟</b>\n"
        "الأدمن بس، عشان يرد على الفيدباك ويراجع إثبات التحويل.\n"
        "مش بنبيع بياناتك ولا بنشاركها مع أي طرف تالت.\n\n"
        "<b>حذف البيانات</b>\n"
        "/delete_me بيمسح كل حاجة محفوظة في قاعدة بيانات البوت.\n"
        "الرسائل والصور اللي اتبعتت على تليجرام\n"
        "بتفضل في المحادثات.\n\n"
        "<b>الصور</b>\n"
        f"{tmdb_attribution()}\n\n"
        "<b>التواصل</b>\n"
        "zyad.waleed.sec@gmail.com\n\n"
        f"{version_line()}"
    )


def tmdb_attribution() -> str:
    return "بوسترات الأفلام من TMDB. البوت بيستخدم TMDB API لكنه غير معتمد من TMDB."


def consent_text() -> str:
    return (
        f"🔐 <b>الموافقة على حفظ البيانات</b>\n{DIVIDER}\n\n"
        "قبل ما نبدأ، محتاجين موافقتك الصريحة.\n"
        "لو مش موافق، مش هنحفظ أي حاجة عنك.\n\n"
        "<b>إيه اللي بيتحفظ؟</b>\n"
        "• رقم تليجرام بتاعك — من غير اسم أو إيميل.\n"
        "• لغتك وإعدادات التنبيهات.\n"
        "• المراقبات اللي بتضيفها:\n"
        "  السينما، الفرع، اليوم، الفيلم، الحفلة.\n"
        "• لو بعت فيدباك: النص واسم المستخدم لو موجود.\n"
        "• لو دعمت المشروع: طريقة التحويل والمبلغ\n"
        "  وأي ملاحظة أو صورة إثبات تبعتها.\n\n"
        "<b>ليه؟</b>\n"
        "عشان نبعتلك تنبيهات الحجز والكراسي\n"
        "ونرد على الفيدباك ونتحقق من الدعم.\n\n"
        "<b>مش بنطلبه منك</b>\n"
        "بيانات كروت أو بنوك، ولا رقم تليفون أو إيميل.\n\n"
        "<b>المدة والتحكم</b>\n"
        "بنحتفظ بالبيانات طول ما حسابك شغال.\n"
        "تقدر تمسح كل حاجة في أي وقت بـ /delete_me.\n"
        "وتقدر تقرأ التفاصيل الكاملة بـ /privacy.\n\n"
        f"<b>التواصل:</b> zyad.waleed.sec@gmail.com\n\n"
        f"{tmdb_attribution()}"
    )


def consent_declined() -> str:
    return (
        "تمام، مفيش أي حاجة اتحفظت ✅\n\n"
        "مش هنقدر نبعتلك تنبيهات من غير الموافقة.\n"
        "لو غيرت رأيك، اضغط الزرار تحت."
    )


# ------------------------------------------------------------------ add watch
def choose_cinema() -> str:
    return _blocks(
        f"🎬 <b>اختار السينما</b>\n{DIVIDER}",
        "منين تحب تراقب؟",
        "اختار سينما معيّنة،\nأو <b>كل السينمات</b> لو عايز الفيلم في كل الفروع مرة واحدة.",
    )


def BTN_MORNING(count: int) -> str:
    return f"🌅 حفلات صباحية ({count})"


def BTN_EVENING(count: int) -> str:
    return f"🌙 حفلات مسائية ({count})"


def window_cutoff_text(hour: int) -> str:
    """Render the morning/evening split hour in Egyptian-Arabic 12-hour form."""

    period = "مساءً" if hour % 24 >= 12 else "صباحاً"
    value = hour % 12 or 12
    return f"{value} {period}"


def window_label(window: str, morning_end_hour: int = 17) -> str:
    cutoff = window_cutoff_text(morning_end_hour)
    return f"حفلات صباحية (قبل {cutoff})" if window == "morning" else f"حفلات مسائية (من {cutoff})"


def choose_window(movie: str, date: str, morning_end_hour: int = 17) -> str:
    cutoff = window_cutoff_text(morning_end_hour)
    return _blocks(
        f"🎬 <b>{esc(movie)}</b> · 📅 {relative_date(date)}\n{DIVIDER}",
        "الصبح ولا بالليل؟",
        f"🌅 <b>صباحي</b> — قبل {cutoff}",
        f"🌙 <b>مسائي</b> — من {cutoff}",
    )


def choose_seats(context: str = "") -> str:
    path = context or "عدد الكراسي"
    return (
        f"{step_header(5, 6, path)}\n\n"
        "<b>محتاج كام كرسي؟</b> 🪑\n\n"
        "هبعتلك تنبيه أول ما عدد الكراسي المتاحة يوصل للرقم ده أو أكتر.\n"
        "اختار من تحت، أو اكتب عدد معين."
    )


def seats_custom_prompt() -> str:
    return (
        f"{step_header(5, 6, 'عدد مخصص')}\n\n"
        "<b>اكتب عدد الكراسي</b> 🪑\n\n"
        "اكتب رقم من <b>1</b> لـ <b>10</b>."
    )


def seats_custom_invalid() -> str:
    return "اكتب رقم صحيح من 1 لـ 10، مثال: 3"


def required_seats_line(seats: int) -> str:
    return f"🪑 محتاج {_needed_seats(seats)}"


def seats_updated(seats: int) -> str:
    return f"تم ✅ هبعتلك لما يتوفر {_needed_seats(seats)} أو أكتر."


def seats_button(seats: int) -> str:
    return f"🪑 عدد الكراسي: {_needed_seats(seats)}"


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
        f"{_branches(branch_count)}\n"
        f"{required_seats_line(required_seats)}",
        "هنراقب كل الحفلات المتاحة في الفترة دي في كل السينمات،\n"
        "وأول ما حفلة جديدة تفتح أو كرسي يرجع هتوصلك رسالة.",
        "تأكد المراقبة؟",
    )


def watch_created_window(
    movie: str, date: str, window: str, branch_count: int, morning_end_hour: int = 17
) -> str:
    return _blocks(
        f"✅ <b>المراقبة شغالة</b>\n{DIVIDER}",
        f"{esc(movie)}\n"
        f"{relative_date(date)} · 🕐 {window_label(window, morning_end_hour)}\n"
        f"كل السينمات ({_branches(branch_count)})",
        "أول ما يفتح حجز أو يظهر وقت جديد في الفترة دي،\nهتوصلك رسالة.",
    )


def no_showtimes_window(movie: str, date: str) -> str:
    return (
        f"🍿 <b>مفيش حفلات</b>\n\n"
        f"مفيش حفلات لـ «<b>{esc(movie)}</b>» في {relative_date(date)} في أي سينما.\n"
        "جرّب يوم تاني أو فترة تانية."
    )


def choose_branch() -> str:
    return _blocks(
        step_header(1, 5, "الفرع"),
        "🏢 <b>اختار الفرع</b>",
        "منين تحب نبدأ؟",
    )


def choose_date(branch: str) -> str:
    return _blocks(
        step_header(2, 5, branch),
        "📅 <b>اختار اليوم</b>",
        "اختار اليوم اللي يناسبك.",
    )


def choose_movie(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return _blocks(
        step_header(3, 5, path),
        "🎞️ <b>اختار الفيلم</b>",
        "مش لاقيه؟ اضغط <b>🔎 دوّر بالاسم</b>.",
    )


def search_choose_branch(query: str = "") -> str:
    head = step_header(2, 5, "بحث")
    if query:
        return _blocks(
            head,
            f"🔎 <b>بندور على «{esc(query)}»</b>",
            "اختار الفرع الأول:",
        )
    return _blocks(head, "🔎 <b>بحث عن فيلم</b>", "اختار الفرع الأول:")


def search_prompt(branch: str, date: str) -> str:
    path = f"{branch} › {relative_date(date)}"
    return _blocks(
        step_header(3, 5, path),
        "🔎 <b>اكتب اسم الفيلم</b>",
        "بالعربي أو الإنجليزي.",
        "مش مشكلة لو فيه غلطة إملائية — جزء من الاسم يكفي.",
    )


def search_too_short() -> str:
    return "اكتب حرفين على الأقل عشان أقدر أدور 🔎"


def search_results(query: str, count: int, total: int) -> str:
    return _blocks(
        "🔎 <b>نتائج البحث</b>",
        f"«<b>{esc(query)}</b>»",
        f"لقينا <b>{count}</b> من {_movies(total)}.",
        "اختار الفيلم اللي عايزه:",
    )


def search_no_results(query: str, suggestions: list[str] | None = None) -> str:
    lines = [
        "🍿 <b>مفيش نتيجة</b>",
        f"مفيش فيلم قريب من «<b>{esc(query)}</b>» في اليوم ده.",
    ]
    if suggestions:
        lines.append("قصدك واحدة من دول؟ اضغط عليها 👇")
    else:
        lines.append("جرّب جزء من الاسم،\nأو اكتبه بالإنجليزي،\nأو شوف كل الأفلام.")
    return _blocks(*lines)


def choose_showtime(movie: str, date: str, extra: str = "") -> str:
    path = f"{relative_date(date)} › {movie}"
    lines = [step_header(4, 5, path)]
    if extra:
        lines.append(extra)
    lines += [
        "🎟️ <b>اختار الحفلة اللي عايز تراقبها</b>",
        "🟢 متاح — احجز دلوقتي\n🔴 مكتمل — كله محجوز\n⚪ لسه مفتحش — استنى التنبيه",
        "لو عايز فورمات معيّن (IMAX، 4DX، VIP…)\nاختار من الأزرار اللي فوق.",
    ]
    return _blocks(*lines)


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
        icon = "🟢"
    elif status == SOLD_OUT:
        icon = "🔴"
    else:
        icon = "⚪"
    label = f"{icon} {format_time(time)} · {esc(hall)}"
    if status == AVAILABLE and seats not in (None, ""):
        label += f" · {_seats(int(seats))}"
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
        note = "الحفلة دي حجوزاتها مكتملة دلوقتي. هنراقبها ونبعتلك أول ما ترجع كراسي."
    elif status == NOT_AVAILABLE:
        note = "هنبعتلك أول ما الحجز يفتح."
    elif status == AVAILABLE:
        note = "الحفلة متاحة دلوقتي — تقدر تحجز فورًا، وهنراقبها كمان لو الكراسي فضيت."
    else:
        note = "هنراقب الحفلة ونبعتلك أول ما يحصل جديد."
    return _blocks(
        step_header(6, 6, "تأكيد"),
        "🎬 <b>راجع المراقبة</b>",
        f"{esc(movie)}\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} ({format_date(date)})\n"
        f"{format_time(time)} · {esc(hall)}\n"
        f"{required_seats_line(required_seats)}",
        note,
        "كله تمام؟ أكد من تحت ✅",
    )


def no_data() -> str:
    return _blocks(
        f"⏳ <b>لسه بنجيب البيانات</b>\n{DIVIDER}",
        "السينما مش بترد دلوقتي.\nجرّب تاني بعد دقيقة 🙏",
        "<i>مش بنعمل طلبات لموقع السينما وانت بتتصفح،\nعشان نحافظ على البوت شغال.</i>",
    )


def loading_branches() -> str:
    return _blocks("⏳ <b>بجيب الفروع…</b>", "ثانية واحدة 🙏")


def loading_showtimes() -> str:
    return _blocks(
        "⏳ <b>بجيب الحفلات من كل السينمات…</b>",
        "دي ممكن تاخد شوية ثواني 🙏",
    )


def window_movie_prompt() -> str:
    return _blocks(
        "🔎 <b>اكتب اسم الفيلم</b>",
        "اكتب اسم الفيلم اللي عايز تراقبه في كل السينمات (عربي أو إنجليزي).",
    )


def choose_date_all_cinemas() -> str:
    return _blocks(
        "📅 <b>اختار اليوم</b>",
        "اختار اليوم اللي عايز تراقب فيه في كل السينمات.",
    )


def no_dates() -> str:
    return _blocks(
        f"📅 <b>مفيش أيام متاحة</b>\n{DIVIDER}",
        "الفرع ده لسه ما نزّلش أيام للحجز.",
        "جرّب فرع تاني، أو استنى شوية.",
    )


def no_movies() -> str:
    return _blocks(
        f"🎬 <b>الحجز لسه مفتحش</b>\n{DIVIDER}",
        "مفيش أفلام متاحة في اليوم ده دلوقتي.",
        "جرّب يوم تاني،\nولو الحفلات ظهرت هتلاقيها هنا دايمًا.",
    )


def no_showtimes() -> str:
    return _blocks(
        f"🎟️ <b>مفيش حفلات</b>\n{DIVIDER}",
        "الحجز لسه مفتحش للفيلم ده في اليوم ده.",
        "جرّب فيلم أو يوم تاني.",
    )


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
    lines = [f"🎬 <b>{esc(name)}</b>\n{DIVIDER}"]
    if facts:
        lines.append(facts)
    if extra:
        lines.append(extra)
    if synopsis:
        lines.append(f"<i>{esc(synopsis)}</i>")
    else:
        lines.append("<i>مفيش قصة متاحة للفيلم ده دلوقتي.</i>")
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
        note = "الحفلات متاحة دلوقتي، وهنراقب كل حفلة عشان لو كراسي ترجع."
    elif states and all(state == "SOLD_OUT" for state in states):
        note = "كل الحفلات محجوزة دلوقتي. هنراقبهم ونبعتلك أول ما ترجع كراسي."
    else:
        note = "هنراقب كل حفلات الفيلم ده في اليوم، ونبعتلك أول ما حجز يفتح أو ترجع كراسي."
    ticket = f"🎟️ كل الحفلات ({count} حفلة)"
    if hall:
        ticket = f"🎭 {esc(hall)} — كل الحفلات ({count} حفلة)"
    return _blocks(
        step_header(6, 6, "تأكيد"),
        "🎬 <b>راجع مراقبة اليوم كامل</b>",
        f"{esc(movie)}\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} ({format_date(date)})\n"
        f"{ticket}\n"
        f"{required_seats_line(required_seats)}",
        note,
        "كله تمام؟ أكد من تحت ✅",
    )


def watch_created_movie(
    branch: str, date: str, movie: str, count: int, hall: str | None = None
) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"✅ <b>المراقبة شغالة</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)}{format_text}\n"
        f"🎟️ كل الحفلات ({count} حفلة)",
        "أول ما أي حجز يفتح أو كراسي ترجع،\nهتوصلك رسالة.",
        "تظبط نوع التنبيه من <b>⚙️ إعدادات التنبيه</b>.",
    )


def watch_created(branch: str, date: str, movie: str, time: str, hall: str) -> str:
    return _blocks(
        f"✅ <b>المراقبة شغالة</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}",
        "أول ما يحصل جديد، هتوصلك رسالة.",
        "تظبط نوع التنبيه من <b>⚙️ إعدادات التنبيه</b>.",
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
        step_header(6, 6, "تأكيد"),
        "🎬 <b>راجع مراقبة كل الأيام</b>",
        f"{esc(branch)}\n"
        f"{esc(movie)}\n"
        f"كل الأيام المتاحة دلوقتي ({_days(count)}){format_text}\n"
        f"{required_seats_line(required_seats)}",
        "هنراقب كل يوم يفتح فيه الفيلم في الفرع ده،\n"
        "وكمان أي يوم جديد ينزل للحجز.\n"
        "أول ما حجز يفتح أو كراسي ترجع هتوصلك رسالة.",
        "كله تمام؟ أكد من تحت ✅",
    )


def watch_created_all_dates(branch: str, movie: str, count: int, hall: str | None = None) -> str:
    format_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"✅ <b>المراقبة شغالة</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}{format_text}\nكل الأيام المتاحة ({_days(count)})",
        "أي يوم جديد ينزل أو كراسي ترجع،\nهتوصلك رسالة.",
        "تظبط نوع التنبيه من <b>⚙️ إعدادات التنبيه</b>.",
    )


def all_dates_unavailable() -> str:
    return _blocks(
        f"📅 <b>مفيش أيام متاحة</b>\n{DIVIDER}",
        "الفرع ده لسه ما نزّلش أيام للحجز.",
        "جرّب يوم معيّن،\nأو استنى لما الحجز يفتح.",
    )


def watch_limit_reached(
    limit: int,
    supporter_limit: int = 10,
    min_amount: int = 50,
    is_supporter: bool = False,
) -> str:
    if is_supporter:
        return _blocks(
            f"⚠️ <b>وصلت للحد الأقصى</b>\n{DIVIDER}",
            f"عندك <b>{_watches(limit)}</b>.",
            "امسح مراقبة قديمة من <b>مراقباتي</b>\nعشان تضيف واحدة جديدة.",
        )
    return _blocks(
        f"⚠️ <b>وصلت للحد المجاني</b>\n{DIVIDER}",
        f"عندك <b>{_watches(limit)}</b>، وهو الحد المجاني.",
        f"لو عايز توصل لـ <b>{_watches(supporter_limit)}</b>،\n"
        "تقدر تدعم المشروع <b>مرة واحدة</b>\n"
        f"بحد أدنى <b>{min_amount} جنيه</b> من <b>ادعم المشروع</b> 💛",
        "أو امسح مراقبة قديمة من <b>مراقباتي</b>.",
    )


def watches_trimmed(removed: int, limit: int) -> str:
    return _blocks(
        f"✂️ <b>ظبطنا مراقباتك</b>\n{DIVIDER}",
        f"شيلنا {_watches(removed)} عشان الحد الجديد بقى <b>{_watches(limit)}</b>.",
        "المراقبات الأقرب في المواعيد فضلت معاك،\n"
        "وتقدر تضيف غيرها من <b>ادعم المشروع</b> أو تمسح وتضيف من جديد.",
    )


def duplicate_watch() -> str:
    return "المراقبة دي عندك بالفعل 👌 هنبعتلك أول ما يحصل جديد."


# ------------------------------------------------------------------- my watches
def no_watches() -> str:
    return _blocks(
        f"🍿 <b>مفيش مراقبات لسه</b>\n{DIVIDER}",
        "نبدأ بأول فيلم؟",
        "اختار الفيلم والحفلة،\nوإحنا نفضل عيننا عليهم.",
        "أول ما الحجز يفتح أو كرسي يرجع،\nهتوصلك رسالة فورًا.",
        "اضغط <b>➕ ضيف مراقبة</b> من تحت.",
    )


def watches_retention_note(days: int) -> str:
    return f"<i>🧹 المراقبات بتتشال لوحدها بعد {_days(days)} من بداية الحفلة.</i>"


def watches_group(date: str) -> str:
    if date == "*":
        return "📅 <b>كل الأيام المتاحة</b>"
    return f"📅 <b>{relative_date(date)}</b>"


def confirm_delete_all(count: int) -> str:
    return _blocks(
        f"🗑️ <b>متأكد؟</b>\n{DIVIDER}",
        f"هنمسح <b>{_active_watches(count)}</b> — ومش هينفع نرجّعهم.",
        "لو حبيت تراقبهم تاني، هتبدأ من الأول.",
    )


def confirm_remove_watch(movie: str, when: str) -> str:
    return _blocks(
        f"❌ <b>نشيل المراقبة دي؟</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(when)}",
        "مش هتوصلك تنبيهات عنها تاني.",
    )


def watches_page_title(count: int) -> str:
    return f"🎟️ <b>مراقباتي</b> · {_active_watches(count)}"


def watch_mode_label(mode: str | None) -> str:
    return {
        "seats": "كراسي رجعت",
        "opening": "فتح الحجز بس",
    }.get(mode or "all", "كل حاجة")


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
    state = STATUS_LABELS_AR.get(str(status or "").upper(), "مش معروف")
    if seats not in (None, ""):
        state = f"{state} · {_seats(int(seats))}"
    scope = scope or "showtime"
    format_text = f" · {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 كل الأيام المتاحة · كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text} · {esc(state)}"
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
        lines.append("التنبيهات متأجلة دلوقتي")
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
    snooze = f"متأجل لحد {esc(snoozed_until_text)}" if snoozed_until_text else "مفيش تأجيل"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"📅 كل الأيام المتاحة — كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text}"
    return _blocks(
        f"⚙️ <b>إعدادات المراقبة</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{cinema_name(provider)} · {esc(branch)} · {relative_date(date)}\n"
        f"{ticket}",
        f"التنبيهات: <b>{watch_mode_label(mode)}</b>\n"
        f"بننبّهك عند: <b>{_needed_seats(required_seats)} أو أكتر</b>\n"
        f"{snooze}",
        "اختار نوع التنبيه اللي يناسبك:",
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
    state = STATUS_LABELS_AR.get(str(status or "").upper(), "مش معروف")
    if seats not in (None, ""):
        state = f"{state} · {_seats(int(seats))}"
    scope = scope or "showtime"
    format_text = f" — {esc(hall)}" if hall and hall != "*" else ""
    if scope == "movie_all_dates":
        ticket = f"🎟️ كل الأيام المتاحة — كل الحفلات{format_text}"
    elif scope == "movie":
        ticket = f"🎟️ كل الحفلات{format_text}"
    else:
        ticket = f"🕐 {format_time(time)}{format_text}"
    lines = [
        f"⏰ <b>فكّرتك بالمراقبة دي</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)} · {relative_date(date)}\n{ticket}",
    ]
    if scope != "movie_all_dates":
        lines.append(f"📊 الحالة دلوقتي: {esc(state)}")
    lines.append("افتح صفحة الحجز وشوف المتاح.")
    return _blocks(*lines)


def watch_snoozed(until_text: str) -> str:
    return f"تمام ⏰ هسكت التنبيهات لحد <b>{esc(until_text)}</b>، وبعدها هفكّرك."


def watch_unsnoozed() -> str:
    return "✅ التنبيهات رجعت شغالة."


def watch_removed_from_alert() -> str:
    return "✅ شيلنا المراقبة. مش هتوصلك تنبيهات عنها تاني."


def watch_mode_set(mode: str | None) -> str:
    return f"✅ التنبيهات بقت: <b>{watch_mode_label(mode)}</b>"


def watch_removed() -> str:
    return "✅ المراقبة اتشالت."


def all_watches_removed() -> str:
    return "✅ مسحنا كل المراقبات."


def watch_expired_summary(items: list[str], more: int = 0) -> str:
    total = len(items) + more
    lines = [f"🧹 <b>شيلنا {_watches(total)} حفلاتهم بدأت</b>\n{DIVIDER}"]
    lines.extend(f"• {item}" for item in items)
    if more:
        lines.append(f"• وكمان {_watches(more)}")
    lines += [
        "المراقبات دي حفلاتها بدأت، فمش هينفع نبعت تنبيهات عنها تاني.",
        "لو حابب تراقب حفلة جديدة، اضغط <b>➕ ضيف مراقبة</b>.",
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
    seat_text = f"\n🪑 {_seats_state(seats)}" if seats else ""
    return _blocks(
        f"🎟️ <b>الحجز فتح</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}{seat_text}",
        "احجز قبل ما يتكمل.",
    )


def alert_seats_available(
    movie: str, hall: str, time: str, branch: str, seats: int | None, date: str
) -> str:
    seat_text = _seats_state(seats) if seats else "كرسي"
    return _blocks(
        f"🪑 <b>رجعت كراسي</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n"
        f"{esc(branch)}\n"
        f"{relative_date(date)} · {format_time(time)}\n"
        f"{esc(hall)}",
        f"بقى فيه <b>{seat_text}</b> دلوقتي.",
        "احجز قبل ما يتكمل.",
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
    seat_text = f"\n🪑 {_seats_state(seats)}" if seats else ""
    return _blocks(
        f"🎟️ <b>الحجز فتح لحفلات الفيلم</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}{seat_text}",
        "احجز قبل ما يتكمل.",
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
    seat_text = f"\n🪑 {_seats_state(seats)}" if seats else ""
    return _blocks(
        f"🪑 <b>رجعت كراسي في حفلات الفيلم</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}{seat_text}",
        "احجز قبل ما يتكمل.",
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
    hall_text = f"\n🎭 {esc(hall)}" if hall else ""
    return _blocks(
        f"📅 <b>الفيلم نزل في يوم جديد</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}{hall_text}\n{joined}{more}",
        "افتح صفحة الحجز وشوف المتاح.",
    )


def alert_new_showtimes(movie: str, branch: str, date: str, times: list[str]) -> str:
    joined = "، ".join(format_time(t) for t in times[:8])
    more = " وغيرها" if len(times) > 8 else ""
    return _blocks(
        f"🕐 <b>حفلات جديدة ظهرت</b>\n{DIVIDER}",
        f"<b>{esc(movie)}</b>\n{esc(branch)}\n{relative_date(date)}\n{joined}{more}",
        "افتح صفحة الحجز وشوف المتاح.",
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
    return "سينما رادار · إحنا بننبّه بس، والحجز على موقع السينما."


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
    branches = "كل الفروع" if branch_count == 0 else _branches(branch_count)
    hall = hall_type or "كل القاعات"
    watch_quiet = "وبتشمل المراقبات ✅" if quiet_watches else "والمراقبات شغالة دايماً 🔔"
    return _blocks(
        f"⚙️ <b>الإعدادات</b>\n{DIVIDER}",
        "<b>🔔 الإشعارات</b>\n"
        f"• رجوع الكراسي: {'مفعل ✅' if notify_cancellations else 'مقفول ⛔'}\n"
        f"• ساعات الهدوء: {format_time(f'{quiet_start}:00')} → {format_time(f'{quiet_end}:00')}\n"
        f"  <i>{watch_quiet}</i>\n"
        f"• أفلام وحجوزات جديدة: {'مفعلة ✅' if discovery_enabled else 'مقفولة ⛔'}",
        "<b>🎯 فلاتر التنبيهات الجديدة</b>\n"
        f"• الفروع: {esc(branches)}\n"
        f"• الأنواع: {esc(types)}\n"
        f"• القاعة: {esc(hall)}\n"
        f"• اللغة: {'العربية' if (language or 'ar') == 'ar' else 'English'}",
        version_line(),
    )


def quiet_hours_text(start: int, end: int, quiet_watches: bool = True) -> str:
    watches = (
        "وتنبيهات المراقبات بتحترم الوقت ده كمان ✅"
        if quiet_watches
        else "لكن تنبيهات المراقبات شغالة حتى في الوقت ده 🔔"
    )
    return _blocks(
        f"🕰️ <b>ساعات الهدوء</b>\n{DIVIDER}",
        f"من <b>{format_time(f'{start}:00')}</b> لـ <b>{format_time(f'{end}:00')}</b>.",
        "مش هنبعت تنبيهات في الوقت ده،\nإلا لو الحفلة النهاردة أو بكرة.",
        watches,
        "اختار وقت جاهز، أو اضغط <b>وقت مخصص</b> وابعت مثلًا <code>23-8</code>.",
    )


def quiet_custom_prompt() -> str:
    return _blocks(
        f"🕰️ <b>وقت مخصص</b>\n{DIVIDER}",
        "ابعت البداية والنهاية بالساعات فقط،\nمثلًا: <code>23-8</code> (من 11 مساءً لـ 8 صباحاً).",
        "الساعة بنظام 24 ساعة (0 = 12 بالليل).",
    )


def quiet_custom_invalid() -> str:
    return "مش فاهم الوقت ده 🤔 ابعت مثلًا <code>23-8</code> (من 11 مساءً لـ 8 صباحاً)."


def choose_branches_text() -> str:
    return _blocks(
        "🏢 <b>اختار الفروع</b>",
        "منين تحب توصلك التنبيهات؟\nتقدر تختار أكتر من فرع.",
    )


def choose_event_types_text() -> str:
    return _blocks(
        "🎯 <b>اختار أنواع التنبيهات</b>",
        "إيه اللي يهمك تعرفه أول ما يحصل؟",
    )


def choose_hall_text() -> str:
    return _blocks(
        "🎭 <b>اختار نوع القاعة</b>",
        "هنعرض بس الأنواع المتاحة\nفي السينمات اللي اخترتها.",
    )


def format_not_offered() -> str:
    return "النوع ده مش متاح في السينمات اللي اخترتها 🙏"


def event_type_label(kind: str) -> str:
    return {
        "NEW_MOVIE": "فيلم جديد",
        "NEW_DATE_OPENED": "حجز يوم جديد",
        "NEW_SHOWTIMES": "حفلات جديدة",
        "UPCOMING_MOVIE": "قولّي لما ينزل",
    }.get(kind, kind)


# -------------------------------------------------------------------- support
def support_text(limit: int = 10, min_amount: int = 50) -> str:
    return _blocks(
        f"💛 <b>ادعم المشروع</b>\n{DIVIDER}",
        "سينما رادار مجاني للكل،\nوكل مستخدم عنده <b>مراقبتين</b> مجانًا.",
        "لو عايز تتابع أكتر،\n"
        "تقدر تدعم المشروع <b>مرة واحدة</b>\n"
        f"بحد أدنى <b>{min_amount} جنيه</b>،\n"
        f"ويبقى حدك <b>{_watches(limit)}</b> دايمًا.\n"
        "مش اشتراك شهري.",
        "التحويل فودافون كاش أو إنستاباي،\n"
        "وبعدها تبعت صورة الإثبات.\n"
        "الأدمن بيراجع الإثبات ويوافق.",
        "اختار طريقة الدعم:",
    )


def support_manual_text(method: str, phone: str, min_amount: int = 50) -> str:
    name = "فودافون كاش" if method == "vodafone_cash" else "إنستاباي"
    return _blocks(
        f"💛 <b>دعم عن طريق {name}</b>\n{DIVIDER}",
        f"حوّل على الرقم ده:\n<code>{esc(phone)}</code>",
        f"الحد الأدنى <b>{min_amount} جنيه</b> — مرة واحدة، مش اشتراك.",
        "بعد التحويل اضغط <b>حوّلت ✅</b>،\n"
        "وابعت صورة التحويل أو رقم العملية.\n"
        "الأدمن هيراجع الإثبات،\n"
        "ولو اتقبل حدك هيبقى <b>10 مراقبات</b>.",
        "⚠️ <i>التحويل مش بيتفعل تلقائيًا.</i>",
    )


def support_ask_amount(min_amount: int = 50) -> str:
    return _blocks(
        f"💰 <b>المبلغ اللي حوّلته كام؟</b>\n{DIVIDER}",
        f"الحد الأدنى <b>{min_amount} جنيه</b>.",
        "اختار المبلغ من تحت،\nأو اكتبه بالأرقام (مثال: 75).",
    )


def support_amount_invalid() -> str:
    return "اكتب مبلغ صحيح بالأرقام، مثال: 50 🙏"


def support_custom_amount_prompt() -> str:
    return _blocks(
        "✍️ <b>اكتب المبلغ</b>",
        "حوّلت كام؟ ابعت الرقم بس (مثال: 75) 💰",
    )


def support_below_minimum_warning() -> str:
    return "⚠️ المبلغ أقل من الحد الأدنى — هيتحول للأدمن وهو يقرر."


def support_ask_proof(method: str) -> str:
    name = "فودافون كاش" if method == "vodafone_cash" else "إنستاباي"
    return _blocks(
        f"📸 <b>إثبات تحويل {name}</b>",
        "ابعت صورة التحويل أو رقم العملية.",
        "لو مش عايز تكمل، اضغط <b>إلغاء</b>.",
    )


def support_proof_received() -> str:
    return _blocks(
        "✅ <b>الإثبات وصل</b>",
        "بعتناه للأدمن للمراجعة.\nهتوصلك رسالة أول ما يتراجع.",
    )


def support_approved(amount: float | None = None, limit: int = 10) -> str:
    amount_text = f" ({amount:g} جنيه)" if amount else ""
    return _blocks(
        f"✅ <b>تم تأكيد دعمك{amount_text}</b>",
        f"شكرًا لدعمك 💛\nحد المراقبات بقى <b>{_watches(limit)}</b>.",
    )


def support_rejected() -> str:
    return _blocks(
        f"❌ <b>الإثبات مش واضح</b>\n{DIVIDER}",
        "التحويل مش مكتمل أو الصورة مش واضحة.",
        "تقدر تبعته تاني من شاشة <b>ادعم المشروع</b>.",
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
    return _blocks(
        f"<b>إثبات دعم جديد #{donation_id}</b>{warning}\n{DIVIDER}",
        f"المستخدم: <code>{user_id}</code>\n"
        f"الطريقة: {name}\n"
        f"المبلغ: {esc(amount_text)}\n"
        f"الملاحظة: {esc(note or '—')}",
        "راجع الإثبات وبعدين قرر:",
    )


def support_admin_decided(donation_id: int, approved: bool) -> str:
    state = "تمت الموافقة ✅" if approved else "تم الرفض ❌"
    return f"الطلب #{donation_id}: {state}"


def support_not_configured() -> str:
    return "الدعم اليدوي مش متظبط دلوقتي. كلّم الأدمن."


# ------------------------------------------------------------------- feedback
def feedback_categories_text() -> str:
    return _blocks(
        f"✍️ <b>ابعتلنا رأيك</b>\n{DIVIDER}",
        "اختار نوع الرسالة الأول،\nوبعدها اكتب تفاصيلك في رسالة واحدة.",
        "كل رسالة بتوصل للأدمن،\nوبتساعدنا نطوّر البوت.",
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
    return _blocks(
        f"✍️ <b>ابعتلنا رأيك</b>\n{DIVIDER}",
        f"النوع: <b>{esc(label)}</b>",
        "اكتب رأيك أو اقتراحك في رسالة واحدة.",
        "كل رسالة بتوصل للأدمن،\nوبتساعدنا نطوّر البوت.",
    )


def feedback_thanks() -> str:
    return _blocks(
        "✅ <b>وصلنا رأيك</b>",
        "شكراً إنك ساعدتنا نطوّر البوت 💛",
    )


def feedback_too_soon() -> str:
    return "وصلنا رأيك قريب 🙏 جرّب تاني بعد ساعة."


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
    return f"<b>✍️ فيدباك جديد</b>\n{DIVIDER}\n\nمن {who}:\n\n{esc(text)}{reference}"


# ------------------------------------------------------------------ discovery
# Telegram renders captions in an automatic direction.  Starting every Arabic
# line with an RLM keeps punctuation and emojis in the right place, and Latin
# branch names / times are wrapped in an LTR isolate so they never drag the
# surrounding Arabic letters or numbers into the wrong order.
_RLM = "\u200f"
_LRI = "\u2066"
_PDI = "\u2069"


def _rtl(line: str) -> str:
    return f"{_RLM}{line}" if line else line


def _ltr(value: str) -> str:
    text = esc(value)
    if any("\u0600" <= char <= "\u06ff" for char in text):
        return text
    return f"{_LRI}{text}{_PDI}"


def _blocks(*blocks: str) -> str:
    """Join non-empty blocks with a blank line so every fact can breathe."""

    return "\n\n".join(block for block in blocks if block)


def _cinema_line(branch: str, provider: str | None = None) -> str:
    """Cinema brand and branch on one readable, correctly ordered line."""

    return _rtl(f"🏢 <b>{cinema_name(provider)}</b> · {_ltr(branch)}")


def _place(movie: str, branch: str, provider: str | None) -> str:
    return _blocks(
        _rtl(f"🎬 <b>{esc(movie)}</b>"),
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
        _rtl("🍿 <b>فيلم جديد فتح حجزه</b>"),
        _rtl(DIVIDER),
        _place(movie, branch, provider),
        _rtl(f"📅 من {relative_date(date)}") if date else "",
        _rtl(f"🎭 {esc(hall)}") if hall else "",
        _rtl("✨ <i>أول حفلاته نزلت… خد مكانك من بدري.</i>"),
    )


def discovery_new_date(
    movie: str,
    branch: str,
    date: str,
    provider: str | None = None,
) -> str:
    return _blocks(
        _rtl("📅 <b>يوم جديد فتح للحجز</b>"),
        _rtl(DIVIDER),
        _place(movie, branch, provider),
        _rtl(f"📅 من {relative_date(date)}"),
        _rtl("🗓️ <i>المواعيد الجديدة بقت متاحة… شوف اللي يناسبك.</i>"),
    )


def discovery_new_showtimes(
    movie: str,
    branch: str,
    date: str,
    times: list[str],
    provider: str | None = None,
) -> str:
    joined = f" {_RLM}·{_RLM} ".join(_ltr_time(t) for t in times[:6])
    more = " وغيرها" if len(times) > 6 else ""
    return _blocks(
        _rtl("🎟️ <b>حفلات جديدة نزلت</b>"),
        _rtl(DIVIDER),
        _place(movie, branch, provider),
        _rtl(f"📅 {relative_date(date)}"),
        _rtl(f"🕘 {joined}{more}"),
        _rtl("🍿 <i>اختار حفلتك ويلا بينا… قبل ما الكراسي تطير.</i>"),
    )


def _ltr_time(value: str) -> str:
    return f"{_LRI}{format_time(value)}{_PDI}"


def discovery_upcoming_released(
    movie: str,
    branch: str,
    date: str | None,
    hall: str | None = None,
    provider: str | None = None,
) -> str:
    return _blocks(
        _rtl("🍿 <b>أخيرًا… الفيلم اللي مستنيه وصل</b>"),
        _rtl(DIVIDER),
        _place(movie, branch, provider),
        _rtl(f"📅 من {relative_date(date)}") if date else "",
        _rtl(f"🎭 {esc(hall)}") if hall else "",
        _rtl("🎬 <i>احجز قبل ما يتكمل.</i>"),
    )


def discovery_digest(
    branch: str,
    count: int,
    lines: list[str],
    provider: str | None = None,
) -> str:
    body = "\n".join(_rtl(f"• {line}") for line in lines)
    return _blocks(
        _rtl(f"🍿 <b>عندك {_updates(count)} في {cinema_name(provider)} · {_ltr(branch)}</b>"),
        _rtl(DIVIDER),
        body,
        _rtl("👀 <i>بص عليهم واختار اللي يعجبك.</i>"),
    )


def discovery_watch_prompt() -> str:
    return _blocks(
        _rtl("🔔 <b>تحب تراقب أنهي فيلم؟</b>"),
        _rtl(DIVIDER),
        _rtl("اختار الفيلم اللي عايز تراقبه من التحديثات اللي فوق:"),
    )


def discovery_channel(event_text: str) -> str:
    return f"{event_text}\n\n#سينما_رادار"


# ---------------------------------------------------------------------- admin
def admin_text(data: dict[str, object]) -> str:
    return _blocks(
        f"🛠️ <b>لوحة الأدمن</b>\n{DIVIDER}",
        "<b>👥 الناس</b>\n"
        f"• مستخدمين نشطين: <b>{data.get('active_users', 0)}</b>\n"
        f"• داعمين: <b>{data.get('supporters', 0)}</b>\n"
        f"• مراقبات نشطة: <b>{data.get('active_watches', 0)}</b>",
        "<b>🌐 الشبكة</b>\n"
        f"• طلبات/دقيقة: <b>{data.get('requests_per_minute', 0):.1f}</b>\n"
        f"• نسبة الكاش: <b>{data.get('cache_hit_ratio', 0):.0%}</b>\n"
        f"• أهداف نشطة: <b>{data.get('active_targets', 0)}</b>\n"
        f"• معامل التباطؤ: <b>{data.get('slowdown_factor', 1):.2f}</b>\n"
        f"• قاطع الدائرة: <b>{esc(data.get('circuit_state', 'closed'))}</b>\n"
        f"• آخر طلب: <b>{esc(data.get('last_poll_status', '—'))}</b>",
        "<b>🛰️ الاكتشاف والبث</b>\n"
        f"• آخر اكتشاف: <b>{esc(data.get('discovery_last_run', '—'))}</b>\n"
        f"• أحداث النهاردة: <b>{data.get('events_today', 0)}</b>\n"
        f"• بثوث: <b>{data.get('broadcasts_sent', 0)}</b>\n"
        f"• طول الطابور: <b>{data.get('queue_length', 0)}</b>",
        version_line(),
    )


def admin_only() -> str:
    return "🔒 الأمر ده للأدمن بس."


def grant_done(telegram_id: int, limit: int) -> str:
    return f"✅ اتفتح الدعم للمستخدم <code>{telegram_id}</code> — الحد <b>{limit}</b>."


def revoke_done(telegram_id: int, limit: int) -> str:
    return f"✅ اتلغى الدعم للمستخدم <code>{telegram_id}</code> — الحد <b>{limit}</b>."


# ------------------------------------------------------------ admin / system
def admin_started() -> str:
    return f"✅ <b>سينما رادار شغالة</b> (v{esc(__version__)})."


def admin_limits_applied(users: int, watches: int) -> str:
    if not users:
        return "✅ حدود المراقبات اتظبطت (2 مجاني / 10 للداعمين)."
    return _blocks(
        "✅ حدود المراقبات اتظبطت (2 مجاني / 10 للداعمين).",
        f"اتأثر <b>{users}</b> مستخدم،\nواتشال <b>{_watches(watches)}</b> زيادة.",
    )


def admin_unexpected_error(name: str) -> str:
    return f"⚠️ <b>خطأ غير متوقع</b>\n<i>{esc(name)}</i>"


REASON_LABELS_AR = {
    "http_403": "({cinema}) رافض الطلب (403) — حماية أو بلوك",
    "http_429": "({cinema}) محدّد الطلبات (429) — rate limit",
    "http_5xx": "سيرفر ({cinema}) بيرجع خطأ (5xx)",
    "timeout": "انتهت مهلة الاتصال بـ ({cinema})",
    "network": "مشكلة شبكة / TLS / DNS",
    "http2": "اتصال ({cinema}) اتقطع فجأة (HTTP/2 reset)",
    "parse": "صفحة ({cinema}) اتغيرت والبوت مش فاهمها",
    "empty": "({cinema}) رجّع صفحة فاضية",
    "circuit": "قاطع الدائرة مفتوح بعد فشل متكرر",
    "unknown": "خطأ غير معروف",
}


def reason_label(reason: str, provider: str | None = None) -> str:
    template = REASON_LABELS_AR.get(reason, REASON_LABELS_AR["unknown"])
    return template.format(cinema=cinema_name(provider))


def format_place(place: str) -> str:
    """Show a technical place key with the localized cinema name."""

    if place.startswith("vox"):
        return f"({cinema_name('vox')})" + place[3:]
    if place.startswith("renaissance"):
        return f"({cinema_name('renaissance')})" + place[len("renaissance") :]
    return place


def _isolate_place(place: str) -> str:
    """Keep the Latin branch slug from reordering the Arabic label."""

    if not place:
        return "—"
    head, separator, tail = place.partition(") ")
    if separator and tail:
        return f"{esc(head)}) {_ltr(tail)}"
    return _ltr(place)


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
    title = f"🚨 <b>({cinema}) واقعة</b>" if opened else f"⚠️ <b>مشكلة مؤقتة مع ({cinema})</b>"
    blocks = [
        title,
        f"<b>السبب</b>\n{esc(reason_label(reason, provider))}",
        f"<b>المكان</b>\n{_isolate_place(place)}",
        f"<b>آخر نجاح</b>\n{_ltr(last_success) if last_success else '—'}",
    ]
    if affected:
        blocks.append(f"👀 <b>مراقبات متأثرة</b>\n{affected}")
    if opened:
        blocks.append("<b>وقفت التنبيهات مؤقتًا</b>\nمش هبعت أي تنبيه على بيانات قديمة لحد ما ترجع.")
        blocks.append(f"🔁 هجرب تاني بعد {retry_seconds} ثانية.")
    else:
        blocks.append(f"🔁 هجرب تاني خلال {retry_seconds} ثانية.")
        blocks.append("<i>لو المشكلة كملت، هوقف التنبيهات المؤقتة وأبلغك.</i>")
    return "\n\n".join(_rtl(block) for block in blocks)


def admin_upstream_recovered(minutes: int, provider: str | None = None) -> str:
    cinema = cinema_name(provider)
    title = f"✅ <b>({cinema}) رجعت</b>"
    if minutes > 0:
        label = _plural(minutes, "دقيقة", "دقيقتين", "دقايق", "دقيقة")
        title += f" بعد {minutes} {label}"
    return _blocks(_rtl(title), _rtl("البيانات بتتحدث تاني ✅"))


def stale_notice(minutes: int, degraded: bool) -> str:
    if minutes <= 0:
        return ""
    if degraded:
        return (
            f"\n\n⚠️ <i>السينما مش متاحة دلوقتي. آخر تحديث قبل {minutes} دقيقة — "
            "البيانات ممكن تكون قديمة.</i>"
        )
    if minutes >= 10:
        return f"\n\n<i>آخر تحديث قبل {minutes} دقيقة.</i>"
    return ""


def admin_status(data: dict[str, object]) -> str:
    return _blocks(
        f"📡 <b>حالة الاتصال</b>\n{DIVIDER}",
        f"• الحالة: <b>{esc(data.get('state', '—'))}</b>\n"
        f"• آخر نجاح: {esc(data.get('last_success', '—'))}\n"
        f"• آخر خطأ: {esc(data.get('last_error', '—'))}\n"
        f"• قاطع الدائرة: <b>{esc(data.get('breaker', 'closed'))}</b>",
        f"• أهداف نشطة: <b>{data.get('targets', 0)}</b>\n"
        f"• مراقبات متأثرة: <b>{data.get('affected', 0)}</b>",
    )


def admin_status_multi(data: dict[str, object]) -> str:
    sections = data.get("sections") or []
    blocks = [
        (
            f"🎬 <b>{esc(section.get('cinema', ''))}</b>\n"
            f"• آخر تحديث: {esc(section.get('last_success', '—'))}\n"
            f"• آخر خطأ: {esc(section.get('last_error', '—'))}\n"
            f"• أحداث النهارده: <b>{section.get('events', 0)}</b>"
        )
        for section in sections
    ]
    footer = (
        f"• قاطع الدائرة: <b>{esc(data.get('breaker', 'closed'))}</b>\n"
        f"• أهداف نشطة: <b>{data.get('targets', 0)}</b>\n"
        f"• مراقبات متأثرة: <b>{data.get('affected', 0)}</b>"
    )
    return _blocks(
        f"📡 <b>حالة الاتصال</b>\n{DIVIDER}",
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
    return "\n\n".join(
        [
            _rtl("⚠️ <b>الاكتشاف مش قادر يجيب الفروع</b>"),
            _rtl(f"<i>{_short_error(error)}</i>"),
        ]
    )


def admin_discovery_branch_failed(branch: object, error: object) -> str:
    return "\n\n".join(
        [
            _rtl(f"⚠️ <b>الاكتشاف فشل في فرع {esc(branch)}</b>"),
            _rtl(f"<i>{_short_error(error)}</i>"),
        ]
    )


# ------------------------------------------------------------------ discovery
def discovery_line_upcoming(name: object) -> str:
    return f"🏁 نزل أخيراً: {esc(name)}"


def discovery_line_new_movie(name: object) -> str:
    return f"🆕 فيلم جديد: {esc(name)}"


def discovery_line_new_date(name: object, date_text: str) -> str:
    return f"📅 حجز يوم جديد: {esc(name)} — {format_date(date_text)}"


def discovery_line_new_showtimes(name: object, times: tuple[str, ...]) -> str:
    formatted = "، ".join(format_time(value) for value in times)
    return f"🕐 حفلات جديدة: {esc(name)} — {formatted}"


# ---------------------------------------------------------------------- errors
def error_expired() -> str:
    return _blocks(
        "⌛ <b>الشاشة دي قديمة</b>",
        "الحفلة اتغيرت أو الصفحة انتهت.\nاضغط /start وابدأ من الأول.",
    )


def error_generic() -> str:
    return _blocks(
        "😅 <b>حصلت مشكلة صغيرة</b>",
        "جرّب تاني بعد شوية 🙏",
    )


def rate_limited() -> str:
    return "استنى شوية بين كل خطوة والتانية 🙏"


def cancelled() -> str:
    return _blocks(
        "تم الإلغاء ✅",
        "لو حابب ترجع للقائمة، اضغط /start.",
    )


def delete_me_confirm() -> str:
    return _blocks(
        f"🗑️ <b>متأكد؟</b>\n{DIVIDER}",
        "هنمسح كل بياناتك:\nالمراقبات، التنبيهات، الفيدباك، وإثباتات الدعم.",
        "ومش هنقدر نرجّعها.",
    )


def delete_me_done() -> str:
    return _blocks(
        "✅ <b>مسحنا كل بياناتك</b>",
        "لو حابب ترجع، استخدم /start في أي وقت.",
    )


def quiet_hours_set(start: int, end: int) -> str:
    return (
        f"✅ <b>ساعات الهدوء اتظبطت</b>\n"
        f"من {format_time(f'{start}:00')} لـ {format_time(f'{end}:00')}"
    )


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
        f"— اتحدّثت {_watches(updated)}."
    )


def user_not_found() -> str:
    return "المستخدم ده مش موجود."
