from datetime import datetime, timedelta
import re
from db import get_conn
import clock


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15,
    "twenty": 20, "thirty": 30
}


def parse_days_input(text: str | int | float) -> int:
    """Parses various day expressions like 5, '5', '5 days', 'within 5 days', 'five days', 'tomorrow', 'next week'."""
    if isinstance(text, (int, float)):
        return max(1, int(text))
    
    s = str(text).lower().strip()
    if s == "tomorrow":
        return 1
    if "today" in s:
        return 0
    if "next week" in s:
        return 7
    if "two weeks" in s or "2 weeks" in s:
        return 14
        
    # Check for number words
    for word, val in NUMBER_WORDS.items():
        if re.search(r'\b' + word + r'\b', s):
            return val

    # Match digits
    match = re.search(r'(\d+)', s)
    if match:
        return max(1, int(match.group(1)))
        
    return 5  # default fallback if unspecified


SUBJECT_SYNONYMS = {
    "os": ["os", "operating system", "operating systems"],
    "dbms": ["dbms", "database", "database management", "database management systems", "databases", "rdbms"],
    "ai": ["ai", "artificial intelligence", "ai & ml", "ai/ml", "machine learning"],
    "ml": ["ml", "machine learning", "ai & ml"],
    "cn": ["cn", "computer networks", "networks", "networking", "network"],
    "se": ["se", "software engineering"],
    "cloud": ["cloud", "cloud computing", "cc"],
    "cc": ["cloud", "cloud computing", "cc"],
    "math": ["math", "mathematics", "maths"],
}


def get_subject_variants(name: str) -> set[str]:
    """Returns canonical words and abbreviations for a subject or course name."""
    if not name:
        return set()
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", str(name)).lower().strip()
    variants = {clean}
    words = [w for w in clean.split() if w not in ("and", "&", "lab", "assignment", "assessment", "task", "reading", "project", "theory", "due")]
    if len(words) >= 2:
        acronym = "".join([w[0] for w in words])
        variants.add(acronym)
    
    for canon, syn_list in SUBJECT_SYNONYMS.items():
        if clean == canon or any(s == clean or s in clean.split() for s in syn_list):
            variants.update(syn_list)
            variants.add(canon)
            
    return variants


def is_subject_match(query: str, *target_strings: str) -> bool:
    """
    Checks if a query subject matches candidate strings (subject_name, title, course_name).
    Supports exact matching, word boundaries, acronyms (e.g. OS <-> Operating Systems), and synonyms.
    """
    if not query:
        return False
    q_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", str(query)).lower().strip()
    if not q_clean:
        return False
        
    q_variants = get_subject_variants(q_clean)
    
    for target in target_strings:
        if not target:
            continue
        t_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", str(target)).lower().strip()
        t_variants = get_subject_variants(t_clean)
        
        # 1. Direct variant overlap (e.g. 'os' in variants of 'operating systems')
        if q_variants & t_variants:
            return True
            
        # 2. Token / word boundary check
        for qv in q_variants:
            if re.search(r'\b' + re.escape(qv) + r'\b', t_clean):
                return True
            if len(qv) >= 4 and (qv in t_clean or t_clean in qv):
                return True
                
    return False


