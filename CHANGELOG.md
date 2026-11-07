# Changelog

All notable changes to Cinema Radar are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org):

- **MAJOR** — a change every user must adapt to.
- **MINOR** — a new capability that stays backward compatible.
- **PATCH** — a fix or copy change with no behaviour change.

## [Unreleased]

## [3.3.0] - 2026-11-07

### Added

- Manual support now accepts a **Vodafone Cash** and an **InstaPay** account,
  configured separately with `DONATION_VODAFONE` / `DONATION_INSTAPAY` (both
  fall back to `DONATION_PHONE`).
- Users can donate **more than once**. Each proof is forwarded to the admin;
  approving it keeps the 10-watch supporter limit, and the admin sees when a
  donation comes from an existing supporter.
- Proof can be a photo, an image sent as a document, or a transaction ID.
  Documents are forwarded to the admin as documents instead of being dropped.

## [3.2.2] - 2026-11-07

### Fixed

- A watch created from the add-watch flow now keeps the cinema the user picked.
  Premiere and Renaissance choices used to be saved as VOX, so the watcher asked
  VOX about foreign branch ids and the watch never worked.
- A missing branch or date (HTTP 404/410) is no longer reported as a cinema
  outage: it does not page the admin, open the circuit breaker, or slow down
  every other target. The admin alert now counts the watches on the failing
  target instead of the whole scheduler.

## [3.2.1] - 2026-11-07

### Fixed

- Messages sent while the bot is restarting (for example `/start` during a
  deploy) are no longer discarded. Polling keeps pending updates and answers
  them as soon as it resumes.

## [3.2.0] - 2026-11-07

### Added

- Discovery alerts now have a one-tap undo: stopping movie alerts shows what was
  switched off and offers **Turn alerts back on** right away.
- Settings, `/help` and onboarding explain how to turn movie and showtime
  alerts on, and Settings shows a hint while they are off.

### Changed

- The quick watch from a discovery alert now follows the whole movie on that
  day (every showtime and hall) instead of one screening, so a later seat
  return or a new slot is not missed.
- Editing branch, type or hall filters no longer opts a user into discovery
  alerts; only the explicit toggle does. Filters chosen while it was off are
  remembered.
- Discovery skips an event when an active watch already covers the same
  branch, movie and date with a mode that would deliver it, removing the
  near-duplicate message the watcher and discovery used to send together.
- A digest shows at most 12 updates and a showtime line at most 6 times, with
  the rest summarised, so a long batch cannot exceed Telegram's caption limit.
- Renaissance movie and branch links now open in the reader's language.

### Fixed

- An expired discovery alert now says the alert is old instead of showing a
  generic error.
- The settings toggle is named **Movie and showtime alerts**, matching the
  dates and showtimes it actually covers.

## [3.1.0] - 2026-11-06

### Added

- Discovery alerts now carry a link button next to "watch" and "stop":
  a single-movie alert opens that movie's public page at VOX, Renaissance or
  Premiere, while a multi-movie digest opens the branch/cinema page. The links
  are built locally from data already on hand and are never fetched by the bot.

## [3.0.0] - 2026-11-06

### Added

- **Premiere Cinemas** is now a third cinema: Nile Cinema, Premiere Plaza,
  Galaxy elManial, Premiere Point90 and Cima Arkan. Showtimes come from
  Premiere's own public JSON API, including after-midnight sessions and the
  exact experience names it sells (`PREMIUM`, `LUXE`, `CineComfort`, `Plus`,
  `MAX`, `MX4D`, `Standard`).
- Premiere appears in the cinema picker, all-cinemas watches, discovery,
  coming-soon dates, search, format filters, alerts and onboarding.
- Coming-soon titles from Premiere start their date picker at the first
  screening day supplied by the API, not the marketing release date.
- `PROVIDERS` now defaults to `vox,renaissance,premiere`. A pinned deployment
  value must include `premiere` to enable the new cinema.
- New settings: `PREMIERE_BASE_URL`, `PREMIERE_API_URL`,
  `PREMIERE_TOKEN_TTL`, `PREMIERE_SHOWTIMES_TTL` and `PREMIERE_SNAPSHOT_TTL`.

### Changed

