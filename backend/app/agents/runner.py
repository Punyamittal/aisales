"""Run each agent with Ollama using project prompts."""
import json
import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

from .ollama_client import ollama_client, load_prompt
from ..models.schemas import (
    ProjectAnalysis,
    CompanyAnalysis,
    MatchResult,
    PitchDeck,
    Slide,
    EmailSendPlan,
    ReplyAnalysis,
    LearnerOutput,
    ManagerOutput,
    SuggestedCompany,
    ProjectInput,
    CompanyInput,
)


def _parse(cls: type, data: dict[str, Any]) -> Any:
    """Parse dict into Pydantic model, fill defaults for missing keys."""
    return cls.model_validate({k: v for k, v in data.items() if k in cls.model_fields})


async def run_analyzer(project: ProjectInput) -> ProjectAnalysis:
    """Run project analyzer agent."""
    system = load_prompt("analyzer")
    user = (
        f"Repository: {project.repo_name}\n"
        f"Description: {project.description}\n"
        f"README (excerpt): {project.readme[:4000] if project.readme else 'N/A'}\n"
        f"Tech stack: {', '.join(project.tech_stack) or 'N/A'}\n"
        f"Stars: {project.stars}, Forks: {project.forks}\n\n"
        "Return only a single JSON object, no markdown or extra text."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(ProjectAnalysis, out)


def _fallback_companies() -> list[SuggestedCompany]:
    """Return example companies when the model returns none, so the user can still try contacts/emails."""
    return [
        SuggestedCompany(company_name="Vercel", company_description="Cloud platform for frontend frameworks", company_domain="vercel.com", why_fit="Builds dev tools and infra", recommended_roles=["CTO", "VP Engineering"]),
        SuggestedCompany(company_name="Linear", company_description="Issue tracking and project management", company_domain="linear.app", why_fit="Developer-focused product", recommended_roles=["Head of Product", "VP Engineering"]),
        SuggestedCompany(company_name="Notion", company_description="Workspace and docs", company_domain="notion.so", why_fit="Productivity and dev workflows", recommended_roles=["CTO", "Head of Product"]),
        SuggestedCompany(company_name="Retool", company_description="Internal tools and workflows", company_domain="retool.com", why_fit="B2B dev tools", recommended_roles=["CTO", "VP Engineering"]),
        SuggestedCompany(company_name="Supabase", company_description="Open source Firebase alternative", company_domain="supabase.com", why_fit="Backend and dev tools", recommended_roles=["CTO", "Developer Advocate"]),
    ]


async def run_company_suggester(project_analysis: ProjectAnalysis) -> list[SuggestedCompany]:
    """Suggest companies and contact roles to email. Focused on high-relevance matching."""
    system = load_prompt("company_suggester")
    
    # Include more specific details for better matching relevance
    project_details = (
        f"PROJECT PURPOSE: {project_analysis.project_summary[:500]}\n"
        f"PROBLEM SOLVED: {project_analysis.problem}\n"
        f"TECHNICAL SOLUTION: {project_analysis.solution}\n"
        f"TARGET INDUSTRIES: {', '.join(project_analysis.industries)}\n"
        f"TARGET USERS: {', '.join(project_analysis.target_users)}"
    )
    
    user = (
        f"PROJECT CONTEXT:\n{project_details}\n\n"
        "TASK: Identify 8 REAL companies (startups or tech firms) that would realistically buy or use this tool. "
        "Strictly prioritize companies within the target industries mentioned above. "
        "Return a JSON object: {\"companies\": []}. "
        "Each object MUST have: company_name, company_description, company_domain, why_fit, recommended_roles. "
        "Output ONLY JSON."
    )
    
    # Use low temperature for high-relevance and stable JSON structure
    out = await ollama_client.generate_json(system, user, temperature=0.1, num_predict=3072)
    
    raw_list = out.get("companies") or out.get("suggested_companies") or out.get("data") or []
    if not isinstance(raw_list, list):
        raw_list = []

    if not raw_list:
        logger.warning("Empty response from Ollama; trying ultra-simple fallback.")
        fallback_user = (
            "List 3 tech companies that would buy a B2B SaaS tool. "
            "Return ONLY JSON: {\"companies\": [{\"company_name\": \"...\", \"company_description\": \"...\", \"company_domain\": \"...\", \"why_fit\": \"...\", \"recommended_roles\": [\"CTO\"]}]}"
        )
        out = await ollama_client.generate_json(system, fallback_user, temperature=0.1, num_predict=1024)
        raw_list = out.get("companies") or []

    if not raw_list:
        logger.info("Providing hardcoded fallback companies.")
        return _fallback_companies()
    parsed: list[SuggestedCompany] = []
    for c in raw_list:
        if not isinstance(c, dict):
            continue
        try:
            parsed.append(_parse(SuggestedCompany, c))
        except Exception as e:
            logger.debug("Skip invalid company item: %s", e)
    if len(parsed) < len(raw_list):
        logger.info("Parsed %d companies from %d raw items", len(parsed), len(raw_list))
    return parsed


async def run_researcher(company: CompanyInput) -> CompanyAnalysis:
    """Run company researcher agent."""
    system = load_prompt("researcher")
    user = (
        f"Company: {company.name}\n"
        f"Website: {company.website}\n"
        f"News: {company.news or 'N/A'}\n"
        f"Product info: {company.product_info or 'N/A'}\n"
        f"Funding: {company.funding_info or 'N/A'}\n"
        f"Job postings: {company.job_postings or 'N/A'}\n\n"
        "Return only a single JSON object, no markdown or extra text."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(CompanyAnalysis, out)


async def run_matcher(project_analysis: ProjectAnalysis, company_analysis: CompanyAnalysis) -> MatchResult:
    """Run project–company matcher agent."""
    system = load_prompt("matcher")
    user = (
        "Project analysis:\n"
        + json.dumps(project_analysis.model_dump(), indent=2)
        + "\n\nCompany analysis:\n"
        + json.dumps(company_analysis.model_dump(), indent=2)
        + "\n\nReturn only a single JSON object with fit_score, match_reasoning, recommended_pitch_angle, risk_factors."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(MatchResult, out)


async def run_pitcher(project: ProjectAnalysis, company: CompanyAnalysis, match: MatchResult, contact_role: str = "Decision Maker") -> str:
    """Write personalized outreach email."""
    system = load_prompt("pitcher")
    user = (
        f"PROJECT:\n{project.model_dump_json(indent=2)}\n\n"
        f"COMPANY:\n{company.model_dump_json(indent=2)}\n\n"
        f"MATCH ANALYSIS:\n{match.model_dump_json(indent=2)}\n\n"
        f"CONTACT ROLE: {contact_role}"
    )
    return await ollama_client.generate(system, user, temperature=0.5)


async def run_fast_pitcher(project: ProjectAnalysis, company: SuggestedCompany) -> str:
    """Quickly generate a personalized pitch for a suggested company using pre-existing fit analysis."""
    system = load_prompt("pitcher")
    user = (
        f"PROJECT CONTEXT:\nSummary: {project.project_summary}\nBusiness Value: {project.business_value}\n\n"
        f"TARGET COMPANY: {company.company_name}\n"
        f"DESCRIPTION: {company.company_description}\n"
        f"WHY THEY ARE A FIT: {company.why_fit}\n"
        f"RECOMMENDED ROLES: {', '.join(company.recommended_roles)}\n\n"
        "TASK: Write a highly personalized, 1-on-1 outreach email. Do not use generic templates. "
        "Reference their specific business and why this project specifically helps them. "
        "Sign as 'Punya Mittal' and start with 'Dear Sir/Ma'am,'."
    )
    # Use low temperature for consistency
    return await ollama_client.generate(system, user, temperature=0.3, num_predict=1024)


async def run_deck_designer(
    project_analysis: ProjectAnalysis,
    company_analysis: CompanyAnalysis,
    match: MatchResult,
) -> PitchDeck:
    """Run pitch deck designer agent."""
    system = load_prompt("deck_designer")
    user = (
        "Project:\n"
        + json.dumps(project_analysis.model_dump(), indent=2)
        + "\n\nCompany:\n"
        + json.dumps(company_analysis.model_dump(), indent=2)
        + "\n\nMatch: "
        + json.dumps(match.model_dump(), indent=2)
        + "\n\nReturn only a single JSON object with title, subtitle, and slides (array of {title, bullet_points})."
    )
    out = await ollama_client.generate_json(system, user)
    slides = [
        Slide(title=s.get("title", ""), bullet_points=s.get("bullet_points", []))
        for s in out.get("slides", [])
    ]
    return PitchDeck(
        title=out.get("title", ""),
        subtitle=out.get("subtitle", ""),
        slides=slides,
    )


async def run_sender(
    lead_count: int = 0,
    recent_bounce_rate: float = 0.0,
    daily_sent_today: int = 0,
) -> EmailSendPlan:
    """Run sender/ops agent for send strategy."""
    system = load_prompt("sender")
    user = (
        f"Lead count: {lead_count}\n"
        f"Recent bounce rate: {recent_bounce_rate}\n"
        f"Emails sent today: {daily_sent_today}\n\n"
        "Return only a single JSON object with send_time, strategy, include_attachment, daily_limit, risk_level."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(EmailSendPlan, out)


async def run_reply_analyzer(reply_text: str, sender_info: str = "") -> ReplyAnalysis:
    """Run reply analyzer agent."""
    system = load_prompt("reply_analyzer")
    user = (
        f"Reply text:\n{reply_text}\n\n"
        f"Sender info: {sender_info or 'Unknown'}\n\n"
        "Return only a single JSON object with category, sentiment, key_points, recommended_action."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(ReplyAnalysis, out)


async def run_learner(
    state_summary: str,
    action_taken: str,
    outcome: str,
    reward: float,
    reward_history: list[float],
) -> LearnerOutput:
    """Run learner agent."""
    system = load_prompt("learner")
    user = (
        f"State: {state_summary}\n"
        f"Action: {action_taken}\n"
        f"Outcome: {outcome}\n"
        f"Reward: {reward}\n"
        f"Recent rewards: {reward_history[-20:]}\n\n"
        "Return only a single JSON object with updated_preferences, insights, strategy_changes."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(LearnerOutput, out)


async def run_manager(
    status_summary: str,
    last_agent_outputs: list[str],
    metrics_summary: str,
) -> ManagerOutput:
    """Run manager/orchestrator agent."""
    system = load_prompt("manager")
    user = (
        f"System status: {status_summary}\n"
        f"Recent agent outputs: {last_agent_outputs}\n"
        f"Metrics: {metrics_summary}\n\n"
        "Return only a single JSON object with next_tasks, priority_level, risk_alerts, optimization_goals."
    )
    out = await ollama_client.generate_json(system, user)
    return _parse(ManagerOutput, out)
