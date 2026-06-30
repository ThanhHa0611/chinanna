
from config import ADMIN_STATUS_APPROVED, ADMIN_STATUS_REJECTED
from database import with_db
from extensions import app
from services.mentee_l1_email import (
    handle_email_apply_progress_action,
    handle_email_registration_action,
)


@app.get("/api/email/l1/registration/approve")
@with_db
def email_l1_registration_approve():
    return handle_email_registration_action("approve", ADMIN_STATUS_APPROVED)


@app.get("/api/email/l1/registration/reject")
@with_db
def email_l1_registration_reject():
    return handle_email_registration_action("reject", ADMIN_STATUS_REJECTED)


@app.get("/api/email/l1/apply-progress/approve")
@with_db
def email_l1_apply_progress_approve():
    return handle_email_apply_progress_action("approve", ADMIN_STATUS_APPROVED)


@app.get("/api/email/l1/apply-progress/reject")
@with_db
def email_l1_apply_progress_reject():
    return handle_email_apply_progress_action("reject", ADMIN_STATUS_REJECTED)