- The provider contract gained `showtimes_per_movie`. For Premiere one
  movie+date request covers all five branches, so requests are coalesced and
  cached per movie and day instead of per branch. Discovery shares a daily
  snapshot so five branch overviews cost one batch rather than five times the
  traffic.
- `HttpClient.get()` accepts per-request headers, used for the bearer token and
  the API's `Accept` header.

### Notes

- Premiere publishes no seat counts and no sold-out flag, so its sessions are
  listed as available and watch alerts fire on new sessions rather than a
  freed-seat total.
- If Premiere ever returns encrypted responses, the provider stops and alerts
  the admin once instead of reporting empty showtimes.
- The Fly deployment moved from `cdg` (Paris) to `fra` (Frankfurt): Premiere's
  Cloudflare edge returns `403` to the Paris address range. The SQLite volume
  was restored from a consistent backup, and the old `cinema_data` volume is
  left in `cdg` as a rollback copy.

## [2.8.4] - 2026-11-06

### Changed

- Rewrote every user-facing screen in Egyptian Arabic and American English with
  a consistent editorial layout: emoji and bold title, divider, short separated
  blocks, and a human closing line. This covers onboarding, the dashboard,
  adding a watch, the watch list and its settings, alerts, settings, support,
  feedback, admin screens and error messages.
- Moved the last hardcoded Arabic labels into the language catalogs: donation
  amounts, approve/reject, feedback categories, the all-dates label, and the
  custom-amount prompt and below-minimum warning. English screens no longer fall
  back to Arabic text.
- Tightened the visual style: emoji now appear only in titles, buttons and list
  items, cards use a lighter divider, and every screen closes with one short
  line. The Egyptian dialect was softened in alerts and support messages.

## [2.8.3] - 2026-11-06

### Changed

- The watcher no longer rescans and rewrites the whole watch table on every
  one-second tick. Reconciliation, expiry sweeps and retention cleanup now run
  at most once per `WATCHER_SYNC_INTERVAL` (120 seconds by default); newly
  created watches are still scheduled immediately.
- Discovery broadcasts are isolated per subscriber: a broken or unexpected row
  is logged and skipped instead of stopping delivery for everyone else.
- Branch date caches and discovery scheduling keys are scoped by provider, so
  two cinemas that share a branch id can never read each other's data.

### Performance

- Added a partial index for snoozed watches and an index on discovery action
  timestamps to keep the maintenance queries cheap as data grows.

## [2.8.2] - 2026-11-06

### Fixed

- Discovery alerts that bundle several updates now list every one of them. The
  digest no longer stops at six lines with an "and N more updates" note, and
  each line carries a small icon for its type (released, new movie, new date or
  new showtimes).
- The "watch a movie" button on a discovery alert works again. It now asks which
  movie you mean and shows one button per movie from that alert; the watch is
  created from the alert data with no extra cinema request, so an upstream
  hiccup can no longer turn the button into an error.
- The alert now stores the Telegram user id with its action, so the person who
  received the alert is recognised when they tap its buttons.

## [2.8.1] - 2026-11-06

### Fixed

- The add-watch date picker no longer offers days before a coming-soon movie is
  out. When the search matches a title on the coming-soon page, the date list
  starts at the first screening day any cinema publishes for it (Dune: Part
  Three, for example, now starts on 17 December instead of today). The Arabic
  title bridge works here too, so an Arabic search gets the same trimming.

## [2.8.0] - 2026-11-05

### Added

- Arabic movie names in alerts and cards: watch alerts, reminders, discovery
  cards and the public channel now use the Arabic TMDB title and overview when
  the reader's interface is Arabic. Matching still runs in English, so IMAX
  detection, dedupe and provider titles are unchanged, and any lookup failure
  silently keeps the provider copy.
- Arabic-name search: typing an Arabic movie name finds the English title that
  the cinema actually lists. TMDB is only consulted when the query contains
  Arabic letters, and its suggestions are re-ranked against real listings.

### Changed

- The format filter only offers formats the selected cinemas actually sell, and
  changing branches clears a filter the new selection cannot serve.
- Format buttons are laid out two per row, with an explicit all-formats row.

## [2.7.3] - 2026-11-05

### Fixed

