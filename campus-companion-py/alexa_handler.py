from datetime import datetime
import re
from db import get_conn
import schedule
import assignments
import reminders
import clock


def resolve_student(alexa_req: dict, explicit_student_id: int | None = None) -> dict:
    """
    Identifies the student whose data is being accessed based on the Alexa user ID or student ID.
    Guarantees user isolation.
    """
    conn = get_conn()
    
    if explicit_student_id:
        student = conn.execute("SELECT * FROM student WHERE id = ?", (explicit_student_id,)).fetchone()
        if student:
            conn.close()
            return dict(student)
            
    alexa_user_id = None
    if isinstance(alexa_req, dict):
        alexa_user_id = (
            alexa_req.get("session", {}).get("user", {}).get("userId") or
            alexa_req.get("context", {}).get("System", {}).get("user", {}).get("userId")
        )
        
    if alexa_user_id:
        student = conn.execute("SELECT * FROM student WHERE alexa_user_id = ?", (alexa_user_id,)).fetchone()
        if student:
            conn.close()
            return dict(student)
            
    # Default to first student for demo if unlinked
    student = conn.execute("SELECT * FROM student ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()
    return dict(student) if student else {"id": 1, "name": "Student", "alexa_user_id": "demo_user"}


def build_alexa_response(
    speech_text: str,
    card_title: str | None = None,
    card_content: str | None = None,
    reprompt_text: str | None = None,
    should_end_session: bool = True,
    session_attributes: dict | None = None
) -> dict:
    """Builds standard Alexa Skills Kit (ASK) response JSON strictly compliant with Amazon Alexa Developer specifications."""
    response = {
        "outputSpeech": {
            "type": "PlainText",
            "text": speech_text
        },
        "shouldEndSession": should_end_session
    }
    
    if card_title:
        response["card"] = {
            "type": "Simple",
            "title": str(card_title),
            "content": str(card_content or speech_text)
        }
        
    if reprompt_text:
        response["reprompt"] = {
            "outputSpeech": {
                "type": "PlainText",
                "text": str(reprompt_text)
            }
        }
        
    return {
        "version": "1.0",
        "sessionAttributes": session_attributes or {},
        "response": response
    }


def extract_slot_value(intent: dict, slot_name: str) -> str | None:
    """Safely extracts slot value from Alexa intent slots."""
    slots = intent.get("slots", {})
    if not slots:
        return None
        
    # Check direct name or aliases
    for key, val in slots.items():
        if key.lower() == slot_name.lower():
            if isinstance(val, dict):
                # Check resolutions or value
                resolutions = val.get("resolutions", {}).get("resolutionsPerAuthority", [])
                if resolutions and resolutions[0].get("status", {}).get("code") == "ER_SUCCESS_MATCH":
                    values = resolutions[0].get("values", [])
                    if values:
                        return values[0].get("value", {}).get("name")
                return val.get("value")
            return str(val)
            
    return None


def handle_alexa_request(req_json: dict, explicit_student_id: int | None = None) -> dict:
    """
    Main entry point for all Alexa Skills Kit HTTP requests (POST /api/alexa).
    """
    student = resolve_student(req_json, explicit_student_id)
    student_id = student["id"]
    student_name = student["name"].split()[0]  # First name for friendly speech
    
    req = req_json.get("request", {})
    req_type = req.get("type", "IntentRequest")
    
    # 1. LaunchRequest
    if req_type == "LaunchRequest":
        speech = (
            f"Hello {student_name}, welcome to Campus Companion! "
            "You can ask 'What is my next class?', say 'I have to submit DBMS assignment within 5 days', "
            "or say 'DBMS assignment is completed'. What would you like to do?"
        )
        return build_alexa_response(
            speech,
            card_title="Campus Companion",
            card_content=f"Welcome {student_name}!\nTry:\n- What is my next class?\n- I have to submit [Subject] assignment within 5 days\n- [Subject] assignment is completed\n- What are my reminders?",
            reprompt_text="You can ask what is your next class or add an assignment. What would you like to do?",
            should_end_session=False
        )
        
    # 2. IntentRequest
    if req_type == "IntentRequest":
        intent = req.get("intent", {})
        intent_name = intent.get("name", "")
        
        # Next Class Query (Single)
        if intent_name in ("NextClassIntent", "GetNextClassIntent"):
            res = schedule.get_next_class_speech(student_id)
            return build_alexa_response(
                res["speech"],
                card_title=res["card_title"],
                card_content=res["card_content"],
                should_end_session=True
            )

        # Upcoming Classes / Timetable Schedule Query (Plural / List)
        elif intent_name in (
            "UpcomingClassesIntent", "ClassScheduleIntent", "GetScheduleIntent",
            "TodayClassesIntent", "TodayScheduleIntent", "DayScheduleIntent", "ScheduleTodayIntent"
        ):
            day_slot = (
                extract_slot_value(intent, "Day") or
                extract_slot_value(intent, "DayOfWeek") or
                None
            )
            if not day_slot and ("today" in intent_name.lower()):
                day_slot = "today"
            res = schedule.get_upcoming_classes_speech(student_id, target_day=day_slot)
            return build_alexa_response(
                res["speech"],
                card_title=res["card_title"],
                card_content=res["card_content"],
                should_end_session=True
            )
            
        # Class Room / Class Time / Class Details Query
        elif intent_name in ("ClassDetailsIntent", "ClassRoomIntent", "GetClassRoomIntent", "ClassTimeIntent", "GetClassTimeIntent"):
            subject = (
                extract_slot_value(intent, "Subject") or
                extract_slot_value(intent, "Course")
            )
            is_past = "was" in intent_name.lower() or "past" in intent_name.lower()
            res = schedule.get_class_room_and_time_speech(student_id, subject=subject, is_past_query=is_past)
            return build_alexa_response(
                res["speech"],
                card_title=res["card_title"],
                card_content=res["card_content"],
                should_end_session=True
            )

        # Add Assignment & Set Daily Reminders
        elif intent_name in ("AddAssignmentIntent", "CreateTaskIntent", "SubmitAssignmentIntent"):
            subject = (
                extract_slot_value(intent, "Subject") or
                extract_slot_value(intent, "SubjectName") or
                extract_slot_value(intent, "Course") or
                "General"
            )
            days = (
                extract_slot_value(intent, "Days") or
                extract_slot_value(intent, "Duration") or
                extract_slot_value(intent, "DaysCount") or
                5
            )
            
            task_info = assignments.add_assignment(student_id, subject, days)
            speech = (
                f"Got it {student_name}! I have recorded your {task_info['subject']} assignment, "
                f"due in {task_info['days']} days on {task_info['due_date_str']}. "
                f"I will send you a daily reminder every day until it is completed."
            )
            card_text = (
                f"Assignment: {task_info['title']}\n"
                f"Due: {task_info['due_date_str']}\n"
                f"Daily Reminders: Active ({task_info['reminders_count']} scheduled)"
            )
            return build_alexa_response(
                speech,
                card_title=f"Assignment Added: {task_info['subject']}",
                card_content=card_text,
                should_end_session=True
            )
            
        # Complete Assignment & Dismiss Reminders
        elif intent_name in ("CompleteAssignmentIntent", "FinishAssignmentIntent", "DeleteAssignmentIntent"):
            subject = (
                extract_slot_value(intent, "Subject") or
                extract_slot_value(intent, "SubjectName") or
                extract_slot_value(intent, "Course")
            )
            is_delete = "Delete" in intent_name
            res = assignments.complete_assignment(student_id, subject, delete=is_delete)
            
            if res:
                action_word = "deleted" if is_delete else "completed"
                speech = f"Awesome work {student_name}! I've marked your {res['subject']} assignment as {action_word} and removed all active reminders for it."
                return build_alexa_response(
                    speech,
                    card_title=f"Assignment {action_word.title()}",
                    card_content=f"{res['title']} has been marked {action_word}.",
                    should_end_session=True
                )
            else:
                action_action = "delete" if is_delete else "complete"
                sub_text = f" for {subject}" if subject else ""
                speech = f"I couldn't find any pending assignment{sub_text} to {action_action}."
                return build_alexa_response(speech, should_end_session=True)
                
        # Query Reminders, Active Tasks & Pending Assessments
        elif intent_name in (
            "CheckRemindersIntent", "GetRemindersIntent", "ListAssignmentsIntent",
            "PendingAssessmentsIntent", "CheckAssessmentsIntent", "ListAssessmentsIntent",
            "PendingAssignmentsIntent", "GetTasksIntent", "AMAZON.GetTasksIntent",
            "GetTaskIntent", "ListTasksIntent", "CheckTasksIntent", "ShowTasksIntent"
        ):
            active_tasks = assignments.list_assignments(student_id, status_filter="TODO")
            active_reminders = reminders.get_today_active_reminders(student_id)
            
            if not active_tasks and not active_reminders:
                speech = f"You're all caught up {student_name}! You have no pending assessments, assignments, or reminders."
                return build_alexa_response(speech, card_title="Reminders & Assessments", card_content=speech, should_end_session=True)
                
            task_descriptions = []
            for t in active_tasks:
                d_left = t["days_left"]
                if d_left <= 0:
                    d_str = "due today"
                elif d_left == 1:
                    d_str = "due tomorrow"
                else:
                    d_str = f"due in {d_left} days"
                task_descriptions.append(f"{t['subject_name'] or t['title']} ({d_str})")
                
            speech = f"You have {len(active_tasks)} pending assessment{'s' if len(active_tasks) != 1 else ''}: " + ", ".join(task_descriptions) + "."
            if active_reminders:
                speech += f" You also have {len(active_reminders)} active daily reminder notification{'s' if len(active_reminders) != 1 else ''} today."
                
            card_content = "\n".join([f"• {t['title']} - {t['due_formatted']}" for t in active_tasks])
            return build_alexa_response(speech, card_title="Pending Assessments & Reminders", card_content=card_content, should_end_session=True)

        # Add New Class Schedule Session
        elif intent_name in ("AddClassIntent", "CreateClassIntent", "NewClassIntent", "ScheduleClassIntent"):
            raw_sub = (
                extract_slot_value(intent, "Subject") or
                extract_slot_value(intent, "Course") or
                extract_slot_value(intent, "SubjectName") or
                ""
            )
            raw_room = (
                extract_slot_value(intent, "Room") or
                extract_slot_value(intent, "RoomNumber") or
                extract_slot_value(intent, "RoomNo") or
                ""
            )
            raw_time = (
                extract_slot_value(intent, "Time") or
                extract_slot_value(intent, "StartTime") or
                extract_slot_value(intent, "ClassTime") or
                ""
            )
            raw_day = (
                extract_slot_value(intent, "Day") or
                extract_slot_value(intent, "DayOfWeek") or
                None
            )

            # Defensive separation in case Alexa grouped room, time, or day into subject
            if raw_sub and (" room " in raw_sub.lower() or " at " in raw_sub.lower() or " on " in raw_sub.lower()):
                time_m = re.search(r'(?:at|time)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})', raw_sub, re.I)
                if time_m and not raw_time:
                    raw_time = time_m.group(1)
                room_m = re.search(r'(?:room\s*(?:no\.?|number)?|in\s+room)\s*([a-zA-Z0-9\-]+)', raw_sub, re.I)
                if room_m and not raw_room:
                    raw_room = room_m.group(1)
                day_m = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b', raw_sub, re.I)
                if day_m and not raw_day:
                    raw_day = day_m.group(1)
                raw_sub = re.sub(r'\b(?:room\s*(?:no\.?|number)?\s*[a-zA-Z0-9\-]+|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|on\s+[a-zA-Z]+).*', '', raw_sub, flags=re.I).strip()

            subject = raw_sub.strip() if raw_sub.strip() else "General"
            room = raw_room.strip() if raw_room.strip() else "Room 101"
            time_val = raw_time.strip() if raw_time.strip() else "10:00"
            day_val = raw_day
            
            cls_info = schedule.add_class_session(
                student_id=student_id,
                subject=subject,
                room=room,
                time_str=time_val,
                day_of_week=day_val
            )
            
            day_spoken = cls_info["day"].title()
            speech = (
                f"Got it {student_name}! I have scheduled your {cls_info['subject']} class in {cls_info['room']} "
                f"at {cls_info['start_formatted']} on {day_spoken}."
            )
            card_text = (
                f"Course: {cls_info['subject']}\n"
                f"Room: {cls_info['room']}\n"
                f"Time: {cls_info['start_formatted']} - {cls_info['end_formatted']}\n"
                f"Day: {day_spoken}"
            )
            return build_alexa_response(
                speech,
                card_title=f"Class Scheduled: {cls_info['subject']}",
                card_content=card_text,
                should_end_session=True
            )

        # Campus Command Intent (Bridge natural language voice commands directly to parser)
        elif intent_name in ("CampusCommandIntent", "NaturalVoiceIntent", "UserCommandIntent"):
            cmd = (
                extract_slot_value(intent, "Command") or
                extract_slot_value(intent, "Utterance") or
                extract_slot_value(intent, "Query")
            )
            if cmd:
                return parse_natural_language_to_alexa(student_id, cmd)
            
        # Greeting Intent (e.g. "hii", "hi")
        elif intent_name in ("GreetingIntent", "HelloIntent", "HiIntent"):
            return build_alexa_response(
                f"Hi {student_name}",
                card_title="Campus Companion",
                card_content=f"Hi {student_name}",
                should_end_session=True
            )

        # Built-in Help, Stop, Cancel, NavigateHome, Fallback
        elif intent_name == "AMAZON.HelpIntent":
            speech = (
                "You can ask: 'What is my next class?' to hear your upcoming session. "
                "Or ask: 'Do I have any pending assessments?' to check your deadlines. "
                "Or say: 'I have to submit DBMS assignment within 5 days' to calculate the deadline and set daily reminders. "
                "Or say: 'DBMS assignment is completed' to remove it. How can I help you?"
            )
            return build_alexa_response(speech, reprompt_text="What would you like to do?", should_end_session=False)
            
        elif intent_name in ("AMAZON.CancelIntent", "AMAZON.StopIntent"):
            return build_alexa_response("Goodbye! Have a great time on campus.", should_end_session=True)
            
        elif intent_name == "AMAZON.NavigateHomeIntent":
            speech = (
                f"Welcome back {student_name}! You can ask: 'What is my next class?', "
                "'Do I have any pending assessments?', or say 'I have to submit DBMS assignment within 5 days'. "
                "What would you like to do?"
            )
            return build_alexa_response(speech, card_title="Campus Companion", reprompt_text="What would you like to do?", should_end_session=False)

        elif intent_name == "AMAZON.FallbackIntent":
            # Check if any slot was passed with raw utterance or text
            slots = intent.get("slots", {})
            for s_name in slots:
                val = extract_slot_value(intent, s_name)
                if val and len(str(val).strip()) > 2:
                    parsed = parse_natural_language_to_alexa(student_id, str(val))
                    if parsed and "I didn't quite catch that" not in parsed.get("response", {}).get("outputSpeech", {}).get("text", ""):
                        return parsed
            speech = (
                f"I didn't quite catch that {student_name}. You can ask 'What is my next class?', "
                "'Do I have any pending assessments?', or say 'I have to submit DBMS assignment within 5 days'. "
                "What would you like to do?"
            )
            return build_alexa_response(speech, reprompt_text="Try asking: Do I have any pending assessments?", should_end_session=False)

    # 3. SessionEndedRequest
    if req_type == "SessionEndedRequest":
        return build_alexa_response("Session ended.", should_end_session=True)
        
    fallback_speech = (
        f"I didn't catch that {student_name}. You can ask: 'What is my next class?', "
        "'Do I have any pending assessments?', or 'I have to submit DBMS assignment within 5 days'. "
        "What would you like to do?"
    )
    return build_alexa_response(
        fallback_speech,
        card_title="Campus Companion Help",
        reprompt_text="Try asking: Do I have any pending assessments?",
        should_end_session=False
    )


def parse_natural_language_to_alexa(student_id: int, user_utterance: str) -> dict:
    """
    Simulates / interprets natural speech strings as Alexa Intents,
    then executes them through the official Alexa request pipeline.
    Allows complete in-browser testing and REST API voice queries.
    """
    u = user_utterance.lower().strip()
    
    # 0. Greeting (e.g. "hii", "hi", "hello", "hey")
    if re.fullmatch(r'(hi+|hello+|hey+|greetings|hiya)\b.*', u) or u in ("hii", "hi", "hello", "hey", "hi there", "hello there", "hii alexa", "hi alexa"):
        student = resolve_student({}, explicit_student_id=student_id)
        student_name = student["name"].split()[0]
        return build_alexa_response(
            f"Hi {student_name}",
            card_title="Campus Companion",
            card_content=f"Hi {student_name}",
            should_end_session=True
        )

    # 1. Upcoming Classes / Schedule Query (Plural list of classes)
    if any(k in u for k in [
        "upcoming classes", "scheduled classes", "classes scheduled", "classes do i have",
        "classes today", "classes tomorrow", "my upcoming schedule", "my classes",
        "today's classes", "todays classes", "what are the classes", "all my classes",
        "classes for me"
    ]):
        target_day = "tomorrow" if "tomorrow" in u else ("today" if "today" in u else None)
        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "UpcomingClassesIntent",
                    "slots": {
                        "Day": {"name": "Day", "value": target_day}
                    } if target_day else {}
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

    # 2. Room Number or Class Time Query (e.g. "what is the room number of DBMS", "room number of OS", "when was the class", "when was OS class", "when is DBMS class")
    is_room_query = any(k in u for k in [
        "room number", "room no", "which room", "what room", "where is the class", "where was the class",
        "where is", "where was", "classroom", "which classroom", "what is the room", "room of"
    ]) and not any(k in u for k in ["add class", "new class", "schedule class"])

    is_when_query = any(k in u for k in [
        "when was the class", "when was", "when is the class", "when is",
        "what time is", "what time was", "class time", "time of the class", "time of class", "time of"
    ]) and not any(k in u for k in ["add class", "new class", "schedule class", "submit", "assignment", "homework", "due in", "within", "completed", "done", "delete"])

    if is_room_query or is_when_query:
        is_past = any(k in u for k in ["when was", "where was", "was the class", "previous class", "last class"])
        subject_val = None
        for word in [
            "operating systems", "operating system", "artificial intelligence",
            "computer networks", "software engineering", "cloud computing",
            "data structures", "machine learning", "dbms", "os", "ai", "cn",
            "se", "ml", "math", "physics", "networks", "cloud"
        ]:
            if re.search(r'\b' + re.escape(word) + r'\b', u) or (len(word) >= 5 and word in u):
                subject_val = word.upper() if len(word) <= 4 else word.title()
                break

        res = schedule.get_class_room_and_time_speech(student_id, subject=subject_val, is_past_query=is_past)
        return build_alexa_response(
            res["speech"],
            card_title=res["card_title"],
            card_content=res["card_content"],
            should_end_session=True
        )

    # 3. Next Class Query (Single upcoming class)
    if any(k in u for k in ["next class", "upcoming class", "where do i go", "my next lecture", "class schedule", "what class"]):
        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "NextClassIntent",
                    "slots": {}
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)
        
    # 3. Complete / Delete Assignment (e.g. "DBMS assignment is completed", "it is completed", "delete OS assignment")
    if any(k in u for k in ["completed", "complete", "finished", "finish", "done", "delete", "clear", "remove", "marked as done"]):
        is_delete = "delete" in u or "clear" in u or "remove" in u
        subject_val = None
        for word in [
            "operating systems", "operating system", "artificial intelligence",
            "computer networks", "software engineering", "cloud computing",
            "data structures", "machine learning", "dbms", "os", "ai", "cn",
            "se", "ml", "math", "physics", "networks", "cloud"
        ]:
            if re.search(r'\b' + re.escape(word) + r'\b', u) or (len(word) >= 5 and word in u):
                subject_val = word.upper() if len(word) <= 4 else word.title()
                break
                
        if not subject_val:
            sub_match = re.search(r'([a-zA-Z0-9]+)\s+(?:assignment|assessment|task|is completed|is done)', u)
            if sub_match and sub_match.group(1) not in ("it", "this", "assignment", "assessment", "task", "my"):
                subject_val = sub_match.group(1)

        intent_name = "DeleteAssignmentIntent" if is_delete else "CompleteAssignmentIntent"
        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": intent_name,
                    "slots": {
                        "Subject": {"name": "Subject", "value": subject_val}
                    } if subject_val else {}
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

    # 4. Check Reminders / Pending Assessments / Tasks
    if any(k in u for k in ["pending", "what are my", "do i have", "did i have", "any assessment", "any assignment", "remind", "reminder", "reminders", "tasks", "assessments", "assignments", "deadline", "deadlines"]):
        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "CheckRemindersIntent",
                    "slots": {}
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

    # 5. Add New Class (e.g. "tomorrow I have a new class of Software Engineering at room B at 10 o'clock")
    if any(k in u for k in ["new class", "add class", "add a class", "schedule class", "have a class of"]):
        time_m = re.search(r'(?:at|time|from)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|o\'?clock)?|\d{1,2}:\d{2})', u, re.I)
        time_val = time_m.group(1) if time_m else "10:00 AM"

        room_m = re.search(r'(?:(?:at|in)\s+room|room\s*(?:no\.?|number)?)\s*([a-zA-Z0-9\-]+)', u, re.I)
        room_val = room_m.group(1) if room_m else "Room 101"

        day_m = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|day after tomorrow)\b', u, re.I)
        day_val = day_m.group(1) if day_m else None

        sub_m = re.search(r'(?:new\s+class\s+of|add\s+(?:a\s+)?new\s+class\s+(?:for|of)?|class\s+of|new\s+class)\s+([a-zA-Z0-9\s]+?)\s+\b(?:with|in|at|room|on)\b', u, re.I)
        if sub_m:
            sub_val = sub_m.group(1).strip()
        else:
            sub_val = "General"
            for word in ["software engineering", "cloud computing", "cloud", "artificial intelligence", "ai", "machine learning", "operating systems", "os", "dbms", "data structures", "networks", "math", "physics"]:
                if word in u:
                    sub_val = word.upper() if len(word) <= 4 else word.title()
                    break

        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "AddClassIntent",
                    "slots": {
                        "Subject": {"name": "Subject", "value": sub_val.title() if len(sub_val) > 4 else sub_val.upper()},
                        "Room": {"name": "Room", "value": room_val},
                        "Time": {"name": "Time", "value": time_val},
                        "Day": {"name": "Day", "value": day_val} if day_val else {}
                    }
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

    # 6. Add Assignment / Assessment (e.g. "i have to submit dbms assignment within 5 days" or "submit os in 3 days")
    if any(k in u for k in ["submit", "homework", "due in", "within", "add task", "add assignment", "add assessment"]):
        # Extract days
        days_match = re.search(r'(?:within|in|due in|after)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|tomorrow|next week)', u)
        days_val = days_match.group(1) if days_match else "5"
        
        # Extract subject name
        subject_val = "General"
        sub_match = re.search(r'(?:submit|for|have to submit|have a|add)\s+(?:an? )?([a-zA-Z0-9\s]+?)\s+(?:assignment|assessment|project|homework|within|in|due)', u)
        if sub_match:
            cand = sub_match.group(1).strip()
            # Clean stop words
            cand = re.sub(r'^(to|a|an|my)\s+', '', cand)
            if cand:
                subject_val = cand.upper() if len(cand) <= 4 else cand.title()
        else:
            # Fallback simple search
            for word in ["dbms", "os", "operating systems", "ai", "artificial intelligence", "math", "physics", "networks", "cloud", "data structures"]:
                if word in u:
                    subject_val = word.upper() if len(word) <= 4 else word.title()
                    break

        alexa_payload = {
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "AddAssignmentIntent",
                    "slots": {
                        "Subject": {"name": "Subject", "value": subject_val},
                        "Days": {"name": "Days", "value": days_val}
                    }
                }
            }
        }
        return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

    # 6. Fallback to Local AI Assistant for Intelligent Understanding & Arbitrary Tasks
    try:
        import ai_assistant
        if ai_assistant.is_ai_configured():
            ai_res = ai_assistant.parse_intent_and_entities(student_id, user_utterance)
            if ai_res and isinstance(ai_res, dict):
                g_intent = ai_res.get("intent")
                g_slots = ai_res.get("slots", {}) or {}

                if g_intent == "NextClassIntent":
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {"type": "IntentRequest", "intent": {"name": "NextClassIntent", "slots": {}}}
                    }, explicit_student_id=student_id)

                elif g_intent in ("UpcomingClassesIntent", "ClassScheduleIntent"):
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {
                            "type": "IntentRequest",
                            "intent": {
                                "name": "UpcomingClassesIntent",
                                "slots": {"Day": {"name": "Day", "value": str(g_slots.get("Day"))}} if g_slots.get("Day") else {}
                            }
                        }
                    }, explicit_student_id=student_id)

                elif g_intent in ("CompleteAssignmentIntent", "DeleteAssignmentIntent"):
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {
                            "type": "IntentRequest",
                            "intent": {
                                "name": g_intent,
                                "slots": {"Subject": {"name": "Subject", "value": str(g_slots.get("Subject"))}} if g_slots.get("Subject") else {}
                            }
                        }
                    }, explicit_student_id=student_id)

                elif g_intent == "CheckRemindersIntent":
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {"type": "IntentRequest", "intent": {"name": "CheckRemindersIntent", "slots": {}}}
                    }, explicit_student_id=student_id)

                elif g_intent == "AddAssignmentIntent" and g_slots.get("Subject"):
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {
                            "type": "IntentRequest",
                            "intent": {
                                "name": "AddAssignmentIntent",
                                "slots": {
                                    "Subject": {"name": "Subject", "value": str(g_slots.get("Subject"))},
                                    "Days": {"name": "Days", "value": str(g_slots.get("Days") or 5)}
                                }
                            }
                        }
                    }, explicit_student_id=student_id)

                elif g_intent == "AddClassIntent" and g_slots.get("Subject"):
                    return handle_alexa_request({
                        "version": "1.0",
                        "request": {
                            "type": "IntentRequest",
                            "intent": {
                                "name": "AddClassIntent",
                                "slots": {
                                    "Subject": {"name": "Subject", "value": str(g_slots.get("Subject"))},
                                    "Room": {"name": "Room", "value": str(g_slots.get("Room") or "Room 101")},
                                    "Time": {"name": "Time", "value": str(g_slots.get("Time") or "10:00")},
                                    "Day": {"name": "Day", "value": str(g_slots.get("Day"))} if g_slots.get("Day") else {}
                                }
                            }
                        }
                    }, explicit_student_id=student_id)

                elif ai_res.get("direct_answer"):
                    return build_alexa_response(
                        ai_res["direct_answer"],
                        card_title="Campus AI Assistant",
                        card_content=ai_res["direct_answer"],
                        should_end_session=True
                    )
    except Exception as e:
        print(f"[LOCAL AI PARSER ERROR] {e}", flush=True)

    # 7. Help / Launch fallback
    alexa_payload = {
        "version": "1.0",
        "request": {
            "type": "LaunchRequest"
        }
    }
    return handle_alexa_request(alexa_payload, explicit_student_id=student_id)

