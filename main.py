"""
main.py — entry point for the Telegram bot.

Usage:
    python main.py morning     # run the daily morning briefing
    python main.py f1_check    # check for a completed F1 session and send result
    python main.py render      # run as a web server for Render deployment
"""
import os
import sys
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from bot.scheduler import run_morning_briefing, run_f1_check

app = Flask(__name__)

@app.route("/")
def health_check():
    """Health check endpoint for Render."""
    return "Bot is alive!", 200

@app.route("/morning")
def trigger_morning():
    """Manually trigger the morning briefing via URL."""
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
        # Get port from environment variable (default to 8080)
        port = int(os.environ.get("PORT", 8080))
        print(f"[main] Starting Flask server on port {port}...")
        app.run(host="0.0.0.0", port=port)
    else:
        print(f"[main] Unknown mode: {mode!r}. Use 'morning', 'f1_check', or 'render'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
