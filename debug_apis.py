"""Debug script to test Linear and Calendar APIs directly."""
from dotenv import load_dotenv
load_dotenv()

import os, json, requests

# ── Linear ────────────────────────────────────────────────────────────────────
print("=" * 60)
print("LINEAR DEBUG")
print("=" * 60)

LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY", "")
print(f"API key present: {bool(LINEAR_API_KEY)}")
print(f"API key starts with: {LINEAR_API_KEY[:12]}...")

QUERY = """
query {
  viewer {
    id
    name
    email
    assignedIssues(
      filter: {
        and: [
          { state: { type: { neq: "completed" } } }
          { state: { type: { neq: "cancelled" } } }
        ]
      }
    ) {
      nodes {
        title
        priority
        state { name type }
        url
      }
    }
  }
}
"""

headers = {
    "Authorization": LINEAR_API_KEY,
    "Content-Type": "application/json",
}
resp = requests.post(
    "https://api.linear.app/graphql",
    json={"query": QUERY},
    headers=headers,
    timeout=15,
)
print(f"Status: {resp.status_code}")
data = resp.json()
print("Raw response:")
print(json.dumps(data, indent=2))

nodes = (
    data.get("data", {})
    .get("viewer", {})
    .get("assignedIssues", {})
    .get("nodes", [])
)
print(f"\nTotal tasks returned: {len(nodes)}")

# ── Calendar ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("CALENDAR DEBUG")
print("=" * 60)

from datetime import datetime
import pytz

CZECH_TZ = pytz.timezone("Europe/Prague")
now_prague = datetime.now(CZECH_TZ)
print(f"Current Prague time: {now_prague}")

try:
    from bot.calendar import fetch_today_events, _build_service
    service = _build_service()
    print("Calendar service built OK")

    start_of_day = now_prague.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_prague.replace(hour=23, minute=59, second=59, microsecond=0)
    print(f"Fetching events from {start_of_day.isoformat()} to {end_of_day.isoformat()}")

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
    items = result.get("items", [])
    print(f"Events returned: {len(items)}")
    for item in items:
        print(f"  - {item.get('summary','(no title)')} at {item.get('start','?')}")

    # Also try fetching the next 7 days to check if any events exist at all
    from datetime import timedelta
    end_week = now_prague + timedelta(days=7)
    result2 = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_week.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=5,
        )
        .execute()
    )
    items2 = result2.get("items", [])
    print(f"\nEvents in next 7 days: {len(items2)}")
    for item in items2:
        print(f"  - {item.get('summary','(no title)')} at {item.get('start','?')}")

    # List available calendars
    cals = service.calendarList().list().execute()
    print(f"\nAvailable calendars:")
    for cal in cals.get("items", []):
        print(f"  - [{cal.get('id')}] {cal.get('summary','?')} (primary={cal.get('primary',False)})")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
