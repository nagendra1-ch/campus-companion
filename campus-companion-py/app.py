import sys
import io
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

# Ensure UTF-8 output on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import clock
import context
import schedule
import assignments
import reminders
import alexa_handler
import ai_assistant
from pathlib import Path
from db import get_conn, reset_db

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")

# Ensure tables are initialized when imported in serverless / production environments
try:
    _conn = get_conn()
    _has_tables = _conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student'").fetchone()
    _conn.close()
    if not _has_tables:
        reset_db()
except Exception:
    reset_db()



@app.get("/")
def home():
    return app.send_static_file("index.html")


# ==========================================================
# 1. ALEXA SKILLS KIT (ASK) & VOICE INTEGRATION ENDPOINTS
# ==========================================================

@app.post("/api/alexa")
def alexa_webhook():
    """
    Main webhook endpoint for Amazon Alexa Skills Kit.
    Receives all JSON POST requests from Alexa Cloud or Alexa Developer Console.
    Supports user isolation via Alexa userId mapping or ?studentId= query parameter.
    """
    req_data = request.get_json(force=True, silent=True) or {}
    explicit_student_id = request.args.get("studentId", None, type=int)
    
    intent_obj = req_data.get('request', {}).get('intent', {})
    print(f"\n[ALEXA REQUEST] Type: {req_data.get('request', {}).get('type')}, Intent: {intent_obj.get('name')}, Slots: {intent_obj.get('slots')}", flush=True)
    try:
        response = alexa_handler.handle_alexa_request(req_data, explicit_student_id=explicit_student_id)
        print(f"[ALEXA RESPONSE] Spoken: \"{response.get('response', {}).get('outputSpeech', {}).get('text')}\"\n", flush=True)
        return jsonify(response)
    except Exception as e:
        print(f"[ALEXA ERROR] {e}", flush=True)
        error_res = alexa_handler.build_alexa_response("Sorry, there was an error processing your request. Please try again.")
        return jsonify(error_res)


@app.post("/api/alexa/simulate-voice")
def alexa_simulate_voice():
    """
    Simulates natural voice utterances directly from the browser/tester.
    e.g. {"utterance": "what is my next class", "studentId": 1}
         {"utterance": "i have to submit DBMS assignment within 5 days", "studentId": 1}
         {"utterance": "DBMS assignment is completed", "studentId": 1}
    """
    data = request.get_json(force=True, silent=True) or {}
    utterance = data.get("utterance", "").strip()
    student_id = data.get("studentId", request.args.get("studentId", 1, type=int))
    
    if not utterance:
        return jsonify({"error": "No utterance provided"}), 400
        
    result = alexa_handler.parse_natural_language_to_alexa(student_id, utterance)
    return jsonify({
        "inputUtterance": utterance,
        "studentId": student_id,
        "spokenResponse": result.get("response", {}).get("outputSpeech", {}).get("text", ""),
        "alexaResponse": result
    })


@app.get("/api/alexa/next-class")
def alexa_get_next_class_quick():
    """Quick GET endpoint for querying next class for an Alexa device/user."""
    student_id = request.args.get("studentId", 1, type=int)
    res = schedule.get_next_class_speech(student_id)
    return jsonify({
        "studentId": student_id,
        "speech": res["speech"],
        "data": res
    })


@app.post("/api/alexa/add-assignment")
def alexa_add_assignment_quick():
    """Quick POST helper for adding an assignment and scheduling daily reminders."""
    data = request.get_json(force=True, silent=True) or {}
    student_id = data.get("studentId", request.args.get("studentId", 1, type=int))
    subject = data.get("subject", "General")
    days = data.get("days", 5)
    
    task_info = assignments.add_assignment(student_id, subject, days)
    return jsonify({
        "success": True,
        "task": task_info,
        "speech": f"I have recorded your {task_info['subject']} assignment due in {task_info['days']} days on {task_info['due_date_str']} and set daily reminders."
    })


