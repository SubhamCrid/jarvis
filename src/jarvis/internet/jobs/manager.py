"""
InternetJobManager for lifecycle management of durable jobs.
Pure lifecycle manager: submit, cancel, resume, persist, recover.
Does NOT execute pipelines directly; delegates execution to platform/runtime composition.
"""

import logging
from typing import List, Optional
from jarvis.internet.jobs.schemas import InternetJob, JobState
from jarvis.internet.jobs.store import JobStore

logger = logging.getLogger("jarvis.internet.jobs.manager")


class InternetJobManager:
    """Pure lifecycle manager for InternetJob records."""

    def __init__(self, store: Optional[JobStore] = None) -> None:
        self.store = store or JobStore()
        self.store.initialize()

    def submit(self, query: str, session_id: str = "default") -> InternetJob:
        """Submit a new job in QUEUED status."""
        job = InternetJob(query=query, session_id=session_id, status=JobState.QUEUED)
        self.store.save_job(job)
        logger.info(f"Submitted job [{job.job_id}] for query: '{query}'")
        return job

    def update_status(self, job_id: str, status: JobState, progress: float = 0.0) -> Optional[InternetJob]:
        """Update job status and progress in JobStore."""
        job = self.store.get_job(job_id)
        if not job:
            return None
        job.status = status
        job.progress = max(0.0, min(1.0, progress))
        self.store.save_job(job)
        return job

    def cancel(self, job_id: str) -> Optional[InternetJob]:
        """Mark a job as CANCELLED."""
        return self.update_status(job_id, JobState.CANCELLED)

    def resume(self, job_id: str) -> Optional[InternetJob]:
        """Mark a RECOVERABLE or FAILED job as QUEUED for execution resumption."""
        job = self.store.get_job(job_id)
        if not job:
            return None
        if job.status in (JobState.RECOVERABLE, JobState.FAILED, JobState.CANCELLED):
            job.status = JobState.QUEUED
            self.store.save_job(job)
            logger.info(f"Resumed job [{job_id}] -> QUEUED state.")
        return job

    def recover(self) -> List[InternetJob]:
        """
        Scan JobStore for jobs left in RUNNING state during an application crash,
        and update their status to RECOVERABLE.
        Does NOT auto-execute pipeline logic.
        """
        running_jobs = self.store.list_jobs(JobState.RUNNING)
        recovered_jobs = []
        for job in running_jobs:
            job.status = JobState.RECOVERABLE
            self.store.save_job(job)
            recovered_jobs.append(job)
            logger.info(f"Recovered interrupted job [{job.job_id}] -> marked RECOVERABLE.")
        return recovered_jobs
