# Product specification

> This document started as the original project brief. It has been cleaned up so
> it no longer contradicts the shipped bot; obsolete ideas (Docker/Oracle
> hosting, Telegram Stars, seat counts, 25-watch supporter limits) were removed.
> [`README.md`](../README.md) is the friendly overview and
> [`TECHNICAL.md`](TECHNICAL.md) holds the implementation notes; together they
> are the authoritative documentation for the shipped bot.

## Goal

Cinema Radar is a **public** Telegram bot that monitors VOX Cinemas and
Renaissance Cinemas showtimes and tells users when booking opens or when a
sold-out session frees up seats. Anyone with the link can use it; there is no
invitation or allowlist. It also announces new movies, newly opened dates and
new showtimes to users who opt in.

Users pick a branch, date, movie, showtime and optional screening format. The
bot watches that target and sends an alert with a button that opens the cinema's
own booking page. The bot **never books, pays or logs in to the cinema site**;
it only sends a link.

VOX, Renaissance and Premiere are supported. The enabled cinemas are selected
with `PROVIDERS`, with `PROVIDER` as the fallback brand; the provider contract
keeps the watcher, discovery and bot layers unchanged when another cinema is
added.

## Stack

- Python 3.12, aiogram 3.x, httpx (async), SQLite via aiosqlite.
- Configuration comes from `.env` (`BOT_TOKEN`, `ADMIN_ID`, `DONATION_PHONE`,
  optional `CHANNEL_ID`, ...) plus `config.py` for every tunable interval and
  limit. Secrets and the donation number never live in source code.
- Long polling only: no domain, webhook, TLS certificate or inbound port.
- The bot runs on the operator's own machine (a local laptop in the reference
  deployment). Docker is not required.
- `.gitignore` excludes `.env`, the SQLite database and logs.

## Architecture

- `providers/base.py`: abstract `CinemaProvider` with `get_branches()`,
  `get_dates(branch)`, `get_movies(branch, date)` and
  `get_showtimes(branch, date, movie)` returning time, hall/format, status and
  booking URL. Some providers do not expose seat counts, so they are not part of
  the contract and `/booking/.../seats` is never requested.
- `providers/vox.py`: VOX implementation. It reads the endpoints the site
  actually uses, prefers whole-branch+day responses over per-movie calls, and
  documents the findings in the README.
- `providers/renaissance.py`: Renaissance implementation. It reads the public
  branch/day/movie pages; online booking is available/disabled, and no seat
  counts are exposed.
- `http_client.py`: one persistent httpx client (keep-alive, gzip, a
  browser-shaped User-Agent ending in `CinemaRadar/<version>` with the contact in
  `From` / `X-Bot-Name` / `X-Bot-Contact`, optional curl_cffi TLS fingerprint)
  wrapped with the global rate limiter, adaptive backoff and circuit breaker.
  Cinema WAFs reset any UA that carries an email, a URL or the word "bot";
  API clients such as TMDB keep the fully identified bot UA.
- `tmdb.py` / `posters.py`: optional TMDB title lookup and cached, official
  poster URLs. Cinema-scraped image URLs are never stored or sent.
- `cache.py`: memory + SQLite cache so a restart does not trigger a request
  burst.
- `scheduler.py`: per-target priority-queue scheduler.
- `watcher.py`: takes due targets, fetches each target once (request
  coalescing), diffs against the stored state and fires events only on change:
  1. `NOT_AVAILABLE -> AVAILABLE` (booking opened),
  2. `SOLD_OUT -> AVAILABLE` (cancelled seats freed up), when the free count
     meets the watch's `required_seats` threshold,
  3. new showtimes for a watched movie/day,
  4. a new bookable day for a same-branch, all-days watch.
- `discovery.py`: the new-movie / new-booking discovery job.
- `broadcaster.py`: rate-limited fan-out queue for discovery alerts and the
  optional public channel.
- `notifier.py`: sends watch alerts with an inline booking button and handles
  Telegram flood limits and blocked users. `notifier.py` and `broadcaster.py`
  share one global Telegram send limiter.
- `support.py`: manual donations and the supporter limit.
- `stats.py`, `feedback.py`: public aggregates and user feedback.
- `i18n/`: the Arabic and English catalogs, the active-language context and the
  admin's language. `strings.py` is only a facade over the active catalog.
