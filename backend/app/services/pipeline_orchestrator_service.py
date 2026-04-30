"""Asynchronous pipeline orchestrator for career workflows."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.db.supabase_client import get_supabase
from app.models.career_schemas import (
    AtsAnalyzeRequest,
    EmailGenerateRequest,
    EmailRecipient,
    PipelineRunRecord,
    PipelineRunRequest,
    PipelineRunStatus,
    PipelineRunStep,
    ResumeGenerateRequest,
)
from app.services.career_services import (
    AtsService,
    EmailService,
    EmployeeService,
    JobService,
    ResumeService,
)

logger = logging.getLogger(__name__)


class PipelineOrchestratorService:
    """In-memory run state plus async queue worker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._runs: dict[str, PipelineRunRecord] = {}
        self._worker_task: asyncio.Task | None = None

        self._jobs = JobService()
        self._resume = ResumeService()
        self._ats = AtsService()
        self._employees = EmployeeService()
        self._emails = EmailService()

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._worker(), name="career-pipeline-worker")
        logger.info("pipeline_orchestrator_worker_started")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("pipeline_orchestrator_worker_stopped")

    async def enqueue(self, payload: PipelineRunRequest) -> PipelineRunRecord:
        record = PipelineRunRecord(
            profile_id=payload.profile_id,
            constraints=payload.constraints,
            auto_send=payload.auto_send,
        )
        self._runs[record.run_id] = record
        await self._queue.put(record.run_id)
        return record

    def get(self, run_id: str) -> PipelineRunRecord | None:
        return self._runs.get(run_id)

    def _persist_run(self, run: PipelineRunRecord) -> None:
        supabase = get_supabase()
        if not supabase:
            return
        try:
            payload = {
                "id": run.run_id,
                "user_id": "local-user",
                "profile_id": run.profile_id,
                "status": run.status.value,
                "started_at": run.steps[0].started_at.isoformat() if run.steps and run.steps[0].started_at else None,
                "completed_at": datetime.utcnow().isoformat() if run.status in {PipelineRunStatus.success, PipelineRunStatus.failed, PipelineRunStatus.partial} else None,
                "error_message": run.error,
                "logs": [step.model_dump(mode="json") for step in run.steps],
                "metrics": run.outputs,
            }
            supabase.table("pipeline_runs").upsert(payload).execute()
        except Exception:
            logger.debug("pipeline_run_persist_failed run_id=%s", run.run_id)

    async def _worker(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                await self._execute(run_id)
            except Exception as exc:  # pragma: no cover - fail-safe
                logger.exception("pipeline_orchestrator_unhandled_error run_id=%s error=%s", run_id, exc)
            finally:
                self._queue.task_done()

    async def _execute(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run:
            return

        run.status = PipelineRunStatus.running
        run.updated_at = datetime.utcnow()
        self._persist_run(run)

        try:
            jobs_step = PipelineRunStep(step="jobs", status="running", started_at=datetime.utcnow())
            run.steps.append(jobs_step)
            jobs = await self._jobs.search(
                profile_id=run.profile_id,
                q="Backend Engineer",
                location="Remote",
                limit=run.constraints.max_jobs,
                offset=0,
            )
            qualified = [job for job in jobs.items if job.match_score >= run.constraints.min_match_score]
            jobs_step.status = "completed"
            jobs_step.finished_at = datetime.utcnow()
            jobs_step.metadata = {"qualified_jobs": len(qualified)}
            run.outputs["jobs"] = [item.model_dump() for item in qualified]

            if not qualified:
                run.status = PipelineRunStatus.partial
                run.error = "No jobs met the threshold."
                run.updated_at = datetime.utcnow()
                self._persist_run(run)
                return

            top_job = qualified[0]

            resume_step = PipelineRunStep(step="resume", status="running", started_at=datetime.utcnow())
            run.steps.append(resume_step)
            resume = await self._resume.generate(
                ResumeGenerateRequest(profile_id=run.profile_id, job_id=top_job.job_id)
            )
            resume_step.status = "completed"
            resume_step.finished_at = datetime.utcnow()
            run.outputs["resume"] = resume.model_dump()

            ats_step = PipelineRunStep(step="ats", status="running", started_at=datetime.utcnow())
            run.steps.append(ats_step)
            ats = await self._ats.analyze(AtsAnalyzeRequest(resume_id=resume.resume_id, job_id=top_job.job_id))
            ats_step.status = "completed"
            ats_step.finished_at = datetime.utcnow()
            ats_step.metadata = {"ats_score": ats.ats_score}
            run.outputs["ats"] = ats.model_dump()

            if ats.ats_score < run.constraints.min_ats_score:
                run.status = PipelineRunStatus.partial
                run.error = "ATS score below minimum threshold."
                run.updated_at = datetime.utcnow()
                self._persist_run(run)
                return

            outreach_step = PipelineRunStep(step="outreach", status="running", started_at=datetime.utcnow())
            run.steps.append(outreach_step)
            contacts = await self._employees.find(company=top_job.company, job_id=top_job.job_id, limit=5)
            run.outputs["contacts"] = contacts.model_dump()

            emails = []
            for contact in contacts.contacts:
                email = await self._emails.generate(
                    EmailGenerateRequest(
                        profile_id=run.profile_id,
                        job_id=top_job.job_id,
                        resume_id=resume.resume_id,
                        recipient=EmailRecipient(
                            name=contact.name,
                            role=contact.title,
                            company=top_job.company,
                            email=contact.email or None,
                        ),
                    )
                )
                emails.append(email.model_dump())
            run.outputs["emails"] = emails
            outreach_step.status = "completed"
            outreach_step.finished_at = datetime.utcnow()
            outreach_step.metadata = {"emails_generated": len(emails), "auto_send": run.auto_send}

            run.status = PipelineRunStatus.success
            run.updated_at = datetime.utcnow()
            self._persist_run(run)
        except Exception as exc:
            run.status = PipelineRunStatus.failed
            run.error = str(exc)
            run.updated_at = datetime.utcnow()
            self._persist_run(run)
            logger.exception("pipeline_orchestrator_failed run_id=%s error=%s", run_id, exc)


pipeline_orchestrator_service = PipelineOrchestratorService()
