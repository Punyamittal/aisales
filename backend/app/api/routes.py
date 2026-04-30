"""FastAPI route handlers."""
import logging
import asyncio
import httpx
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ProjectInput, CompanyInput

logger = logging.getLogger(__name__)
from app.services.orchestrator import run_pipeline
from app.agents.runner import (
    run_analyzer,
    run_researcher,
    run_matcher,
    run_pitcher,
    run_deck_designer,
    run_sender,
    run_reply_analyzer,
    run_learner,
    run_manager,
    run_company_suggester,
)
from app.services.rewards import get_reward
from app.services.github_service import fetch_repo, parse_github_url
from app.services.ats_engine import score_ats
from app.services.lead_enrichment import enrich_suggested_companies
from app.services.email_service import send_email
from app.services.job_application_pipeline import (
    index_jobs_for_rag,
    index_resume_for_rag,
    rag_architecture_overview,
    retrieve_top_matching_jobs,
    run_job_application_pipeline,
    sample_pipeline_input,
    sample_pipeline_output,
)
from app.services.outreach_engine import (
    build_outreach_package,
    send_campaign,
    get_campaign_tracking,
    sample_outreach_input,
)
from config import get_settings

router = APIRouter(prefix="/api", tags=["api"])


class SendOutreachContact(BaseModel):
    email: str
    name: str = ""
    custom_body: str = ""  # If set, use this instead of the global body


class SendOutreachRequest(BaseModel):
    subject: str = "Quick intro – partnership opportunity"
    body: str
    contacts: list[SendOutreachContact]


class PipelineRequest(BaseModel):
    project: ProjectInput
    company: CompanyInput
    contact_role: str = "Decision Maker"
    include_deck: bool = True


class ReplyAnalyzeRequest(BaseModel):
    reply_text: str
    sender_info: str = ""


class LearnerRequest(BaseModel):
    state_summary: str
    action_taken: str
    outcome: str
    reward: float
    reward_history: list[float]


class ManagerRequest(BaseModel):
    status_summary: str
    last_agent_outputs: list[str]
    metrics_summary: str


class JobApplicationPipelineRequest(BaseModel):
    role: str
    company: str
    links: dict[str, str]


class OutreachGenerateRequest(BaseModel):
    company: str
    role: str
    candidate_profile: dict[str, str]
    job_description: str = ""
    outreach_types: list[str] = Field(
        default_factory=lambda: ["referral_request", "internship_inquiry", "networking_message"]
    )


class OutreachSendRequest(BaseModel):
    campaign_id: str
    generated_messages: list[dict]
    tone: str = "formal"
    sender_name: str = "AI Sales Bot"


class ATSScoreRequest(BaseModel):
    resume_text: str
    job_description: str


class RagJobsIndexRequest(BaseModel):
    jobs: list[dict]


class RagResumeIndexRequest(BaseModel):
    resume_id: str
    resume_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagRetrieveRequest(BaseModel):
    candidate_text: str
    top_k: int = 3


async def _ollama_reachable() -> bool:
    """Return True if Ollama is running and responding."""
    s = get_settings()
    url = f"{s.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            return r.status_code == 200
    except Exception:
        return False


@router.get("/health")
async def health():
    """Health check. ollama_reachable must be true for Suggest companies to work."""
    s = get_settings()
    ollama_ok = await _ollama_reachable()
    return {
        "status": "ok",
        "service": "aisales-backend",
        "ollama_reachable": ollama_ok,
        "ollama_model": s.ollama_model if ollama_ok else None,
        "enrichment": "web-scraper",
    }


@router.get("/debug/contacts")
async def debug_contacts(domain: str = "stripe.com"):
    """
    Test contact scraping for a domain. Use ?domain=stripe.com to verify the scraper works.
    """
    from app.services.scraper_contacts import scrape_contacts_for_domain
    try:
        contacts = await scrape_contacts_for_domain(domain, max_results=10, max_pages=6)
        return {
            "domain": domain,
            "method": "web-scraper",
            "contacts_count": len(contacts),
            "contacts": [c.model_dump() for c in contacts],
        }
    except Exception as e:
        return {
            "domain": domain,
            "method": "web-scraper",
            "contacts_count": 0,
            "contacts": [],
            "error": str(e),
        }


@router.get("/github/repo")
async def github_repo(owner: str = "", repo: str = "", q: str = ""):
    """
    Fetch repo data from GitHub. Use ?owner=x&repo=y or ?q=owner/repo or ?q=https://github.com/owner/repo.
    Requires GITHUB_TOKEN in .env for best rate limits and private repos.
    """
    if q:
        parsed = parse_github_url(q)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid q: use owner/repo or GitHub URL")
        owner, repo = parsed
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Provide owner and repo, or q=owner/repo")
    project = await fetch_repo(owner, repo)
    if not project:
        raise HTTPException(status_code=404, detail="Repo not found or GitHub request failed")
    return project.model_dump()