- VOX requests failed with `curl: (92) HTTP/2 stream 1 reset by server`. The VOX
  edge resets any request whose User-Agent contains an email address, a URL or
  the word "bot", and the transparent UA from 2.7.0 contained all three. Cinema
  requests now use a browser-shaped UA ending in `CinemaRadar/<version>`, while
  the contact address travels in the standard `From`, `X-Bot-Name` and
  `X-Bot-Contact` headers. TMDB keeps the fully identified bot UA.
- An unsafe `HTTP_USER_AGENT` override (one containing an email, a URL or "bot")
  is replaced with the safe default instead of breaking every poll.
- An HTTP/2 stream reset now retries once over HTTP/1.1 with a fresh session, so
  a single edge quirk does not open the circuit breaker.

### Changed

- A first upstream failure is reported as "temporary problem with …" instead of
  "… is down". Only a tripped circuit breaker sends the outage wording and says
  that alerts are paused, which matches what the bot actually does.
- Outage and recovery admin alerts name the correct provider (`VOX` or
  `Renaissance`), use explicit RTL marks and blank lines between blocks, and
  truncate long transport errors.
- Discovery no longer sends a second raw-error alert for transport failures that
  the shared HTTP layer already reported.

## [2.7.2] - 2026-11-05

### Changed

- Arabic discovery cards now use explicit RTL marks on every line, with Latin
  branch names and showtimes wrapped in LTR isolates. This keeps Arabic words
  from being re-ordered around English names and digits.
- The copy is more colloquial Egyptian Arabic and every block (title, poster
  details, cinema, date, showtimes, call to action) is separated by a blank line
  so the card is easier to scan.
- English cards follow the same airy layout.

## [2.7.1] - 2026-11-05

### Changed

- Discovery alerts are redesigned as a readable card: a TMDB poster, the movie
  title, the cinema brand and branch on one line, the date, the showtimes and a
  short call to action. The same layout is used for new movies, new dates and
  released upcoming movies, and in the public channel.
- Discovery alerts now resolve their poster through the same cached TMDB service
  as watch alerts, so they never fall back to cinema-scraped artwork.
- The discovery buttons now carry the bell icons used elsewhere in the bot.

## [2.7.0] - 2026-11-05

### Added

- Explicit first-run consent. Nothing is written to the database until the user
  taps **I agree**; choosing a language keeps the choice in memory only. The
  consent screen lists what is stored, why, how long it is kept, how to erase it
  with `/delete_me`, and the contact address. Declining stores nothing. Bumping
  `consent.CONSENT_VERSION` asks everyone to consent again.
- TMDB poster artwork. Cinema-scraped image URLs are no longer stored, cached or
  sent; movie cards and alerts use TMDB-hosted posters when `TMDB_READ_TOKEN` is
  configured, and fall back to text-only cards otherwise. TMDB attribution is
  shown in `/privacy` and the consent screen.
- The bot is now documented and operated as a public bot for everyone, not a
  private circle.

### Changed

- Every upstream request now sends a transparent User-Agent:
  `CinemaRadarBot/<version> (+https://t.me/RadarElCinemaBot; contact:
  zyad.waleed.sec@gmail.com)`. TMDB requests use the same value.
- Existing watches with stored VOX or Renaissance poster URLs are cleared on
  startup; they keep working text-only.

## [2.6.0] - 2026-11-05

### Added

- Watches can now require a minimum number of free seats. The add flow asks
  "how many seats?" as step 5 of 6 with quick buttons **1–4** and a
  **custom number** option (1–10). Seat alerts only fire when a showtime has at
  least that many seats free; an unknown count still alerts so nothing is
  missed. Movie and all-dates watches apply the requirement per showtime.
- The seat requirement can be changed later from **Manage watch**, and is shown
  on the watch list and watch settings screen.
- Feedback sent to the admin now shows the sender's `@username`, then their
  first name, then the Telegram ID, with the ID kept in a small reference line.

## [2.5.2] - 2026-11-05

### Added

- [`DEPLOY.md`](DEPLOY.md): a step-by-step Fly.io deployment guide (Docker
  image, volume, secrets, logs, troubleshooting).

### Changed

- Polish pass across every screen: Arabic now uses proper dual and plural forms
  ("مراقبتين", "5 فروع", "4 كراسي", "3 أفلام"), duplicated emojis are gone,
  alert headers are distinct, and freshness/empty-state copy reads more
  naturally. The English catalog received the same fixes.
