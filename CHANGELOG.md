# Changelog

All notable changes to Cinema Radar are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org):

- **MAJOR** — a change every user must adapt to.
- **MINOR** — a new capability that stays backward compatible.
- **PATCH** — a fix or copy change with no behaviour change.

## [Unreleased]

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

[Unreleased]: https://github.com/zyadwaleedsec/cinema-radar/compare/v2.4.0...HEAD
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
