# Deploying Cinema Radar on Fly.io

This guide deploys the bot as a **single long-polling worker** with a **1 GB
volume** that keeps the SQLite database across deploys. No domain, webhook,
public port or TLS certificate is needed.

> The bot must run as **one process per `BOT_TOKEN`**. Two instances polling the
> same token make Telegram answer `409 Conflict` to both.

---

## 0. What you need

| Item | Where to get it |
| --- | --- |
| Fly.io account | https://fly.io/apps — a card may be required even for tiny apps |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `ADMIN_ID` | your numeric id from [@userinfobot](https://t.me/userinfobot) |
| The repo | `https://github.com/zyadwaleedsec/cinema-radar` |

Cost: a 256 MB machine running 24/7 is roughly **$2–3/month** plus a few cents
for the volume. Fly has no permanent free tier for new organisations.

---

## 1. Install `flyctl` (Windows PowerShell)

```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

Close and reopen the terminal, then:

```powershell
fly version
fly auth login
```

`fly auth login` opens the browser; approve the CLI.

---

## 2. Clone the repo

```powershell
git clone https://github.com/zyadwaleedsec/cinema-radar.git
cd cinema-radar
```

You do **not** need Python or Docker on your machine: the image is built on
Fly's remote builder.

---

## 3. Create the app

App names are global on Fly, so `cinema-radar` may already be taken. Pick a
unique name and put the same name in `fly.toml` (`app = "..."`).

```powershell
fly apps create cinema-radar-<something-unique>
```

If you already created an app from the web UI, either reuse it or delete it and
start clean:

```powershell
fly apps destroy cinema-radar      # only if you want a fresh start
```

---

## 4. Create the volume

The volume name **must** be `cinema_data` (see `[[mounts]]` in `fly.toml`) and
it must be in the same region as the machine (`primary_region = "cdg"`).

```powershell
fly volumes create cinema_data --region cdg --size 1 --yes
```

Create exactly **one** volume: one volume = one machine.

---

## 5. Set the secrets

`BOT_TOKEN` and `ADMIN_ID` are secrets, never committed.

```powershell
fly secrets set BOT_TOKEN="123456:ABC..." ADMIN_ID="8644303990"
```

Optional:

```powershell
fly secrets set DONATION_PHONE="01xxxxxxxxx"
fly secrets set CHANNEL_ID="-100xxxxxxxxxx"
```

`DB_PATH` is already set in `fly.toml` to `/data/cinemaradar.sqlite3`.
Everything else (providers, cache TTLs, quiet hours defaults) has a safe
default in `config.py` and can stay unset.

Check what is configured:

```powershell
fly secrets list
```

---

## 6. Deploy

```powershell
fly deploy --remote-only
```

`--remote-only` builds on Fly, so Docker Desktop is not required. The first
build takes a few minutes.

After the deploy:

```powershell
fly status
fly scale count 1          # must be 1, never 2
fly logs
```

`fly logs` should show `Cinema Radar v2.5.1 starting` and no traceback.

---

## 7. Verify in Telegram

1. Open your bot and send `/start`.
2. Pick a language, then `/status` as the admin: it should answer.
3. Add one watch with `/add` and wait for the next poll cycle.

---

## 8. Update a running bot

```powershell
git pull
fly deploy --remote-only
```

The volume is not touched: users, watches and settings survive the deploy.

---

## 9. Useful commands

| Command | Why |
| --- | --- |
| `fly logs` | live logs (startup errors, polling conflicts) |
| `fly status` | machine state and image |
| `fly scale count 1` | force a single instance |
| `fly apps restart cinema-radar` | restart without rebuilding |
| `fly ssh console` | shell inside the machine |
| `fly volumes list` | check the volume exists |
| `fly secrets list` | check configured secrets (values hidden) |
| `fly apps destroy cinema-radar` | delete everything |

Back up the database:

```powershell
fly ssh console -C "cp /data/cinemaradar.sqlite3 /data/backup.sqlite3"
fly sftp get /data/backup.sqlite3 .\cinemaradar-backup.sqlite3
```

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `bash: gunicorn: command not found` | Fly used a buildpack, not the Dockerfile | `fly.toml` must contain `[build] dockerfile = "Dockerfile"` |
| `No dependencies found in pyproject.toml` | A `pyproject.toml` without `[project]` made the launcher pick buildpacks | keep only `ruff.toml` (this repo) or add real `[project]` dependencies |
| `Missing or invalid check type` | old `[checks]` block | this repo has no checks; the bot has no HTTP server |
| `needs volumes with name 'cinema_data'` | volume not created, or in another region | `fly volumes create cinema_data --region cdg --size 1 --yes` |
| `409 Conflict: terminated by other getUpdates request` | two machines or two machines running the bot | `fly scale count 1`, and stop any local instance |
| `database is locked` | bot running twice on the same SQLite file | keep one machine, never share one volume between machines |
| Machine restarts in a loop | bad token / missing secret | `fly logs`, then re-check `fly secrets list` |
| `instance refused connection ... :8080` | leftover `[http_service]` from the web launcher | remove it (already removed here) |

---

## 11. Alternative: run it on your own PC

If you only need it for yourself, a PC is free:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
# edit .env: BOT_TOKEN, ADMIN_ID
python -m main
```

See `docs/TECHNICAL.md` → *Deployment on a local laptop* for keeping it alive
with Task Scheduler.