- Rich messages now follow the selected language direction, so English screens
  are no longer forced right-to-left.
- Morning/evening copy spells out "5 مساءً" / "8 صباحاً" instead of abbreviating
  the period, and the custom quiet-hours prompt matches it.
- `fly.toml` now sets `HTTP_IMPERSONATE=chrome124`, matching `.env`, so VOX
  requests no longer time out on the deployed bot.
- The Docker image is slimmer: runtime dependencies only, no apt packages, no
  `EXPOSE`/health check (the bot is a long-polling worker with no HTTP server).
- Ruff configuration moved to `ruff.toml` so a bare `pyproject.toml` can never
  push Fly.io into its buildpack path again.
- `fly.toml` pins the app to one worker machine with a `/data` volume and a
  20-second shutdown timeout. The VM uses **1 GB** of RAM: 256 MB and 512 MB are
  OOM-killed while scraping.

## [2.5.1] - 2026-11-05

### Fixed

- The morning/evening buttons are now hidden when a period has no shows, and
  the split hour in the copy follows `MORNING_END_HOUR` ("before 5 PM" by
  default).
- The leftover `movie_waits` table from the removed `/wait` feature is dropped
  on startup.

## [2.5.0] - 2026-11-05

### Added

- **Cross-cinema window watch**: the cinema picker now offers `🌍 All cinemas`.
  Pick a movie, then a day, then Morning (before 5 PM) or Evening (from 5 PM),
  and the bot watches every show in that period across all VOX and Renaissance
  branches as one logical watch (`MORNING_END_HOUR` sets the split).

### Removed

- The `/wait <movie>` command and the "wait in all cinemas" buttons; the
  all-cinemas option in the picker replaces them.

## [2.4.0] - 2026-11-04

### Added

- **Movie waits** (`/wait <movie>`): tell the bot a title you're waiting for
  and it messages you once the movie becomes bookable at any cinema — now
  showing or opened for pre-booking. The search screens also offer a
  "wait in all cinemas" button next to "search again".
- Waits match Arabic transliterations and partial English titles (for example
  `افنجرز` → `Avengers: Doomsday`) and are one-shot: after the alert they
  deactivate.
- The limit reuses the normal watch limit (2 free / 10 supporter).

## [2.3.0] - 2026-11-04

### Added

- **Renaissance pre-book dates**: Coming Soon titles that are already bookable
  (for example `Avengers: Doomsday` and `Dune: Part Three` in December) now
  appear in the date picker. The branch page only exposes a ten-day strip, so
  the provider scans the coming-soon movie pages for their bookable dates and
  merges them into the branch list.
- `PREBOOK_DATES_TTL` (default 3 h) and `PREBOOK_DATES_MAX_DAYS` (default 120)
  control how often the scan runs and how far ahead it looks.

## [2.2.0] - 2026-11-04

### Added

- **Multi-cinema support**: VOX and Renaissance run together in one bot. A
  cinema picker (`🎬`) opens before the add/search flow whenever more than one
  provider is enabled, and branch filters are scoped per cinema.
- `PROVIDERS=vox,renaissance` (comma-separated) chooses the enabled cinemas;
  both are on by default. `PROVIDER` is kept for backward-compat as the
  fallback brand in single-cinema mode.
- Discovery now runs per provider (branches, Coming Soon and state are keyed
  per cinema), and `/status` shows one section per enabled cinema plus the
  shared circuit breaker.
- Alerts, reminders and watch cards carry the cinema name (`(فوكس)` /
  `(VOX)`, `(رينيسانس)` / `(Renaissance)`), including seats-back alerts that
  are status-based for Renaissance.

### Changed

- Deep links now accept `?start=b<provider>_<branch>`; legacy `?start=b<branch>`
  links still work and default to VOX.
- Existing branch filters are migrated once from plain ids to `vox:<id>` keys.

## [2.1.0] - 2026-11-04

### Added

- **Renaissance Cinemas Egypt provider**: branches, dates, movies, showtimes,
  movie details and Coming Soon, all parsed from the public server-rendered
  pages.
