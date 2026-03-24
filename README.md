# Telegram Bot — F1 & Productivity Updates

Sends automated Telegram messages:
- **Morning briefing** (7:00 AM Czech time) — Linear tasks, Google Calendar events, next F1 race countdown
- **F1 race result** (after race completes) — Top 10 + Driver & Constructor standings
- **F1 session result** (after any qualifying/practice) — Lap times with gaps

Runs automatically via **GitHub Actions**.

---

## Project Structure

```
telegram_bot/
├── main.py                   # Entry point (morning | f1_check)
├── requirements.txt
├── .github/
│   └── workflows/
│       └── bot.yml           # Cron schedule + manual dispatch
└── bot/
    ├── __init__.py
    ├── calendar.py           # Google Calendar integration
    ├── f1.py                 # OpenF1 + Ergast fallback
    ├── linear.py             # Linear GraphQL API
    ├── scheduler.py          # Message routing logic
    └── telegram.py           # Telegram sendMessage wrapper
```

---

## Setup

### 1. Install dependencies (local testing)

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

| Variable | Description |
|---|---|
| `TELEGRAM_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (use [@userinfobot](https://t.me/userinfobot)) |
| `LINEAR_API_KEY` | Personal API key from **Linear → Settings → API** |
| `GOOGLE_CALENDAR_CREDENTIALS` | Full JSON of a service account key or OAuth2 token |

### 3. Google Calendar credentials

**Option A — Service Account (recommended for automation):**
1. Create a service account in [Google Cloud Console](https://console.cloud.google.com) with **Google Calendar API** enabled.
2. Download the `.json` key file.
3. Share your primary calendar with the service account email (Editor or Viewer).
4. Copy the entire JSON file content as the `GOOGLE_CALENDAR_CREDENTIALS` secret.

**Option B — OAuth2 token JSON:**
Run `google-auth-oauthlib` locally once to generate a token, then supply the token JSON as the secret.

### 4. Add GitHub Secrets

Go to **Repo → Settings → Secrets and variables → Actions** and add all four secrets listed above.

### 5. GitHub Actions schedule

The workflow runs automatically:
- `0 6 * * *` — morning briefing at **6:00 UTC** (7:00 AM CET / 8:00 AM CEST)
- `*/30 * * * *` — F1 session checker every **30 minutes**

You can also trigger it manually from the **Actions** tab.

---

## Local Testing

```bash
# Morning briefing
python main.py morning

# F1 session check
python main.py f1_check
```

---

## F1 Data Sources

| Source | Used for |
|---|---|
| [OpenF1 API](https://api.openf1.org) | Session detection, lap times, positions |
| [Ergast API](https://ergast.com/api/f1) | Race countdown, standings (fallback) |

> [!NOTE]
> The Ergast API is being deprecated; standings may fall back gracefully if it goes offline. OpenF1 is used for all live session data.
