
import time

from flask import request

from database import ensure_db, mentor_inbox
from extensions import app
from services.inbox import send_daily_inbox_summary_for_mentor

_last_inbox_reminder_check = 0.0


@app.after_request
def add_geolocation_policy(response):
    response.headers["Permissions-Policy"] = "geolocation=(self)"
    return response


@app.before_request
def maybe_process_inbox_reminders():
    global _last_inbox_reminder_check

    if request.path.startswith("/api/email/"):
        return None

    now = time.time()
    if now - _last_inbox_reminder_check < 900:
        return None
    _last_inbox_reminder_check = now

    try:
        ensure_db()
        from inbox_tasks import ensure_stale_pending_daily_reminders, process_due_reminders

        ensure_stale_pending_daily_reminders(mentor_inbox)
        process_due_reminders(mentor_inbox, send_daily_inbox_summary_for_mentor)
    except Exception:
        pass
    return None

