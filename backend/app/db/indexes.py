"""Index bootstrap. Run at startup and by the seed script; idempotent."""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase


async def ensure_indexes(db: AsyncDatabase) -> None:  # type: ignore[type-arg]
    await db["businesses"].create_indexes(
        [
            IndexModel([("slug", ASCENDING)], unique=True),
            IndexModel(
                [("vapi_assistant_id", ASCENDING)],
                unique=True,
                sparse=True,
                name="uniq_vapi_assistant",
            ),
            IndexModel(
                [("vapi_phone_number_id", ASCENDING)],
                unique=True,
                sparse=True,
                name="uniq_vapi_phone",
            ),
        ]
    )
    await db["admin_users"].create_indexes(
        [IndexModel([("email", ASCENDING)], unique=True)]
    )
    await db["sessions"].create_indexes(
        [
            IndexModel([("token_hash", ASCENDING)], unique=True),
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="ttl_session_expiry",
            ),
        ]
    )
    await db["services"].create_indexes(
        [IndexModel([("business_id", ASCENDING), ("slug", ASCENDING)], unique=True)]
    )
    await db["providers"].create_indexes(
        [IndexModel([("business_id", ASCENDING), ("name", ASCENDING)])]
    )
    await db["availability_rules"].create_indexes(
        [
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("provider_id", ASCENDING),
                    ("weekday", ASCENDING),
                ]
            )
        ]
    )
    await db["availability_exceptions"].create_indexes(
        [
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("provider_id", ASCENDING),
                    ("local_date", ASCENDING),
                ]
            )
        ]
    )
    await db["resource_schedule_days"].create_indexes(
        [
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("provider_id", ASCENDING),
                    ("local_date", ASCENDING),
                ],
                unique=True,
            )
        ]
    )
    await db["patients"].create_indexes(
        [
            IndexModel(
                [("business_id", ASCENDING), ("phone", ASCENDING)],
                unique=True,
                sparse=True,
                name="uniq_patient_phone",
            )
        ]
    )
    await db["appointments"].create_indexes(
        [
            IndexModel(
                [("business_id", ASCENDING), ("booking_intent_id", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [("business_id", ASCENDING), ("start_at", ASCENDING), ("status", ASCENDING)]
            ),
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("provider_id", ASCENDING),
                    ("start_at", ASCENDING),
                    ("status", ASCENDING),
                ]
            ),
            IndexModel(
                [("business_id", ASCENDING), ("patient_id", ASCENDING), ("created_at", DESCENDING)]
            ),
        ]
    )
    await db["calls"].create_indexes(
        [
            IndexModel(
                [("business_id", ASCENDING), ("vapi_call_id", ASCENDING)], unique=True
            ),
            IndexModel([("business_id", ASCENDING), ("started_at", DESCENDING)]),
        ]
    )
    await db["integration_events"].create_indexes(
        [
            IndexModel([("fingerprint", ASCENDING)], unique=True),
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="ttl_integration_events",
            ),
        ]
    )
    await db["jobs"].create_indexes(
        [
            IndexModel(
                [("status", ASCENDING), ("available_at", ASCENDING)],
                name="job_claim",
            ),
            IndexModel(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="ttl_jobs",
            ),
        ]
    )
    await db["audit_events"].create_indexes(
        [
            IndexModel(
                [("business_id", ASCENDING), ("created_at", DESCENDING)]
            )
        ]
    )
    await db["tool_results"].create_indexes(
        [
            IndexModel(
                [
                    ("business_id", ASCENDING),
                    ("call_id", ASCENDING),
                    ("tool_call_id", ASCENDING),
                ],
                unique=True,
            )
        ]
    )
