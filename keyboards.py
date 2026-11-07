"""Inline keyboards only.  Callback data is compact and validated by handlers."""

from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any

import i18n
import strings
from models import CANONICAL_FORMATS
from providers.base import PROVIDER_DISPLAY

try:  # pragma: no cover - exercised in production
    from aiogram.types import (
        CopyTextButton,
        DisabledButton,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
    )
except Exception:  # pragma: no cover - lets core tests run without aiogram

    class InlineKeyboardButton:  # type: ignore[no-redef]
        def __init__(
            self,
            text: str,
            callback_data: str | None = None,
            url: str | None = None,
            style: str | None = None,
            copy_text: Any = None,
            disabled: Any = None,
            **kwargs: Any,
        ):
            self.text = text
            self.callback_data = callback_data
            self.url = url
            self.style = style
            self.copy_text = copy_text
            self.disabled = disabled

    class InlineKeyboardMarkup:  # type: ignore[no-redef]
        def __init__(self, inline_keyboard: list[list[Any]]):
            self.inline_keyboard = inline_keyboard

    class CopyTextButton:  # type: ignore[no-redef]
        def __init__(self, text: str):
            self.text = text

    class DisabledButton:  # type: ignore[no-redef]
        pass


def _markup(rows: list[list[Any]]) -> Any:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    *,
    style: str | None = None,
    copy_text: str | None = None,
    disabled: bool = False,
) -> Any:
    if disabled:
        return InlineKeyboardButton(text=text, disabled=DisabledButton())
    if copy_text is not None:
        return InlineKeyboardButton(text=text, copy_text=CopyTextButton(text=copy_text))
    if style is not None:
        return InlineKeyboardButton(text=text, callback_data=callback_data, url=url, style=style)
    return InlineKeyboardButton(text=text, callback_data=callback_data, url=url)


def _field(item: Any, name: str, default: Any = "") -> Any:
    """Read a field from either a dataclass/model or a cached JSON dict."""

    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


PAGE_SIZE = 8
WATCH_PAGE_SIZE = 6


def main_menu_keyboard() -> Any:
    return _markup(
        [
            [
                _btn(strings.BTN_ADD_WATCH, "menu:add", style="primary"),
                _btn(strings.BTN_MY_WATCHES, "menu:watches"),
            ],
            [
                _btn(strings.BTN_SEARCH, "menu:search"),
                _btn(strings.BTN_SETTINGS, "menu:settings"),
            ],
            [
                _btn(strings.BTN_SUPPORT, "menu:support"),
                _btn(strings.BTN_FEEDBACK, "menu:feedback"),
            ],
        ]
    )


def back_home_keyboard() -> Any:
    return _markup([[_btn(strings.BTN_HOME, "menu:home")]])


def onboarding_keyboard(step: int) -> Any:
    rows = []
    if step < 2:
        rows.append([_btn(strings.BTN_ONBOARD_NEXT, f"ob:{step + 1}", style="primary")])
    else:
        rows.append([_btn(strings.BTN_ONBOARD_START, "ob:done", style="success")])
    footer = [_btn(strings.BTN_ONBOARD_SKIP, "ob:done")]
    if step > 0:
        footer.insert(0, _btn(strings.BTN_BACK, f"ob:{step - 1}"))
    rows.append(footer)
    return _markup(rows)


def consent_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CONSENT_ACCEPT, "consent:yes", style="success")],
            [_btn(strings.BTN_CONSENT_DECLINE, "consent:no", style="danger")],
        ]
    )


def consent_declined_keyboard() -> Any:
    return _markup([[_btn(strings.BTN_CONSENT_REVIEW, "consent:ask", style="primary")]])


def language_keyboard(source: str = "") -> Any:
    """Bilingual picker; ``source="s"`` returns to Settings after the change."""

    suffix = f":{source}" if source else ""
    return _markup(
        [
            [
                _btn(strings.BTN_ARABIC, f"lang:set:ar{suffix}"),
                _btn(strings.BTN_ENGLISH, f"lang:set:en{suffix}"),
            ]
        ]
    )