@router.post("/suggest-companies")
async def suggest_companies(project: ProjectInput):
    """
    Analyze the project and return suggested companies, representative roles,
    and when HUNTER_API_KEY is set and company_domain is present, contact names and emails.
    """
    try:
        get_settings.cache_clear()
        logger.info("Suggest companies: checking Ollama")
        if not await _ollama_reachable():
            raise HTTPException(
                status_code=503,
                detail="Ollama is not running. Start it (e.g. run 'ollama serve' and 'ollama run llama3.2'), then try again.",
            )
        
        logger.info("Suggest companies: running analyzer")
        analysis = await run_analyzer(project)
        
        logger.info("Suggest companies: running suggester")
        companies = await run_company_suggester(analysis)
        
        logger.info("Suggest companies: enriching %d companies", len(companies))
        # Add contact enrichment
        await enrich_suggested_companies(companies)
        
        logger.info("Suggest companies: generating personalized pitches")
        # Parallel personalized pitching with semaphore to avoid overwhelming Ollama
        from app.agents.runner import run_fast_pitcher
        pitch_semaphore = asyncio.Semaphore(3) # Only 3 parallel LLM calls
        async def _pitch_one(c):
            async with pitch_semaphore:
                try:
                    c.personalized_email = await run_fast_pitcher(analysis, c)
                except Exception as e:
                    logger.warning("Pitcher failed for %s: %s", c.company_name, e)
                    c.personalized_email = ""
        
        await asyncio.gather(*[_pitch_one(c) for c in companies])
        logger.info("Suggest companies: completed successfully")
        return {"companies": [c.model_dump() for c in companies]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("suggest-companies failed")
        msg = str(e).strip() or "Suggest companies failed"
        if len(msg) > 400:
            msg = msg[:397] + "..."
        raise HTTPException(status_code=500, detail=msg)


@router.post("/send-outreach")
async def send_outreach(req: SendOutreachRequest):
    """
    Send the same outreach email to each contact. Uses SMTP (Gmail) or Resend.
    Set SMTP_USER + SMTP_PASSWORD (e.g. Gmail app password) in .env to use SMTP.
    """
    if not req.contacts:
        return {"sent": 0, "failed": 0, "message": "No contacts to send to"}
    sent = 0
    failed = 0
    errors: list[str] = []
    for c in req.contacts:
        if not c.email or "@" not in c.email:
            failed += 1
            continue
        # Use custom body if provided, else fallback to global body
        body = c.custom_body if c.custom_body else req.body
        
        contact_name = c.name if (c.name and len(c.name) > 1 and " " in c.name) else "Sir/Ma'am"
        body = body.replace("[Decision Makers Name]", contact_name).replace("[Contact Name]", contact_name).replace("Dear Decision Maker,", f"Dear {contact_name},")
        
        ok = await send_email(c.email, req.subject, body, from_name="Punya Mittal")
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append(c.email)
    return {"sent": sent, "failed": failed, "errors": errors[:10] if errors else None}


@router.post("/pipeline")
async def pipeline(req: PipelineRequest):
    """Run full pipeline: analyze project + company → match → email + deck."""
    try:
        result = await run_pipeline(
            req.project,
            req.company,
            req.contact_role,
            include_deck=req.include_deck,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/project")
async def analyze_project(project: ProjectInput):
    """Analyze a GitHub project."""
    try:
        analysis = await run_analyzer(project)
        return analysis.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/company")
async def analyze_company(company: CompanyInput):
    """Analyze a company."""
    try:
        analysis = await run_researcher(company)
        return analysis.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match")
async def match(project_analysis: dict, company_analysis: dict):
    """Match project to company (pass analysis dicts from analyzer/researcher)."""
    from app.models.schemas import ProjectAnalysis, CompanyAnalysis
    try:
        pa = ProjectAnalysis.model_validate(project_analysis)
        ca = CompanyAnalysis.model_validate(company_analysis)
        result = await run_matcher(pa, ca)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pitch/email")
async def pitch_email(project_analysis: dict, company_analysis: dict, match: dict, contact_role: str = "Decision Maker"):
    """Generate outreach email from analyses and match."""
    from app.models.schemas import ProjectAnalysis, CompanyAnalysis, MatchResult
    try:
        pa = ProjectAnalysis.model_validate(project_analysis)
        ca = CompanyAnalysis.model_validate(company_analysis)
        m = MatchResult.model_validate(match)
        body = await run_pitcher(pa, ca, m, contact_role)
        return {"email_body": body}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pitch/deck")
async def pitch_deck(project_analysis: dict, company_analysis: dict, match: dict):
    """Generate pitch deck content from analyses and match."""
    from app.models.schemas import ProjectAnalysis, CompanyAnalysis, MatchResult
    try:
        pa = ProjectAnalysis.model_validate(project_analysis)
        ca = CompanyAnalysis.model_validate(company_analysis)
        m = MatchResult.model_validate(match)
        deck = await run_deck_designer(pa, ca, m)
        return deck.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sender/plan")
async def sender_plan(lead_count: int = 0, recent_bounce_rate: float = 0.0, daily_sent_today: int = 0):
    """Get send strategy from sender agent."""
    try:
        plan = await run_sender(lead_count, recent_bounce_rate, daily_sent_today)
        return plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reply/analyze")
async def reply_analyze(req: ReplyAnalyzeRequest):
    """Analyze an email reply."""
    try:
        analysis = await run_reply_analyzer(req.reply_text, req.sender_info)
        return analysis.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learner")
async def learner(req: LearnerRequest):
    """Run learner agent and return strategy updates."""
    try:
        out = await run_learner(
            req.state_summary,
            req.action_taken,
            req.outcome,
            req.reward,
            req.reward_history,
        )
        return out.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manager")
async def manager(req: ManagerRequest):
    """Run manager/orchestrator agent."""
    try:
        out = await run_manager(
            req.status_summary,
            req.last_agent_outputs,
            req.metrics_summary,
        )
        return out.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rewards")
async def rewards():
    """Return reward model (category -> base reward)."""
    from app.models.schemas import REWARD_VALUES
    return REWARD_VALUES


@router.post("/job-application/pipeline")
async def job_application_pipeline(req: JobApplicationPipelineRequest):
    """
    Run first working resume pipeline:
    jobs -> match -> skills -> profile parse -> resume -> LaTeX -> PDF -> ATS score.
    """
    try:
        result = await run_job_application_pipeline(req.role, req.company, req.links)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job-application/pipeline/sample")
async def job_application_pipeline_sample():
    """Return sample input/output for the pipeline."""
    return {
        "sample_input": sample_pipeline_input(),
        "sample_output": sample_pipeline_output(),
    }


@router.get("/job-application/rag/architecture")
async def job_application_rag_architecture():
    """RAG architecture, flow diagram, and recommended tech stack."""
    return rag_architecture_overview()


@router.post("/job-application/rag/index/jobs")
async def job_application_rag_index_jobs(req: RagJobsIndexRequest):
    """Create embeddings for jobs and store vectors."""
    try:
        return await index_jobs_for_rag(req.jobs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/job-application/rag/index/resume")
async def job_application_rag_index_resume(req: RagResumeIndexRequest):
    """Create embeddings for resume text and store vectors."""
    try:
        return await index_resume_for_rag(req.resume_id, req.resume_text, req.metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/job-application/rag/retrieve-jobs")
async def job_application_rag_retrieve_jobs(req: RagRetrieveRequest):
    """Retrieve top matching jobs from vector index."""
    try:
        matches = await retrieve_top_matching_jobs(req.candidate_text, req.top_k)
        return {"matches": matches, "count": len(matches)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ats/score")
async def ats_score(req: ATSScoreRequest):
    """Score resume text against a job description."""
    try:
        return score_ats(req.resume_text, req.job_description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outreach/generate")
async def outreach_generate(req: OutreachGenerateRequest):
    """
    Build outreach package:
    find employees -> generate personalized email variants -> create tracking record.
    """
    try:
        return await build_outreach_package(
            company=req.company,
            role=req.role,
            candidate_profile=req.candidate_profile,
            job_description=req.job_description,
            outreach_types=req.outreach_types,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outreach/send")
async def outreach_send(req: OutreachSendRequest):
    """Send generated emails and update campaign tracking statuses/timestamps."""
    try:
        return await send_campaign(
            campaign_id=req.campaign_id,
            generated_messages=req.generated_messages,
            tone=req.tone,
            sender_name=req.sender_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outreach/tracking/{campaign_id}")
async def outreach_tracking(campaign_id: str):
    """Read outreach tracking state for one campaign."""
    try:
        return get_campaign_tracking(campaign_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/outreach/sample")
async def outreach_sample():
    """Sample outreach input and generated output preview."""
    sample_input = sample_outreach_input()
    sample_output = await build_outreach_package(**sample_input)
    return {"sample_input": sample_input, "sample_output": sample_output}
