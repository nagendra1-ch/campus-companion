"""Context engine. Layer 1: location (set by simulator). Layer 2: sub-state derived from the schedule."""
from db import get_conn
import clock
import schedule
import reminders
import assignments


def _get_student(student_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM student WHERE id=?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"id": student_id, "name": "Student", "avatar": "🎓"}


def _sim_row(student_id: int):
    conn = get_conn()
    row = conn.execute("SELECT location, destination FROM sim_state WHERE student_id=?", (student_id,)).fetchone()
    conn.close()
    if not row:
        # Create default sim_state if missing
        conn = get_conn()
        conn.execute("INSERT OR REPLACE INTO sim_state VALUES (?, '2026-10-12T07:45:00', 'AT_HOME', NULL)", (student_id,))
        conn.commit()
        row = conn.execute("SELECT location, destination FROM sim_state WHERE student_id=?", (student_id,)).fetchone()
        conn.close()
    return row


def classify(student_id: int) -> str:
    loc = _sim_row(student_id)["location"]
    if loc != "AT_COLLEGE":
        return loc

    if schedule.current(student_id):
        return "IN_CLASS"                       # quiet mode
    nxt = schedule.next_session(student_id)
    if nxt is None:
        return "LEAVING_COLLEGE_SOON"           # day is done
    minutes = schedule.minutes_until(student_id, nxt["start"])
    if nxt["type"] == "LAB" and minutes <= 45:
        return "BEFORE_LAB"
    if minutes <= 30:
        return "BEFORE_CLASS"
    return "BETWEEN_CLASSES"


def snapshot(student_id: int) -> dict:
    student_info = _get_student(student_id)
    row = _sim_row(student_id)
    curr = schedule.current(student_id)
    nxt = schedule.next_session(student_id)
    active_reminders = reminders.get_today_active_reminders(student_id)
    all_tasks = assignments.list_assignments(student_id, status_filter="TODO")
    
    out = {
        "student": student_info,
        "state": classify(student_id),
        "now": clock.now(student_id).isoformat(),
        "isLive": clock.is_live(student_id),
        "location": row["location"],
        "destination": row["destination"],
        "simulated": not clock.is_live(student_id),
        "currentEvent": {
            "title": curr["title"],
            "room": curr["room"],
            "type": curr["type"],
            "endsInMin": schedule.minutes_until(student_id, curr["end"])
        } if curr else None,
        "nextEvent": {
            "title": nxt["title"],
            "room": nxt["room"],
            "type": nxt["type"],
            "start": nxt["start"],
            "startsInMin": schedule.minutes_until(student_id, nxt["start"]),
        } if nxt else None,
        "pendingTasksCount": len(all_tasks),
        "activeRemindersCount": len(active_reminders),
        "reminders": active_reminders
    }
    return out


EVENTS = {
    "LEAVE_HOME":     ("LEAVING_HOME", "COLLEGE"),
    "START_TRAVEL":   ("TRAVELING", "COLLEGE"),
    "ARRIVE_COLLEGE": ("AT_COLLEGE", None),
    "LEAVE_COLLEGE":  ("LEAVING_COLLEGE", "HOME"),
    "ARRIVE_HOME":    ("AT_HOME", None),
}


def transition(student_id: int, event: str) -> dict:
    """Simulator event -> location change."""
    if event not in EVENTS:
        raise ValueError(f"Unknown event: {event}")
    loc, dest = EVENTS[event]
    conn = get_conn()
    conn.execute("UPDATE sim_state SET location=?, destination=? WHERE student_id=?", (loc, dest, student_id))
    conn.commit()
    conn.close()
    return snapshot(student_id)
