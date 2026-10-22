"""The central time module. Supports live system date & time and simulation mode."""
from datetime import datetime
from db import get_conn


def is_live(student_id: int) -> bool:
    """Checks whether student clock is currently in live system time mode."""
    try:
        conn = get_conn()
        row = conn.execute("SELECT is_live FROM sim_state WHERE student_id=?", (student_id,)).fetchone()
        conn.close()
        if row and "is_live" in row.keys():
            return bool(row["is_live"])
    except Exception:
        pass
    return True


def now(student_id: int) -> datetime:
    """
    Returns the student's current datetime.
    In Live mode (default), returns the real live date and time from the system.
    In Simulation mode, returns the set simulated datetime.
    """
    try:
        conn = get_conn()
        row = conn.execute("SELECT * FROM sim_state WHERE student_id=?", (student_id,)).fetchone()
        conn.close()
        if row:
            keys = row.keys()
            if "is_live" in keys and row["is_live"] == 0 and row["sim_now"]:
                return datetime.fromisoformat(row["sim_now"])
    except Exception:
        pass
    return datetime.now()


def set_now(student_id: int, t: datetime) -> None:
    """Sets a simulated time and switches to simulation mode."""
    conn = get_conn()
    try:
        conn.execute("UPDATE sim_state SET sim_now=?, is_live=0 WHERE student_id=?", (t.isoformat(), student_id))
    except Exception:
        conn.execute("UPDATE sim_state SET sim_now=? WHERE student_id=?", (t.isoformat(), student_id))
    conn.commit()
    conn.close()


def set_live(student_id: int) -> None:
    """Switches back to live system date and time."""
    conn = get_conn()
    curr_now = datetime.now()
    try:
        conn.execute("UPDATE sim_state SET sim_now=?, is_live=1 WHERE student_id=?", (curr_now.isoformat(), student_id))
    except Exception:
        conn.execute("UPDATE sim_state SET sim_now=? WHERE student_id=?", (curr_now.isoformat(), student_id))
    conn.commit()
    conn.close()
