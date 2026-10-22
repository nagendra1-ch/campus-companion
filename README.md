# Campus Companion 🎓🎙️

> **Smart Voice & Academic Management Assistant powered by Amazon Alexa & Built-in Local Academic AI (Zero API Keys Needed).**

Campus Companion is an intelligent student assistant that keeps track of classes, assignment deadlines, and daily reminders through natural voice interaction via **Amazon Alexa** and an interactive web dashboard.

---

## 🌟 Features

- 🎙️ **Full Amazon Alexa Skill Integration**: Query your next class, create assignments with countdowns, and dismiss completed tasks using natural speech.
- ⏰ **Dynamic Timetable & Schedule Awareness**: Know exactly which class is next, room numbers, and how many minutes remain.
- 📝 **Assignment Deadlines & Recurring Reminders**: Automatic daily reminders scheduled from assignment creation until due date.
- 🧠 **Built-in Local Academic AI Mentor**: Personalized study advice, prioritized task breakdowns, and natural answers to student queries — 100% offline with **zero external API keys** needed.
- 👥 **Multi-Tenant User Isolation**: Individual schedules and task lists for different students (e.g., Ravi vs Priya).
- 🌐 **Interactive Web Dashboard**: Built-in voice simulator, audio player, timetable viewer, and live Alexa ASK request/response inspector.

---

## 🚀 Quick Start (Local)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

```

### 2. Start the Server
```bash
python campus-companion-py/app.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.
*(No API keys needed — the project includes a built-in intelligent local academic and study planning engine!)*

---

## ☁️ Deploying to Vercel (1-Click Ready)

This repository is pre-configured with `vercel.json`, `public/`, and `api/index.py` serverless functions for seamless zero-config deployment on Vercel.

### Deploy Steps:
1. Push this repository to GitHub.
2. Go to **[vercel.com/new](https://vercel.com/new)** and import your `campus-companion` repository.
3. No environment variables are required! Just click **Deploy**.
4. Once deployed, your public URL will look like `https://campus-companion-xyz.vercel.app`.


### Connect Vercel to Alexa:
In the [Amazon Alexa Developer Console](https://developer.amazon.com/alexa/console/ask):
- Under **Endpoint** -> **HTTPS**, enter:
  `https://your-app-name.vercel.app/api/alexa`
- Select *"My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority"*.
- Save and test!

---

## 🗣️ Alexa Voice Commands

| Voice Utterance | Intent | Action |
| :--- | :--- | :--- |
| *"Alexa, ask Campus Companion what is my next class"* | `NextClassIntent` | Tells next class, classroom, and time remaining |
| *"Alexa, tell Campus Companion I have to submit DBMS assignment within 5 days"* | `AddAssignmentIntent` | Records deadline and schedules daily reminders |
| *"Alexa, ask Campus Companion what are my reminders"* | `ListRemindersIntent` | Lists active reminders |
| *"Alexa, tell Campus Companion DBMS assignment is completed"* | `CompleteAssignmentIntent` | Marks assignment complete & clears reminders |

---

## 📁 Repository Structure

```
campus-companion/
├── api/
│   └── index.py               # Vercel serverless WSGI entrypoint
├── campus-companion-py/
│   ├── static/                # Modern UI dashboard, CSS, JS
│   ├── alexa/                 # Alexa interaction model & skill manifest
│   ├── app.py                 # Flask server & REST / Alexa endpoints
│   ├── ai_assistant.py        # Built-in local academic AI study guidance & intent extractor
│   ├── alexa_handler.py       # ASK JSON request & speech parser
│   ├── assignments.py         # Assignment deadline logic
│   ├── clock.py               # Time simulator
│   ├── context.py             # User state builder
│   ├── db.py                  # SQLite connector (Vercel /tmp compatible)
│   ├── reminders.py           # Reminder engine
│   ├── schedule.py            # Timetable lookup
│   ├── schema.sql             # SQL schema & demo seeds
│   └── campus.db              # Pre-seeded SQLite database
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies (Flask, Gunicorn, etc.)
└── vercel.json                # Vercel routing & rewrites configuration
```

---

## 📄 License
MIT License. Built for students and educators.
