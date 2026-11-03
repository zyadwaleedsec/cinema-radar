# 🎬 Cinema Radar

An unofficial Telegram bot that watches **VOX Cinemas Egypt** showtimes and tells
you when booking opens or when seats free up. It also discovers brand-new
movies, newly opened dates and new showtimes, and broadcasts them to users who
opt in.

The bot **never books, pays or logs in to VOX**. It only sends a link to the
cinema's own booking page.

All user-facing copy is simple Egyptian-dialect Arabic in [`strings.py`](strings.py).

---

## Features

- **Per-showtime watches** — branch → date → movie → showtime → format filter.
- **Whole movie/day watches** ⭐ — one watch covers every session of a movie on
  a given day, with a single aggregated alert listing all changed times instead
  of one message per hall. Filter it to IMAX, 4DX, VIP, MAX, 3D or any other
  format present in the data.
- **Same-branch, all-days watches** ⭐ — from the showtime step, pick
  «📅 راقب كل الأيام المتاحة» to follow one movie across every currently
  bookable day in that branch. Each day is polled like a normal target; the
  first scan is silent and a later new day produces one
  «الفيلم نزل في يوم جديد» alert. Cross-branch following is intentionally not
  supported.
- **Alerts** for:
  - `NOT_AVAILABLE → AVAILABLE` (booking opened),
  - `SOLD_OUT → AVAILABLE` («رجعت كراسي» — cancelled seats freed up),
  - new showtimes added for a watched movie,
  - a new day opening for an all-days watch.
- **Movie info + trailer** ⭐ — synopsis, duration, rating and language from the
  movie page, plus a «شوف التريلر» button that opens YouTube externally (no
  in-Telegram playback). The trailer also appears inside watch alerts.
- **IMAX-shot indicator** ⭐ — when a movie has an IMAX screening, its card says
  whether it was actually shot with IMAX cameras (fully/partially on 70mm or
  certified digital) instead of merely upscaled. The data comes from a local
  snapshot of Wikipedia's *List of IMAX films*; TMDB is only used to normalise an
  ambiguous title. No extra VOX requests are made.
- **Automatic watch cleanup** ⭐ — a watch closes as soon as its last screening
  starts (the latest showtime for a whole-day watch, the last bookable day for an
  all-days watch). The user gets one grouped «شيلنا مراقبات خلصت» message, and
  closed watches are hard-deleted after `WATCH_RETENTION_DAYS` (3 by default).
  Manual removals follow the same retention window, silently.
- **Two-read confirmation** (~5 s apart) and a per-watch cooldown to avoid false
  or duplicate alerts.
- **Actionable alerts**: open the booking page, watch the trailer, remove the
  watch, or snooze it for an hour. Snoozed watches send a reminder with their
  latest status.
- **Per-watch notification mode**: everything («كل حاجة»), seats-back only
  («كراسي رجعت»), or booking-open only. Set it when the watch is created or
  later from **My Watches**.
- **Three-screen onboarding** on first `/start`, with skip; it explains alerts,
  the free/no-booking model and the unofficial-data disclaimer.
- **Quiet hours for watch alerts** (on by default, can be turned off): silent at
  night, except for screenings today or tomorrow.
- **Discovery + broadcast** of `NEW_MOVIE`, `NEW_DATE_OPENED`,
  `NEW_SHOWTIMES` and `UPCOMING_MOVIE`, with opt-in subscriptions,
  branch/event/hall filters, quiet hours, a daily cap and an optional public
  channel.
- **Coming Soon tracking** ⭐ — reads VOX `/movies/comingsoon` once an hour and
  sends a «قولّي لما ينزل» release alert when a known upcoming title finally
  gets showtimes. The release replaces the duplicate `NEW_MOVIE` alert.
- **Movie details + posters** ⭐ — poster, duration, age rating and language
  from the movie page, cached for 7 days and attached to watch and discovery
  alerts. Telegram receives the poster as a photo; if it is rejected the alert
  falls back to text.
- **Inline-keyboard-only flow**, paginated lists, one edited message per step,
  clickable «قصدك…؟» suggestions on a failed search and retry buttons on empty
  states instead of dead ends.
