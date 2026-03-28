"""
telegram.py — sends messages via the Telegram Bot API.
"""

import os
import requests
import html


TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram (handles &, <, >)."""
    return html.escape(str(text), quote=False)


def send_message(text: str) -> None:
    """Send an HTML-formatted message to the configured chat."""
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"[telegram] Message sent (status={resp.status_code})")
