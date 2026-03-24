"""
main.py — entry point for the Telegram bot.

Usage:
    python main.py morning     # run the daily morning briefing
    python main.py f1_check    # check for a completed F1 session and send result
"""
from dotenv import load_dotenv
load_dotenv()

import sys
from bot.scheduler import run_morning_briefing, run_f1_check



def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py [morning|f1_check]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "morning":
        print("[main] Running morning briefing...")
        run_morning_briefing()
    elif mode == "f1_check":
        print("[main] Running F1 session check...")
        run_f1_check()
    else:
        print(f"[main] Unknown mode: {mode!r}. Use 'morning' or 'f1_check'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