def retry_keyboard(retry_cb: str, back_cb: str = "menu:home") -> Any:
    return _markup(
        [
            [
                _btn(strings.BTN_RETRY, retry_cb, style="primary"),
                _btn(strings.BTN_BACK, back_cb),
            ]
        ]
    )


def _page_row(page: int, pages: int, prev_cb: str, next_cb: str) -> list[Any]:
    row = []
    if page > 0:
        row.append(_btn(strings.BTN_PREV, prev_cb))
    row.append(_btn(strings.page_label(page, pages), disabled=True))
    if page + 1 < pages:
        row.append(_btn(strings.BTN_NEXT, next_cb))
    return row


def paginate(
    items: list[Any],
    page: int,
    prefix: str,
    label,
    per_page: int = PAGE_SIZE,
) -> tuple[list[Any], int]:
    pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    start = page * per_page
    rows = [
        [_btn(label(item), f"{prefix}:{start + index}")]
        for index, item in enumerate(items[start : start + per_page])
    ]
    nav = []
    if pages > 1:
        nav = _page_row(
            page,
            pages,
            f"{prefix}_p:{page - 1}",
            f"{prefix}_p:{page + 1}",
        )
    if nav:
        rows.append(nav)
    rows.append([_btn(strings.BTN_HOME, "menu:home")])
    return rows, page


def _with_back(rows: list[list[Any]], back_cb: str) -> list[list[Any]]:
    """Insert a Back/Home row before the trailing Home row from ``paginate``."""

    if rows and rows[-1] and rows[-1][0].callback_data == "menu:home":
        rows = rows[:-1]
    rows.append([_btn(strings.BTN_BACK, back_cb), _btn(strings.BTN_HOME, "menu:home")])
    return rows


