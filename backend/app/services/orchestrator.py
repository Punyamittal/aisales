"""Orchestrate agents into pipelines."""
from ..models.schemas import ProjectInput, CompanyInput
from ..agents.runner import (
    run_analyzer,
    run_researcher,
    run_matcher,
    run_pitcher,
    run_deck_designer,
)


async def run_pipeline(
    project: ProjectInput,
    company: CompanyInput,
    contact_role: str = "Decision Maker",
    *,
    include_deck: bool = True,
):
    """
    Run full pipeline: analyze project → analyze company → match → pitch email + optional deck.
    Returns dict with analysis, match, email_body, deck (if requested).
    """
    project_analysis = await run_analyzer(project)
    company_analysis = await run_researcher(company)
    match = await run_matcher(project_analysis, company_analysis)
    email_body = await run_pitcher(project_analysis, company_analysis, match, contact_role)
    deck = None
    if include_deck:
        deck = await run_deck_designer(project_analysis, company_analysis, match)
    return {
        "project_analysis": project_analysis.model_dump(),
        "company_analysis": company_analysis.model_dump(),
        "match": match.model_dump(),
        "email_body": email_body,
        "deck": deck.model_dump() if deck else None,
    }
