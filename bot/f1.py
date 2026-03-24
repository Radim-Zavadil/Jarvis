"""
f1.py — F1 data via OpenF1 API with Ergast as fallback.

Provides:
  - next_race_info()          → countdown for morning briefing
  - get_session_result()      → latest completed session on a race weekend
  - format_race_result()      → Message 2 (race result + standings)
  - format_session_result()   → Message 3 (qualifying / practice result)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import pytz
import requests

OPENF1_BASE = "https://api.openf1.org/v1"
ERGAST_BASE = "https://ergast.com/api/f1"
CZECH_TZ = pytz.timezone("Europe/Prague")

SESSION_TYPE_LABELS = {
    "Practice 1": "Practice 1",
    "Practice 2": "Practice 2",
    "Practice 3": "Practice 3",
    "Qualifying": "Qualifying",
    "Sprint": "Sprint",
    "Race": "Race",
}

MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

POSITION_POINTS = {
    1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
    6: 8, 7: 6, 8: 4, 9: 2, 10: 1,
}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get(url: str, params: dict | None = None, timeout: int = 10) -> dict | list | None:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[f1] GET {url} failed: {exc}")
        return None


def _format_gap(gap_seconds: float | None) -> str:
    if gap_seconds is None:
        return ""
    if gap_seconds == 0:
        return ""
    ms = round(gap_seconds * 1000)
    mins = ms // 60000
    secs = (ms % 60000) // 1000
    millis = ms % 1000
    if mins:
        return f"+{mins}:{secs:02d}.{millis:03d}"
    return f"+{secs}.{millis:03d}"


def _format_laptime(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    mins = int(seconds) // 60
    secs = seconds % 60
    return f"{mins}:{secs:06.3f}"


def _position_change_label(change: int) -> str:
    if change > 0:
        return f"↑ +{change} position{'s' if change > 1 else ''}"
    if change < 0:
        return f"↓ {change} position{'s' if abs(change) > 1 else ''}"
    return "↑ no change"


# ──────────────────────────────────────────────
# OpenF1 helpers
# ──────────────────────────────────────────────

def _openf1_current_meeting() -> dict | None:
    """Return the most recent meeting from OpenF1."""
    data = _get(f"{OPENF1_BASE}/meetings", {"year": datetime.now().year})
    if not data:
        return None
    # Sort by date_start descending, pick current/most recent
    meetings = sorted(data, key=lambda m: m.get("date_start", ""), reverse=True)
    now_utc = datetime.now(timezone.utc).isoformat()
    for m in meetings:
        if m.get("date_start", "") <= now_utc:
            return m
    return meetings[-1] if meetings else None


def _openf1_sessions(meeting_key: int) -> list[dict]:
    data = _get(f"{OPENF1_BASE}/sessions", {"meeting_key": meeting_key})
    return data if data else []


def _openf1_drivers(session_key: int) -> dict[int, dict]:
    """Return {driver_number: driver_info} for a session."""
    data = _get(f"{OPENF1_BASE}/drivers", {"session_key": session_key})
    if not data:
        return {}
    return {d["driver_number"]: d for d in data}


def _openf1_race_results(session_key: int) -> list[dict]:
    """Return position data for a race session."""
    data = _get(f"{OPENF1_BASE}/position", {"session_key": session_key})
    if not data:
        return []
    # Keep only the final position for each driver
    final: dict[int, dict] = {}
    for entry in data:
        dn = entry["driver_number"]
        final[dn] = entry  # last entry wins (data is time-ordered)
    return sorted(final.values(), key=lambda x: x.get("position", 99))


def _openf1_lap_times(session_key: int) -> list[dict]:
    """Return best lap time per driver for quali/practice."""
    data = _get(f"{OPENF1_BASE}/laps", {"session_key": session_key})
    if not data:
        return []
    best: dict[int, float] = {}
    for lap in data:
        dn = lap["driver_number"]
        dur = lap.get("lap_duration")
        if dur is not None:
            if dn not in best or dur < best[dn]:
                best[dn] = dur
    return [{"driver_number": k, "best_lap": v} for k, v in best.items()]


# ──────────────────────────────────────────────
# Ergast fallback helpers
# ──────────────────────────────────────────────

def _ergast_next_race() -> dict | None:
    data = _get(f"{ERGAST_BASE}/current/next.json")
    if not data:
        return None
    races = (
        data.get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )
    return races[0] if races else None


def _ergast_last_race_results() -> dict | None:
    data = _get(f"{ERGAST_BASE}/current/last/results.json")
    if not data:
        return None
    races = (
        data.get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )
    return races[0] if races else None


def _ergast_driver_standings() -> list[dict]:
    data = _get(f"{ERGAST_BASE}/current/driverStandings.json")
    if not data:
        return []
    standings_list = (
        data.get("MRData", {})
        .get("StandingsTable", {})
        .get("StandingsLists", [])
    )
    if not standings_list:
        return []
    return standings_list[0].get("DriverStandings", [])


def _ergast_constructor_standings() -> list[dict]:
    data = _get(f"{ERGAST_BASE}/current/constructorStandings.json")
    if not data:
        return []
    standings_list = (
        data.get("MRData", {})
        .get("StandingsTable", {})
        .get("StandingsLists", [])
    )
    if not standings_list:
        return []
    return standings_list[0].get("ConstructorStandings", [])


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def next_race_info() -> str:
    """Return formatted countdown block for the morning briefing."""
    race = _ergast_next_race()
    if not race:
        return "🏎️ *NEXT F1 RACE*\n_Could not fetch race data._"

    race_name = race.get("raceName", "Unknown GP")
    circuit = race.get("Circuit", {})
    location = circuit.get("Location", {})
    city = location.get("locality", "")
    country = location.get("country", "")

    race_date_str = race.get("date", "")
    race_time_str = race.get("time", "00:00:00Z")
    try:
        race_dt = datetime.fromisoformat(
            f"{race_date_str}T{race_time_str.rstrip('Z')}+00:00"
        )
    except ValueError:
        race_dt = None

    lines = [f"🏎️ *NEXT F1 RACE*", f"{race_name} — {city}"]

    if race_dt:
        prague_dt = race_dt.astimezone(CZECH_TZ)
        lines.append(f"📅 {prague_dt.strftime('%B %-d, %Y')} at {prague_dt.strftime('%H:%M')} CET")

        now_utc = datetime.now(timezone.utc)
        delta = race_dt - now_utc
        if delta.total_seconds() > 0:
            total_secs = int(delta.total_seconds())
            days = total_secs // 86400
            hours = (total_secs % 86400) // 3600
            minutes = (total_secs % 3600) // 60
            lines.append(f"⏳ {days} days, {hours} hours, {minutes} minutes")
        else:
            lines.append("⏳ Race is happening now!")
    else:
        lines.append(f"📅 {race_date_str}")

    return "\n".join(lines)


def get_latest_completed_session() -> Optional[dict]:
    """Return the latest completed OpenF1 session dict, or None."""
    meeting = _openf1_current_meeting()
    if not meeting:
        return None

    sessions = _openf1_sessions(meeting["meeting_key"])
    now_utc = datetime.now(timezone.utc).isoformat()

    completed = [
        s for s in sessions
        if s.get("date_end") and s["date_end"] <= now_utc
    ]
    if not completed:
        return None

    completed.sort(key=lambda s: s.get("date_end", ""), reverse=True)
    session = completed[0]
    session["_meeting"] = meeting
    return session


def format_race_result(session: dict) -> str:
    """Build Message 2 — race result + championship standings."""
    meeting = session.get("_meeting", {})
    race_name = meeting.get("meeting_name", "Grand Prix")
    session_key = session["session_key"]

    drivers = _openf1_drivers(session_key)
    positions = _openf1_race_results(session_key)

    lines = [f"🏁 *RACE RESULT — {race_name}*", "", "🏆 *Top 10:*"]

    for entry in positions[:10]:
        dn = entry["driver_number"]
        pos = entry.get("position", "?")
        drv = drivers.get(dn, {})
        name = drv.get("full_name", f"Driver #{dn}")
        team = drv.get("team_name", "")
        pts = POSITION_POINTS.get(pos, 0)
        pts_str = f"+{pts} pts" if pts else ""
        lines.append(f"{pos}. {name} — {team} ({pts_str})")

    # --- Driver standings ---
    lines += ["", "📊 *DRIVERS CHAMPIONSHIP (after race):*"]
    d_standings = _ergast_driver_standings()
    for i, s in enumerate(d_standings[:10], 1):
        drv_obj = s.get("Driver", {})
        name = f"{drv_obj.get('givenName', '')} {drv_obj.get('familyName', '')}".strip()
        pts = s.get("points", "?")
        pos_change = i - int(s.get("position", i))
        change_str = _position_change_label(pos_change)
        lines.append(f"{i}. {name} — {pts} pts ({change_str})")

    # --- Constructor standings ---
    lines += ["", "🏗️ *CONSTRUCTORS CHAMPIONSHIP (after race):*"]
    c_standings = _ergast_constructor_standings()
    for i, s in enumerate(c_standings[:5], 1):
        con = s.get("Constructor", {})
        name = con.get("name", "?")
        pts = s.get("points", "?")
        pos_change = i - int(s.get("position", i))
        change_str = _position_change_label(pos_change)
        lines.append(f"{i}. {name} — {pts} pts ({change_str})")

    return "\n".join(lines)


def format_session_result(session: dict) -> str:
    """Build Message 3 — qualifying or practice result."""
    meeting = session.get("_meeting", {})
    race_name = meeting.get("meeting_name", "Grand Prix")
    session_type = session.get("session_name", "Session")
    session_key = session["session_key"]

    drivers = _openf1_drivers(session_key)
    lap_data = _openf1_lap_times(session_key)

    # Sort by best lap time ascending
    lap_data.sort(key=lambda x: x["best_lap"])

    header_emoji = "⏱️"
    lines = [f"{header_emoji} *{session_type.upper()} RESULT — {race_name}*", ""]

    best_lap = lap_data[0]["best_lap"] if lap_data else None

    for i, entry in enumerate(lap_data[:20], 1):
        dn = entry["driver_number"]
        drv = drivers.get(dn, {})
        name = drv.get("full_name", f"Driver #{dn}")
        lap_time = entry["best_lap"]
        lap_str = _format_laptime(lap_time)

        medal = MEDAL.get(i, f"{i}.")
        if i == 1:
            gap_str = ""
        else:
            gap_str = f" ({_format_gap(lap_time - best_lap)})"

        lines.append(f"{medal} {name} — {lap_str}{gap_str}")

    return "\n".join(lines)
