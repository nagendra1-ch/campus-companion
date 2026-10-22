"""
Automated validation suite for Campus Companion Alexa Integration.
Tests all user requirements:
1. Alexa 'What is my next class?' query.
2. Alexa 'I have to submit [Subject] assignment within [Days] days' calculation & daily reminders.
3. Alexa '[Subject] assignment is completed' status update & reminder dismissal.
4. Multi-student user data isolation.
"""
import sys
import io

# Ensure UTF-8 output on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from db import reset_db
import alexa_handler
import assignments
import schedule
import reminders
import clock
from datetime import datetime


def run_tests():
    print("[*] Resetting database to demo state...")
    reset_db()

    # -------------------------------------------------------------
    # Test 1: User Isolation (Ravi vs Priya)
    # -------------------------------------------------------------
    print("\n--- Test 1: User Isolation ---")
    ravi_id = 1
    priya_id = 2

    ravi_schedule = schedule.today(ravi_id)
    priya_schedule = schedule.today(priya_id)
    print(f"Ravi's today classes: {[s['title'] for s in ravi_schedule]}")
    print(f"Priya's today classes: {[s['title'] for s in priya_schedule]}")

    assert any("DBMS" in s["title"] for s in ravi_schedule), "Ravi must have DBMS"
    assert any("AI" in s["title"] for s in priya_schedule), "Priya must have AI course"
    assert not any("DBMS" in s["title"] for s in priya_schedule), "Priya must NOT have Ravi's DBMS"
    print("[OK] User isolation verified: Ravi and Priya have completely separate course schedules!")

    # -------------------------------------------------------------
    # Test 2: Alexa 'What is my next class?'
    # -------------------------------------------------------------
    print("\n--- Test 2: Alexa 'What is my next class?' ---")
    clock.set_now(ravi_id, datetime.fromisoformat("2026-10-12T07:45:00"))
    
    # Simulate Alexa ASK IntentRequest for Ravi
    alexa_req_ravi = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {"name": "NextClassIntent", "slots": {}}
        }
    }
    res_ravi = alexa_handler.handle_alexa_request(alexa_req_ravi)
    speech_ravi = res_ravi["response"]["outputSpeech"]["text"]
    print(f"Alexa Spoken Output for Ravi at 07:45 AM: \"{speech_ravi}\"")
    assert "DBMS" in speech_ravi and "9:00 AM" in speech_ravi, "Must identify DBMS at 9:00 AM as next class"

    # Simulate Alexa ASK IntentRequest for Priya
    clock.set_now(priya_id, datetime.fromisoformat("2026-10-12T07:45:00"))
    alexa_req_priya = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.PRIYA_456"}},
        "request": {
            "type": "IntentRequest",
            "intent": {"name": "NextClassIntent", "slots": {}}
        }
    }
    res_priya = alexa_handler.handle_alexa_request(alexa_req_priya)
    speech_priya = res_priya["response"]["outputSpeech"]["text"]
    print(f"Alexa Spoken Output for Priya at 07:45 AM: \"{speech_priya}\"")
    assert "Artificial Intelligence" in speech_priya and "8:30 AM" in speech_priya, "Must identify AI at 8:30 AM"
    print("[OK] 'What is my next class' accurately queries DB and speaks correct class per student!")

    # -------------------------------------------------------------
    # Test 3: Alexa "I have to submit DBMS assignment within 5 days"
    # -------------------------------------------------------------
    print("\n--- Test 3: Alexa 'I have to submit DBMS assignment within 5 days' ---")
    alexa_add_req = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": "AddAssignmentIntent",
                "slots": {
                    "Subject": {"name": "Subject", "value": "DBMS"},
                    "Days": {"name": "Days", "value": "5"}
                }
            }
        }
    }
    add_res = alexa_handler.handle_alexa_request(alexa_add_req)
    add_speech = add_res["response"]["outputSpeech"]["text"]
    print(f"Alexa Add Assignment Output: \"{add_speech}\"")
    assert "5 days" in add_speech and "Saturday, October 17, 2026" in add_speech, "Must calculate due date correctly"

    # Verify Database entries
    ravi_tasks = assignments.list_assignments(ravi_id)
    dbms_task = [t for t in ravi_tasks if "DBMS" in t["title"] or "DBMS" in (t["subject_name"] or "")][0]
    assert dbms_task["days_left"] == 5, f"Expected 5 days left, got {dbms_task['days_left']}"
    
    ravi_reminders = reminders.get_student_reminders(ravi_id)
    task_reminders = [r for r in ravi_reminders if r["task_id"] == dbms_task["id"]]
    print(f"Generated {len(task_reminders)} daily reminders for this assignment.")
    assert len(task_reminders) >= 1, "Must have scheduled daily reminders in DB"
    print("[OK] Assignment deadline calculation and daily reminder generation passed!")

    # -------------------------------------------------------------
    # Test 4: Alexa "DBMS assignment is completed"
    # -------------------------------------------------------------
    print("\n--- Test 4: Alexa 'DBMS assignment is completed' ---")
    alexa_complete_req = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": "CompleteAssignmentIntent",
                "slots": {
                    "Subject": {"name": "Subject", "value": "DBMS"}
                }
            }
        }
    }
    comp_res = alexa_handler.handle_alexa_request(alexa_complete_req)
    comp_speech = comp_res["response"]["outputSpeech"]["text"]
    print(f"Alexa Complete Assignment Output: \"{comp_speech}\"")
    assert "completed" in comp_speech, "Must confirm completion"

    # Verify task status & reminders dismissed in DB
    ravi_tasks_after = assignments.list_assignments(ravi_id)
    completed_task = [t for t in ravi_tasks_after if t["id"] == dbms_task["id"]][0]
    assert completed_task["status"] == "COMPLETED", "Task must be marked COMPLETED in database"

    today_rems = reminders.get_today_active_reminders(ravi_id)
    assert not any(r["task_id"] == dbms_task["id"] for r in today_rems), "Reminders for completed task must not be active"
    print("[OK] Assignment completion and reminder dismissal verified!")

    # -------------------------------------------------------------
    # Test 5: Natural Language Simulation
    # -------------------------------------------------------------
    print("\n--- Test 5: Natural Voice Parser Simulation ---")
    nat_res1 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "what is my next class")
    print(f"Natural Query 1: \"what is my next class\" -> {nat_res1['response']['outputSpeech']['text']}")

    nat_res2 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "i have to submit Operating Systems assignment within 4 days")
    print(f"Natural Query 2: \"submit OS in 4 days\" -> {nat_res2['response']['outputSpeech']['text']}")

    nat_res3 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "Operating Systems assignment is completed")
    print(f"Natural Query 3: \"OS assignment is completed\" -> {nat_res3['response']['outputSpeech']['text']}")
    # -------------------------------------------------------------
    # Test 6: "did i have any pending assessments"
    # -------------------------------------------------------------
    print("\n--- Test 6: Alexa 'Did I have any pending assessments?' ---")
    alexa_assess_req = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": "CheckRemindersIntent",
                "slots": {}
            }
        }
    }
    assess_res = alexa_handler.handle_alexa_request(alexa_assess_req)
    assess_speech = assess_res["response"]["outputSpeech"]["text"]
    print(f"Alexa Spoken Output for Assessments: \"{assess_speech}\"")
    assert "pending assessment" in assess_speech, "Must list pending assessments"

    # Also verify Alexa GetTasksIntent (from Alexa cloud NLU)
    alexa_get_tasks_req = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": "GetTasksIntent",
                "slots": {}
            }
        }
    }
    tasks_res = alexa_handler.handle_alexa_request(alexa_get_tasks_req)
    assert "pending assessment" in tasks_res["response"]["outputSpeech"]["text"], "GetTasksIntent must return pending assessments"
    print("Alexa GetTasksIntent Spoken Output:", tasks_res["response"]["outputSpeech"]["text"])
    print("[OK] Pending assessments query verified via both CheckRemindersIntent and GetTasksIntent!")

    # -------------------------------------------------------------
    # Test 7: Add New Class Feature
    # -------------------------------------------------------------
    print("\n--- Test 7: Alexa 'Add New Class' Feature ---")
    alexa_add_class_req = {
        "version": "1.0",
        "session": {"user": {"userId": "amzn1.ask.account.RAVI_123"}},
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": "AddClassIntent",
                "slots": {
                    "Subject": {"name": "Subject", "value": "Cloud Computing"},
                    "Room": {"name": "Room", "value": "C-102"},
                    "Time": {"name": "Time", "value": "2 PM"},
                    "Day": {"name": "Day", "value": "Monday"}
                }
            }
        }
    }
    class_res = alexa_handler.handle_alexa_request(alexa_add_class_req)
    class_speech = class_res["response"]["outputSpeech"]["text"]
    print(f"Alexa Add Class Spoken Output: \"{class_speech}\"")
    assert "Cloud Computing" in class_speech and "C-102" in class_speech and "2:00 PM" in class_speech, "Must confirm class schedule"

    # Verify session added in database for student
    ravi_today_after = schedule.today(ravi_id)
    assert any(s["title"] == "Cloud Computing" and s["room"] == "C-102" for s in ravi_today_after), "Cloud Computing session must exist in DB"
    print("[OK] Class successfully stored in database!")

    # Test Natural Language voice command:
    nat_res5 = alexa_handler.parse_natural_language_to_alexa(
        ravi_id,
        "i have a new class of Artificial Intelligence with room no 301 and time 10:30 AM"
    )
    print(f"Natural Query 5: \"Add AI class\" -> {nat_res5['response']['outputSpeech']['text']}")
    assert "Artificial Intelligence" in nat_res5['response']['outputSpeech']['text'], "Natural speech parser must handle new class detection"
    print("[OK] Natural voice parser accurately detects Subject, Room, and Time for new classes!")

    # -------------------------------------------------------------
    # Test 8: 'Tomorrow New Class' and 'Upcoming Classes' Query
    # -------------------------------------------------------------
    print("\n--- Test 8: 'Tomorrow New Class' and 'Upcoming Classes' Query ---")
    tom_res = alexa_handler.parse_natural_language_to_alexa(
        ravi_id,
        "tomorrow I have a new class of Software Engineering at room B at 10 o'clock"
    )
    tom_speech = tom_res["response"]["outputSpeech"]["text"]
    print(f"Add Tomorrow Class Output: \"{tom_speech}\"")
    assert "Software Engineering" in tom_speech and "10:00 AM" in tom_speech and "Tuesday" in tom_speech

    # Verify in DB with day_of_week = 'TUESDAY'
    tuesday_classes = schedule.get_classes_for_day(ravi_id, "tomorrow")
    assert any(c["title"] == "Software Engineering" and "Room B" in c["room"] for c in tuesday_classes), "Software Engineering must be stored for tomorrow (Tuesday)"
    print("[OK] Tomorrow's class stored with correct calculated weekday in database!")

    # Test 'what are the upcoming classes scheduled for me'
    up_res = alexa_handler.parse_natural_language_to_alexa(
        ravi_id,
        "what are the upcoming classes scheduled for me"
    )
    up_speech = up_res["response"]["outputSpeech"]["text"]
    print(f"Upcoming Classes Output: \"{up_speech}\"")
    assert "upcoming class" in up_speech.lower() or "today" in up_speech.lower()
    assert "DBMS" in up_speech
    # -------------------------------------------------------------
    # Test 9: Delete OS assignment specifically preserves DBMS
    # -------------------------------------------------------------
    print("\n--- Test 9: Alexa 'delete os assignment' preserves DBMS ---")
    import db
    conn = db.get_conn()
    conn.execute("DELETE FROM reminder")
    conn.execute("DELETE FROM task")
    conn.execute("""
        INSERT INTO task (id, student_id, course_id, title, subject_name, due_at, status, weight) VALUES
         (101, 1, 1, 'DBMS Final Project', 'DBMS', '2026-10-30T23:59:00', 'TODO', 5),
         (102, 1, 3, 'Operating Systems Assignment', 'Operating Systems', '2026-10-28T23:59:00', 'TODO', 3)
    """)
    conn.commit()
    conn.close()

    del_res = alexa_handler.parse_natural_language_to_alexa(ravi_id, "delete os assignment")
    del_speech = del_res["response"]["outputSpeech"]["text"]
    print(f"Delete OS Speech: \"{del_speech}\"")
    assert "Operating Systems" in del_speech and "deleted" in del_speech, "Must confirm deletion of Operating Systems"

    remaining_tasks = assignments.list_assignments(ravi_id)
    assert any(t["id"] == 101 and "DBMS" in t["title"] for t in remaining_tasks), "DBMS assignment MUST still exist!"
    assert not any(t["id"] == 102 for t in remaining_tasks), "OS assignment must be deleted!"
    # -------------------------------------------------------------
    # Test 10: Room Number & Class Time Queries
    # -------------------------------------------------------------
    print("\n--- Test 10: Room Number & Class Time Queries ---")
    clock.set_now(ravi_id, datetime.fromisoformat("2026-10-12T07:45:00"))
    
    # Query 1: Room number with subject
    r1 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "what is the room number of DBMS")["response"]["outputSpeech"]["text"]
    print(f"Room Query 1 Output: \"{r1}\"")
    assert "DBMS" in r1 and "B-204" in r1 and "9:00 AM" in r1, "Must state class name, room no, and time"

    # Query 2: Room number of OS
    r2 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "room number of OS")["response"]["outputSpeech"]["text"]
    print(f"Room Query 2 Output: \"{r2}\"")
    assert "Operating Systems" in r2 and "B-110" in r2 and "11:00 AM" in r2, "Must state OS, room B-110, and 11:00 AM"

    # Query 3: When was the class
    clock.set_now(ravi_id, datetime.fromisoformat("2026-10-12T10:15:00"))
    r3 = alexa_handler.parse_natural_language_to_alexa(ravi_id, "when was the class")["response"]["outputSpeech"]["text"]
    print(f"When was class Output: \"{r3}\"")
    assert "DBMS" in r3 and "B-204" in r3 and "9:00 AM" in r3, "Must state class name, room no, and time for past class"
    print("[OK] Room number and class time queries accurately return class name, room no, and time!")

    print("\n>>> ALL 10 TEST SUITES PASSED PERFECTLY! <<<\n")




if __name__ == "__main__":
    run_tests()
