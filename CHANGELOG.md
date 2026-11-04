# Changelog

All notable changes to Cinema Radar are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org):

- **MAJOR** — a change every user must adapt to.
- **MINOR** — a new capability that stays backward compatible.
- **PATCH** — a fix or copy change with no behaviour change.

## [Unreleased]

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

[Unreleased]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/zyadwaleedsec/cinema-radar/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/zyadwaleedsec/cinema-radar/releases/tag/v1.0.0
