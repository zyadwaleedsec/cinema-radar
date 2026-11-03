<p align="center">
  <img src="assets/logo-4096.png" width="170" alt="Cinema Radar logo">
</p>

<h1 align="center">Cinema Radar</h1>

A Telegram bot that watches **VOX Cinemas Egypt** showtimes for you.

Pick a branch, date, movie and showtime. Cinema Radar checks it quietly in the
background and messages you the moment booking opens — or when a sold-out show
frees up seats.

It is unofficial, free to use, and **never** books or pays for you. Every alert
has one button that opens the cinema's own booking page.

---

## What it does

- 🎯 **Watch one showtime, a whole movie/day, or every open day at a branch.**
- 🎭 **Filter by format** — IMAX, 4DX, VIP, MAX, 3D and whatever VOX lists.
- 🔔 **Instant alerts** when booking opens, seats come back, or new showtimes appear.
- 🆕 **Optional release alerts** for new movies, new dates and Coming Soon titles.
- 🔎 **Search in Arabic or English**, typos included (سبايدر مان → Spider-Man).
- 🎬 **Movie cards** with poster, duration, rating, language, synopsis and trailer.
- 🌙 **Quiet hours**, per-watch alert modes, and a clean paged watch list.
- 🔐 **Privacy first** — `/delete_me` removes everything; no cards, no phone numbers.

The interface is 100% Egyptian Arabic and 100% inline buttons — no typing needed.

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

Open `.env` and fill three values:

| Key | What to put |
| --- | --- |
| `BOT_TOKEN` | the token from @BotFather |
| `ADMIN_ID` | your numeric Telegram id (from @userinfobot) |
| `DONATION_PHONE` | the Vodafone Cash / InstaPay number users should see |

Then run:

```bash
python -m main
```

That's it. The bot uses long polling, so you do not need a domain, webhook, open
port or TLS certificate.

> Want it to keep running after you close the laptop? See the deployment notes in
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
| [`docs/TECHNICAL.md`](docs/TECHNICAL.md) | How it works: VOX parsing, polling, cache, full configuration, deployment, troubleshooting |
| [`docs/SPEC.md`](docs/SPEC.md) | Product specification and behaviour details |
| [`scripts/cli_test.py`](scripts/cli_test.py) | Live VOX smoke test |

---

## Privacy

Cinema Radar stores only what it needs to send your alerts: your Telegram id,
your watches, optional discovery filters, your supporter flag and any donation
proof you send. It never stores card numbers, bank details, phone numbers or seat
maps, and it never logs in to VOX.

`/privacy` explains everything inside the bot; `/delete_me` erases it all.

---

## Disclaimer

Cinema Radar is **not affiliated with, endorsed by or sponsored by VOX
Cinemas**. Showtime data can be delayed, incomplete or wrong — always confirm on
the cinema's official website. Booking, payment and tickets happen entirely on
the cinema's site.

The IMAX snapshot in `data/imax_films.json` is derived from Wikipedia and is
licensed **CC BY-SA 4.0**.