@app.post("/api/alexa/complete-assignment")
def alexa_complete_assignment_quick():
    """Quick POST helper to mark assignment completed or delete."""
    data = request.get_json(force=True, silent=True) or {}
    student_id = data.get("studentId", request.args.get("studentId", 1, type=int))
    subject = data.get("subject")
    task_id = data.get("taskId")
    delete = data.get("delete", False)
    
    res = assignments.complete_assignment(student_id, subject=subject, task_id=task_id, delete=delete)
    if res:
        return jsonify({
            "success": True,
            "task": res,
            "speech": f"Marked {res['subject']} assignment as completed and dismissed reminders."
        })
    return jsonify({"success": False, "message": "No matching assignment found"}), 404


# ==========================================================
# 2. STUDENT & CONTEXT MANAGEMENT (MULTI-USER ISOLATION)
# ==========================================================

@app.get("/api/students")
def get_all_students():
    """Lists all student profiles in the database."""
    conn = get_conn()
    students = conn.execute("SELECT * FROM student ORDER BY id ASC").fetchall()
    conn.close()
    return jsonify([dict(s) for s in students])


@app.get("/api/context/<int:student_id>")
def get_context(student_id):
    """Returns real-time context snapshot for the specific student."""
    return jsonify(context.snapshot(student_id))


# ==========================================================
# 3. SCHEDULE & TIMETABLE ENDPOINTS
# ==========================================================

@app.get("/api/schedule/today")
def get_schedule_today():
    """Returns today's sessions for the specified student."""
    student_id = request.args.get("studentId", 1, type=int)
    return jsonify(schedule.today(student_id))


@app.get("/api/schedule/weekly/<int:student_id>")
def get_schedule_weekly(student_id):
    """Returns full weekly timetable for the specified student."""
    return jsonify(schedule.weekly(student_id))


@app.post("/api/schedule/add")
def add_new_class_session():
    """Adds a new class schedule session for the student."""
    data = request.get_json(force=True, silent=True) or {}
    student_id = data.get("studentId", request.args.get("studentId", 1, type=int))
    subject = data.get("subject", "General")
    room = data.get("room", "Room 101")
    time_val = data.get("time", "10:00")
    day_val = data.get("day", None)
    res = schedule.add_class_session(student_id, subject, room, time_val, day_val)
    return jsonify({"success": True, "class": res})


# ==========================================================
# 4. ASSIGNMENTS & TASKS ENDPOINTS
# ==========================================================

@app.get("/api/assignments/<int:student_id>")
def get_assignments(student_id):
    """Lists all assignments for the student with calculated days remaining."""
    status_filter = request.args.get("status", "ALL")
    return jsonify(assignments.list_assignments(student_id, status_filter=status_filter))


@app.post("/api/assignments/<int:student_id>")
def add_new_assignment(student_id):
    """Creates a new assignment and automatically generates daily reminders."""
    data = request.get_json(force=True, silent=True) or {}
    subject = data.get("subject", "General")
    days = data.get("days", 5)
    title = data.get("title")
    weight = data.get("weight", 3)
    
    result = assignments.add_assignment(student_id, subject, days, title=title, weight=weight)
    return jsonify(result), 201


@app.put("/api/assignments/<int:student_id>/<int:task_id>/complete")
def complete_task(student_id, task_id):
    """Marks task as completed and dismisses its reminders."""
    res = assignments.complete_assignment(student_id, task_id=task_id, delete=False)
    if res:
        return jsonify(res)
    return jsonify({"error": "Task not found"}), 404


@app.delete("/api/assignments/<int:student_id>/<int:task_id>")
def delete_task(student_id, task_id):
    """Deletes task and its reminders."""
    ok = assignments.delete_assignment(student_id, task_id)
    if ok:
        return jsonify({"success": True, "id": task_id})
    return jsonify({"error": "Task not found"}), 404


# ==========================================================
# 5. REMINDERS & NOTIFICATIONS ENDPOINTS
# ==========================================================