def find_or_create_course(student_id: int, subject: str) -> tuple[int, str]:
    """Finds existing course matching subject for student or creates a new course."""
    conn = get_conn()
    subject_clean = subject.strip()
    
    # 1. Exact, acronym, or synonym match against student's enrolled courses
    rows = conn.execute(
        "SELECT id, name, code FROM course WHERE student_id = ?",
        (student_id,)
    ).fetchall()
    
    for r in rows:
        if is_subject_match(subject_clean, r["name"], r["code"]):
            conn.close()
            return r["id"], r["name"]

            
    # 2. If not found, create new course for this student
    cur = conn.cursor()
    code_guess = "".join([w[0].upper() for w in subject_clean.split()[:3]]) + "101"
    cur.execute(
        "INSERT INTO course (student_id, code, name, type) VALUES (?, ?, ?, 'THEORY')",
        (student_id, code_guess, subject_clean.title())
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id, subject_clean.title()


def add_assignment(student_id: int, subject: str, days: int | str, title: str = None, weight: int = 3) -> dict:
    """
    Calculates due date, saves assignment to DB, and schedules daily reminders.
    """
    num_days = parse_days_input(days)
    now_dt = clock.now(student_id)
    due_dt = (now_dt + timedelta(days=num_days)).replace(hour=23, minute=59, second=0)
    
    course_id, resolved_subject = find_or_create_course(student_id, subject)
    
    task_title = title if title else f"{resolved_subject} Assignment"
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO task (student_id, course_id, title, subject_name, due_at, status, weight)
           VALUES (?, ?, ?, ?, ?, 'TODO', ?)""",
        (student_id, course_id, task_title, resolved_subject, due_dt.isoformat(), weight)
    )
    task_id = cur.lastrowid
    
    # Generate daily reminders from day 1 up to due day
    reminders_created = []
    for day_offset in range(1, num_days + 1):
        remind_dt = (now_dt + timedelta(days=day_offset)).replace(hour=8, minute=0, second=0)
        days_remaining = num_days - day_offset
        if days_remaining == 0:
            msg = f"URGENT: {resolved_subject} assignment is due TODAY by 11:59 PM!"
        elif days_remaining == 1:
            msg = f"Reminder: {resolved_subject} assignment is due TOMORROW!"
        else:
            msg = f"Daily Reminder: {resolved_subject} assignment is due in {days_remaining} days ({due_dt.strftime('%b %d')})"
            
        cur.execute(
            """INSERT INTO reminder (student_id, task_id, text, remind_date, remind_time, status)
               VALUES (?, ?, ?, ?, '08:00', 'PENDING')""",
            (student_id, task_id, msg, remind_dt.strftime('%Y-%m-%d'))
        )
        reminders_created.append(msg)
        
    conn.commit()
    conn.close()
    
    return {
        "id": task_id,
        "student_id": student_id,
        "course_id": course_id,
        "subject": resolved_subject,
        "title": task_title,
        "days": num_days,
        "due_at": due_dt.isoformat(),
        "due_date_str": due_dt.strftime("%A, %B %d, %Y"),
        "reminders_count": len(reminders_created)
    }


def complete_assignment(student_id: int, subject: str = None, task_id: int = None, delete: bool = False) -> dict | None:
    """
    Finds assignment by subject or task_id for that student,
    marks it completed or deletes it, and clears associated reminders.
    """
    conn = get_conn()
    
    target_task = None
    if task_id:
        target_task = conn.execute(
            "SELECT * FROM task WHERE id = ? AND student_id = ?",
            (task_id, student_id)
        ).fetchone()
    elif subject and str(subject).strip():
        sub_str = str(subject).strip()
        tasks = conn.execute(
            """SELECT t.*, c.name AS course_name FROM task t
               LEFT JOIN course c ON t.course_id = c.id
               WHERE t.student_id = ? AND t.status != 'COMPLETED'
               ORDER BY t.due_at ASC""",
            (student_id,)
        ).fetchall()
        
        for t in tasks:
            if is_subject_match(sub_str, t["subject_name"], t["title"], t["course_name"]):
                target_task = t
                break
                
        # If the user explicitly named a subject (e.g. "OS") and it does not match any task,
        # DO NOT fall back to deleting/completing an arbitrary task like DBMS!
    else:
        # Only when NO subject was specified (e.g. "it is completed") and ONLY for completion (not delete)
        if not delete:
            target_task = conn.execute(
                "SELECT * FROM task WHERE student_id = ? AND status != 'COMPLETED' ORDER BY due_at ASC LIMIT 1",
                (student_id,)
            ).fetchone()


    if not target_task:
        conn.close()
        return None

    matched_id = target_task["id"]
    matched_title = target_task["title"]
    matched_subject = target_task["subject_name"] or target_task["title"]

    if delete:
        conn.execute("DELETE FROM reminder WHERE task_id = ?", (matched_id,))
        conn.execute("DELETE FROM task WHERE id = ?", (matched_id,))
    else:
        conn.execute("UPDATE task SET status = 'COMPLETED' WHERE id = ?", (matched_id,))
        conn.execute("UPDATE reminder SET status = 'DISMISSED' WHERE task_id = ?", (matched_id,))
        
    conn.commit()
    conn.close()

    return {
        "id": matched_id,
        "title": matched_title,
        "subject": matched_subject,
        "deleted": delete,
        "status": "COMPLETED" if not delete else "DELETED"
    }


def delete_assignment(student_id: int, task_id: int) -> bool:
    """Permanently deletes an assignment and its reminders."""
    conn = get_conn()
    conn.execute("DELETE FROM reminder WHERE task_id = ? AND student_id = ?", (task_id, student_id))
    cur = conn.execute("DELETE FROM task WHERE id = ? AND student_id = ?", (task_id, student_id))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def list_assignments(student_id: int, status_filter: str = "ALL") -> list[dict]:
    """Retrieves all assignments for a specific student with time calculations."""
    conn = get_conn()
    now_dt = clock.now(student_id)
    
    query = """
        SELECT t.id, t.student_id, t.course_id, t.title, t.subject_name,
               t.due_at, t.status, t.weight, t.created_at,
               c.name AS course_name, c.code AS course_code
        FROM task t
        LEFT JOIN course c ON t.course_id = c.id
        WHERE t.student_id = ?
    """
    params = [student_id]
    
    if status_filter != "ALL":
        query += " AND t.status = ?"
        params.append(status_filter)
        
    query += " ORDER BY t.due_at ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        try:
            due_dt = datetime.fromisoformat(d["due_at"])
            delta = due_dt - now_dt
            days_left = delta.days
            hours_left = int(delta.total_seconds() // 3600)
            
            d["days_left"] = days_left
            d["hours_left"] = hours_left
            d["is_overdue"] = delta.total_seconds() < 0 and d["status"] != "COMPLETED"
            d["due_formatted"] = due_dt.strftime("%b %d, %Y (%I:%M %p)")
            d["due_date_only"] = due_dt.strftime("%Y-%m-%d")
        except Exception:
            d["days_left"] = 0
            d["hours_left"] = 0
            d["is_overdue"] = False
            d["due_formatted"] = d["due_at"]
            
        results.append(d)
        
    return results
