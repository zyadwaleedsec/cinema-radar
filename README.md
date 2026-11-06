<p align="center">
  <img src="assets/logo-4096.png" width="170" alt="Cinema Radar logo">
</p>

<h1 align="center">Cinema Radar</h1>

A Telegram bot that watches **VOX Cinemas** and **Renaissance Cinemas** showtimes
in Egypt for you.

Pick a branch, date, movie and showtime. Cinema Radar checks it quietly in the
background and messages you the moment booking opens — or when a sold-out show
frees up seats.

It is a **public bot**: anyone with the link can use it, no invitation or
allowlist is required. It is unofficial, free to use, and **never** books or
pays for you. Every alert has one button that opens the cinema's own booking
page.

---

## What it does

- 🌍 **Arabic or English** — pick your language on first launch and change it
  anytime from Settings. Every screen, alert and error follows your choice.
- 🎯 **Watch one showtime, a whole movie/day, or every open day at a branch.**
- 🪑 **Seat threshold** — ask for 1–4 seats or a custom count (1–10) and only
  get the seat alert once that many are free.
- 🎭 **Filter by format** — IMAX, 4DX, VIP, MAX, DBOX, 3D and whatever the
  selected cinemas actually sell; changing branches never leaves a dead filter.
- 🏢 **Two cinemas** — VOX and Renaissance run together; pick one in-app, or
  limit to a single cinema with `PROVIDERS` in `.env`.
- 🔔 **Instant alerts** when booking opens, seats come back, or new showtimes appear.
- 🌍 **All-cinemas watch** — pick a movie, a day and morning/evening, and watch
  every show in that period across VOX and Renaissance at once.
- 🆕 **Optional release alerts** for new movies, new dates and Coming Soon titles.
- 🔎 **Search in Arabic or English**, typos included — an Arabic name finds the
  English title the cinema actually lists, and Arabic queries fall back to TMDB.
- 🎬 **Movie cards** with a TMDB poster, duration, rating, language, synopsis and
  trailer. In Arabic, alerts and cards use the Arabic title and overview.
- 🌙 **Quiet hours**, per-watch alert modes, and a clean paged watch list.
- 🔐 **Privacy first** — an explicit consent screen appears before anything is
  stored, `/delete_me` clears the bot's data, no card details are requested and
  no phone number is ever required.
- ✨ **Polished screens** — clear dividers, status icons, progress bars and
  colored primary/confirm/delete actions.

The interface is fully bilingual — **Egyptian Arabic** (default) and **American
English**. Almost every step is an inline button; you only type a movie name when
searching or a custom quiet-hours range. You choose the language before anything
else, and Settings (`/language`) changes it later.

Current release: **v2.8.2** - see [`CHANGELOG.md`](CHANGELOG.md).

---

## Limits and support

| | Free | Supporter |
| --- | --- | --- |
| Active watches | 2 | 10 |
| Alert speed | same | same |
| Price | 0 EGP | one-off donation of 50 EGP or more |

Support is voluntary and **one-off** (not a subscription). Donate via Vodafone
Cash or InstaPay, send the screenshot inside the bot, and the admin approves it
manually. No Telegram Stars and no recurring payments.

---

## Quick start

You need **Python 3.12** and a bot token from
[@BotFather](https://t.me/BotFather).

```bash
git clone https://github.com/zyadwaleedsec/cinema-radar.git
cd cinema-radar
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and set these values:

| Key | What to put |
| --- | --- |
| `BOT_TOKEN` | the token from @BotFather (required) |
| `ADMIN_ID` | your numeric Telegram id (from @userinfobot) |
| `DONATION_PHONE` | optional; the Vodafone Cash / InstaPay number users see |
| `PROVIDERS` | comma-separated cinemas, default `vox,renaissance` |
| `PROVIDER` | fallback brand for single-cinema mode |
| `TMDB_READ_TOKEN` | optional TMDB API read token; enables posters |

Without `ADMIN_ID`, admin commands and admin alerts stay disabled; without
`DONATION_PHONE`, the manual donation flow is hidden.

Then run:

```bash
python -m main
```

That's it. The bot uses long polling, so you do not need a domain, webhook, open
port or TLS certificate.

### BotFather settings

Before the first run, open [@BotFather](https://t.me/BotFather) → your bot:

- **Bot Settings → Threaded Mode → off.** Leaving it on can group replies in
  unexpected ways in private chats.
- Leave group privacy as it is — the bot only needs private chats.
- Do not add commands manually: they are registered automatically at startup,
  in both Arabic and English.

> Want it online 24/7? See [`DEPLOY.md`](DEPLOY.md) for a step-by-step Fly.io
> deployment (Docker, volume, secrets, logs). For keeping it alive on your own
> laptop, see
> [`docs/TECHNICAL.md`](docs/TECHNICAL.md#deployment-on-a-local-laptop).

---

## Commands

| Command | For | What it does |
| --- | --- | --- |
| `/start` | everyone | Open the dashboard |
| `/add` | everyone | Add a watch, step by step |
| `/search` | everyone | Find a movie by name |
| `/watches` | everyone | Manage your watches |
| `/settings` | everyone | Quiet hours, filters and data controls |
| `/language` | everyone | Switch between Arabic and English |
| `/help` | everyone | Help and disclaimer |
| `/privacy` | everyone | What is stored and how to delete it |
| `/delete_me` | everyone | Erase your data |
| `/cancel` | everyone | Cancel the current step |

Admins also get `/admin`, `/status`, `/grant`, `/revoke` and `/imax`. Those
commands never appear in the public menu.

---

## Documentation

| File | What is inside |
| --- | --- |
| [`DEPLOY.md`](DEPLOY.md) | Deploying online on Fly.io, step by step: Docker, volume, secrets, logs, troubleshooting |
| [`docs/TECHNICAL.md`](docs/TECHNICAL.md) | How it works: provider parsing, polling, cache, languages, versioning, full configuration, deployment, troubleshooting |
| [`docs/SPEC.md`](docs/SPEC.md) | Product specification and behaviour details |
| [`CHANGELOG.md`](CHANGELOG.md) | Every release, newest first |
| [`scripts/cli_test.py`](scripts/cli_test.py) | Live VOX smoke test |

---

## Privacy

Cinema Radar asks for **explicit consent before storing anything**. Once you
agree, it stores what it needs to run: your Telegram id, language and
preferences, your watches, optional discovery filters, your supporter flag, and
any donation proof or feedback you send. Declining leaves no row behind. It
never asks for card or bank details, never requires a phone number, and never
logs in to the cinema site.

Anything you type yourself in a donation note or feedback — including a phone
number or email — is stored exactly as you wrote it. `/delete_me` deletes every
row the bot stored; messages and photos already delivered in Telegram remain in
the chat.

`/privacy` explains this inside the bot; `/delete_me` erases the bot's data.

---

## Disclaimer

Cinema Radar is **not affiliated with, endorsed by or sponsored by VOX
Cinemas or Renaissance Cinemas**. Showtime data can be delayed, incomplete or
wrong — always confirm on the cinema's official website. Booking, payment and
tickets happen entirely on the cinema's site.

The IMAX snapshot in `data/imax_films.json` is derived from Wikipedia and is
licensed **CC BY-SA 4.0**.

Movie posters are provided by **TMDB**. This product uses the TMDB API but is
not endorsed or certified by TMDB. Cinema-scraped poster URLs are not stored or
sent by the bot.

Contact: **zyad.waleed.sec@gmail.com** · Bot: **[@RadarElCinemaBot](https://t.me/RadarElCinemaBot)**.