- `PROVIDER=renaissance` switches the bot to Renaissance; `PROVIDER=vox`
  remains the default. `RENAISSANCE_BASE_URL` is configurable.
- The cinema name in onboarding, help, status, alerts and reason labels is now
  dynamic, so copy says `(فوكس)` / `(VOX)` or `(رينيسانس)` / `(Renaissance)`.
- DBOX, Balcone and Special formats are recognised by the filters.

### Notes

- Renaissance does not expose seat counts. Availability comes from the
  bookable/disabled markup, so seat-count alerts are status-based.
- The provider runs in single-provider mode for now; the cinema picker for
  using both providers in one bot is the next step.

## [2.0.1] - 2026-11-04

### Performance

- The showtimes page is parsed once per fetch instead of three times: the same
  `BeautifulSoup` tree is shared by `parse_showtimes`, `parse_movies` and
  `parse_dates`. Measured on a 155 KB page: **58.8 ms → 21.2 ms** per fetch.
- SQLite now uses a 20 MB page cache, memory temp storage and a 5 s busy
  timeout.
- The main menu callbacks acknowledge the tap before rendering, so slow menu
  builds no longer leave the button spinning.
- The add/search menus show a short loading screen while branches are fetched.

## [2.0.0] - 2026-11-04

### Added

- A shared visual system (`ui/theme.py`): a thin divider under titles, a
  progress bar (`▰▰▱ 2/5`), and one consistent emoji vocabulary across screens.
- Colored inline buttons: blue `primary` for the main action, green `success`
  for confirmations, red `danger` for destructive actions.
- Showtime buttons start with a status icon: `🟢` available, `🔴` sold out,
  `⚪` not on sale yet.
- Watch cards are separated by a divider, with one fact per line.
- Pagination is shown as a non-clickable `page X / Y` button between Previous
  and Next.
- The language picker shows `🇪🇬 العربية` and `🇺🇸 English`.
- Clearer empty states with a large emoji, a short reason and a primary action.
- A unified footer `🎬 Cinema Radar · vX.Y.Z` on help, privacy, settings and the
  admin panel.

### Changed

- Every main screen follows the same rhythm: title → divider → short content →
  action hint, with generous blank lines.
- Rewrote the add-watch steps, alerts, watch list/settings, discovery messages,
  support and admin screens around the new visual system.
- Bumped the version to 2.0.0 because the interface is a visible, coordinated
  redesign rather than a small copy change.

## [1.1.6] - 2026-11-04

### Fixed

- Rich messages (the default renderer) now convert line breaks to `<br>`, so
  every screen keeps its paragraphs, bullets and spacing instead of collapsing
  into one dense block.

### Changed

- Rewrote the main screens — dashboard, add-watch steps, alerts, watch settings,
  help, privacy, support, settings and the admin panel — with one idea per line,
  blank-line sections and consistent separators.
- Privacy copy now states exactly what is stored (including donation notes and
  proof references) and that `/delete_me` clears the bot database, while
  messages already delivered in Telegram stay in the chat.

### Chore

- Removed the leftover test watch from the local database before launch.

## [1.1.5] - 2026-11-04

### Changed

- The cinema name is now always written in parentheses and localized:
  `(فوكس)` / `(فوكس سينما)` in Arabic, `(VOX)` / `(VOX Cinemas)` in English.
  This covers onboarding, help, privacy, status, reason labels, outage alerts
  and the technical place line.

## [1.1.4] - 2026-11-04

### Fixed

- A transient transport error no longer sends a false "VOX is down" alert when
  the retry succeeds. Failures are counted once per logical fetch, after the
  retries are exhausted.
- A transport error now drops the pooled HTTP session before the retry, so a
  stale keep-alive connection cannot make the next attempt fail too.
- curl_cffi timeouts are classified as timeouts instead of generic network
  errors in the admin alert.

### Changed

- Reworked the three welcome screens in both languages: shorter lines, one idea
  per line, and commands at the end of a line for a cleaner RTL layout.
- The outage alert now shows the last success time to the second, and a recovery
  under a minute no longer claims "1 minute".

## [1.1.3] - 2026-11-04

### Fixed

- A deep link (`?start=w…` / `?start=b…`) is no longer lost when a user has
  chosen a language but has not finished onboarding. It is parked and resumed
  when onboarding completes.
