"""Worker process: claims jobs with a lease, retries transient failures
with backoff, and dead-letters exhausted jobs. Run as a separate
process: `python -m app.workers.runner`."""

from __future__ import annotations

import asyncio
import secrets
import signal
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.client import close_client, init_client
from app.db.indexes import ensure_indexes
from app.repositories.system_repo import JobRepo
from app.services import jobs as job_svc
from app.services.timeutil import now_utc
from app.workers.handlers import HANDLERS

logger = get_logger(__name__)

RETENTION_INTERVAL_SECONDS = 3600


class Worker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.worker_id = f"wrk_{secrets.token_hex(6)}"
        self.running = True
        self._last_retention_check = 0.0

    async def run(self) -> None:
        configure_logging(self.settings.log_level)
        client = init_client(self.settings.mongodb_uri)
        db = client[self.settings.mongodb_database]
        await ensure_indexes(db)
        jobs = JobRepo(db)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.stop)

        logger.info("worker_started", worker_id=self.worker_id)
        while self.running:
            try:
                await jobs.requeue_expired_leases()
                await self._maybe_schedule_retention(db)
                job = await jobs.claim(self.worker_id, self.settings.worker_lease_seconds)
                if job is None:
                    await asyncio.sleep(self.settings.worker_poll_seconds)
                    continue
                await self._execute(db, jobs, job)
            except Exception:
                logger.exception("worker_loop_error")
                await asyncio.sleep(2)
        await close_client()

    def stop(self) -> None:
        self.running = False

    async def _execute(self, db, jobs: JobRepo, job: dict[str, Any]) -> None:
        handler = HANDLERS.get(job["type"])
        if handler is None:
            await jobs.dead_letter(job["_id"], "unknown_job_type")
            return
        try:
            await handler(db, job, self.settings)
            await jobs.complete(job["_id"])
        except Exception as exc:
            attempts = int(job.get("attempts") or 0)
            if attempts >= self.settings.worker_max_attempts:
                await jobs.dead_letter(job["_id"], type(exc).__name__)
                logger.warning("job_dead_lettered", job_id=job["_id"], type=job["type"])
            else:
                delay = min(60.0, 2.0 ** attempts)
                await jobs.reschedule(job["_id"], delay, type(exc).__name__)
                logger.info(
                    "job_rescheduled", job_id=job["_id"], attempts=attempts, delay=delay
                )

    async def _maybe_schedule_retention(self, db) -> None:
        import time

        now = time.monotonic()
        if now - self._last_retention_check < 60:
            return
        self._last_retention_check = now
        meta = await db["meta"].find_one({"_id": "last_retention_purge"})
        last = (meta or {}).get("at")
        if last is None or (now_utc() - last).total_seconds() > RETENTION_INTERVAL_SECONDS:
            await job_svc.enqueue(db, job_svc.JOB_RETENTION_PURGE, {})
            await db["meta"].update_one(
                {"_id": "last_retention_purge"},
                {"$set": {"at": now_utc()}},
                upsert=True,
            )


def main() -> None:
    asyncio.run(Worker().run())


if __name__ == "__main__":
    main()