- `middleware.py`: the language gate (before anything else) and the per-user rate
  limiter.
- `version.py`: the only place the release number is written.
- `ui/`: classic HTML renderer plus the rich-message renderer with a cached
  capability fallback.

## Polling and caching

Goal: the minimum number of requests to the cinema, spread evenly over time and
self-throttling. These rules apply to every upstream request, including
discovery.

1. Scheduler: one heap keyed by `next_run` per target
   `(provider, branch, date, movie)`. No fixed global cycles. ±20% random jitter
   on every interval.
2. Adaptive intervals (defaults; see `config.py`):
   - open with seats: 100 s
   - waiting for booking to open: 60 s (burst to 12 s inside the opening window)
   - sold out: 120 s
   - dates more than 7 days away: 480–720 s
   Targets with no active watchers or past showtimes are removed.
3. Request coalescing: one in-flight fetch per target key; results fan out to
   all watchers of that target.
4. Cache: static data 12–24 h; movies/dates 10–15 min; watched showtimes use
   their poll interval. Bot menus read from cache only and never trigger
   upstream requests. Stale-while-revalidate, persisted in SQLite.
5. Conditional requests: send `ETag` / `If-None-Match` and `If-Modified-Since`
   when supported; otherwise compare a body hash and skip parsing if unchanged.
6. Global token bucket (1 req/s by default), at most 2 concurrent connections
   to the host.
7. Adaptive backoff (AIMD): on 429/403/5xx/timeout, back off the affected
   targets and a global slowdown factor; recover gradually after consecutive
   successes. Honour `Retry-After`.
8. Circuit breaker: after 3 consecutive failures pause requests (120–240 s),
   then probe with a single request. The admin gets one message when it opens
   and one when it recovers, including the reason, place, last success, retry
   ETA and the number of affected watches. `/status` shows the same on demand.
9. Alert debounce: send an alert only after a second read confirms the state
   change, plus a per-watch cooldown to prevent duplicates.
10. Freshness: watch and alert paths never alert on stale data. Menus may show
    cached data with an "آخر تحديث" warning, but a stale payload cannot produce
    or suppress an alert.
11. No proxy rotation or IP evasion. If blocked, slow down and notify the admin.

## Discovery and broadcast

Goal: detect when (a) a brand-new movie appears at a branch, (b) booking opens
for a new date of an existing movie, (c) new showtimes are added, or (d) an
upcoming movie is announced, and tell every subscribed user without requiring a
watch.

Detection:

- A separate low-frequency job: one request per branch every
  `DISCOVERY_INTERVAL` (480 s, ±20% jitter), always through the shared rate
  limiter, cache and circuit breaker. It reuses cached branch/day data when
  possible.
- Keeps `known_state` per branch: movie ids, `(movie_id, date)` pairs and
  `(movie_id, date, showtime, hall_type)` triples.
- Events: `NEW_MOVIE`, `NEW_DATE_OPENED`, `NEW_SHOWTIMES`, `UPCOMING_MOVIE`.
- First run baseline: on first start, or when a branch has no stored state, the
  current state is stored **without** sending alerts.
- Debounce: confirm with a second read, and ignore items that flap within
  `DISCOVERY_FLAP_WINDOW` (30 min).
- Broadcast each event once only (idempotency key: event type + branch + movie +
  date).

Subscriptions (opt-in, in Settings):

- Toggle plus filters: branches (multi-select), event types, optional format.
- Default: OFF. Nobody is auto-subscribed.

Sending:

- One queue with a sender worker limited to 25 messages/second globally and 1
  message/second per chat. Retry on `RetryAfter`; deactivate subscriptions of
  users who blocked the bot.
- Respect quiet hours (`QUIET_START`/`QUIET_END`, default 23–8), except for
  events whose date is today or tomorrow.
- Group multiple events from the same cycle into one message per user.
- Cap discovery alerts per user per day (`DISCOVERY_DAILY_CAP`, default 10).
- Optional public channel: when `CHANNEL_ID` is set, post every confirmed event
  there too (one post per event, no user data).

## Database (SQLite)

- `users(id, telegram_id, is_supporter, watch_limit, notify_cancellations,
  quiet_start, quiet_end, quiet_watches, onboarded, created_at)`
