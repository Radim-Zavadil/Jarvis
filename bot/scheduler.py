"""
scheduler.py — decides which bot action to trigger based on context.

Triggered modes:
  - "morning"   → daily briefing (invoked by the 6:00 UTC cron)
  - "f1_check"  → F1 session checker (invoked by the */30 cron)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytz

from bot import f1, calendar, linear, telegram

CZECH_TZ = pytz.timezone("Europe/Prague")

# Sessions already sent (persisted via env var set before run, or in-memory
# across the GitHub Actions run which is stateless per invocation).
# We use a simple file-based state to prevent double-sending.
STATE_FILE = "/tmp/f1_sent_sessions.txt"


def _load_sent_sessions() -> set[str]:
    try:
        with open(STATE_FILE) as fh:
            return {line.strip() for line in fh if line.strip()}
    except FileNotFoundError:
        return set()


def _save_sent_session(session_key: str) -> None:
    with open(STATE_FILE, "a") as fh:
        fh.write(f"{session_key}\n")


def run_morning_briefing() -> None:
    """Compose and send the daily morning briefing."""
    tasks = linear.fetch_tasks()
    events = calendar.fetch_today_events()
    countdown = f1.next_race_info()

    tasks_section = linear.format_tasks_section(tasks)
    calendar_section = calendar.format_calendar_section(events)

    now_prague = datetime.now(CZECH_TZ)
    day = str(now_prague.day)
    date_str = now_prague.strftime(f"%A, %B {day}, %Y")
    greeting = f"🌅 *Good morning Radim!*\n_{date_str}_"

    message = "\n\n".join([greeting, tasks_section, calendar_section, countdown])
    telegram.send_message(message)


def run_f1_check() -> None:
    """Check for a newly completed F1 session and send a result message if found."""
    session = f1.get_latest_completed_session()
    if not session:
        print("[scheduler] No completed session found.")
        return

    session_key = str(session["session_key"])
    sent = _load_sent_sessions()

    if session_key in sent:
        print(f"[scheduler] Session {session_key} already sent.")
        return

    session_name = session.get("session_name", "").lower()
    print(f"[scheduler] New completed session: {session_name} (key={session_key})")

    if session_name == "race":
        msg = f1.format_race_result(session)
    else:
        msg = f1.format_session_result(session)

    telegram.send_message(msg)
    _save_sent_session(session_key)
    print(f"[scheduler] Sent result for session {session_key}.")
