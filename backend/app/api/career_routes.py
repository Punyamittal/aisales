"""Career assistant module routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.career_schemas import (
    ApplicationOptimizeRequest,
    ApplicationOptimizeResponse,
    AtsAnalyzeRequest,
    AtsAnalyzeResponse,
    EmailGenerateRequest,
    EmailGenerateResponse,
    EmployeeFindResponse,
    JobSearchResponse,
    OverleafResumeRequest,
    OverleafResumeResponse,
    PipelineRunRecord,
    PipelineRunRequest,
    ProfileIngestRequest,
    ProfileIngestResponse,
    ResumeGenerateRequest,
    ResumeGenerateResponse,
)
from app.services.career_services import (
    ApplicationOptimizerService,
    AtsService,
    EmailService,
    EmployeeService,
    JobService,
    OverleafResumeService,
    ProfileService,
    ResumeService,
)
from app.services.pipeline_orchestrator_service import pipeline_orchestrator_service

router = APIRouter(prefix="/api", tags=["career-assistant"])

profile_service = ProfileService()
job_service = JobService()
resume_service = ResumeService()
ats_service = AtsService()
employee_service = EmployeeService()
email_service = EmailService()
application_optimizer_service = ApplicationOptimizerService()
overleaf_resume_service = OverleafResumeService()


@router.post("/profile/ingest", response_model=ProfileIngestResponse)
async def profile_ingest(payload: ProfileIngestRequest) -> ProfileIngestResponse:
    return await profile_service.ingest(payload)


@router.get("/jobs/search", response_model=JobSearchResponse)
async def jobs_search(
    profile_id: str = Query(...),
    q: str = Query(default=""),
    location: str = Query(default="Remote"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobSearchResponse:
    return await job_service.search(profile_id=profile_id, q=q, location=location, limit=limit, offset=offset)


@router.post("/resume/generate", response_model=ResumeGenerateResponse)
async def resume_generate(payload: ResumeGenerateRequest) -> ResumeGenerateResponse:
    return await resume_service.generate(payload)


@router.post("/ats/analyze", response_model=AtsAnalyzeResponse)
async def ats_analyze(payload: AtsAnalyzeRequest) -> AtsAnalyzeResponse:
    return await ats_service.analyze(payload)


@router.get("/employees/find", response_model=EmployeeFindResponse)
async def employees_find(
    company: str = Query(...),
    job_id: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
) -> EmployeeFindResponse:
    return await employee_service.find(company=company, job_id=job_id, limit=limit)


@router.post("/emails/generate", response_model=EmailGenerateResponse)
async def emails_generate(payload: EmailGenerateRequest) -> EmailGenerateResponse:
    return await email_service.generate(payload)


@router.post("/application/optimize", response_model=ApplicationOptimizeResponse)
async def application_optimize(payload: ApplicationOptimizeRequest) -> ApplicationOptimizeResponse:
    return await application_optimizer_service.optimize(payload)


@router.post("/resume/overleaf/generate", response_model=OverleafResumeResponse)
async def resume_overleaf_generate(payload: OverleafResumeRequest) -> OverleafResumeResponse:
    return await overleaf_resume_service.generate_with_gemma(payload)


@router.get("/resume/overleaf/{export_id}/tex")
async def resume_overleaf_tex(export_id: str):
    item = overleaf_resume_service.get_export(export_id)
    if not item or not item.get("tex_path"):
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path=item["tex_path"], filename=f"{export_id}.tex", media_type="application/x-tex")


@router.get("/resume/overleaf/{export_id}/pdf")
async def resume_overleaf_pdf(export_id: str):
    item = overleaf_resume_service.get_export(export_id)
    if not item or not item.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF not found for export")
    return FileResponse(path=item["pdf_path"], filename=f"{export_id}.pdf", media_type="application/pdf")


@router.post("/pipeline/run", response_model=PipelineRunRecord)
async def pipeline_run(payload: PipelineRunRequest) -> PipelineRunRecord:
    return await pipeline_orchestrator_service.enqueue(payload)


@router.get("/pipeline/{run_id}", response_model=PipelineRunRecord)
async def pipeline_status(run_id: str) -> PipelineRunRecord:
    run = pipeline_orchestrator_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run not found: {run_id}")
    return run


@router.get("/pipeline/{run_id}/steps")
async def pipeline_steps(run_id: str) -> dict:
    run = pipeline_orchestrator_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run not found: {run_id}")
    return {"run_id": run_id, "steps": [step.model_dump() for step in run.steps]}