def cinema_keyboard(providers: list[str], current: str | None = None) -> Any:
    """The cinema picker shown at the start of the add/search flow."""

    rows = [
        [
            _btn(
                ("✅ " if current == name else "") + f"🎬 {PROVIDER_DISPLAY.get(name, name)}",
                f"pr:{name}",
            )
        ]
        for name in providers
    ]
    rows.append([_btn(("✅ " if current == "all" else "") + strings.BTN_ALL_CINEMAS, "pr:all")])
    rows.append([_btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def window_keyboard(morning_count: int, evening_count: int) -> Any:
    """Morning / evening choice for the cross-cinema watch flow."""

    rows = []
    if morning_count > 0:
        rows.append([_btn(strings.BTN_MORNING(morning_count), "win:morning")])
    if evening_count > 0:
        rows.append([_btn(strings.BTN_EVENING(evening_count), "win:evening")])
    rows.append([_btn(strings.BTN_BACK, "ab:date"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def branch_keyboard(branches: Iterable[Any], page: int = 0, back_cb: str | None = None) -> Any:
    items = list(branches)
    rows, _ = paginate(items, page, "br", lambda b: str(_field(b, "name")))
    if back_cb is not None:
        rows = _with_back(rows, back_cb)
    return _markup(rows)


def date_keyboard(dates: list[str], page: int = 0, back_cb: str = "ab:branch") -> Any:
    rows, _ = paginate(dates, page, "dt", lambda d: strings.relative_date(d))
    return _markup(_with_back(rows, back_cb))


def movie_keyboard(movies: list[Any], page: int = 0, show_search: bool = True) -> Any:
    rows, _ = paginate(movies, page, "mv", lambda m: str(_field(m, "name")))
    if show_search:
        rows.insert(-1, [_btn(strings.BTN_SEARCH_MOVIE, "mv_search")])
    return _markup(_with_back(rows, "ab:date"))


def search_results_keyboard(movies: list[Any], page: int = 0) -> Any:
    rows, _ = paginate(movies, page, "mv", lambda m: str(_field(m, "name")))
    rows.insert(
        -1,
        [
            _btn(strings.BTN_SEARCH_AGAIN, "mv_search"),
            _btn(strings.BTN_ALL_MOVIES, "mv_all"),
        ],
    )
    return _markup(_with_back(rows, "ab:date"))


def suggestion_keyboard(movies: list[Any]) -> Any:
    rows = [[_btn(str(_field(movie, "name")), f"mv:{index}")] for index, movie in enumerate(movies)]
    rows.append(
        [
            _btn(strings.BTN_SEARCH_AGAIN, "mv_search"),
            _btn(strings.BTN_ALL_MOVIES, "mv_all"),
        ]
    )
    rows.append([_btn(strings.BTN_BACK, "ab:date"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def search_keyboard() -> Any:
    return _markup(
        [
            [
                _btn(strings.BTN_SEARCH_AGAIN, "mv_search"),
                _btn(strings.BTN_ALL_MOVIES, "mv_all"),
            ],
            [_btn(strings.BTN_BACK, "ab:date"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def showtime_keyboard(
    showtimes: list[Any],
    page: int = 0,
    formats: dict[str, int] | None = None,
    current_format: str | None = None,
    date_count: int | None = None,
) -> Any:
    rows: list[list[Any]] = []
    names = list((formats or {}).keys())
    if len(names) > 1:
        format_buttons = [
            _btn(
                ("✅ " if current_format == key else "")
                + f"{strings.format_label(key)} ({formats[key]})",
                f"fm:{key}",
            )
            for key in names
        ]
        rows.extend(format_buttons[index : index + 2] for index in range(0, len(format_buttons), 2))

    def label(s: Any) -> str:
        return strings.showtime_button(
            _field(s, "time"),
            _field(s, "hall_type"),
            _field(s, "status"),
            _field(s, "seats_available"),
        )

    body, _ = paginate(showtimes, page, "st", label)
    rows.extend(body)
    if len(names) > 1 and current_format:
        rows.insert(-1, [_btn(strings.BTN_ALL_FORMATS, "fm:all")])
    rows.insert(-1, [_btn(strings.BTN_MOVIE_INFO, "mv:info")])
    if date_count is None or date_count > 1:
        rows.insert(-1, [_btn(strings.BTN_WATCH_ALL_DATES, "st:alldays")])
    rows.insert(-1, [_btn(strings.BTN_WATCH_ALL_SHOWTIMES, "st:all")])
    return _markup(_with_back(rows, "ab:movie"))


def confirm_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CONFIRM, "add:confirm", style="success")],
            [_btn(strings.BTN_BACK, "ab:showtime"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def confirm_window_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CONFIRM, "add:confirm_window", style="success")],
            [_btn(strings.BTN_BACK, "ab:date"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def movie_info_keyboard(trailer_url: str | None) -> Any:
    rows = []
    if trailer_url:
        rows.append([_btn(strings.BTN_TRAILER, url=trailer_url)])
    rows.append([_btn(strings.BTN_BACK_TO_SHOWTIMES, "info:back")])
    rows.append([_btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def _short(text: object, limit: int = 32) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def watches_keyboard(watches: list[dict[str, Any]], page: int = 0) -> Any:
    def label(watch: dict[str, Any]) -> str:
        scope = watch.get("scope") or "showtime"
        if scope == "movie_all_dates":
            when = strings.all_dates_label()
        else:
            detail = (
                strings.BTN_ALL_SHOWTIMES
                if scope == "movie"
                else strings.format_time(watch["showtime"])
            )
            when = f"{strings.format_date(watch['date'])} {detail}"
        return f"⚙️ {when} — {_short(watch['movie_name'], 24)}"

    total = len(watches)
    pages = max(1, (total + WATCH_PAGE_SIZE - 1) // WATCH_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * WATCH_PAGE_SIZE
    visible = watches[start : start + WATCH_PAGE_SIZE]
    rows = [[_btn(label(w), f"w:cfg:{w['id']}")] for w in visible]
    if pages > 1:
        rows.append(_page_row(page, pages, f"wp:{page - 1}", f"wp:{page + 1}"))
    if total:
        rows.append([_btn(strings.BTN_ADD_WATCH, "menu:add", style="primary")])
        rows.append([_btn(strings.BTN_DELETE_ALL, "w:all", style="danger")])
    else:
        rows.append([_btn(strings.BTN_ADD_WATCH, "menu:add", style="primary")])
    rows.append([_btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def watch_detail_keyboard(watch: dict[str, Any]) -> Any:
    watch_id = int(watch["id"])
    mode = watch.get("alert_mode") or "all"
    required_seats = int(watch.get("required_seats") or 1)
    marked = lambda value: "✅ " if mode == value else ""  # noqa: E731
    rows = [
        [
            _btn(marked("seats") + strings.BTN_MODE_SEATS, f"w:mode:{watch_id}:seats"),
            _btn(marked("opening") + strings.BTN_MODE_OPENING, f"w:mode:{watch_id}:opening"),
        ],
        [_btn(marked("all") + strings.BTN_MODE_ALL, f"w:mode:{watch_id}:all")],
        [_btn(strings.seats_button(required_seats), f"w:seats:{watch_id}")],
    ]
    if watch.get("snoozed_until"):
        rows.append([_btn(strings.BTN_UNSNOOZE, f"w:snz0:{watch_id}")])
    else:
        rows.append([_btn(strings.BTN_SNOOZE, f"w:snz:{watch_id}")])
    rows.append([_btn(strings.BTN_REMOVE_WATCH, f"w:del:{watch_id}", style="danger")])
    rows.append([_btn(strings.BTN_BACK, "menu:watches"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def seat_choice_keyboard() -> Any:
    return _markup(
        [
            [_btn(str(seats), f"add:seats:{seats}") for seats in (1, 2, 3, 4)],
            [_btn(strings.BTN_SEATS_CUSTOM, "add:seats_custom")],
            [_btn(strings.BTN_CANCEL, "menu:home")],
        ]
    )


def watch_seat_choice_keyboard(watch_id: int) -> Any:
    return _markup(
        [
            [_btn(str(seats), f"ws:{watch_id}:{seats}") for seats in (1, 2, 3, 4)],
            [_btn(strings.BTN_SEATS_CUSTOM, f"ws:{watch_id}:custom")],
            [_btn(strings.BTN_CANCEL, f"w:cfg:{watch_id}")],
        ]
    )


def watch_delete_confirm_keyboard(watch_id: int) -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CONFIRM_REMOVE_WATCH, f"w:dely:{watch_id}", style="danger")],
            [
                _btn(strings.BTN_CANCEL, f"w:cfg:{watch_id}"),
                _btn(strings.BTN_HOME, "menu:home"),
            ],
        ]
    )


def watches_clear_confirm_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CONFIRM_DELETE_ALL, "w:ally", style="danger")],
            [_btn(strings.BTN_CANCEL, "menu:watches"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def watch_created_keyboard(watch_id: int) -> Any:
    return _markup(
        [
            [_btn(strings.BTN_WATCH_SETTINGS, f"w:cfg:{watch_id}", style="primary")],
            [_btn(strings.BTN_MY_WATCHES, "menu:watches"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def watch_expired_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_ADD_WATCH, "menu:add", style="primary")],
            [_btn(strings.BTN_MY_WATCHES, "menu:watches"), _btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def watch_alert_keyboard(
    watch_id: int,
    booking_url: str | None,
    trailer_url: str | None = None,
    manage_url: str | None = None,
) -> Any:
    rows = []
    if booking_url:
        rows.append([_btn(strings.BTN_OPEN_BOOKING, url=booking_url, style="success")])
    if manage_url:
        rows.append([_btn(strings.BTN_MANAGE_WATCH, url=manage_url)])
    if trailer_url:
        rows.append([_btn(strings.BTN_TRAILER, url=trailer_url)])
    rows.append([_btn(strings.BTN_SNOOZE, f"wa:snz:{watch_id}")])
    rows.append([_btn(strings.BTN_REMOVE_WATCH, f"wa:del:{watch_id}", style="danger")])
    return _markup(rows)


def settings_keyboard(user: dict[str, Any], subscription: dict[str, Any] | None) -> Any:
    cancellations = bool(user.get("notify_cancellations", 1))
    discovery = bool(subscription and subscription.get("active"))
    return _markup(
        [
            [
                _btn(
                    f"{'✅' if cancellations else '⛔'} {strings.BTN_CANCELLATIONS}",
                    "set:cancel",
                )
            ],
            [_btn(strings.BTN_QUIET_HOURS, "set:quiet")],
            [
                _btn(
                    f"{'✅' if discovery else '⛔'} {strings.BTN_DISCOVERY_ALERTS}",
                    "set:disc",
                )
            ],
            [
                _btn(strings.BTN_BRANCHES_FILTER, "set:branches"),
                _btn(strings.BTN_TYPES_FILTER, "set:types"),
            ],
            [_btn(strings.BTN_HALL_FILTER, "set:hall")],
            [
                _btn(
                    f"{strings.BTN_LANGUAGE}: {i18n.language_name(i18n.get_language())}", "set:lang"
                )
            ],
            [_btn(strings.BTN_DELETE_MY_DATA, "del:ask", style="danger")],
            [_btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def quiet_keyboard(
    current_start: int = 23, current_end: int = 8, quiet_watches: bool = True
) -> Any:
    presets = [(23, 8), (22, 8), (0, 7), (1, 9)]
    rows = [
        [
            _btn(
                ("✅ " if quiet_watches else "⛔ ") + strings.BTN_QUIET_WATCHES,
                "q:watch",
                style="success" if quiet_watches else None,
            )
        ]
    ]
    rows += [
        [
            _btn(
                f"{strings.format_time(f'{s}:00')} → {strings.format_time(f'{e}:00')}"
                + (" ✅" if (s, e) == (current_start, current_end) else ""),
                f"q:{s}:{e}",
                style="success" if (s, e) == (current_start, current_end) else None,
            )
        ]
        for s, e in presets
    ]
    rows.append([_btn(strings.BTN_QUIET_CUSTOM, "q:cust")])
    rows.append([_btn(strings.BTN_BACK, "menu:settings"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def quiet_custom_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_CANCEL, "set:quiet")],
            [_btn(strings.BTN_HOME, "menu:home")],
        ]
    )


def branches_filter_keyboard(branches: list[Any], selected: list[str], page: int = 0) -> Any:
    pages = max(1, (len(branches) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = []
    start = page * PAGE_SIZE
    for index, branch in enumerate(branches[start : start + PAGE_SIZE]):
        provider = _field(branch, "provider") or "vox"
        key = f"{provider}:{_field(branch, 'id')}"
        mark = "✅ " if key in selected else ""
        label = _field(branch, "name")
        if label and provider in PROVIDER_DISPLAY:
            label = f"{PROVIDER_DISPLAY[provider]} · {label}"
        rows.append([_btn(f"{mark}{label}", f"fb:{start + index}")])
    if pages > 1:
        rows.append(_page_row(page, pages, f"fb_p:{page - 1}", f"fb_p:{page + 1}"))
    rows.append([_btn(strings.BTN_DONE, "fb:done")])
    rows.append([_btn(strings.BTN_BACK, "menu:settings"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def event_types_keyboard(selected: list[str]) -> Any:
    kinds = ["NEW_MOVIE", "NEW_DATE_OPENED", "NEW_SHOWTIMES", "UPCOMING_MOVIE"]
    rows = [
        [_btn(("✅ " if kind in selected else "") + strings.event_type_label(kind), f"ft:{kind}")]
        for kind in kinds
    ]
    rows.append([_btn(strings.BTN_DONE, "ft:done")])
    rows.append([_btn(strings.BTN_BACK, "menu:settings"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def hall_keyboard(current: str | None, formats: Iterable[str] | None = None) -> Any:
    """Only offer formats the selected cinemas actually sell."""

    keys = [key for key in (formats if formats is not None else CANONICAL_FORMATS)]
    options = [(key, strings.format_label(key)) for key in keys]
    rows = [[_btn(("✅ " if current is None else "") + strings.BTN_ALL_HALLS, "fh:all")]]
    buttons = [
        _btn(("✅ " if current == value else "") + label, f"fh:{value}") for value, label in options
    ]
    rows.extend(buttons[index : index + 2] for index in range(0, len(buttons), 2))
    rows.append([_btn(strings.BTN_BACK, "menu:settings"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def support_keyboard() -> Any:
    rows = [[_btn(strings.BTN_VODAFONE_CASH, "sup:vodafone_cash")]]
    rows.append([_btn(strings.BTN_INSTAPAY, "sup:instapay")])
    rows.append([_btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def donation_amount_keyboard(min_amount: int = 50) -> Any:
    presets = [min_amount, min_amount * 2, min_amount * 4]
    rows = [
        [_btn(strings.donation_amount_label(amount), f"sup:amt:{amount}")] for amount in presets
    ]
    rows.append([_btn(strings.donation_custom_label(), "sup:amtc")])
    rows.append([_btn(strings.BTN_BACK, "menu:support"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def donation_admin_keyboard(donation_id: int) -> Any:
    return _markup(
        [
            [
                _btn(
                    strings.donation_approve_label(),
                    f"dn:a:{donation_id}",
                    style="success",
                ),
                _btn(
                    strings.donation_reject_label(),
                    f"dn:r:{donation_id}",
                    style="danger",
                ),
            ]
        ]
    )


def manual_payment_keyboard(method: str, phone: str | None = None) -> Any:
    rows = []
    if phone:
        rows.append([_btn(strings.BTN_COPY_PHONE, copy_text=phone)])
    rows.append([_btn(strings.BTN_I_PAID, f"sup:paid:{method}", style="success")])
    rows.append([_btn(strings.BTN_BACK, "menu:support"), _btn(strings.BTN_HOME, "menu:home")])
    return _markup(rows)


def proof_cancel_keyboard() -> Any:
    return _markup([[_btn(strings.BTN_CANCEL, "menu:support")]])


def feedback_categories_keyboard() -> Any:
    return _markup(
        [
            [
                _btn(strings.feedback_category_button("idea"), "fc:idea"),
                _btn(strings.feedback_category_button("bug"), "fc:bug"),
            ],
            [
                _btn(strings.feedback_category_button("movie"), "fc:movie"),
                _btn(strings.feedback_category_button("other"), "fc:other"),
            ],
            [_btn(strings.BTN_CANCEL, "menu:home")],
        ]
    )


def feedback_waiting_keyboard() -> Any:
    return _markup([[_btn(strings.BTN_CANCEL, "menu:home")]])


def discovery_keyboard(
    token: str,
    booking_url: str | None,
    page_url: str | None = None,
    page_label: str | None = None,
) -> Any:
    rows = []
    if booking_url:
        rows.append([_btn(strings.BTN_OPEN_BOOKING, url=booking_url, style="success")])
    if page_url:
        rows.append([_btn(page_label or strings.BTN_MOVIE_PAGE, url=page_url)])
    rows.append([_btn(strings.BTN_WATCH_MOVIE, f"dw:{token}")])
    rows.append([_btn(strings.BTN_STOP_ALERTS, "ds:stop")])
    return _markup(rows)


def discovery_movie_keyboard(token: str, choices: list[dict[str, Any]]) -> Any:
    """One button per movie in a digest, so the user picks what to watch."""

    rows = []
    for index, choice in enumerate(choices):
        label = str(choice.get("line") or choice.get("title") or choice.get("movie_name") or "")
        # Button labels are plain text, so undo the HTML escaping used in the alert.
        rows.append([_btn(html.unescape(label)[:60], f"dwm:{token}:{index}")])
    return _markup(rows)


def discovery_stopped_keyboard() -> Any:
    """Confirmation after stopping movie alerts, with a one-tap undo."""

    return _markup(
        [
            [_btn(strings.BTN_TURN_ON_ALERTS, "ds:on", style="success")],
            [
                _btn(strings.BTN_SETTINGS, "menu:settings"),
                _btn(strings.BTN_HOME, "menu:home"),
            ],
        ]
    )


def delete_me_keyboard() -> Any:
    return _markup(
        [
            [_btn(strings.BTN_YES_DELETE, "del:yes", style="danger")],
            [_btn(strings.BTN_NO, "menu:home")],
        ]
    )
