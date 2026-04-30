"""Schemas for AI career assistant services."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    """Standardized error contract for API responses."""

    error: dict[str, Any]
    request_id: str


class ProfilePreferences(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)
    visa_required: bool = False


class ProfileSource(BaseModel):
    github_url: str = ""
    linkedin_url: str = ""


class ProfileIngestRequest(BaseModel):
    user_id: str
    source: ProfileSource = Field(default_factory=ProfileSource)
    raw_resume_text: str = ""
    preferences: ProfilePreferences = Field(default_factory=ProfilePreferences)


class ProfileIngestResponse(BaseModel):
    profile_id: str
    normalized_skills: list[str]
    experience_years: int
    readiness_score: float
    created_at: datetime


class JobItem(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    match_score: float
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    apply_link: str = ""
    raw_html: str = ""
    parsed_data: dict[str, Any] = Field(default_factory=dict)
    required_skills: list[str] = Field(default_factory=list)


class JobSearchResponse(BaseModel):
    items: list[JobItem]
    total: int
    limit: int
    offset: int


class ResumeGenerateRequest(BaseModel):
    profile_id: str
    job_id: str
    style: str = "concise"
    tone: str = "professional"
    max_pages: int = 1


class ResumeGenerateResponse(BaseModel):
    resume_id: str
    version: int
    summary: str
    storage_path: str
    keyword_coverage: float
    latex_source: str = ""
    pdf_path: str = ""
    selected_skills: list[str] = Field(default_factory=list)
    selected_projects: list[str] = Field(default_factory=list)


class AtsAnalyzeRequest(BaseModel):
    resume_id: str
    job_id: str
    ruleset: str = "default_v1"


class AtsAnalyzeResponse(BaseModel):
    analysis_id: str
    ats_score: int
    breakdown: dict[str, float] = Field(default_factory=dict)
    missing_keywords: list[str] = Field(default_factory=list)
    format_issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class EmployeeContact(BaseModel):
    employee_id: str
    name: str
    title: str
    confidence: float
    linkedin_url: str = ""
    email: str = ""


class EmployeeFindResponse(BaseModel):
    company: str
    contacts: list[EmployeeContact] = Field(default_factory=list)
    no_real_emails_found: bool = False
    scraper_source: str = "unknown"


class EmailRecipient(BaseModel):
    name: str
    role: str
    company: str
    email: str | None = None


class EmailGenerateRequest(BaseModel):
    profile_id: str
    job_id: str
    resume_id: str
    recipient: EmailRecipient
    variant: str = "intro"


class EmailGenerateResponse(BaseModel):
    email_id: str
    subject: str
    body: str
    tone_options: dict[str, dict[str, str]] = Field(default_factory=dict)
    personalization_score: float


class ApplicationOptimizeRequest(BaseModel):
    profile_id: str
    job_id: str
    company_context: str = ""


class ApplicationOptimizeResponse(BaseModel):
    optimized_resume: str
    key_improvements: list[str] = Field(default_factory=list)
    personalized_outreach_email: str
    estimated_ats_score: int
    estimated_match_score: int


class OverleafResumeRequest(BaseModel):
    profile_id: str
    job_id: str
    candidate_name: str = "Candidate"


class OverleafResumeResponse(BaseModel):
    export_id: str
    latex_source: str
    overleaf_url: str
    tex_download_url: str
    pdf_download_url: str | None = None
    no_real_images_found: bool = True
    warnings: list[str] = Field(default_factory=list)


class PipelineConstraints(BaseModel):
    min_match_score: float = 0.75
    min_ats_score: int = 70
    max_jobs: int = 10


class PipelineRunRequest(BaseModel):
    profile_id: str
    constraints: PipelineConstraints = Field(default_factory=PipelineConstraints)
    auto_send: bool = False


class PipelineRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    partial = "partial"


class PipelineRunStep(BaseModel):
    step: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    profile_id: str
    status: PipelineRunStatus = PipelineRunStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    constraints: PipelineConstraints = Field(default_factory=PipelineConstraints)
    auto_send: bool = False
    steps: list[PipelineRunStep] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
