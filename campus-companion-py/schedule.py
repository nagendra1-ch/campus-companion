from datetime import datetime, timedelta
import re
from db import get_conn
import clock



def _format_time_12h(hhmm: str) -> str:
    """Converts '09:00' to '9:00 AM'."""
    try:
        t = datetime.strptime(hhmm, "%H:%M")
        return t.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return hhmm


def today(student_id: int) -> list[dict]:
    """Today's sessions (by student's clock date), earliest first."""
    day = clock.now(student_id).strftime("%A").upper()   # 'MONDAY'
    conn = get_conn()
    rows = conn.execute(
        """SELECT cs.id, c.name AS title, c.code, c.type, cs.room,
                  cs.start_time AS start, cs.end_time AS end
           FROM class_session cs JOIN course c ON c.id = cs.course_id
           WHERE c.student_id = ? AND cs.day_of_week = ?
           ORDER BY cs.start_time""",
        (student_id, day),
    ).fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        d["start_formatted"] = _format_time_12h(d["start"])
        d["end_formatted"] = _format_time_12h(d["end"])
        results.append(d)
    return results


def weekly(student_id: int) -> dict[str, list[dict]]:
    """Full weekly schedule for the student."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT cs.id, c.name AS title, c.code, c.type, cs.room,
                  cs.day_of_week, cs.start_time AS start, cs.end_time AS end
           FROM class_session cs JOIN course c ON c.id = cs.course_id
           WHERE c.student_id = ?
           ORDER BY 
             CASE cs.day_of_week
               WHEN 'MONDAY' THEN 1
               WHEN 'TUESDAY' THEN 2
               WHEN 'WEDNESDAY' THEN 3
               WHEN 'THURSDAY' THEN 4
               WHEN 'FRIDAY' THEN 5
               WHEN 'SATURDAY' THEN 6
               WHEN 'SUNDAY' THEN 7
             END, cs.start_time""",
        (student_id,),
    ).fetchall()
    conn.close()
    
    schedule_by_day = {}
    for r in rows:
        d = dict(r)
        d["start_formatted"] = _format_time_12h(d["start"])
        d["end_formatted"] = _format_time_12h(d["end"])
        day = d["day_of_week"]
        if day not in schedule_by_day:
            schedule_by_day[day] = []
        schedule_by_day[day].append(d)
        
    return schedule_by_day


def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def current(student_id: int):
    t = _hhmm(clock.now(student_id))
    for s in today(student_id):
        if s["start"] <= t < s["end"]:
            return s
    return None


def next_session(student_id: int):
    t = _hhmm(clock.now(student_id))
    for s in today(student_id):
        if s["start"] > t:
            return s
    return None


def minutes_until(student_id: int, hhmm: str) -> int:
    n = clock.now(student_id)
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m) - (n.hour * 60 + n.minute)


def format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "now"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours} hour{'s' if hours != 1 else ''} and {rem_min} minute{'s' if rem_min != 1 else ''}"


