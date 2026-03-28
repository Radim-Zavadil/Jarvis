"""
linear.py — fetches the current user's open/in-progress tasks from Linear.
"""

import os
import requests

LINEAR_API_KEY = os.environ["LINEAR_API_KEY"]
GRAPHQL_URL = "https://api.linear.app/graphql"

PRIORITY_LABELS = {
    0: "No priority",
    1: "Urgent",
    2: "High",
    3: "Medium",
    4: "Low",
}

# Fetch tasks assigned to the viewer that are not completed/cancelled.
QUERY = """
query {
  viewer {
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
        state { name }
        url
      }
    }
  }
}
"""


def fetch_tasks() -> list[dict]:
    """Return a list of open tasks assigned to the Linear viewer.

    Each dict has keys: title, priority (int), priority_label, state, url.
    """
    headers = {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json",
    }
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    nodes = (
        data.get("data", {})
        .get("viewer", {})
        .get("assignedIssues", {})
        .get("nodes", [])
    )

    tasks = []
    for node in nodes:
        priority = node.get("priority", 0)
        tasks.append(
            {
                "title": node["title"],
                "priority": priority,
                "priority_label": PRIORITY_LABELS.get(priority, "Unknown"),
                "state": node["state"]["name"],
                "url": node.get("url", ""),
            }
        )
    return sorted(tasks, key=lambda t: (t["priority"] == 0, t["priority"]))


from bot.telegram import escape_html


def format_tasks_section(tasks: list[dict]) -> str:
    """Format tasks for the morning briefing message."""
    if not tasks:
        return "📋 <b>LINEAR TASKS</b>\n<i>No open tasks</i> ✅"

    lines = ["📋 <b>LINEAR TASKS</b>"]
    for task in tasks:
        safe_title = escape_html(task['title'])
        safe_priority = escape_html(task['priority_label'])
        lines.append(f"- {safe_title} [Priority: {safe_priority}]")
    return "\n".join(lines)