- `watches(id, user_id, provider, branch_id, branch_name, date, movie_id,
  movie_name, poster_url, duration_minutes, rating, language, synopsis,
  trailer_url, scope, showtime, hall_type, booking_url, alert_mode,
  snoozed_until, last_status, last_seats, required_seats, baseline_done,
  imax_status, expires_at, deactivated_at, expiry_notified, active,
  last_alert_at, created_at)`
  - `scope`: `showtime`, `day` (whole movie/day) or `*` (all bookable days at one
    branch).
  - `required_seats`: minimum number of free seats before a seat alert fires
    (default `1`). Unknown seat counts still alert so nothing is missed.
- `watch_baselines(watch_id, date, status)`
- `state_cache(target_key, payload, etag, last_modified, body_hash, fetched_at,
  ttl)`
- `subscriptions(id, user_id, branch_ids, event_types, hall_type, active,
  created_at)`
- `known_state(branch_id, payload, updated_at)`
- `broadcast_log(event_key, created_at)`
- `donations(id, user_id, method, amount, status, note, file_id, approved_at,
  approved_by, below_minimum, created_at)`
  - `method`: `vodafone_cash` or `instapay`.
  - `status`: `pending`, `approved` or `rejected`.
- `feedback(id, user_id, username, text, created_at)`
- `daily_stats(date, alerts_sent, active_watches, active_users)`
- `discovery_alerts(user_id, date, count)`
- `discovery_actions(token, user_id, branch_id, branch_name, date, movie_id,
  movie_name, created_at)`
- `imax_overrides(movie_id, status, created_at)`
- `bot_meta(key, value)`

Migrations are applied in place at startup; existing databases keep their data.

## Bot flow

Inline keyboards only, minimal typing, three short onboarding screens on first
`/start`, then a dashboard with the next watch and the free/supporter limit.

- **Language first**: before onboarding or any command, a new user chooses
  Egyptian Arabic (default) or American English. Existing users see the picker
  once. Deep links are remembered and resumed after the choice. Settings and
  `/language` switch the interface later; the choice is stored per user, and
  background messages use the recipient's language while admin notices use the
  admin's language.
- **Add a watch**: branch → date → movie → showtime → format filter (when
  formats exist) → confirmation. Movie info, synopsis and an external trailer
  button are available before confirming.
- **Search**: typo-tolerant Arabic/English movie search that jumps straight to
  the matching movie.
- **My watches**: paged list with per-watch management (format filter, quiet
  behaviour, remove), "remove all" with confirmation, and a clear empty state.
- **Settings**: quiet hours, cancellation alerts, discovery subscription and its
  filters, data controls.
- **Support**: the manual donation flow.
- **Feedback**: one free-text message forwarded to the admin.
- Every screen keeps Back/Home navigation and breadcrumbs.
- Alert messages include a button that opens the booking page and a button to
  stop alerts for that watch; discovery alerts can create a watch in one tap
  (respecting the limit).
- Deep links: `?start=w<watch_id>` and `?start=b<branch_id>`, usable only by
  their owner.