- **2026 UX layer** ⭐ — a personalised dashboard home, breadcrumb step headers,
  Back + Home on every screen, one primary action, destructive-action
  confirmations, loading/empty/error states, grouped and paged watch lists,
  poster cards for movie info and confirmations, copy-text buttons for donation
  numbers, user-created deep links (`?start=w<id>` and `?start=b<branch>`), and
  a scoped command menu. Messages use Bot API 10.3 rich messages when the client
  supports them and fall back automatically to classic HTML; set
  `UI_RENDERER=classic` to disable rich messages entirely.
- **Arabic/English fuzzy search** for movie names: tolerant of typos, Arabic
  spelling variants (`أ/ا`, `ة/ه`, `ى/ي`), optional `ال`, punctuation/spacing
  and common transliterations (`افنجرز` → *Avengers*, `سبايدر مان` →
  *Spider-Man*). Available from the movie list, the main menu and `/search`.
- **Fair-use limits**: 2 active watches free, 10 for supporters. Nothing else is
  gated.
- **Voluntary support**: one-off Vodafone Cash / InstaPay donation of at least
  50 EGP. The user sends a screenshot; the admin approves or rejects it inline,
  and approval raises the watch limit to 10 permanently. No subscriptions and no
  Telegram Stars.
- **Privacy**: `/delete_me` removes all personal rows; `/privacy` explains what
  is stored, what is never stored, and how to delete it.
- **Admin dashboard** (`/admin`, admin-only).
- **Strict low-volume polling** through a shared HTTP client: token bucket,
  conditional requests, cache, jittered per-target heap scheduler, request
  coalescing, AIMD backoff, circuit breaker and stale-cache fallback.
- **SQLite persistence** for cache and known state, so restarts do not cause a
  request burst.
- **Automated test suite** covering parsers, scheduling, security and payments.

---

## Project structure

```
cinemaradar/
├── main.py                 # bootstrap, long polling, background loops, shutdown
├── config.py               # every tunable interval/limit; secrets come from .env
├── strings.py              # all Egyptian-Arabic user-facing text
├── search.py               # Arabic/English fuzzy movie search (typo-tolerant)
├── models.py               # dataclasses: Branch, Movie, Showtime, events...
├── db.py                   # aiosqlite schema + persistence methods
├── cache.py                # memory + SQLite two-level cache and key helpers
├── http_client.py          # shared client, token bucket, ETag, backoff, breaker
├── scheduler.py            # per-target heap with adaptive jittered intervals
├── watcher.py              # coalescing, diff, confirm, alert dispatch
├── discovery.py            # baseline, diff, flap window, exactly-once events
├── broadcaster.py          # grouped fan-out queue, quiet hours, daily cap
├── notifier.py             # Telegram sender (global + per-chat limits)
├── imax.py                 # local IMAX-film matcher (Wikipedia snapshot)
├── tmdb.py                 # TMDB title/year normaliser (not an IMAX source)
├── support.py              # one-off manual donations and admin approval
├── stats.py                # internal metrics for the admin dashboard
├── feedback.py             # one feedback per user per hour
├── keyboards.py            # inline keyboards
├── middleware.py           # per-user anti-spam rate limit
├── timeutil.py             # timezone and quiet-hour helpers
├── utils.py                # small dependency-free shared helpers
├── handlers/               # /start, watches, settings, support, feedback, admin
├── ui/                     # screen model, classic + rich renderers, fallback
├── providers/
│   ├── base.py             # CinemaProvider abstraction + registry
│   └── vox.py              # VOX Egypt provider and pure HTML parsers
├── data/imax_films.json    # generated IMAX snapshot (CC BY-SA 4.0, see below)
├── docs/SPEC.md            # original product brief (historical)
├── scripts/cli_test.py     # live VOX smoke test
├── scripts/update_imax_list.py  # regenerates the IMAX snapshot
├── tests/                  # pytest suite (152 tests)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml          # ruff lint/format configuration
└── .env.example
```

---

## VOX Cinemas Egypt: what we found

