# Technical documentation

Implementation notes for developers and operators. For a friendly overview, see
[`README.md`](../README.md).

## Contents

1. [Project structure](#project-structure)
2. [Brand assets](#brand-assets)
3. [Languages and versioning](#languages-and-versioning)
4. [VOX Cinemas Egypt: what we found](#vox-cinemas-egypt-what-we-found)
5. [Renaissance Cinemas provider](#renaissance-cinemas-provider)
6. [Premiere Cinemas provider](#premiere-cinemas-provider)
7. [Low-volume design](#low-volume-design)
8. [Configuration](#configuration)
9. [IMAX data](#imax-data)
10. [Watch retention](#watch-retention)
11. [Local setup](#local-setup)
12. [Tests, lint and audit](#tests-lint-and-audit)
13. [UI QA checklist](#ui-qa-checklist)
14. [Deployment on a local laptop](#deployment-on-a-local-laptop)
15. [Security and privacy](#security-and-privacy)
16. [Terms of use of the source site](#terms-of-use-of-the-source-site)
17. [Troubleshooting](#troubleshooting)

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
├── tmdb.py                 # TMDB title/year lookup, posters and localised copy
├── metadata.py             # cached Arabic titles/overviews + Arabic search aliases
├── posters.py              # cached TMDB poster resolution (never scraped URLs)
├── consent.py              # explicit first-run consent version + pending choice
├── support.py              # repeatable manual donations and admin approval
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
│   ├── premiere.py         # Premiere Cinemas JSON API provider
│   ├── renaissance.py      # Renaissance Cinemas provider and parsers
│   └── vox.py              # VOX Egypt provider and pure HTML parsers
├── data/imax_films.json    # generated IMAX snapshot (CC BY-SA 4.0, see below)
├── assets/                 # brand mark (logo.svg + PNG exports)
├── docs/
│   ├── TECHNICAL.md        # this file
│   └── SPEC.md             # product specification
├── scripts/cli_test.py     # live VOX smoke test
├── scripts/update_imax_list.py  # regenerates the IMAX snapshot
├── tests/                  # pytest suite (275 tests)
├── requirements.txt
├── requirements-dev.txt
├── ruff.toml               # ruff lint/format configuration
├── Dockerfile              # slim runtime image (worker, no HTTP port)
├── fly.toml                # Fly.io app: region, volume, single machine
├── DEPLOY.md               # step-by-step online deployment guide
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
- `LanguageMiddleware` runs before the rate limiter. It loads the user row
  **without creating one**, and for an unchosen user it shows the bilingual
  picker instead of running the handler. The operator sees the picker on
  `/start` as well; only the hidden admin commands bypass it, defaulting to
  Arabic.
- After the language, a first-time user sees the **consent screen**. Nothing is
  persisted until they tap **I agree**: the chosen language is kept in memory
  (`consent.py`). Accepting writes `users.lang`, `consent_at` and
  `consent_version`; declining leaves no row. Existing rows with a lower
  `consent_version` see the screen again. `/privacy` and `/language` remain
  readable while the gate is open.
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

Copy uses one editorial shape everywhere:

- **Title** — one emoji and a bold headline, followed by the light `DIVIDER`.
- **Blocks** — facts on their own lines, separated by blank lines. Emoji are
  reserved for titles, buttons and list items, not for every fact row. Use the
  private `_blocks(...)` helper instead of manual
  `"\n\n".join(...)`; it drops empty blocks.
- **Close** — one short, human line, with no emoji except the `👇` hint on
  chooser screens. Confirmation screens can stop at their `✅` title.
- **Arabic** — warm Egyptian dialect, short lines, no heavy MSA phrasing.
- **English** — concise American English and sentence case.
- **Stability** — copy changes must not alter flows, callback data or dynamic
  values. Tests pin a few phrases (seat and watch counts, digest wording, times
  and the English welcome line), so keep those anchors intact.

### Arabic metadata and search

`metadata.py` wraps the TMDB client so display copy can follow the interface
without touching matching:

- **Matching stays English.** `TmdbClient.resolve()` still searches `en-US`;
  the IMAX snapshot, dedupe and provider titles therefore behave exactly as
  before.
- **Display is localised.** When the reader's language is Arabic, alerts and
  movie cards ask for `ar-SA` and use the Arabic title and overview. Any
  failure, missing translation or English interface silently keeps the
  provider copy.
- **Caching.** A positive answer is cached for 30 days, a miss for one day, and
  an in-process memo avoids repeated SQLite reads within one screen or alert
  batch.
- **Arabic search.** A query containing Arabic letters asks TMDB for candidate
  titles, then re-ranks the *original English titles* against the real cinema
  listing. A loose translation simply produces no match; English queries never
  call TMDB.

### Format filter

`PROVIDER_FORMATS` in `providers/base.py` lists the formats each cinema chain
sells. `available_formats(branch_ids, enabled_providers)` unions the selected
branches' chains (an empty branch filter means every enabled cinema) and orders
the result by `CANONICAL_FORMATS`. The settings screen only renders those
buttons; an unknown callback value is rejected, and changing branches clears a
stored format the new selection cannot serve.

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
other evasion.

The VOX edge also inspects the User-Agent. Any value containing an email
address, a URL (`://`) or the substring `bot` is answered with
`curl: (92) HTTP/2 stream 1 reset by server`. Cinema requests therefore send a
browser-shaped UA that still names the project:

```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 CinemaRadar/<version>
```

The contact address travels in the standard `From` header, plus `X-Bot-Name` and
`X-Bot-Contact`. `upstream_user_agent()` rewrites an unsafe `HTTP_USER_AGENT`
override to this default rather than letting it break every poll. APIs that
want a fully identified caller (TMDB) use `IDENTIFIED_USER_AGENT`
(`CinemaRadarBot/<version> (+https://...; contact: ...)`) instead.

If a request fails with an HTTP/2 stream reset, the client discards the session,
pins HTTP/1.1 for the next one and retries once before counting a failure. If
VOX blocks us anyway, the bot slows down, opens the circuit breaker, tells the
admin (reason, place, last success, retry ETA and the number of watches on the
failing target), and sends one recovery message when VOX is back. A first failure
is reported as a temporary problem; the outage wording and "alerting paused"
note are only sent when the breaker actually trips. An HTTP 404/410 for one
branch/date means that listing does not exist yet: it is logged and retried, but
it never pages the admin, opens the breaker, or slows unrelated targets. While an
incident is open, alerts are paused: the watcher never diffs stale cache. Menus
may still show the last known data with an age warning.

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

## Renaissance Cinemas provider

Renaissance runs alongside VOX and Premiere by default
(`PROVIDERS=vox,renaissance,premiere`). Set `PROVIDERS=renaissance` to run the
same bot against only
[`rnscinemas.com`](https://rnscinemas.com). The provider lives in
`providers/renaissance.py` and implements the same `CinemaProvider` contract,
so the watcher, scheduler, cache, alerts and discovery need no changes.

### Multi-cinema

`ProviderRegistry` holds one `CinemaProvider` per enabled cinema. The add and
search flows show a cinema picker (`🎬`) first when more than one cinema is
enabled, then the existing branch → date → movie → showtime steps. Branch ids
are unique across the shipped providers, so branch filters, discovery state and
deep links are keyed `provider:<branch>`. Legacy `?start=b<branch>` deep links
and pre-migration branch filters default to VOX.

When a search term matches a coming-soon title, the date picker starts at that
title's first screening day instead of "today": the provider's coming-soon page
publishes a release date per movie (VOX as `Release Date:` on the card), and
`handlers.watches._dates_from_release` trims every earlier day from the branch
strip / all-cinemas union. Days the strip has not reached yet yield an honest
"no dates", and titles without a published date are left untouched.

### Pages used

| Page | Purpose |
| --- | --- |
| `/en/cinemas` | Branch list; also `/ar/cinemas` has Arabic names |
| `/en/cinemas/<slug>` | Ten-day date strip + first day's showtimes |
| `/en/cinemas/<slug>/DD-MM-YYYY` | Every movie/session for one day |
| `/en/movie/<slug>` | Poster, duration, rating, synopsis, trailer |
| `/en/coming-soon` | Announced releases |

The site is server-rendered; no JSON API is required. Date URLs accept any
`DD-MM-YYYY` value, so a watch can fetch a date outside the visible ten-day
strip. The strip itself is still ten days, so `get_dates` returns that window
and new dates appear as the window rolls forward.

Coming Soon titles can be bookable far ahead (for example a December premiere
while the strip still ends mid-November). Their bookable dates live on each
movie page, not the branch page, so `refresh_prebook_dates` scans the
coming-soon movie pages on the `PREBOOK_DATES_TTL` cadence and merges those
dates into `get_dates`.

### Parsing rules

- Available sessions: `<a class="js-booking-confirm-link" data-booking-url=...>`.
- Sessions closed for online booking: `<a class="disabled">`; the page tells
  users to buy at the cinema. The bot maps these to `SOLD_OUT` (status-based
  alerts only).
- Time: `data-event-time` (`04:30 PM`) normalized to 24-hour `HH:MM`.
- Title: `data-movie-name-en`; branch/date from the page URL and `data-*`.
- Hall: the format heading (`VIP`, `Regular`, `Premium`, `DBOX`, `Balcone`,
  `Special`) plus `3D` when `data-is-3d="1"`; `Regular` maps to `Standard`.
- After-midnight sessions are moved to the next calendar day.
- The same booking id can appear under several format headings; the provider
  merges those and keeps the more specific hall (VIP over Standard).

### Known limitations

- **No seat counts.** Renaissance does not expose `seats_available`; watches
  detect availability status changes and new showtimes, not a seat total.
- **No explicit "not on sale" status.** A day with no sessions means no data;
  `disabled` means online booking is closed / box office only.
- **Ten-day date strip** (arbitrary date URLs still work if you know the date).
- **Cloudflare** fronts the site; `HTTP_IMPERSONATE=chrome124` is recommended.
  There is no `ETag`/`Last-Modified`, so conditional requests cannot help.
- HTML can change; parser tests live in `tests/test_renaissance.py`.

---

## Premiere Cinemas provider

Premiere ([`premiere-cinemas.com`](https://premiere-cinemas.com)) is a Next.js
site backed by its own public JSON API. The provider lives in
`providers/premiere.py`; it implements the `CinemaProvider` contract and only
adds the `showtimes_per_movie` capability described below. The five branches
are Nile Cinema, Premiere Plaza, Galaxy elManial, Premiere Point90 and Cima
Arkan (API ids `1`–`5`).

### Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/hybrid/get-now-showing-movies?lang_id=1` | Every film with its playable dates and branch list |
| `GET /api/v1/hybrid/get-movie-show-times/<unique>?fromDate=YYYY-MM-DD&lang_id=1` | Every branch's sessions for one film and day |
| `GET /api/v1/hybrid/get-movie-show-dates/<unique>?cinema_id=N` | One film's sellable days at one branch |

The identifier in the showtimes path is the listing's
`movie_unique_identifier` (for example `6901.192`), not the numeric
`movie_id`. Older watches stored the numeric id, so the provider resolves it
through the listing before fetching. `Movie.id` and `Movie.slug` are the
unique identifier.

### Token and headers

The API expects `Authorization: Bearer <jwt>`. That token is public: it is
embedded in the site's layout bundle
(`/_next/static/chunks/app/[lang]/layout-<hash>.js`). The provider reads the
home page once, extracts the layout URL from the HTML (or the home document
itself), then extracts the JWT; it is cached for `PREMIERE_TOKEN_TTL` and
shared behind an `asyncio.Lock` so a burst of snapshot requests does not
re-download the bundle. A `401`/`403` triggers one forced token refresh.

Requests deliberately omit the `x-web-security` header. Without it the API
answers plain JSON; with it the response is `{"encryptedData": ...}`. The
provider also does **not** send the shared browser-shaped `Accept` header
(it contains `application/xml` and `*/*`, which the Premiere edge tarpits);
token requests use `Accept: text/html` for the home page and `*/*` for the
bundle, while API calls send `Accept: application/json`.

If the API ever starts returning `encryptedData` regardless of headers, the
contract has changed: the provider latches off (`_encrypted`), reports one
parse failure so the admin is alerted once, and raises instead of returning
empty showtimes. An empty day would otherwise look like every session
disappeared and create false alerts.

### One request per movie, not per branch

`PremiereProvider.showtimes_per_movie = True`. A movie+date response is
grouped by cinema and already contains all five branches, so:

- the watcher passes `movie_id` to `get_showtimes()` and keys request
  coalescing by `provider:date:movie`, not `provider:branch:date:movie`;
- the response is cached by movie+date (`movie_showtimes_key`) and the
  branch filter is applied in memory;
- discovery's branch overview shares a single daily snapshot
  (`day_snapshot_key`): one request per movie playing that day (~19),
  cached for `PREMIERE_SNAPSHOT_TTL` (10 minutes). A partial snapshot raises
  rather than committing half a day, which would trigger false "session
  disappeared" alerts. Branch overviews read this snapshot instead of
  refetching per branch.

`get_showtimes()` without a `movie_id` returns an empty list instead of
firing a whole-day fan-out; every bot call path supplies the movie.

### Parsing rules

- Branch and time: `cinema_id` and `ss_start_time` (`15:30`, 24-hour).
- Date: `ss_actual_start_date` is the real calendar day, so a `00:30`
  session listed under the previous day's schedule moves to the next day.
  `ss_start_date` is the fallback.
- Title: `movie_title`; `movie_experience` is the hall/experience (`PREMIUM`,
  `LUXE`, `CineComfort`, `Plus`, `MAX`, `MX4D`, `Standard`).
- `mf_name` `3D` appends `3D` to the experience when it is not already there.
- Duration/language/rating/synopsis from `movie_runtime`, `lang_name`,
  `ratings[0].rating`, `movie_plot`; posters come from TMDB only.
- Coming Soon: a title whose first `show_dates` entry is later than today.
  The date picker starts at that first screening day, not
  `movie_release_date`.
- Sessions are `AVAILABLE` with `seats_available = None`; there is no
  sold-out flag.

### Known limitations

- **No seat counts or sold-out state.** Watches alert on new sessions and
  availability changes, never a specific freed seat.
- **Listing dates are a union across branches.** A title's `show_dates` may
  include a day a specific branch does not actually play, so that branch can
  offer a day with no sessions.
- **Experience names are kept verbatim.** `LUXE`, `CineComfort`, `Plus` and
  `MX4D` are Premiere concepts and are never mapped to VOX's VIP/Premium.
- **Public token can rotate.** Re-reading the bundle refreshes it; if the
  bundle URL or token shape changes, the provider reports a parse failure and
  the admin is alerted.
- **Cloudflare blocks some datacenter ranges.** The site and API answer `403`
  from Fly's Paris (`cdg`) range and work from Frankfurt (`fra`), so
  `fly.toml` keeps the bot in `fra`. A fresh deployment must use a region that
  Premiere serves.
- Parser tests live in `tests/test_premiere.py`.

---

## Low-volume design

1. **Per-target heap scheduler** — no global polling cycle. Each
   `(provider, branch, date, movie)` target has its own `next_run` with ±20%
   jitter.
2. **Adaptive intervals** — 100 s open-with-seats, 60 s waiting, 120 s sold
   out, 480–720 s for dates more than 7 days away, 12 s burst near opening.
3. **Request coalescing** — one in-flight fetch per
   `provider:branch:date`, or `provider:date:movie` for per-movie providers
   such as Premiere; all watchers of that target await the same future.
4. **Two-level cache** — memory + SQLite, with stale-while-revalidate and
   persistence across restarts. Menus read only from cache and label old data.
   Alerting paths pass `allow_stale=False`, so an outage can never produce a
   false alert.
5. **Conditional requests** — `If-None-Match` / `If-Modified-Since` plus a
   SHA-256 body hash to skip unchanged pages.
6. **Global token bucket** — 1 request/second by default, max 2 connections.
7. **AIMD backoff** — on 429/403/5xx/timeout, double the affected target and
   global slowdown; recover gradually on successes; honor `Retry-After`. A
   404/410 is treated as "this branch/date has no listing" and is not counted.
8. **Circuit breaker** — after 3 consecutive failures, pause all upstream
   requests for 2–4 minutes, then probe once. The admin gets one message when
   the outage starts (with the reason, retry ETA and the watches on the failing
   target) and one when it recovers.
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
(default one hour), and movie details are cached for a week. When one cycle
produces several updates for the same branch they ship as a single digest with
at most twelve lines; any remainder is summarised as "and N more updates"
(`MAX_DIGEST_LINES`, chosen to stay well below the photo-caption limit). Each
showtime line also caps at six visible times. The digest stores each movie's
branch, date, every showtime seen, artwork and booking URL as JSON in
`discovery_actions.payload`; tapping "watch a movie" therefore creates the
watch locally instead of fetching showtimes again.

That quick watch covers the whole movie on the alert's day
(`scope="movie"`, `showtime="*"`, `hall_type="*"`, expiring at 23:59 local), not
one screening, so a later seat return or a new hall is still covered. Before
sending, the broadcaster skips an event for any subscriber who already has an
active watch for the same provider, branch, movie and date whose alert mode
would deliver it: this removes the near-duplicate message the watcher and
discovery used to send together, while a seats-only watch still lets new-movie
news through. All subscriber watches are loaded in one bulk query per cycle.
Every alert also carries a public link button: a single-movie alert points at
that movie's page on the cinema site, while a digest points at the branch page
(Premiere falls back to its now-showing listing). Renaissance URLs are
rewritten to the reader's language, and the link is assembled from the slug/id
we already hold and is never fetched by the bot. The stop button switches all
movie alerts off, states the scope plainly and offers a one-tap undo.

The cross-cinema window watch ("All cinemas") stores one `scope="movie"` row
per branch that has the movie, all sharing a `group_id` so the watch limit
counts them once. The watcher filters the diff by `time_window` (morning /
evening, split by `MORNING_END_HOUR`) so only shows in the chosen period alert.
The day list and the movie's shows are read once per branch from the normal
cached pages — no extra endpoints.

Seat alerts compare the freed-seat count with the watch's `required_seats`
(1–10, default `1`). `SEATS_AVAILABLE` fires when a showtime newly reaches the
threshold — either a `SOLD_OUT -> AVAILABLE` transition or a rise inside
`AVAILABLE` that crosses it — and stays quiet once the count was already enough,
until it drops below and climbs again. When the provider does not report a count
(`None`) the alert still fires, so a missing field never hides a returned seat.
Movie and all-dates watches apply the threshold to each showtime separately,
never to a sum across halls. The value is set during the add flow (step 5 of 6)
and can be changed from **Manage watch**.

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
| `DONATION_PHONE` | — | Shared manual donation account (never hard-coded) |
| `DONATION_VODAFONE` | `DONATION_PHONE` | Vodafone Cash account shown to users |
| `DONATION_INSTAPAY` | `DONATION_PHONE` | InstaPay number or address shown to users |
| `CHANNEL_ID` | empty | Optional public channel for discovery posts |
| `BOT_USERNAME` | empty | Bot @username for deep links; filled at startup |
| `UI_RENDERER` | `auto` | `auto` = rich with classic fallback, `rich`, or `classic` |
| `DB_PATH` | `cinemaradar.sqlite3` | SQLite file |
| `TIMEZONE` | `Africa/Cairo` | Quiet hours, daily caps, stats |
| `PROVIDERS` | `vox,renaissance,premiere` | Comma-separated enabled cinemas |
| `PROVIDER` | `vox` | Fallback brand for single-cinema mode |
| `VOX_BASE_URL` | `https://egy.voxcinemas.com` | VOX provider base URL |
| `RENAISSANCE_BASE_URL` | `https://rnscinemas.com` | Renaissance provider base URL |
| `PREMIERE_BASE_URL` | `https://premiere-cinemas.com` | Premiere site (public layout bundle) |
| `PREMIERE_API_URL` | `https://mifcentral-api.premiere-cinemas.com` | Premiere JSON API base |
| `PREMIERE_TOKEN_TTL` | `43200` | Seconds before the public bearer token is re-read |
| `PREMIERE_SHOWTIMES_TTL` | `600` | Seconds a movie+date response is reused |
| `PREMIERE_SNAPSHOT_TTL` | `600` | Seconds a whole-day snapshot is reused |
| `HTTP_USER_AGENT` | browser UA ending in `CinemaRadar/<version>` | Cinema UA; never put an email, URL or "bot" in it (VOX resets those) |
| `HTTP_IMPERSONATE` | empty | e.g. `chrome124` (needs `curl_cffi`) |
| `TMDB_USER_AGENT` | fully identified bot UA | API UA; names the bot and contact address |
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
| `WATCHER_SYNC_INTERVAL` | `120` | Seconds between watch reconciliation/expiry sweeps |
| `WATCH_ALERT_COOLDOWN` | `600` | Per-watch duplicate cooldown |
| `WATCH_RETENTION_DAYS` | `3` | Days a closed watch is kept before hard deletion |
| `MORNING_END_HOUR` | `17` | Split hour: shows before it are "morning", at/after "evening" |
| `IMAX_DATA_PATH` | `data/imax_films.json` | Local IMAX snapshot path |
| `TMDB_READ_TOKEN` | empty | Optional TMDB read token (title normalisation + posters) |
| `TMDB_TIMEOUT` | `10` | TMDB request timeout (seconds) |
| `CACHE_POSTER_TTL` | `2592000` | TMDB poster cache TTL (30 days; misses retry after 1 day) |
| `ALL_DATES_MAX` | `21` | Technical cap on days expanded per all-days watch |
| `ALL_DATES_REFRESH` | `1200` | Seconds between branch date-list refreshes |
| `DISCOVERY_INTERVAL` | `480` | Per-branch discovery interval |
| `DISCOVERY_DAILY_CAP` | `10` | Max discovery messages per user/day |
| `DISCOVERY_FLAP_WINDOW` | `1800` | Ignore items that flap within this window |
| `COMING_SOON_INTERVAL` | `3600` | How often `/movies/comingsoon` is refreshed |
| `CACHE_COMING_SOON_TTL` | `3600` | Coming Soon listing cache TTL |
| `CACHE_MOVIE_DETAILS_TTL` | `604800` | Duration/rating/language/synopsis/trailer cache (7 days) |
| `PREBOOK_DATES_TTL` | `10800` | How often Renaissance pre-book dates are re-scanned (3 h) |
| `PREBOOK_DATES_MAX_DAYS` | `120` | Horizon for bookable Coming Soon dates |
| `FREE_WATCH_LIMIT` | `2` | Free active-watch limit |
| `SUPPORTER_WATCH_LIMIT` | `10` | Limit after an approved donation |
| `DONATION_MIN_AMOUNT` | `50` | Minimum per donation (EGP); lower amounts are flagged to the admin but can still be approved. A user may donate again after being approved |
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

Discovery alerts are opt-in and their filters are stored on the same
`subscriptions` row. Saving branch, type or hall filters copies the existing
`active` value; only the dedicated toggle in Settings writes `active = 1`, so
adjusting a filter can never quietly start sending alerts. Filters chosen while
the feature is off are kept and take effect when the user turns it on.

---

## IMAX data

`data/imax_films.json` is generated from
[Wikipedia's *List of IMAX films*](https://en.wikipedia.org/wiki/List_of_IMAX_films)
by `scripts/update_imax_list.py`. It is committed with the project, so the bot
never scrapes Wikipedia at runtime. The snapshot is derived from Wikipedia
content and is therefore licensed **CC BY-SA 4.0**; keep the `source` and
`license` fields in the JSON when redistributing it.

TMDB is optional and serves two unrelated jobs behind `TMDB_READ_TOKEN`:

1. **IMAX normalisation** — canonical title/year before matching the snapshot.
   It is not the source of truth: TMDB's `imax` keyword marks screenings, not
   films shot with IMAX cameras.
2. **Official posters** - `posters.py` resolves a cached TMDB image URL for every
   movie card and alert, including discovery alerts and public-channel posts
   (resolved by `Broadcaster`). Cinema-scraped poster URLs are stripped at the
   provider boundary, and existing watch rows containing VOX/Renaissance image
   URLs are cleared on startup. With no token, the bot sends text-only cards.

If the token is empty, IMAX matching is name-based and the snapshot still works.
Put the token in `.env` only; rotate it if it was ever shared in chat. TMDB
attribution is shown in `/privacy` and on the consent screen: *This product uses
the TMDB API but is not endorsed or certified by TMDB.*

To refresh the snapshot:

```bash
python scripts/update_imax_list.py
```

The script is a development/maintenance tool, not part of the running bot.

---

## Watch retention

Each watch stores `expires_at` (UTC). Single-showtime watches expire when that
screening starts, whole-day movie watches when the latest showtime starts, and
all-days watches at 23:59 on the last bookable day they follow. The watcher
still ticks every `WATCHER_TICK` second to fire due targets, but reconciliation
(`sync_targets`) runs at most once per `WATCHER_SYNC_INTERVAL` because new
watches are scheduled directly when they are created. During a reconciliation
the watcher:

1. backfills `expires_at` for older rows,
2. closes due watches and sends **one grouped message per user**
   (`expiry_notified` prevents duplicates; a failed send is retried next cycle),
3. closes any remaining past-date rows, and
4. hard-deletes watches closed more than `WATCH_RETENTION_DAYS` ago
   (`watch_baselines` rows cascade with them).

Manual removals set `expiry_notified` so they are never announced; they still
disappear after the retention window.

---

## Manual support and donations

The bot never handles card details and never activates a transfer
automatically. A user opens **Support the project**, picks Vodafone Cash or
InstaPay, sees the configured account (`DONATION_PHONE`, or the method-specific
`DONATION_VODAFONE` / `DONATION_INSTAPAY`), transfers manually, and sends proof
inside the bot. The proof can be a photo, an image sent as a document, or a
transaction ID.

`SupportService.create_manual()` stores the row as `pending` and forwards the
proof to `ADMIN_ID` with the donor's name, Telegram username (when set), numeric
Telegram ID, and **Approve** / **Reject** buttons (`dn:a:<id>` / `dn:r:<id>`).
Approving sets `is_supporter = 1` and the watch limit to
`SUPPORTER_WATCH_LIMIT`; rejecting changes nothing. Both decisions are
idempotent. A repeat donation from an existing supporter is still forwarded and
thanked, but does not change the limit again. Photos reach the admin as photos;
documents reach the admin as documents. Telegram Stars are intentionally not
supported.

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
- `DONATION_PHONE` - shared Vodafone Cash / InstaPay account shown to users
- `DONATION_VODAFONE` / `DONATION_INSTAPAY` - optional per-method overrides
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

Expected: `244 passed`.

The core tests do not require a Telegram token or network access. They use a
fake clock, a temporary SQLite database and mocked providers.

```bash
python -m ruff check .
python -m ruff format .
python -m pip_audit -r requirements.txt
```

Configuration lives in [`ruff.toml`](../ruff.toml). `ruff` and
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
      screen; choosing English opens the consent screen in English, and no row is
      created until **I agree**.
- [ ] Declining consent stores nothing and offers a button to review it again.
- [ ] `/privacy` and `/language` still work while the consent gate is open.
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
- [ ] Posters are TMDB images (or text-only when `TMDB_READ_TOKEN` is empty); no
      VOX/Renaissance image URL appears in alerts or the database.
- [ ] Deep links `?start=w<id>` and `?start=b<branch>` work for their owner only.
- [ ] `/start` shows only the public commands; admin commands appear only in the
      admin's private chat.
- [ ] Run with `UI_RENDERER=classic` to confirm the fallback has identical copy
      and buttons.

---

## Deployment on a local laptop

The bot uses long polling, so it needs no inbound ports, domain or public IP.
Run exactly one long-polling process per bot token. Pending updates are not
discarded on startup, so a `/start` sent while the process restarts is answered
as soon as polling resumes.

1. Install Python 3.12 and create a virtual environment:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill `BOT_TOKEN`, `ADMIN_ID` and
   `DONATION_PHONE` (or `DONATION_VODAFONE` / `DONATION_INSTAPAY`).
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
- The bot never logs in to a cinema site, never books, never pays, and never
  handles tickets.

---

## Terms of use of the source sites

This project is an **unofficial** monitoring tool. Before scaling it, the
developer/operator **must review the terms of service of the cinema they
monitor** (VOX Cinemas or Renaissance Cinemas) and any applicable Egyptian law.
The design intentionally keeps request volume very low (one global request per
second, max two connections, jittered per-target intervals, conditional
requests, caching, circuit breaker). Do not raise these limits to scrape
aggressively. If a cinema asks you to stop, or changes its terms,
**disable or remove the provider** (`PROVIDERS` / `providers/vox.py` or
`providers/renaissance.py`) and keep the rest of the bot running with another
provider.

The bot only sends links to the cinema's own site. It does not bypass
authentication, access booking or seat-map pages, or automate purchases.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `BOT_TOKEN is missing` | `.env` not created or not loaded; copy `.env.example` |
| VOX requests time out / reset | Install `curl_cffi` and set `HTTP_IMPERSONATE=chrome124` |
| `curl: (92) HTTP/2 stream 1 reset` | The UA contains an email, a URL or "bot"; use the built-in value. The client also retries over HTTP/1.1 once |
| `HTTP_USER_AGENT` override ignored | Unsafe overrides are replaced by the browser-safe default; check the startup warning |
| Admin alert says "temporary problem" | One upstream failure; it escalates to "is down" only when the breaker trips |
| `ZoneInfoNotFoundError` | `pip install tzdata` (already in requirements) |
| Bot starts but no alerts | Check `/status`: VOX state, last success, breaker and affected watches. While an outage is open, alerts are paused on purpose |
| Breaker stays open | VOX is blocking or down; wait for the pause and check logs |
| `database is locked` | Only one bot process should use the same SQLite file |
| Discovery sends nothing | First run stores a baseline by design; new items appear later |

Logs are structured JSON on stdout, which works well with `journalctl`.
