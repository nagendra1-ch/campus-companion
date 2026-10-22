# Alexa Skill Integration & Setup Guide for Campus Companion

This application is built to directly connect with **Amazon Alexa**. All voice commands, queries, deadlines, and status updates are processed through the backend webhook.

---

## 1. How Alexa Requests & Voice Flows Work

### A. "What is my next class?"
1. **Utterance**: *"Alexa, ask Campus Companion what is my next class"*
2. **Intent**: `NextClassIntent`
3. **Backend Logic**:
   - Identifies the authenticated student from Alexa `userId` (or selected active profile).
   - Queries `class_session` and `course` tables for today's sessions relative to current time.
   - Alexa speaks: *"Your next class is DBMS at 9:00 AM in room B-204 (starts in 1 hour 15 minutes)."*

---

### B. "I have to submit {subject} assignment within {days} days"
1. **Utterance**: *"Alexa, tell Campus Companion I have to submit DBMS assignment within 5 days"*
2. **Intent**: `AddAssignmentIntent`
3. **Slots**: `Subject = "DBMS"`, `Days = "5"`
4. **Backend Logic**:
   - Computes target deadline: `due_date = current_date + 5 days`.
   - Stores task in database under the user's `task` table.
   - Generates daily recurring reminders in `reminder` table for each day until the due date.
   - Alexa speaks: *"Got it! I have recorded your DBMS assignment due in 5 days on Saturday, October 17. I will send you a daily reminder every day until it is completed."*

---

### C. "DBMS assignment is completed" or "It is completed"
1. **Utterance**: *"Alexa, tell Campus Companion DBMS assignment is completed"*
2. **Intent**: `CompleteAssignmentIntent`
3. **Slots**: `Subject = "DBMS"`
4. **Backend Logic**:
   - Finds the active assignment for this student.
   - Updates `task.status = 'COMPLETED'` (or deletes if requested).
   - Dismisses/clears all corresponding daily reminders.
   - Alexa speaks: *"Awesome work! I have marked your DBMS assignment as completed and dismissed all active reminders for it."*

---

### D. User Isolation & Multi-Tenancy
- Each Alexa request delivers `session.user.userId` (e.g. `amzn1.ask.account.RAVI_123` or `amzn1.ask.account.PRIYA_456`).
- The backend matches this identifier to the user's row in the `student` table.
- **Ravi** only accesses Ravi's schedule and assignments; **Priya** only accesses Priya's schedule and assignments.

---

## 2. Connecting to Amazon Alexa Developer Console

1. Go to [Amazon Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).
2. Click **Create Skill**:
   - Skill Name: `Campus Companion`
   - Primary Locale: `English (US)`
   - Model: `Custom`
   - Hosting: `Provision your own` (HTTPS Webhook).
3. Under **Interaction Model** -> **JSON Editor**, paste the content of [`alexa/interaction_model.json`](file:///c:/Users/chnag/Downloads/campus/campus-companion-py/alexa/interaction_model.json).
4. Click **Save Model** and **Build Model**.
5. Under **Endpoint**:
   - Select **HTTPS**.
   - Default Region: `https://<your-ngrok-or-server-url>/api/alexa`
   - SSL Certificate: Select *"My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority"* (e.g., for ngrok / cloudflare tunnel).
6. Click **Save Endpoints**.
7. Navigate to the **Test** tab:
   - Switch test mode from *Off* to *Development*.
   - Type or speak:
     - `"open campus companion"`
     - `"what is my next class"`
     - `"i have to submit DBMS assignment within 5 days"`
     - `"what are my reminders"`
     - `"DBMS assignment is completed"`

---

## 3. Testing Locally in the Built-in Web Simulator
The app includes a fully functional **Interactive Voice & Alexa Simulator** directly on the web dashboard (`http://localhost:8080`):
- Click pre-configured prompt chips or speak into your microphone.
- Listen to live voice synthesis answers.
- Inspect the raw Alexa ASK request and response JSON payloads in real time.
- Switch between student profiles (Ravi vs Priya) to verify user isolation.