Research notes are also in [`providers/vox.py`](providers/vox.py).

### Correct domain

`https://egy.voxcinemas.com` is the working Egypt site.
`https://egypt.voxcinemas.com` does **not** resolve.

### No public JSON showtimes API

The VOX Egypt web app is **server-rendered HTML**. We did not find a stable,
public JSON endpoint for showtimes. The useful pages are:

| Page | Purpose |
| --- | --- |
| `/cinemas` | branch list; links look like `/cinemas/<branch-slug>` |
| `/showtimes?c=<branch-slug>` | date strip plus the first on-sale day |
| `/showtimes?c=<branch-slug>&d=YYYYMMDD` | **whole branch + whole day**: movies and sessions in one request |
| `/movies/comingsoon` | announced titles for the Coming Soon release alerts |
| `/movies/<movie-slug>` | poster, duration, rating and language (cached 7 days) |
| `/booking/<session-id>` | booking page — **we never fetch it** |

The whole-branch/day page is preferred: one request returns every movie and
session for that day. VOX marks bookable sessions with a real
`/booking/<session-id>` link, so availability can be derived from the public
showtimes markup without opening booking or seat-map pages.

### TLS / bot protection

Plain `curl` and `httpx` requests are often reset or time out. A real Chrome TLS
fingerprint works much more reliably, so `http_client.py` can use
[`curl_cffi`](https://github.com/lexiforest/curl_cffi) with
`HTTP_IMPERSONATE=chrome124`. If `curl_cffi` is unavailable, the client falls
back to `httpx` automatically. We do **not** use proxies, IP rotation or any
other evasion. If VOX blocks us, the bot slows down, opens the circuit breaker,
tells the admin immediately (reason, place, last success, retry ETA and the
number of affected watches), and sends one recovery message when VOX is back.
While an incident is open, alerts are paused: the watcher never diffs stale
cache. Menus may still show the last known data with an age warning.

### Parser

The HTML parser is deliberately isolated in `providers/vox.py` and uses
heuristics (`/booking/...` anchors, `data-*` attributes, time/format/status
classes, movie links). If VOX changes markup, only that file should need work.
The parser normalizes:

- dates to ISO `YYYY-MM-DD` internally (VOX URLs use `YYYYMMDD`),
- times to 24-hour `HH:MM`,
- hall types to `MAX`, `Standard`, `IMAX`, etc.

VOX only renders a session once its day is on sale. A grey
`<span class="action showtime unavailable">` therefore means the session is
sold out, not "booking has not opened yet"; a day with no sessions at all is
the not-open case. The bot labels these **«الحجز مكتمل»** and
**«الحجز لسه مفتحش»** respectively, and a watch on a sold-out session alerts
when seats are released.
Movie names are read from the movie `<h2>`, not from the generic "Info" link,
and the currently selected day (rendered as a `<span>` with no date link) is
read from the page's hidden `d` input.

If the page format is unexpected, the bot logs it, alerts the admin and keeps
running on cached data. A small fallback branch list is used if `/cinemas`
cannot be read.

### Known limitation

VOX returns one day per showtimes request. Discovery therefore reads the
default day page once per branch per interval (as required for low volume).
`NEW_MOVIE` and `NEW_SHOWTIMES` are detected reliably from that page;
`NEW_DATE_OPENED` is detected when a new movie/date pair becomes visible in the
day data. Covering every future date in one pass would require one request per
date, which conflicts with the low-volume rule. This is documented rather than
silently hammering the site.

---

## Local setup

Requirements: **Python 3.12** (3.11+ should work) and pip.

```bash
git clone <your-repo-url> cinemaradar
cd cinemaradar

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env
```

Edit `.env`:

- `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `ADMIN_ID` — your numeric id (from [@userinfobot](https://t.me/userinfobot))
- `DONATION_PHONE` — Vodafone Cash / InstaPay number shown to users
- `CHANNEL_ID` — optional public channel
- `BOT_USERNAME` — optional @username for deep links (filled from `bot.me()` at startup)
- `UI_RENDERER` — `auto` (default), `rich` or `classic`
- `HTTP_IMPERSONATE=chrome124` — recommended for VOX

Run the VOX smoke test first:

```bash
python -m scripts.cli_test
python -m scripts.cli_test --branch city-centre-almaza
python -m scripts.cli_test --branch city-centre-almaza --date 2026-12-16
```

Then start the bot:

```bash
python -m main
```

The bot uses **long polling**, so no domain, TLS certificate or webhook is
needed.

### Run the tests

```bash
python -m pytest
```

Expected: `152 passed`.

The core tests do not require a Telegram token or network access. They use a
fake clock, a temporary SQLite database and mocked providers.

### UI QA checklist

Run these once per release on a real Telegram client:

- [ ] Arabic renders right-to-left; no clipped words at 320 px width.
- [ ] Every screen has **رجوع** (where a previous step exists) and **الرئيسية**.
- [ ] A tap is acknowledged in under 200 ms, followed by a typing indicator only
      when a network step is actually slow.
- [ ] Lists page at 6 watches and 8 branches/movies without losing the footer.
- [ ] Empty, loading and error states each offer a primary action.
- [ ] «امسح الكل» and «شيل المراقبة» both ask for confirmation first.
- [ ] Movie-info and confirmation poster cards are replaced in place, and Back
      from a poster card returns to the previous text screen.
- [ ] Deep links `?start=w<id>` and `?start=b<branch>` work for their owner only.
- [ ] `/start` shows only the public commands; admin commands appear only in the
      admin's private chat.
- [ ] Run with `UI_RENDERER=classic` to confirm the fallback has identical copy
      and buttons.

### Lint, format and dependency audit

```bash
python -m ruff check .
python -m ruff format .
python -m pip_audit -r requirements.txt
```

Configuration lives in [`pyproject.toml`](pyproject.toml). `ruff` and
`pip-audit` are included in `requirements-dev.txt`.

---

## Configuration

Everything tunable lives in [`config.py`](config.py) and can be overridden from
`.env`. Secrets are only read from the environment.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BOT_TOKEN` | — | Telegram bot token (required) |
| `ADMIN_ID` | — | Admin numeric id (required for admin features) |
| `DONATION_PHONE` | — | Manual donation number (never hard-coded) |
| `CHANNEL_ID` | empty | Optional public channel for discovery posts |
| `BOT_USERNAME` | empty | Bot @username for deep links; filled at startup |
| `UI_RENDERER` | `auto` | `auto` = rich with classic fallback, `rich`, or `classic` |
| `DB_PATH` | `cinemaradar.sqlite3` | SQLite file |
| `TIMEZONE` | `Africa/Cairo` | Quiet hours, daily caps, stats |
| `VOX_BASE_URL` | `https://egy.voxcinemas.com` | Provider base URL |
| `HTTP_IMPERSONATE` | empty | e.g. `chrome124` (needs `curl_cffi`) |
| `GLOBAL_RATE_LIMIT` | `1.0` | Upstream requests/second |
| `MAX_CONNECTIONS` | `2` | Max concurrent upstream connections |
| `REQUEST_TIMEOUT` | `12` | Upstream request timeout (seconds) |
| `MAX_RETRIES` | `1` | Extra attempts after a failed request |
| `POLL_OPEN_WITH_SEATS` | `100` | Poll interval when seats are open |
| `POLL_WAITING_FOR_OPEN` | `60` | Poll interval while waiting for booking |
| `POLL_SOLD_OUT` | `120` | Poll interval when sold out |
| `POLL_FAR_MIN` / `POLL_FAR_MAX` | `480` / `720` | Far-date interval range |
| `POLL_BURST` | `12` | Burst interval near expected opening |
| `POLL_JITTER` | `0.20` | ±20% interval jitter |
| `WATCH_CONFIRM_DELAY` | `3` | Seconds before confirmation read |
| `WATCHER_TICK` | `1` | Seconds between scheduler ticks |
| `WATCH_ALERT_COOLDOWN` | `600` | Per-watch duplicate cooldown |
| `WATCH_RETENTION_DAYS` | `3` | Days a closed watch is kept before hard deletion |
| `IMAX_DATA_PATH` | `data/imax_films.json` | Local IMAX snapshot path |
| `TMDB_READ_TOKEN` | empty | Optional TMDB read token (title normalisation only) |
| `TMDB_TIMEOUT` | `10` | TMDB request timeout (seconds) |
| `ALL_DATES_MAX` | `21` | Technical cap on days expanded per all-days watch |
| `ALL_DATES_REFRESH` | `1200` | Seconds between branch date-list refreshes |
| `DISCOVERY_INTERVAL` | `480` | Per-branch discovery interval |
| `DISCOVERY_DAILY_CAP` | `10` | Max discovery messages per user/day |
| `DISCOVERY_FLAP_WINDOW` | `1800` | Ignore items that flap within this window |
| `COMING_SOON_INTERVAL` | `3600` | How often `/movies/comingsoon` is refreshed |
| `CACHE_COMING_SOON_TTL` | `3600` | Coming Soon listing cache TTL |
| `CACHE_MOVIE_DETAILS_TTL` | `604800` | Poster/duration/rating/language/synopsis/trailer cache (7 days) |
| `FREE_WATCH_LIMIT` | `2` | Free active-watch limit |
| `SUPPORTER_WATCH_LIMIT` | `10` | Limit after an approved donation |
| `DONATION_MIN_AMOUNT` | `50` | Minimum one-off donation (EGP); lower amounts are flagged to the admin but can still be approved |
| `USER_RATE_LIMIT_PER_MINUTE` | `20` | Anti-spam bot actions/user/minute |
| `TELEGRAM_RATE_PER_SECOND` | `25` | Global Telegram send rate |
| `TELEGRAM_PER_CHAT_PER_SECOND` | `1` | Per-chat send rate |
| `BROADCAST_LOG_DAYS` | `90` | Days of broadcast keys kept for duplicate suppression |
| `QUIET_START` / `QUIET_END` | `23` / `8` | Default quiet hours |
| `CIRCUIT_FAILURE_THRESHOLD` | `3` | Consecutive failures before opening |
| `CIRCUIT_PAUSE_MIN` / `MAX` | `120` / `240` | Breaker pause range |
| `CIRCUIT_PROBE_TIMEOUT` | `20` | Seconds before a stuck half-open probe is retried |
| `BACKOFF_GLOBAL_MAX` | `8.0` | Maximum AIMD multiplier |
| `CACHE_*_TTL` | see `.env.example` | Static/listings/showtimes/stale TTLs |

Per-user quiet hours can be changed from Settings; `NULL` means "use the global
values from config". Watch alerts honour quiet hours by default (today/tomorrow
screenings always bypass them) and each user can turn that off from the quiet
hours screen.