def get_next_class_speech(student_id: int) -> dict:
    """
    Constructs the exact spoken response and card for Alexa when user asks 'What is my next class?'.
    """
    now_dt = clock.now(student_id)
    curr = current(student_id)
    nxt = next_session(student_id)
    todays_classes = today(student_id)

    if not todays_classes:
        day_name = now_dt.strftime("%A")
        speech = f"You don't have any classes scheduled for {day_name}. Enjoy your free day!"
        return {
            "speech": speech,
            "card_title": "No Classes Today",
            "card_content": speech,
            "has_next": False,
            "session": None
        }

    if curr and nxt:
        curr_end_fmt = _format_time_12h(curr["end"])
        nxt_start_fmt = _format_time_12h(nxt["start"])
        min_to_next = minutes_until(student_id, nxt["start"])
        speech = (
            f"You are currently in {curr['title']} in room {curr['room']} until {curr_end_fmt}. "
            f"Your next class after that is {nxt['title']} at {nxt_start_fmt} in room {nxt['room']}."
        )
        return {
            "speech": speech,
            "card_title": f"Next: {nxt['title']}",
            "card_content": f"Currently in {curr['title']}.\nNext: {nxt['title']} at {nxt_start_fmt} in {nxt['room']}",
            "has_next": True,
            "session": nxt,
            "current": curr
        }

    if curr and not nxt:
        curr_end_fmt = _format_time_12h(curr["end"])
        speech = f"You are currently in {curr['title']} in room {curr['room']} until {curr_end_fmt}. That is your final class for today!"
        return {
            "speech": speech,
            "card_title": f"Current: {curr['title']}",
            "card_content": f"In {curr['title']} until {curr_end_fmt}. No more classes today.",
            "has_next": False,
            "session": curr,
            "is_last": True
        }

    if nxt:
        nxt_start_fmt = _format_time_12h(nxt["start"])
        mins = minutes_until(student_id, nxt["start"])
        dur_str = format_duration(mins)
        speech = f"Your next class is {nxt['title']} at {nxt_start_fmt} in room {nxt['room']}. It starts in {dur_str}."
        return {
            "speech": speech,
            "card_title": f"Next Class: {nxt['title']}",
            "card_content": f"{nxt['title']} at {nxt_start_fmt} ({nxt['room']})\nStarts in {dur_str}",
            "has_next": True,
            "session": nxt,
            "starts_in_min": mins
        }

    # All classes for today have finished
    tom_classes = get_classes_for_day(student_id, "tomorrow")
    if tom_classes:
        tom_day = (now_dt + timedelta(days=1)).strftime("%A")
        first_tom = tom_classes[0]
        speech = f"You have completed all your classes for today! Your next class tomorrow on {tom_day} is {first_tom['title']} at {first_tom['start_formatted']} in {first_tom['room']}."
        return {
            "speech": speech,
            "card_title": f"Next Class: {first_tom['title']} (Tomorrow)",
            "card_content": f"Today finished.\nNext: {first_tom['title']} at {first_tom['start_formatted']} in {first_tom['room']} ({tom_day})",
            "has_next": True,
            "session": first_tom
        }

    speech = "You have completed all your classes for today! No more classes scheduled."
    return {
        "speech": speech,
        "card_title": "Classes Finished for Today",
        "card_content": speech,
        "has_next": False,
        "session": None
    }


