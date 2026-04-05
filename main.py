"""
main.py — entry point for the Telegram bot.

Usage:
    python main.py morning     # run the daily morning briefing
    python main.py f1_check    # check for a completed F1 session and send result
    python main.py render      # run as a web server for Render deployment

Scheduling strategy:
    APScheduler BackgroundScheduler is used instead of the `schedule` library.
    It starts automatically when this module is imported (i.e. by Gunicorn),
    which means it works correctly on Render without any extra env-var tricks.

    UptimeBot should ping / every 14 minutes to prevent Render free-tier
    spin-downs.  The /morning and /f1_check endpoints can also be called
    directly from UptimeBot as a belt-and-suspenders backup.
"""
import os
import sys
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from bot.scheduler import run_morning_briefing, run_f1_check

app = Flask(__name__)

# ── APScheduler ────────────────────────────────────────────────────────────
# Import here so the scheduler only starts once (gunicorn imports main once
# per worker; BackgroundScheduler handles the threading internally).
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

CZECH_TZ = pytz.timezone("Europe/Prague")

_scheduler = BackgroundScheduler(timezone=CZECH_TZ)

# Morning briefing at exactly 07:00 Prague time every day
_scheduler.add_job(
    run_morning_briefing,
    CronTrigger(hour=7, minute=0, timezone=CZECH_TZ),
    id="morning_briefing",
    replace_existing=True,
)

# F1 session check every 5 minutes (race-week messages + post-race results)
_scheduler.add_job(
    run_f1_check,
    IntervalTrigger(minutes=5),
    id="f1_check",
    replace_existing=True,
)

_scheduler.start()
print("[main] APScheduler started — morning@07:00 CET, f1_check every 5 min.")
# ───────────────────────────────────────────────────────────────────────────


@app.route("/")
def health_check():
    """Health check endpoint for Render / UptimeBot."""
    return "Bot is alive!", 200


@app.route("/morning")
def trigger_morning():
    """Manually trigger the morning briefing via URL (e.g. UptimeBot at 07:00)."""
    try:
        run_morning_briefing(force=True)
        return "Morning briefing triggered successfully.", 200
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/f1_check")
def trigger_f1():
    """Manually trigger the F1 session check via URL."""
    try:
        run_f1_check()
        return "F1 check triggered successfully.", 200
    except Exception as e:
        return f"Error: {str(e)}", 500


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py [morning|f1_check|render]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "morning":
        force = "--force" in [a.lower() for a in sys.argv]
        print(f"[main] Running morning briefing (force={force})...")
        run_morning_briefing(force=force)
    elif mode == "f1_check":
        print("[main] Running F1 session check...")
        run_f1_check()
    elif mode == "render":
        # Scheduler already started above at import time.
        # Just run Flask so Gunicorn has something to serve.
        port = int(os.environ.get("PORT", 8080))
        print(f"[main] Starting Flask server on port {port}...")
        app.run(host="0.0.0.0", port=port)
    else:
        print(f"[main] Unknown mode: {mode!r}. Use 'morning', 'f1_check', or 'render'.")
        sys.exit(1)


if __name__ == "__main__":
    main()