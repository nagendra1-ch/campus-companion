import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _resolve_db_path() -> Path:
    if os.environ.get("VERCEL"):
        tmp_dir = Path(tempfile.gettempdir())
        tmp_db = tmp_dir / "campus.db"

        valid = False
        if tmp_db.exists():
            try:
                conn = sqlite3.connect(tmp_db)
                has_student = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student'").fetchone()
                conn.close()
                if has_student:
                    valid = True
            except Exception:
                valid = False

        if not valid:
            orig_db = BASE / "campus.db"
            if not orig_db.exists():
                orig_db = BASE.parent / "campus.db"

            if orig_db.exists() and orig_db.stat().st_size > 0:
                try:
                    shutil.copy2(orig_db, tmp_db)
                    valid = True
                except Exception as e:
                    print(f"Error copying orig_db: {e}", flush=True)

            if not valid:
                schema_file = BASE / "schema.sql"
                if not schema_file.exists():
                    schema_file = BASE.parent / "schema.sql"
                conn = sqlite3.connect(tmp_db)
                conn.executescript(schema_file.read_text(encoding="utf-8"))
                conn.commit()
                conn.close()

        return tmp_db
    return BASE / "campus.db"


DB_PATH = _resolve_db_path()


def get_conn():
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    return conn


def reset_db():
    """Rebuild the database from schema.sql. Called on start = demo reset."""
    conn = get_conn()
    schema_file = BASE / "schema.sql"
    if not schema_file.exists():
        schema_file = BASE.parent / "schema.sql"
    conn.executescript(schema_file.read_text(encoding="utf-8"))

    # Dynamically align demo tasks, reminders, and sim_state to live system date & time
    try:
        from datetime import datetime, timedelta
        now = datetime.now()
        now_str = now.isoformat()
        today_date_str = now.strftime("%Y-%m-%d")

        # Set sim_state to live system time
        conn.execute("UPDATE sim_state SET sim_now = ?, is_live = 1", (now_str,))

        # Set tasks due dates relative to live system time
        t1_due = (now + timedelta(days=5)).replace(hour=23, minute=59, second=0).isoformat()
        t2_due = (now + timedelta(days=4)).replace(hour=17, minute=0, second=0).isoformat()
        t3_due = (now + timedelta(days=3)).replace(hour=23, minute=59, second=0).isoformat()

        conn.execute("UPDATE task SET due_at = ? WHERE id = 1", (t1_due,))
        conn.execute("UPDATE task SET due_at = ? WHERE id = 2", (t2_due,))
        conn.execute("UPDATE task SET due_at = ? WHERE id = 3", (t3_due,))

        # Set reminders to today
        conn.execute("UPDATE reminder SET remind_date = ? WHERE student_id IN (1, 2)", (today_date_str,))
        conn.commit()
    except Exception as e:
        print(f"Notice updating live dates: {e}", flush=True)

    conn.commit()
    conn.close()