def get_classes_for_day(student_id: int, day_name: str) -> list[dict]:
    """Gets all classes for a specific day of week (e.g. 'MONDAY', 'TUESDAY', 'TOMORROW', 'TODAY')."""
    d_clean = (day_name or "").lower().strip()
    now_dt = clock.now(student_id)
    if d_clean in ("today", ""):
        target_day = now_dt.strftime("%A").upper()
    elif d_clean == "tomorrow":
        target_day = (now_dt + timedelta(days=1)).strftime("%A").upper()
    else:
        target_day = d_clean.upper()

    conn = get_conn()
    rows = conn.execute(
        """SELECT cs.id, c.name AS title, c.code, c.type, cs.room,
                  cs.start_time AS start, cs.end_time AS end, cs.day_of_week
           FROM class_session cs JOIN course c ON c.id = cs.course_id
           WHERE c.student_id = ? AND cs.day_of_week = ?
           ORDER BY cs.start_time""",
        (student_id, target_day),
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d["start_formatted"] = _format_time_12h(d["start"])
        d["end_formatted"] = _format_time_12h(d["end"])
        results.append(d)
    return results


def get_class_room_and_time_speech(student_id: int, subject: str = None, is_past_query: bool = False) -> dict:
    """
    Returns speech and card details stating class name, room no, and time for a class.
    Handles queries like:
    - 'what is the room number of DBMS'
    - 'when was the class of DBMS'
    - 'room number of OS'
    - 'when was the class'
    - 'what is the room number'
    """
    from assignments import is_subject_match

    now_dt = clock.now(student_id)
    now_time = _hhmm(now_dt)
    today_day = now_dt.strftime("%A").upper()

    chosen_session = None

    # Case 1: Subject specified
    if subject and str(subject).strip():
        sub_clean = str(subject).strip()

        # Check today's sessions first
        todays = today(student_id)
        matching_today = [s for s in todays if is_subject_match(sub_clean, s.get("title"), s.get("code"))]

        if matching_today:
            for s in matching_today:
                s["day_of_week"] = today_day

            if is_past_query:
                # Pick latest session that already started or ended
                past_matches = [s for s in matching_today if s["start"] <= now_time]
                chosen_session = past_matches[-1] if past_matches else matching_today[0]
            else:
                # Pick next upcoming session today, or first today
                upcoming_matches = [s for s in matching_today if s["end"] > now_time]
                chosen_session = upcoming_matches[0] if upcoming_matches else matching_today[0]
        else:
            # Check weekly schedule for next upcoming day with this subject
            all_week = weekly(student_id)
            day_order = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
            today_idx = day_order.index(today_day) if today_day in day_order else 0

            rotated_days = day_order[today_idx + 1:] + day_order[:today_idx + 1]
            for day in rotated_days:
                day_sessions = all_week.get(day, [])
                matches = [s for s in day_sessions if is_subject_match(sub_clean, s.get("title"), s.get("code"))]
                if matches:
                    chosen_session = matches[0]
                    chosen_session["day_of_week"] = day
                    break

        if not chosen_session:
            speech = f"I couldn't find any scheduled class for {sub_clean} in your timetable."
            return {
                "speech": speech,
                "card_title": f"Class Details: {sub_clean}",
                "card_content": speech,
                "session": None
            }

    # Case 2: Subject NOT specified (e.g. "when was the class", "what is the room number")
    else:
        todays = today(student_id)
        if is_past_query:
            # Look for most recent session that already started/ended today
            past_sessions = [s for s in todays if s["start"] <= now_time]
            if past_sessions:
                chosen_session = past_sessions[-1]
                chosen_session["day_of_week"] = today_day
            elif todays:
                chosen_session = todays[0]
                chosen_session["day_of_week"] = today_day
        else:
            # Look for current or next session
            curr = current(student_id)
            nxt = next_session(student_id)
            if curr:
                chosen_session = curr
                chosen_session["day_of_week"] = today_day
            elif nxt:
                chosen_session = nxt
                chosen_session["day_of_week"] = today_day
            elif todays:
                chosen_session = todays[0]
                chosen_session["day_of_week"] = today_day
            else:
                # Check tomorrow
                tom = get_classes_for_day(student_id, "tomorrow")
                if tom:
                    chosen_session = tom[0]
                    chosen_session["day_of_week"] = (now_dt + timedelta(days=1)).strftime("%A").upper()

        if not chosen_session:
            speech = "You have no classes scheduled for today or tomorrow."
            return {
                "speech": speech,
                "card_title": "Class Details",
                "card_content": speech,
                "session": None
            }

    title = chosen_session["title"]
    room = chosen_session["room"]
    start_fmt = chosen_session["start_formatted"]
    end_fmt = chosen_session.get("end_formatted", "")
    day_name = chosen_session.get("day_of_week", today_day).title()

    if chosen_session.get("day_of_week") == today_day:
        if is_past_query and chosen_session["end"] <= now_time:
            speech = f"Your {title} class was in room {room} at {start_fmt}."
        else:
            speech = f"Your {title} class is in room {room} at {start_fmt}."
    else:
        speech = f"Your {title} class is on {day_name} in room {room} at {start_fmt}."

    card_content = f"Class: {title}\nRoom: {room}\nTime: {start_fmt} - {end_fmt}\nDay: {day_name}"

    return {
        "speech": speech,
        "card_title": f"{title} (Room {room})",
        "card_content": card_content,
        "session": chosen_session
    }


def get_upcoming_classes_speech(student_id: int, target_day: str | None = None) -> dict:
    """
    Constructs spoken text and card content for upcoming classes query:
    e.g. 'what are the upcoming classes scheduled for me' or 'what classes do I have tomorrow'.
    """
    now_dt = clock.now(student_id)
    t = _hhmm(now_dt)
    
    # If user explicitly asked for tomorrow
    if target_day and str(target_day).lower().strip() == "tomorrow":
        tom_classes = get_classes_for_day(student_id, "tomorrow")
        tom_day_name = (now_dt + timedelta(days=1)).strftime("%A")
        if not tom_classes:
            speech = f"You don't have any classes scheduled for tomorrow ({tom_day_name}). Enjoy your free day!"
            return {
                "speech": speech,
                "card_title": f"No Classes Tomorrow ({tom_day_name})",
                "card_content": speech,
                "classes": []
            }
        
        classes_str = ", ".join([f"{c['title']} at {c['start_formatted']} in {c['room']}" for c in tom_classes])
        speech = f"Tomorrow on {tom_day_name}, you have {len(tom_classes)} class{'es' if len(tom_classes) != 1 else ''} scheduled: {classes_str}."
        card_text = "\n".join([f"• {c['title']} ({c['start_formatted']} - {c['end_formatted']}) - {c['room']}" for c in tom_classes])
        return {
            "speech": speech,
            "card_title": f"Classes Tomorrow ({tom_day_name})",
            "card_content": card_text,
            "classes": tom_classes
        }

    # General upcoming classes (today remaining + tomorrow preview)
    todays_all = today(student_id)
    upcoming_today = [s for s in todays_all if s["end"] > t]
    tom_classes = get_classes_for_day(student_id, "tomorrow")
    tom_day_name = (now_dt + timedelta(days=1)).strftime("%A")

    if upcoming_today:
        today_str = ", ".join([f"{c['title']} at {c['start_formatted']} in {c['room']}" for c in upcoming_today])
        speech = f"You have {len(upcoming_today)} upcoming class{'es' if len(upcoming_today) != 1 else ''} today: {today_str}."
        if tom_classes:
            speech += f" And tomorrow on {tom_day_name}, you have {len(tom_classes)} class{'es' if len(tom_classes) != 1 else ''} scheduled, starting with {tom_classes[0]['title']} at {tom_classes[0]['start_formatted']} in {tom_classes[0]['room']}."
            
        card_lines = [f"Today's Upcoming:"] + [f"• {c['title']} ({c['start_formatted']} - {c['end_formatted']}) - {c['room']}" for c in upcoming_today]
        if tom_classes:
            card_lines.append(f"\nTomorrow ({tom_day_name}):")
            card_lines.extend([f"• {c['title']} ({c['start_formatted']} - {c['end_formatted']}) - {c['room']}" for c in tom_classes])

        return {
            "speech": speech,
            "card_title": "Upcoming Classes",
            "card_content": "\n".join(card_lines),
            "classes": upcoming_today
        }

    # If no classes left today, check tomorrow
    if tom_classes:
        tom_str = ", ".join([f"{c['title']} at {c['start_formatted']} in {c['room']}" for c in tom_classes])
        speech = f"You have completed all classes for today! Tomorrow on {tom_day_name}, you have {len(tom_classes)} class{'es' if len(tom_classes) != 1 else ''} scheduled: {tom_str}."
        card_text = "\n".join([f"• {c['title']} ({c['start_formatted']} - {c['end_formatted']}) - {c['room']}" for c in tom_classes])
        return {
            "speech": speech,
            "card_title": f"Upcoming Tomorrow ({tom_day_name})",
            "card_content": card_text,
            "classes": tom_classes
        }

    speech = "You have no upcoming classes scheduled for today or tomorrow. Enjoy your break!"
    return {
        "speech": speech,
        "card_title": "No Upcoming Classes",
        "card_content": speech,
        "classes": []
    }



def parse_time_input(time_str: str) -> str:
    """Parses various time expressions into 'HH:MM' (24-hour)."""
    if not time_str:
        return "10:00"
    s = str(time_str).strip().lower()
    s = re.sub(r"o'?clock", "", s).strip()
    
    # Handle Alexa special period codes
    if s in ("mo", "morning"):
        return "09:00"
    if s in ("af", "afternoon"):
        return "14:00"
    if s in ("ev", "evening"):
        return "17:00"
    if s in ("ni", "night"):
        return "19:00"
        
    # Word numbers map for spoken times like "two p.m."
    word_hours = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
        "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12"
    }
    s_norm = s.replace(".", "").strip()
    for w, num_s in word_hours.items():
        s_norm = re.sub(r'\b' + w + r'\b', num_s, s_norm)

    # Match standard time e.g. "14:00", "09:30"
    iso_match = re.match(r'^(\d{1,2}):(\d{2})$', s_norm)
    if iso_match:
        h = int(iso_match.group(1))
        m = int(iso_match.group(2))
        return f"{h:02d}:{m:02d}"

    # Match 12-hour or natural format e.g. "2 pm", "2:30 pm", "10 am", "11:15", "10"
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s_norm)
    if m:
        h = int(m.group(1))
        min_val = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        elif not ampm:
            # If no AM/PM provided: college hours typical heuristic
            # 1 to 7 is usually 1 PM to 7 PM (13:00 to 19:00)
            if 1 <= h <= 7:
                h += 12
        return f"{h:02d}:{min_val:02d}"
        
    return "10:00"


