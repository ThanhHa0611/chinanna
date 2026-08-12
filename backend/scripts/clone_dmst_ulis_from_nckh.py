"""One-off: clone NCKH ULIS activity groups/registrations into ĐMST ULIS 17/8.

Keeps hide_from_mentees=True, no keeptrack/HDNK entries, groups unfinalized.
Idempotent: skips if an ĐMST ULIS 17/08/2026 activity already exists.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

SOURCE_ID = ObjectId("6a7c53911db762f592af9e2e")


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    client = MongoClient(os.environ["MONGODB_URL"])
    db = client[os.environ.get("DATABASE_NAME", "phong_van")]
    col = db.profile_activities

    source = col.find_one({"_id": SOURCE_ID})
    if not source:
        raise SystemExit("source NCKH ULIS activity not found")

    existing = col.find_one(
        {
            "activity_type": "ĐMST",
            "organizer": "ULIS",
            "deadline": "17/08/2026",
        }
    )
    if existing:
        print(
            json.dumps(
                {
                    "already_exists": str(existing["_id"]),
                    "name": existing.get("activity_name"),
                    "n_groups": len(existing.get("groups") or []),
                    "n_regs": len(
                        [s for s in (existing.get("mentee_states") or []) if s.get("registered_at")]
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    now = datetime.now(timezone.utc)
    admin_id = source.get("created_by_admin_id") or ""

    new_groups = []
    for group in source.get("groups") or []:
        new_groups.append(
            {
                "group_id": str(uuid.uuid4()),
                "group_name": group.get("group_name") or "Nhóm",
                "mentee_ids": [str(item) for item in (group.get("mentee_ids") or [])],
                "notification_sent_at": None,
                "finalized_at": None,
                "leader_mentee_id": "",
                "approval_status": "approved",
                "submitted_by_admin_id": admin_id,
                "submitted_at": now,
                "approved_at": now,
                "approved_by_admin_id": admin_id,
                # Dismiss reminders so mentor inbox is not flooded until ready.
                "finalize_reminder_dismissed_at": now,
            }
        )

    new_states = []
    for state in source.get("mentee_states") or []:
        if not state.get("registered_at"):
            continue
        new_states.append(
            {
                "mentee_id": str(state.get("mentee_id")),
                "read_at": None,
                "hidden": False,
                "registered_at": now,
                "group_response_status": None,
                "group_response_note": "",
                "group_response_at": None,
                "participation_choice": "group",
                "wants_group_leader": bool(state.get("wants_group_leader")),
            }
        )

    doc = {
        "activity_name": "ĐMST của ULIS, dl 17/08/2026",
        "activity_type": "ĐMST",
        "link": source.get("link") or "",
        "description": "ĐMST / Đổi mới sáng tạo — Khởi nghiệp ULIS 17/8 — clone nhóm từ NCKH ULIS",
        "deadline": "17/08/2026",
        "organizer": "ULIS",
        "target_audience": source.get("target_audience") or "",
        "content": "",
        "attachment_url": source.get("attachment_url") or "",
        "suitable_majors": list(source.get("suitable_majors") or []),
        "suitable_majors_other": source.get("suitable_majors_other") or "",
        "importance": source.get("importance") if source.get("importance") is not None else 3,
        "internal_note": (
            "Paired với NCKH ULIS 17/8 (6a7c53911db762f592af9e2e). "
            "Ẩn mentee đến khi Chốt nhóm."
        ),
        "participant_limit": source.get("participant_limit") or 0,
        "referrer_zalo_phone": "",
        "participation_mode": "group",
        "hide_from_mentees": True,
        "approval_status": "approved",
        "created_by_admin_id": admin_id,
        "approved_at": now,
        "approved_by_admin_id": admin_id,
        "mentor_name": source.get("mentor_name") or "",
        "created_at": now,
        "updated_at": now,
        "mentee_states": new_states,
        "groups": new_groups,
    }

    result = col.insert_one(doc)
    created = col.find_one({"_id": result.inserted_id}) or doc

    col.update_one(
        {"_id": SOURCE_ID},
        {
            "$set": {
                "activity_name": "NCKH ULIS 17/8",
                "description": (
                    "NCKH ULIS 17/8 — paired với ĐMST ULIS (cùng nhóm). Import từ Apply 2027."
                ),
                "updated_at": now,
            }
        },
    )

    regs = len([s for s in (created.get("mentee_states") or []) if s.get("registered_at")])
    print(
        json.dumps(
            {
                "dmst_id": str(created["_id"]),
                "activity_name": created.get("activity_name"),
                "activity_type": created.get("activity_type"),
                "hide_from_mentees": created.get("hide_from_mentees"),
                "n_groups": len(created.get("groups") or []),
                "n_regs": regs,
                "group_names": [g.get("group_name") for g in (created.get("groups") or [])],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
