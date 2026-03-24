"""
calendar.py — fetches today's events from the user's primary Google Calendar.

Credential strategy (tries each in order):
  1. GOOGLE_TOKEN_JSON env var — serialised OAuth2 token JSON (fastest, for CI)
  2. GOOGLE_CALENDAR_CREDENTIALS env var — service-account JSON
  3. bot/credentials.json local file — OAuth2 client-secrets, runs interactive
     consent flow once and saves the resulting token to bot/token.json.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytz
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CZECH_TZ = pytz.timezone("Europe/Prague")

# Paths for the local OAuth2 flow
_BOT_DIR = Path(__file__).parent
_CREDS_FILE = _BOT_DIR / "credentials.json"
_TOKEN_FILE = _BOT_DIR / "token.json"


def _build_service():
    """Return an authorised Google Calendar API service object."""
    creds = None

    # ── Option 1: token JSON supplied as env var (GitHub Actions / CI) ──────
    token_json_str = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json_str:
        from google.oauth2.credentials import Credentials
        token_data = json.loads(token_json_str)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", SCOPES),
        )

    # ── Option 2: service-account JSON in env var ───────────────────────────
    if creds is None:
        sa_json_str = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")
        if sa_json_str:
            sa_data = json.loads(sa_json_str)
            if sa_data.get("type") == "service_account":
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_info(
                    sa_data, scopes=SCOPES
                )

    # ── Option 3: local credentials.json → OAuth2 installed-app flow ────────
    if creds is None:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        # Load a previously saved token if it exists
        if _TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)

        # If no valid token, run the consent flow (opens browser once)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not _CREDS_FILE.exists():
                    raise FileNotFoundError(
                        f"No Google credentials found. Provide GOOGLE_TOKEN_JSON "
                        f"or GOOGLE_CALENDAR_CREDENTIALS env vars, or place "
                        f"credentials.json in {_BOT_DIR}."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(_CREDS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Persist the token so future runs skip the browser step
            _TOKEN_FILE.write_text(creds.to_json())
            print(f"[calendar] Token saved to {_TOKEN_FILE}")

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def fetch_today_events() -> list[dict]:
    """Return today's calendar events sorted by start time (Czech timezone)."""
    service = _build_service()

    now_prague = datetime.now(CZECH_TZ)
    start_of_day = now_prague.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_prague.replace(hour=23, minute=59, second=59, microsecond=0)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item["start"]
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(CZECH_TZ)
            time_str = dt.strftime("%H:%M")
        else:
            time_str = "All day"
        events.append({"time": time_str, "summary": item.get("summary", "(No title)")})

    return events


def format_calendar_section(events: list[dict]) -> str:
    """Format today's events for the morning briefing message."""
    if not events:
        return "📅 *TODAY'S CALENDAR*\n_Nothing scheduled today_ 🎉"

    lines = ["📅 *TODAY'S CALENDAR*"]
    for ev in events:
        lines.append(f"- {ev['time']} – {ev['summary']}")
    return "\n".join(lines)
