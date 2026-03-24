"""
telegram.py — sends messages via the Telegram Bot API.
"""

import os
import requests


TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(text: str) -> None:
    """Send a plain-text (Markdown) message to the configured chat."""
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"[telegram] Message sent (status={resp.status_code})")