def compute_end_time(start_hhmm: str, duration_minutes: int = 60) -> str:
    """Computes end time by adding duration_minutes to start_hhmm."""
    try:
        h, m = map(int, start_hhmm.split(":"))
        total_min = (h * 60 + m + duration_minutes) % (24 * 60)
        return f"{total_min // 60:02d}:{total_min % 60:02d}"
    except Exception:
        return "11:00"


def clean_room_number(room_str: str) -> str:
    """Standardizes room number representations including spoken numbers like 'c. one oh two'."""
    if not room_str:
        return "Room 101"
    r = str(room_str).strip()
    r = re.sub(r'^(?:with\s+)?(?:in\s+)?(?:at\s+)?(?:room\s+(?:no\.?|number)?|no\.?)\s*', '', r, flags=re.I).strip()
    if not r:
        return "Room 101"
        
    # Normalize spoken digit words e.g. "c. one oh two", "b two oh four"
    word_to_num = {
        "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
    }
    r_clean = r.replace(".", " ").replace("-", " ").lower()
    tokens = r_clean.split()
    converted_tokens = [word_to_num.get(t, t) for t in tokens]
    
    # Letter + digits e.g. ['c', '1', '0', '2'] -> "C-102"
    if len(converted_tokens) >= 2 and len(converted_tokens[0]) == 1 and converted_tokens[0].isalpha() and all(t.isdigit() for t in converted_tokens[1:]):
        digits = "".join(converted_tokens[1:])
        return f"{converted_tokens[0].upper()}-{digits}"
        
    # Just digits e.g. ['1', '0', '2'] -> "Room 102"
    if converted_tokens and all(t.isdigit() for t in converted_tokens):
        return f"Room {''.join(converted_tokens)}"
        
    joined = "".join(converted_tokens).upper()
    if re.match(r'^[A-Z]\d{2,4}$', joined):
        return f"{joined[0]}-{joined[1:]}"
    r_no_dot = r.strip('. \t\n')
    if len(r_no_dot) <= 2 or r_no_dot.isdigit():
        return f"Room {r_no_dot.upper()}"
    return r_no_dot.upper() if len(r_no_dot) <= 6 else r_no_dot.title()


