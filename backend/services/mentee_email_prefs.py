"""Mentee email notification preference helpers."""

from __future__ import annotations


def mentee_email_notify_documents_enabled(user: dict) -> bool:
    """Default True — document emails were always sent before this feature."""
    value = user.get("email_notify_documents")
    if value is None:
        return True
    return bool(value)


def mentee_email_notify_activities_enabled(user: dict) -> bool:
    """Default False — daily activity digest is opt-in."""
    return bool(user.get("email_notify_activities"))


def is_document_email_action(action: str) -> bool:
    if not action:
        return False
    if action in {
        "mentor_document_upload",
        "document_bulk_approve",
        "document_feedback",
    }:
        return True
    if action.startswith("document_"):
        return True
    if action.startswith("inbox_processed_document"):
        return True
    return False


def is_profile_activity_status_action(action: str) -> bool:
    """Mentor responses about registrations/keeptrack — in-app only, not digest."""
    return bool(action) and action.startswith("profile_activity")
