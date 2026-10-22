from datetime import datetime
from db import get_conn
import clock


def get_student_reminders(student_id: int, status_filter: str = "PENDING") -> list[dict]:
    """Retrieves all reminders for a student."""
    conn = get_conn()
    now_dt = clock.now(student_id)
    today_str = now_dt.strftime("%Y-%m-%d")
    
    query = """
        SELECT r.id, r.student_id, r.task_id, r.text, r.remind_date,
               r.remind_time, r.status, r.created_at,
               t.title AS task_title, t.subject_name, t.due_at, t.status AS task_status
        FROM reminder r
        LEFT JOIN task t ON r.task_id = t.id
        WHERE r.student_id = ?
    """
    params = [student_id]
    if status_filter != "ALL":
        query += " AND r.status = ?"
        params.append(status_filter)
        
    query += " ORDER BY r.remind_date ASC, r.remind_time ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        d["is_today"] = (d["remind_date"] == today_str)
        results.append(d)
        
    return results


def get_today_active_reminders(student_id: int) -> list[dict]:
    """Returns today's active/pending reminders for the student."""
    now_dt = clock.now(student_id)
    today_str = now_dt.strftime("%Y-%m-%d")
    
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.id, r.student_id, r.task_id, r.text, r.remind_date, r.remind_time,
                  t.title AS task_title, t.subject_name, t.due_at
           FROM reminder r
           LEFT JOIN task t ON r.task_id = t.id
           WHERE r.student_id = ? 
             AND r.status = 'PENDING'
             AND (r.remind_date <= ? OR r.remind_date IS NULL)
             AND (t.status IS NULL OR t.status != 'COMPLETED')
           ORDER BY r.remind_date ASC""",
        (student_id, today_str)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_reminder(student_id: int, reminder_id: int) -> bool:
    """Marks a reminder as dismissed."""
    conn = get_conn()
    cur = conn.execute(
        "UPDATE reminder SET status = 'DISMISSED' WHERE id = ? AND student_id = ?",
        (reminder_id, student_id)
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def dismiss_all_for_task(task_id: int) -> None:
    """Dismisses all reminders for a specific task."""
    conn = get_conn()
    conn.execute("UPDATE reminder SET status = 'DISMISSED' WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