### IMAX data

`data/imax_films.json` is generated from
[Wikipedia's *List of IMAX films*](https://en.wikipedia.org/wiki/List_of_IMAX_films)
by `scripts/update_imax_list.py`. It is committed with the project, so the bot
never scrapes Wikipedia at runtime. The snapshot is derived from Wikipedia
content and is therefore licensed **CC BY-SA 4.0**; keep the `source` and
`license` fields in the JSON when redistributing it.

TMDB is optional and used **only** to normalise a title/year before matching
(`TMDB_READ_TOKEN`). It is not the source of truth: TMDB's `imax` keyword marks
screenings, not films shot with IMAX cameras. If the token is empty, matching is
name-based and the snapshot still works. Put the token in `.env` only; rotate it
if it was ever shared in chat.

To refresh the snapshot:

```bash
python scripts/update_imax_list.py
```

The script is a development/maintenance tool, not part of the running bot.

### Watch retention

Each watch stores `expires_at` (UTC). Single-showtime watches expire when that
screening starts, whole-day movie watches when the latest showtime starts, and
all-days watches at 23:59 on the last bookable day they follow. During
`sync_targets` the watcher:

1. backfills `expires_at` for older rows,
2. closes due watches and sends **one grouped message per user**
   (`expiry_notified` prevents duplicates; a failed send is retried next cycle),
3. closes any remaining past-date rows, and
4. hard-deletes watches closed more than `WATCH_RETENTION_DAYS` ago
   (`watch_baselines` rows cascade with them).

Manual removals set `expiry_notified` so they are never announced; they still
disappear after the retention window.

---

## Bot commands

| Command | Who | Purpose |
| --- | --- | --- |
| `/start` | everyone | Welcome + dashboard / main menu |
| `/add` | everyone | Start the guided add-watch flow |
| `/search` | everyone | Search movies by Arabic or English name (typo-tolerant) |
| `/watches` | everyone | List, page and manage active watches |
| `/settings` | everyone | Quiet hours, filters and data controls |
| `/help` | everyone | Help, disclaimer and booking-link explanation |
| `/cancel` | everyone | Cancel the current flow |
| `/privacy` | everyone | What is stored, what is never stored, and `/delete_me` |
| `/delete_me` | everyone | Confirm and permanently delete personal data |
| `/admin` | admin | Dashboard: users, watches, requests/min, cache hit ratio, targets, slowdown, breaker, last poll, discovery, events, broadcasts, queue |
| `/status` | admin | On-demand VOX state: connected/outage, last success, last error reason, breaker, active targets and affected watches |
| `/grant <id>` | admin | Grant supporter limit |
| `/revoke <id>` | admin | Revoke supporter limit |
| `/imax <movie_id> <status>` | admin | Override a movie's IMAX status (`FULL_70MM`, `PARTIAL_70MM`, `CERTIFIED_DIGITAL`, `PARTIAL_DIGITAL`, `UNKNOWN`) |

Admin checks compare the caller with `ADMIN_ID` on every command and callback.
Public commands are registered in the default Telegram command scope; admin
commands are registered only in the admin's private chat scope, so they never
appear in the public menu.

---

## Low-volume design

1. **Per-target heap scheduler** — no global polling cycle. Each
   `(provider, branch, date, movie)` target has its own `next_run` with ±20%
   jitter.
2. **Adaptive intervals** — 100 s open-with-seats, 60 s waiting, 120 s sold
   out, 480–720 s for dates more than 7 days away, 12 s burst near opening.
3. **Request coalescing** — one in-flight fetch per
   `provider:branch:date`; all watchers of that target await the same future.
4. **Two-level cache** — memory + SQLite, with stale-while-revalidate and
   persistence across restarts. Menus read only from cache and label old data.
   Alerting paths pass `allow_stale=False`, so an outage can never produce a
   false alert.
5. **Conditional requests** — `If-None-Match` / `If-Modified-Since` plus a
   SHA-256 body hash to skip unchanged pages.
6. **Global token bucket** — 1 request/second by default, max 2 connections.
7. **AIMD backoff** — on 429/403/5xx/timeout, double the affected target and
   global slowdown; recover gradually on successes; honor `Retry-After`.
8. **Circuit breaker** — after 3 consecutive failures, pause all upstream
   requests for 2–4 minutes, then probe once. The admin gets one message when
   the outage starts (with the reason and retry ETA) and one when it recovers.
9. **Alert debounce** — a second read ~3 s later must confirm the change, plus a
   per-watch cooldown.
10. **No evasion** — no proxies or IP rotation.

All-days watches are expanded into one ordinary target per branch/day (capped
at `ALL_DATES_MAX`), so they reuse the same scheduler, request coalescing,
adaptive intervals and stale-cache fallback as day watches. The branch date
list itself is refreshed at most once per `ALL_DATES_REFRESH` (30 minutes by
default), which keeps the added request volume negligible.

Discovery reuses the same client, cache and breaker, and by default confirms a
change by re-reading the provider cache
(`DISCOVERY_CONFIRM_NETWORK=false`), so it does not create a second upstream
request. Coming Soon is refreshed at most once per `COMING_SOON_INTERVAL`
(default one hour), and movie details are cached for a week.

IMAX matching reads a local JSON snapshot and adds no VOX requests. TMDB is
contacted only when a film has an IMAX screening and its title is not already in
the snapshot, and the result is cached for 30 days.

---

## Donations

- **One-off, manual only.** A donation is not a subscription: once approved, the
  supporter limit of 10 stays.
- **Vodafone Cash / InstaPay** — the number comes from `DONATION_PHONE`. The user
  picks a method, chooses or types the amount, then sends a screenshot or a
  transfer reference. The bot stores a `pending` donation row and forwards the
  proof to the admin with **✅ موافقة / ❌ رفض** buttons.
- **Minimum 50 EGP.** Lower amounts are accepted for review but the admin sees a
  clear warning; the decision is always manual.
- **Approve** grants the supporter flag and the 10-watch limit exactly once;
  double taps are idempotent. **Reject** tells the user politely and grants
  nothing.
- Telegram Stars are intentionally **not** supported. The bot stores no card or
  bank details.

---

## Deployment on a local laptop

The bot uses long polling, so it needs no inbound ports, domain or public IP.
Run exactly one long-polling process per bot token.

1. Install Python 3.12 and create a virtual environment:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill `BOT_TOKEN`, `ADMIN_ID` and
   `DONATION_PHONE`.
3. Run it once in the foreground to confirm it starts, then stop it with
   `Ctrl+C`:
   ```powershell
   .\.venv\Scripts\python.exe -m main
   ```
4. To keep it running after logout, create a Windows Task Scheduler task that
   runs `.\.venv\Scripts\python.exe -m main` with the project folder as the
   working directory, "Run whether user is logged on or not", and restart on
   failure. Alternatively use [NSSM](https://nssm.cc/) to install it as a
   service.

The SQLite database stays at `DB_PATH` (default `cinemaradar.sqlite3`). It is
git-ignored, so updates never overwrite it. Keep the laptop awake (power plan)
if you rely on alerts overnight.

---

## Security and privacy

- Secrets live only in `.env`; `.env` is git-ignored.
- SQL is parameterized; callback data and user input are validated.
- Telegram errors are handled without leaking tracebacks to users.
- Stored data is minimal: `telegram_id`, watches, subscription filters,
  supporter flag, donations, and feedback text (with username only inside
  feedback rows).
- `/delete_me` deletes the user row, watches, subscriptions, feedback, donations
  and proof references; only anonymous counters (no personal data) remain.
- No card numbers, bank details, phone numbers or seat-map data are stored.
- The bot never logs in to VOX, never books, never pays, and never handles
  tickets.

---

## Terms of use of the source site

This project is an **unofficial** monitoring tool. Before scaling it, the
developer/operator **must review VOX Cinemas' terms of service** and any
applicable Egyptian law. The design intentionally keeps request volume very low
(one global request per second, max two connections, jittered per-target
intervals, conditional requests, caching, circuit breaker). Do not raise these
limits to scrape aggressively. If VOX asks you to stop, or changes its terms,
**disable or remove the provider** (`PROVIDER` / `providers/vox.py`) and keep the
rest of the bot running with another provider.

The bot only sends links to the cinema's own site. It does not bypass
authentication, access booking or seat-map pages, or automate purchases.

---

## Disclaimer

Cinema Radar is **not affiliated with, endorsed by, or sponsored by VOX
Cinemas**. Availability data can be delayed, incomplete or wrong. Always confirm
on the cinema's official website. Booking, payment and ticket handling happen
entirely on the cinema's site; the bot is not responsible for those
transactions.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `BOT_TOKEN is missing` | `.env` not created or not loaded; copy `.env.example` |
| VOX requests time out / reset | Install `curl_cffi` and set `HTTP_IMPERSONATE=chrome124` |
| `ZoneInfoNotFoundError` | `pip install tzdata` (already in requirements) |
| Bot starts but no alerts | Check `/status`: VOX state, last success, breaker and affected watches. While an outage is open, alerts are paused on purpose |
| Breaker stays open | VOX is blocking or down; wait for the pause and check logs |
| `database is locked` | Only one bot process should use the same SQLite file |
| Discovery sends nothing | First run stores a baseline by design; new items appear later |

Logs are structured JSON on stdout, which works well with `journalctl`.