def add_class_session(
    student_id: int,
    subject: str,
    room: str,
    time_str: str,
    day_of_week: str | None = None,
    duration_minutes: int = 60
) -> dict:
    """
    Adds a new class session to the database.
    Creates the course if it doesn't already exist for this student.
    """
    conn = get_conn()
    subject_clean = subject.strip() if subject else "General"
    room_clean = clean_room_number(room)
    start_time = parse_time_input(time_str)
    end_time = compute_end_time(start_time, duration_minutes)
    
    # Day of week calculation
    now_dt = clock.now(student_id)
    if not day_of_week:
        day_of_week = now_dt.strftime("%A").upper()
    else:
        d_lower = str(day_of_week).lower().strip()
        days_map = {
            "monday": "MONDAY", "tuesday": "TUESDAY", "wednesday": "WEDNESDAY",
            "thursday": "THURSDAY", "friday": "FRIDAY", "saturday": "SATURDAY", "sunday": "SUNDAY",
            "today": now_dt.strftime("%A").upper(),
            "tomorrow": (now_dt + timedelta(days=1)).strftime("%A").upper(),
            "day after tomorrow": (now_dt + timedelta(days=2)).strftime("%A").upper(),
            "yesterday": (now_dt - timedelta(days=1)).strftime("%A").upper(),
        }
        day_of_week = days_map.get(d_lower, d_lower.upper())
        valid_days = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}
        if day_of_week not in valid_days:
            if "tom" in d_lower:
                day_of_week = (now_dt + timedelta(days=1)).strftime("%A").upper()
            else:
                day_of_week = now_dt.strftime("%A").upper()
        
    course_type = "LAB" if "lab" in subject_clean.lower() else "THEORY"
    
    # 1. Find existing course for this student or create a new one
    course = conn.execute(
        "SELECT id, name, code FROM course WHERE student_id = ? AND LOWER(name) = LOWER(?)",
        (student_id, subject_clean)
    ).fetchone()
    
    if course:
        course_id = course["id"]
        course_name = course["name"]
    else:
        # Generate code from initials
        words = subject_clean.split()
        initials = "".join([w[0].upper() for w in words if w])[:4]
        code = f"CS{initials}" if len(initials) >= 2 else f"CS{initials}101"
        cur = conn.execute(
            "INSERT INTO course (student_id, code, name, type) VALUES (?, ?, ?, ?)",
            (student_id, code, subject_clean, course_type)
        )
        course_id = cur.lastrowid
        course_name = subject_clean
        
    # 2. Insert into class_session
    cur = conn.execute(
        """INSERT INTO class_session (course_id, day_of_week, start_time, end_time, room)
           VALUES (?, ?, ?, ?, ?)""",
        (course_id, day_of_week, start_time, end_time, room_clean)
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    start_fmt = _format_time_12h(start_time)
    end_fmt = _format_time_12h(end_time)
    
    return {
        "id": session_id,
        "course_id": course_id,
        "subject": course_name,
        "room": room_clean,
        "day": day_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "start_formatted": start_fmt,
        "end_formatted": end_fmt
    }
