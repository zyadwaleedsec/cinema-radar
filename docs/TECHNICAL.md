# Technical documentation

Implementation notes for developers and operators. For a friendly overview, see
[`README.md`](../README.md).

## Contents

1. [Project structure](#project-structure)
2. [Brand assets](#brand-assets)
3. [Languages and versioning](#languages-and-versioning)
4. [VOX Cinemas Egypt: what we found](#vox-cinemas-egypt-what-we-found)
5. [Low-volume design](#low-volume-design)
6. [Configuration](#configuration)
7. [IMAX data](#imax-data)
8. [Watch retention](#watch-retention)
9. [Local setup](#local-setup)
10. [Tests, lint and audit](#tests-lint-and-audit)
11. [UI QA checklist](#ui-qa-checklist)
12. [Deployment on a local laptop](#deployment-on-a-local-laptop)
13. [Security and privacy](#security-and-privacy)
14. [Terms of use of the source site](#terms-of-use-of-the-source-site)
15. [Troubleshooting](#troubleshooting)

---

## Project structure

```
cinema-radar/
├── main.py                 # bootstrap, long polling, background loops, shutdown
├── version.py              # single source of truth for the SemVer release
├── config.py               # every tunable interval/limit; secrets come from .env
├── strings.py              # facade that resolves copy from the active catalog
├── i18n/
│   ├── ar.py               # Egyptian Arabic catalog (default)
│   ├── en.py               # American English catalog
│   └── __init__.py         # language registry, per-update context, admin language
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
├── deeplinks.py            # parks ?start= payloads until a language is chosen
├── keyboards.py            # inline keyboards
├── middleware.py           # language gate + per-user anti-spam rate limit
├── timeutil.py             # timezone and quiet-hour helpers
├── utils.py                # small dependency-free shared helpers
├── handlers/               # /start, language, watches, settings, support, admin
├── ui/                     # screen model, classic + rich renderers, fallback
│   └── theme.py            # dividers, progress bars and shared visual tokens
├── providers/
│   ├── base.py             # CinemaProvider abstraction + registry
│   └── vox.py              # VOX Egypt provider and pure HTML parsers
├── data/imax_films.json    # generated IMAX snapshot (CC BY-SA 4.0, see below)
├── assets/                 # brand mark (logo.svg + PNG exports)
├── docs/
│   ├── TECHNICAL.md        # this file
│   └── SPEC.md             # product specification
├── scripts/cli_test.py     # live VOX smoke test
├── scripts/update_imax_list.py  # regenerates the IMAX snapshot
├── tests/                  # pytest suite (178 tests)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml          # ruff lint/format configuration
├── CHANGELOG.md            # release history (Keep a Changelog)
└── .env.example
```

---

## Brand assets

`assets/` holds the one official mark. Every raster file is generated from
`assets/logo.svg`; never edit a PNG by hand.

| File | Use |
| --- | --- |
| `logo.svg` | source of truth — 2048×2048, all text outlined to paths, no external references |
| `logo-512.png` | chat/social previews and lightweight embeds |
| `logo-1024.png` | general raster use |
| `logo.png` (2048) | high-DPI screens |
| `logo-4096.png` | master export; README header |

Palette: cream `#F2EDDA` background, ink `#15100C`, red `#C81E1E`. The lockup is
dark-on-light only — keep it on the cream field. To add a size, render the SVG at
that exact size; never upscale an existing PNG.

---

## Languages and versioning

### How the interface language is chosen

Egyptian Arabic is the default and American English is the second official
catalog. The full rule set lives in `i18n/__init__.py`; the important parts are:

- `users.lang` stores `ar` or `en`. A `NULL` value means **not chosen yet** — the
  bot deliberately does not backfill it, so users who onboarded before v1.1.0 see
  the picker exactly once.
- `LanguageMiddleware` runs before the rate limiter. It loads the user row, and
  for an unchosen user it shows the bilingual picker instead of running the
  handler. The operator sees the picker on `/start` as well; only the hidden
  admin commands and donation decisions bypass it, defaulting to Arabic.
- A deep link that arrives with the picker (`?start=b…`, `?start=w…`) is parked in
  `deeplinks.py` (in memory, 10 minutes) and resumed after the choice.
- `strings.py` is a facade: `strings.dashboard(...)` resolves the active catalog
  through a `ContextVar`, so handlers never thread a language argument.
- Background work uses `with i18n.use(lang):` per recipient. Admin and system
  messages use `i18n.admin_language()`, which is loaded from the admin's stored
  choice at startup and updated when the admin changes it.
- The stale-data note is stored as `(minutes, degraded)` in `ui/render.py` and
  rendered per request, so it follows the reader rather than the health loop.

Telegram command menus are registered twice: Arabic in the default scope and
English with `language_code="en"`. Telegram chooses a menu using the **client's**
language, not the bot's stored choice, so an Arabic-speaking user with an English
Telegram app sees the English command descriptions. This is a Telegram
limitation; the screens themselves always follow the stored choice.

### Adding or changing copy

1. Add the name to `i18n/ar.py` **and** `i18n/en.py` with the same signature.
2. Keep dynamic values escaped with `esc(...)`; messages use `parse_mode=HTML`.
3. Run `python -m pytest tests/test_i18n.py`. It checks catalog parity,
   signatures, and that English output contains no Arabic (except the bilingual
   picker and language names).

### Release checklist

The version lives only in `version.py`. Do not hardcode it anywhere else.

1. Pick the next SemVer number: MAJOR for a forced migration, MINOR for a new
   capability, PATCH for a fix or copy change.
2. Update `__version__` in `version.py` and `RELEASE_NAME`.
3. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`, newest first, and
   update the comparison links at the bottom.
4. Run the full gate:
   ```bash
   python -m pytest
   python -m ruff check .
   python -m ruff format --check .
   ```
5. Commit the release, then tag it and push:
   ```bash
   git tag -a vX.Y.Z -m "Cinema Radar vX.Y.Z"
   git push origin main --tags
   ```
6. Confirm the version in `/help`, Settings, `/admin` and the startup log.

---

## VOX Cinemas Egypt: what we found

Research notes are also in [`providers/vox.py`](../providers/vox.py).

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
when seats are released. Movie names are read from the movie `<h2>`, not from
the generic "Info" link, and the currently selected day (rendered as a
`<span>` with no date link) is read from the page's hidden `d` input.

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

## Configuration

Everything tunable lives in [`config.py`](../config.py) and can be overridden
from `.env`. Secrets are only read from the environment.

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

---

## IMAX data

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

---

## Watch retention

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

## Local setup

Requirements: **Python 3.12** (3.11+ should work) and pip.

```bash
git clone <your-repo-url> cinema-radar
cd cinema-radar

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

Before the first run, check the bot in [@BotFather](https://t.me/BotFather):

- **Bot Settings → Threaded Mode → off.** Leaving it on can group replies
  unexpectedly in private chats.
- Group privacy can stay at its default; Cinema Radar only needs private chats.
- Do not add commands by hand: they are registered at startup in both languages.

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

Expected: `178 passed`.

The core tests do not require a Telegram token or network access. They use a
fake clock, a temporary SQLite database and mocked providers.

```bash
python -m ruff check .
python -m ruff format .
python -m pip_audit -r requirements.txt
```

Configuration lives in [`pyproject.toml`](../pyproject.toml). `ruff` and
`pip-audit` are included in `requirements-dev.txt`.

---

## UI QA checklist

Run these once per release on a real Telegram client:

Both renderers share the same HTML. The rich renderer is real HTML, so
`ui/rich.py` converts newlines to `<br>`; without that every paragraph would
collapse into a single line.

- [ ] Arabic renders right-to-left; no clipped words at 320 px width.
- [ ] English screens contain no Arabic text and no left-over RTL punctuation.
- [ ] A brand-new account sees the bilingual language picker **before** any other
      screen; choosing English opens onboarding in English.
- [ ] Switching back to Arabic from Settings re-renders Settings immediately and
      keeps every watch and preference.
- [ ] `?start=w<id>` and `?start=b<branch>` tapped before choosing a language
      resume after the choice instead of being lost.
- [ ] Alerts arrive in the recipient's stored language, and admin notices use the
      admin's language.
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

## Performance notes

- The VOX day page is parsed **once** per fetch; the same `BeautifulSoup` tree
  feeds `parse_showtimes`, `parse_movies` and `parse_dates`. On a 155 KB page
  this cut parsing from ~59 ms to ~21 ms.
- Menus read parsed JSON from the two-level cache. The watcher force-refreshes
  on its own schedule, so alert detection is never served from stale data.
- SQLite runs in WAL mode with a 20 MB page cache, memory temp storage and a
  5-second busy timeout.
- Top-level menu callbacks are acknowledged before any rendering, so a slow
  cache build cannot leave the button spinning.

---

## Security and privacy

- Secrets live only in `.env`; `.env` is git-ignored.
- SQL is parameterized; callback data and user input are validated.
- Telegram errors are handled without leaking tracebacks to users.
- Stored data is minimal: `telegram_id`, language, watches, subscription
  filters, supporter flag, donations (method, amount, note, proof reference),
  and feedback text (with username only inside feedback rows).
- `/delete_me` deletes the user row, watches, subscriptions, feedback, donations
  and proof references from the bot's database; messages and photos already
  delivered in Telegram remain in the chat. Only anonymous counters (no
  personal data) remain.
- Card numbers, bank details and seat maps are never requested or stored.
  Free-text donation notes and feedback are stored as written, so a phone number
  or email typed there is stored with that message.
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
