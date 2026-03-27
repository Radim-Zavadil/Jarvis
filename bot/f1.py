"""
f1.py — F1 data exclusively via OpenF1 API.

Provides:
  - next_race_info()            → countdown for morning briefing
  - get_latest_completed_session() → latest completed session within last 35 min
  - format_race_result()        → Top 10 drivers + Top 5 teams (race)
  - format_session_result()     → Top 3 drivers (qualifying / practice)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

import pytz
import requests

OPENF1_BASE = "https://api.openf1.org/v1"
CZECH_TZ = pytz.timezone("Europe/Prague")

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

POSITION_POINTS = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8,  7: 6,  8: 4,  9: 2,  10: 1,
}

# How far back to look when deciding a session is "fresh" (slightly over 30 min)
FRESHNESS_WINDOW_MINUTES = 35


# ──────────────────────────────────────────────
# HTTP helper
# ──────────────────────────────────────────────

def _get(url: str, params: dict | None = None, timeout: int = 15) -> dict | list | None:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[f1] GET {url} failed: {exc}")
        return None


# ──────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────

def _format_laptime(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    mins = int(seconds) // 60
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


def _format_gap(gap_seconds: float) -> str:
    if gap_seconds <= 0:
        return ""
    ms = round(gap_seconds * 1000)
    mins = ms // 60000
    secs = (ms % 60000) // 1000
    millis = ms % 1000
    if mins:
        return f" (+{mins}:{secs:02d}.{millis:03d})"
    return f" (+{secs}.{millis:03d})"


def _parse_dt(dt_str: str | None) -> datetime | None:
    """Parse an ISO 8601 string from OpenF1 into a UTC-aware datetime."""
    if not dt_str:
        return None
    try:
        # OpenF1 returns strings like "2024-03-02T05:00:00+00:00" or "2024-03-02T05:00:00"
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ──────────────────────────────────────────────
# OpenF1 data fetchers
# ──────────────────────────────────────────────

def _openf1_meetings(year: int) -> list[dict]:
    data = _get(f"{OPENF1_BASE}/meetings", {"year": year})
    return data if isinstance(data, list) else []


def _openf1_sessions(meeting_key: int) -> list[dict]:
    data = _get(f"{OPENF1_BASE}/sessions", {"meeting_key": meeting_key})
    return data if isinstance(data, list) else []


def _openf1_drivers(session_key: int) -> dict[int, dict]:
    data = _get(f"{OPENF1_BASE}/drivers", {"session_key": session_key})
    if not isinstance(data, list):
        return {}
    return {d["driver_number"]: d for d in data}


def _openf1_race_positions(session_key: int) -> list[dict]:
    """Return final position for each driver in a race session."""
    data = _get(f"{OPENF1_BASE}/position", {"session_key": session_key})
    if not isinstance(data, list):
        return []
    # Keep only the last recorded position per driver (data is time-ordered)
    final: dict[int, dict] = {}
    for entry in data:
        dn = entry.get("driver_number")
        if dn is not None:
            final[dn] = entry
    return sorted(final.values(), key=lambda x: x.get("position", 99))


def _openf1_lap_times(session_key: int) -> list[dict]:
    """Return best lap time per driver for quali/practice."""
    data = _get(f"{OPENF1_BASE}/laps", {"session_key": session_key})
    if not isinstance(data, list):
        return []
    best: dict[int, float] = {}
    for lap in data:
        dn = lap.get("driver_number")
        dur = lap.get("lap_duration")
        if dn is not None and dur is not None:
            if dn not in best or dur < best[dn]:
                best[dn] = dur
    return sorted(
        [{"driver_number": k, "best_lap": v} for k, v in best.items()],
        key=lambda x: x["best_lap"],
    )


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def next_race_info() -> str:
    """Return formatted countdown block for the morning briefing using OpenF1."""
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year

    meetings = _openf1_meetings(year)
    if not meetings:
        # Try next year in case we are between seasons
        meetings = _openf1_meetings(year + 1)

    # Find meetings that have not ended yet (date_end in the future)
    upcoming = []
    for m in meetings:
        end_dt = _parse_dt(m.get("date_end"))
        if end_dt and end_dt > now_utc:
            start_dt = _parse_dt(m.get("date_start"))
            upcoming.append((start_dt, m))

    if not upcoming:
        return "🏎️ *NEXT F1 RACE*\n_No upcoming races found._"

    # Earliest upcoming/ongoing meeting
    upcoming.sort(key=lambda x: x[0] if x[0] else datetime.max.replace(tzinfo=timezone.utc))
    race_start_dt, meeting = upcoming[0]
    meeting_key = meeting.get("meeting_key")

    # Try to get the actual Race session start time for this meeting
    race_session_dt = None
    if meeting_key:
        sessions = _openf1_sessions(meeting_key)
        for s in sessions:
            if s.get("session_name", "").lower() == "race":
                race_session_dt = _parse_dt(s.get("date_start"))
                break

    target_dt = race_session_dt or race_start_dt

    meeting_name = meeting.get("meeting_name", "Grand Prix")
    country = meeting.get("country_name", "")
    circuit = meeting.get("circuit_short_name", "")

    prague_dt = target_dt.astimezone(CZECH_TZ)
    now_prague = now_utc.astimezone(CZECH_TZ)

    # Label detection
    is_race_today = False
    if race_session_dt and race_session_dt.astimezone(CZECH_TZ).date() == now_prague.date():
        is_race_today = True

    is_ongoing = race_start_dt <= now_utc

    if is_race_today:
        label_header = "🏁 *RACE TODAY!*"
    elif is_ongoing:
        label_header = "🏎️ *GP WEEKEND*"
    else:
        label_header = "🏎️ *NEXT F1 RACE*"

    # Date formatting
    day = str(prague_dt.day)
    date_str = prague_dt.strftime(f"%A, %B {day}, %Y")
    time_str = prague_dt.strftime("%H:%M")

    delta = target_dt - now_utc
    total_secs = int(delta.total_seconds())
    
    if total_secs > 0:
        days = total_secs // 86400
        hours = (total_secs % 86400) // 3600
        minutes = (total_secs % 3600) // 60
        countdown_str = f"⏳ {days}d {hours}h {minutes}m to go"
    else:
        countdown_str = "🟢 *Session in progress* (or already started)"

    session_label = "Race" if race_session_dt else "Weekend start"
    lines = [
        label_header,
        f"*{meeting_name}* — {circuit}, {country}",
        f"📅 {session_label}: {date_str} at {time_str} CET",
        countdown_str,
    ]
    return "\n".join(lines)


def get_latest_completed_session() -> Optional[dict]:
    """
    Return the most recently completed OpenF1 session IF it ended within the
    last FRESHNESS_WINDOW_MINUTES minutes. Returns None otherwise.

    This stateless approach means we don't need /tmp state persistence across
    GitHub Actions runs — we simply report each session right after it ends.
    """
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year

    meetings = _openf1_meetings(year)
    if not meetings:
        return None

    # Look at the most recent meeting (the one that started latest but before now)
    past_meetings = [
        m for m in meetings
        if _parse_dt(m.get("date_start")) and _parse_dt(m.get("date_start")) <= now_utc
    ]
    if not past_meetings:
        return None

    past_meetings.sort(key=lambda m: _parse_dt(m["date_start"]), reverse=True)
    meeting = past_meetings[0]
    meeting_key = meeting["meeting_key"]

    sessions = _openf1_sessions(meeting_key)

    # Find sessions that ended in the last FRESHNESS_WINDOW_MINUTES
    window_start = now_utc - timedelta(minutes=FRESHNESS_WINDOW_MINUTES)

    fresh_sessions = []
    for s in sessions:
        date_end = _parse_dt(s.get("date_end"))
        if date_end and window_start <= date_end <= now_utc:
            fresh_sessions.append((date_end, s))

    if not fresh_sessions:
        print(f"[f1] No session ended in the last {FRESHNESS_WINDOW_MINUTES} min.")
        return None

    # Pick the one that ended most recently
    fresh_sessions.sort(key=lambda x: x[0], reverse=True)
    session = fresh_sessions[0][1]
    session["_meeting"] = meeting
    return session


def format_race_result(session: dict) -> str:
    """Build race result message — Top 10 finishers + Top 5 constructor points from this race."""
    meeting = session.get("_meeting", {})
    race_name = meeting.get("meeting_name", "Grand Prix")
    session_key = session["session_key"]
    drivers = _openf1_drivers(session_key)
    positions = _openf1_race_positions(session_key)

    lines = [f"🏁 *RACE RESULT — {race_name}*", ""]

    # Track team points earned in this race
    team_points: dict[str, int] = {}
    
    # Process positions to track points for all, but format specifically
    all_results = []
    for entry in positions:
        dn = entry.get("driver_number")
        pos = entry.get("position", "?")
        drv = drivers.get(dn, {})
        name = drv.get("full_name", f"Driver #{dn}")
        team = drv.get("team_name", "Unknown")
        pts = POSITION_POINTS.get(pos, 0)
        
        all_results.append({
            "pos": pos,
            "name": name,
            "team": team,
            "pts": pts
        })
        
        if team and team != "Unknown":
            team_points[team] = team_points.get(team, 0) + pts

    # Top 3 section
    lines.append("🏆 *Top 3 Drivers (Podium):*")
    for res in all_results[:3]:
        medal = MEDAL.get(res["pos"], f"{res['pos']}.")
        pts_str = f"  (+{res['pts']} pts)" if res['pts'] else ""
        lines.append(f"{medal} {res['name']} ({res['team']}){pts_str}")

    # Top 10 section
    if len(all_results) > 3:
        lines.append("")
        lines.append("🏁 *Full Top 10:*")
        for res in all_results[:10]:
            medal = MEDAL.get(res["pos"], f"{res['pos']}.")
            pts_str = f"  +{res['pts']} pts" if res['pts'] else ""
            lines.append(f"{medal} {res['name']} ({res['team']}){pts_str if res['pos'] > 3 else ''}")

    # Top 3 constructor points from this race
    if team_points:
        top_teams = sorted(team_points.items(), key=lambda x: x[1], reverse=True)[:3]
        lines += ["", "🏗️ *Top 3 Teams (this race):*"]
        for i, (team, pts) in enumerate(top_teams, 1):
            medal = MEDAL.get(i, f"{i}.")
            lines.append(f"{medal} {team} — {pts} pts")

    return "\n".join(lines)


def format_session_result(session: dict) -> str:
    """Build practice/qualifying result message — Top 3 drivers only."""
    meeting = session.get("_meeting", {})
    race_name = meeting.get("meeting_name", "Grand Prix")
    session_type = session.get("session_name", "Session")
    session_key = session["session_key"]

    drivers = _openf1_drivers(session_key)
    lap_data = _openf1_lap_times(session_key)

    if not lap_data:
        return f"⏱️ *{session_type.upper()} — {race_name}*\n_No lap time data available._"

    best_lap = lap_data[0]["best_lap"]

    emoji = "⏱️"
    if "qualifying" in session_type.lower():
        emoji = "🔥"
    elif "sprint" in session_type.lower():
        emoji = "💨"

    lines = [f"{emoji} *{session_type.upper()} — {race_name}*", ""]

    for i, entry in enumerate(lap_data[:3], 1):
        dn = entry["driver_number"]
        drv = drivers.get(dn, {})
        name = drv.get("full_name", f"Driver #{dn}")
        team = drv.get("team_name", "")
        lap_time = entry["best_lap"]
        lap_str = _format_laptime(lap_time)

        medal = MEDAL[i]
        gap_str = "" if i == 1 else _format_gap(lap_time - best_lap)
        lines.append(f"{medal} {name} ({team}) — {lap_str}{gap_str}")

    return "\n".join(lines)
