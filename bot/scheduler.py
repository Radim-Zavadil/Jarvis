"""
scheduler.py — decides which bot action to trigger based on context.

Triggered modes:
  - "morning"   → daily briefing (7:00 AM Prague time)
  - "f1_check"  → F1 session checker (stateless — checks if a session just ended)
"""

from __future__ import annotations

from datetime import datetime

import pytz

from bot import f1, calendar, linear, telegram

CZECH_TZ = pytz.timezone("Europe/Prague")


def run_morning_briefing(force: bool = False) -> None:
    """Compose and send the daily morning briefing."""
    now_prague = datetime.now(CZECH_TZ)
    
    # Only run at 7:00 AM Prague time unless forced (to avoid duplicate triggers)
    if not force and now_prague.hour != 7:
        print(f"[scheduler] Skipping morning briefing (it is {now_prague.hour}:00, expected 7:00)")
        return

    tasks = linear.fetch_tasks()
    events = calendar.fetch_today_events()
    countdown = f1.next_race_info()

    tasks_section = linear.format_tasks_section(tasks)
    calendar_section = calendar.format_calendar_section(events)

    day = str(now_prague.day)
    date_str = now_prague.strftime(f"%A, %B {day}, %Y")
    greeting = f"🌅 <b>Good morning Radim!</b>\n<i>{date_str}</i>"

    message = "\n\n".join([greeting, tasks_section, calendar_section, countdown])
    telegram.send_message(message)


def run_f1_check() -> None:
    """
    Check for a newly completed F1 session and send a result if one ended
    within the last 35 minutes (stateless — no /tmp required).
    """
    session = f1.get_latest_completed_session()
    if not session:
        print("[scheduler] No session ended in the freshness window.")
        return

    session_name = session.get("session_name", "").lower()
    session_key = session.get("session_key", "?")
    print(f"[scheduler] Fresh session detected: {session_name} (key={session_key})")

    if session_name == "race":
        msg = f1.format_race_result(session)
    else:
        msg = f1.format_session_result(session)

    telegram.send_message(msg)
    print(f"[scheduler] Result sent for session {session_key}.")