@app.get("/api/reminders/<int:student_id>")
def get_student_reminders(student_id):
    """Returns active and pending daily reminders for the student."""
    return jsonify({
        "todayReminders": reminders.get_today_active_reminders(student_id),
        "allReminders": reminders.get_student_reminders(student_id, status_filter="ALL")
    })


@app.post("/api/reminders/<int:student_id>/<int:reminder_id>/dismiss")
def dismiss_student_reminder(student_id, reminder_id):
    """Dismisses a daily reminder notification."""
    ok = reminders.dismiss_reminder(student_id, reminder_id)
    return jsonify({"success": ok})


# ==========================================================
# 6. SIMULATOR & TIME TRAVEL CONTROLS
# ==========================================================

@app.post("/api/sim/transition/<int:student_id>")
def sim_transition(student_id):
    try:
        return jsonify(context.transition(student_id, request.get_json()["event"]))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/sim/clock/<int:student_id>")
def sim_clock(student_id):
    clock.set_now(student_id, datetime.fromisoformat(request.get_json()["simNow"]))
    return jsonify(context.snapshot(student_id))


@app.post("/api/sim/clock/live/<int:student_id>")
def sim_clock_live(student_id):
    """Restores live system date and time from the system."""
    clock.set_live(student_id)
    return jsonify(context.snapshot(student_id))


@app.post("/api/sim/advance-day/<int:student_id>")
def sim_advance_day(student_id):
    """Advances simulated time by 1 full day (24h) to test daily reminders ticking down."""
    curr_now = clock.now(student_id)
    next_day = curr_now + timedelta(days=1)
    clock.set_now(student_id, next_day)
    return jsonify(context.snapshot(student_id))


@app.post("/api/sim/reset")
def sim_reset():
    """Resets the entire database with fresh demo data."""
    reset_db()
    return jsonify({"status": "Database reset to initial demo state"})


# ==========================================================
# 7. LOCAL TRANSFORMERS AI ACADEMIC & TASK ASSISTANT ENDPOINTS
# ==========================================================

@app.get("/api/ai/status")
def ai_status():
    """Checks if AI Engine is configured and ready."""
    return jsonify({
        "configured": True,
        "model": ai_assistant.AI_MODEL_NAME,
        "engine": ai_assistant.AI_ENGINE_NAME
    })


@app.get("/api/ai/advice/<int:student_id>")
def get_ai_advice(student_id):
    """Generates personalized study advice and priority task action plan."""
    res = ai_assistant.generate_smart_study_advice(student_id)
    return jsonify(res)


@app.post("/api/ai/chat")
def ai_chat():
    """General AI assistant endpoint to handle academic queries, plan study, and prioritize tasks."""
    data = request.get_json(force=True, silent=True) or {}
    student_id = data.get("studentId", 1)
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    conn = get_conn()
    student = conn.execute("SELECT name FROM student WHERE id = ?", (student_id,)).fetchone()
    student_name = student["name"] if student else "Student"
    conn.close()

    classes = schedule.today(student_id)
    tasks = assignments.list_assignments(student_id, status_filter="PENDING")

    context_str = (
        f"You are the Campus Companion AI Assistant for {student_name}.\n"
        f"Today's Schedule: {classes}\n"
        f"Pending Tasks/Assignments: {tasks}\n"
        "Provide a clear, helpful, well-formatted response to the student's question or request."
    )
    answer = ai_assistant.answer_student_query(student_id, prompt, context_str)
    return jsonify({
        "studentId": student_id,
        "prompt": prompt,
        "response": answer,
        "engine": ai_assistant.AI_ENGINE_NAME
    })


if __name__ == "__main__":
    reset_db()                      # Fresh demo data on start
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Campus Companion is running at http://0.0.0.0:{port}")
    print(f"🎙️ Alexa Endpoint: POST http://0.0.0.0:{port}/api/alexa")
    app.run(host="0.0.0.0", port=port, debug=False)