- The language picker is throttled to one message every 30 seconds per
  language-less account, closing the only path around the rate limiter.

### Changed

- `/start` and the Home button now greet the user by name, like the onboarding
  and the language picker.

### Docs

- Documented the required BotFather setup (Threaded Mode off) and corrected the
  README claim that every step is button-only.
- `DONATION_PHONE` is now documented as optional: leaving it empty hides the
  manual donation flow.
- Corrected stale references to the catalog module and to Arabic-only privacy
  and support copy.

## [1.1.2] - 2026-11-04

### Fixed

- The operator account now sees the first-run language picker on `/start` too.
  Previously the admin bypassed the gate entirely, so testing with the admin
  account made it look like the picker never appeared.
- Hidden admin commands (`/admin`, `/status`, `/grant`, `/revoke`, `/imax`) and
  donation decisions still work before the admin picks a language.

## [1.1.1] - 2026-11-04

### Changed

- After choosing a language from the first-run picker, the three welcome
  screens now always follow in the chosen language — including for accounts
  that completed onboarding before the picker existed.
- Quiet-hours presets, the quiet-hours header and the confirmation message now
  use readable 12-hour times with AM/PM (`11:00 م` / `11:00 PM`) instead of a
  bare 24-hour clock.

### Fixed

- The custom quiet-hours prompt and error now show both the 24-hour input and
  its 12-hour meaning, so the example is unambiguous.

## [1.1.0] - 2026-11-04

### Added

- **Official English interface.** Every screen, button, alert, error, help page
  and privacy page is available in American English, and the whole interface
  follows one switch.
- **Language picker before anything else.** A new user chooses Arabic or English
  first; existing users see the picker once on their next update. Deep links
  (`?start=b…`, `?start=w…`) are remembered and resumed after the choice.
- **Language switcher in Settings** and a `/language` command, so the choice can
  be changed at any time without losing watches or preferences.
- **Per-user language for background messages.** Alerts, reminders, expiry
  notices, discovery digests and supporter replies use the recipient's language;
  admin and system messages use the admin's own language (Arabic by default).
- **A single version source** (`version.py`) shown in `/help`, Settings, the
  admin panel and the startup log, plus this changelog and the `v1.1.0` tag.
- A bilingual language picker that leads with the Telegram app language when it
  can be detected.

### Changed

- `strings.py` is now a facade over `i18n/ar.py` and `i18n/en.py`; the Arabic
  copy and all call sites are unchanged.
- The stale-data note is rendered per request, so it follows the reader's
  language instead of the language the health loop happened to use.
- Telegram command menus are registered in both Arabic (default scope) and
  English (`language_code="en"`).

### Fixed

- Onboarding no longer starts in Arabic for a user who chose English.
- Admin notices produced by the HTTP client, discovery job, donations and
  feedback no longer depend on the language of the last handled update.

## [1.0.0] - 2026-11-01

### Added

- First public release: watch a showtime, a movie/day or every open day at a
  branch, with instant alerts when booking opens, seats return or new showtimes
  appear.
- Egyptian Arabic interface with inline buttons only.
- Optional discovery alerts for new movies, new dates and Coming Soon titles.
- Quiet hours, per-watch alert modes, hall and format filters.
- Search in Arabic or English, including common transliterations and typos.
- Movie cards with poster, duration, rating, language, synopsis and trailer.
- Privacy controls: `/privacy` and `/delete_me`.
- Free limit of 2 watches; 10 watches for supporters after a one-off 50 EGP
  donation approved by the admin.
- Low-volume VOX polling, circuit breaker and stale-data protection.

[Unreleased]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.3.0...HEAD
[3.3.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.2.2...v3.3.0
[3.2.2]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v3.0.0...v3.1.0
[2.8.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.8.0...v2.8.1
[2.8.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.7.3...v2.8.0
[2.7.3]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.7.2...v2.7.3
[2.7.2]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.7.1...v2.7.2
[2.7.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.7.0...v2.7.1
[2.7.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.5.2...v2.6.0
[2.5.2]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.5.1...v2.5.2
[2.5.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.6...v2.0.0
[1.1.6]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.5...v1.1.6
[1.1.5]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/zyadwaleedsec/cinema-radar/releases/tag/v1.0.0