- Commands:
  - public: `/start`, `/add`, `/search`, `/watches`, `/settings`, `/language`,
    `/help`, `/cancel`, `/privacy`, `/delete_me`;
  - admin (registered only in the admin's private scope): `/admin`, `/status`,
    `/grant`, `/revoke`, `/imax`.

## Fair-use limits

- Free users: 2 active watches (`FREE_WATCH_LIMIT`).
- Supporters: 10 active watches (`SUPPORTER_WATCH_LIMIT`). Nothing else is
  gated; alert speed and quality are identical for everyone.
- When a user hits the limit, show a friendly message explaining it and offering
  the Support menu, without nagging.
- When the limits change, existing users above the new limit keep the watches
  with the nearest `expires_at`; the excess is deactivated silently and each
  affected user is told once.
- Per-user anti-spam: `USER_RATE_LIMIT_PER_MINUTE` bot actions per minute
  through a middleware; excess actions get a polite "استنى شوية" and are
  ignored.

## Support / donations

Donations are voluntary and never required to use the core features. The bot
stores no card or bank data.

- The Support menu explains, in the user's chosen language, that the bot is free,
  that running it has costs, and that donations are optional.
- Methods: Vodafone Cash and InstaPay only. The number comes from
  `DONATION_PHONE` and is shown in an easy-to-copy format.
- Flow: the user taps "حوّلت ✅", sends a screenshot or the transfer reference,
  and the bot stores a `pending` donation with the file reference.
- The admin receives the proof with the user id, method, amount and note, plus
  ✅/❌ inline buttons.
- Approve grants the supporter flag and the 10-watch limit exactly once
  (idempotent). Reject records the decision and tells the user politely.
- `DONATION_MIN_AMOUNT` is 50 EGP. A smaller amount is flagged as
  `below_minimum`; the admin still sees a warning and may approve it.
- There is no automatic verification and no Telegram Stars flow.

## Public stats and feedback

- `/stats` (everyone): alerts sent today and this week, active watches and
  active users. Aggregates only, never user data. `daily_stats` is updated once
  per day.
- Feedback: the user sends one free-text message; it is stored and forwarded to
  the admin. One feedback per user per hour.

## Security, privacy and legal

- The bot only sends booking links. It never logs in to a cinema site, never
  submits bookings, never handles tickets or card data.
- Minimum data: `telegram_id`, watches, subscriptions, supporter flag,
  donations, and feedback. A username is stored only inside feedback rows.
- `/privacy` explains exactly what is stored and why, in the user's chosen
  language.
- `/delete_me`: after a confirmation button, permanently delete the user's row,
  watches, subscriptions, feedback, donations and proof references; only
  anonymous counters remain.
- Add a disclaimer in `/help` and the README: the bot is unofficial, not
  affiliated with VOX Cinemas or Renaissance Cinemas, availability data can be
  delayed or wrong, and booking happens on the cinema's own site.
- The README must include a "Terms of use of the source site" section: review
  each cinema's terms before scaling, keep request volume low as designed, and
  remove or disable the provider if requested.
- Validate all callback data and user input; parameterized SQL only; handle
  Telegram errors without leaking tracebacks to users; secrets only in `.env`.
- Admin-only commands check `ADMIN_ID` on every call.

## Copy

All user-facing text is simple Egyptian-dialect Arabic by default, with a full
American English catalog for users who choose it. Every string lives in
`i18n/ar.py` and `i18n/en.py`; the two files expose the same names and
signatures, and `strings.py` resolves the active one. Messages are short and end
with an obvious next action. Support copy is warm, short and non-pushy. The
language picker itself is bilingual so a new user can recognize their language
immediately.

## Versioning

Every release has a Semantic Versioning number. `version.py` is the single source
of truth; it is displayed in `/help`, Settings, the admin panel and the startup
log. `CHANGELOG.md` records what changed in each release, and the matching Git tag
is `vX.Y.Z`.

## Quality

- Structured logging, a global error handler and graceful shutdown.
- If a provider returns an unexpected format, log it, alert the admin and keep
  running from cache.
- `/admin` (admin only): active users and watches, supporters, requests/min,
  cache hit ratio, active targets, slowdown factor, circuit-breaker state, last
  poll, discovery state, events today, broadcasts sent, queue length and the
  running version.
- `/status` (admin only): provider outage state, last success, last error
  reason, breaker, active targets and affected watches.
- Tests cover: diff/event logic with mocked providers; coalescing (requests equal
  due targets); 429 storms and the circuit breaker; stale-data suppression;
  watch expiry and retention; donation approval/rejection idempotency;
  free vs supporter limits; `/delete_me`; discovery baseline, one-shot events,
  flapping and the daily cap; the VOX, Renaissance and Premiere parsers;
  keyboards and UI copy; catalog parity and English purity; the language gate
  and persistence; and version / changelog consistency.
- `ruff check` and `ruff format --check` are clean; the suite runs without a
  Telegram token or network access.

## Future (not built)

More cinemas can be added without touching the watcher, discovery or bot
layers: the provider contract and the `provider` columns already isolate them.
The in-app cinema picker (VOX, Renaissance and Premiere side by side) is built.

## Deliverables

The shipped project: application modules, `requirements.txt`,
`requirements-dev.txt`, `pyproject.toml`, `pytest.ini`, `.env.example`, tests,
`scripts/cli_test.py` (VOX smoke test) and `scripts/update_imax_list.py`
(IMAX snapshot generator), plus a README with local setup, configuration,
low-volume design, privacy notes and troubleshooting, and a `CHANGELOG.md` that
tracks each version.
