"""
Lead enrichment: fetch contact names and emails by company domain.
Uses web scraping ONLY — no external API dependencies (Hunter, Apollo removed).
"""
import asyncio
import logging
import re

from ..models.schemas import SuggestedContact

logger = logging.getLogger(__name__)


def _normalize_domain(domain: str) -> str:
    """Strip protocol and path, lowercase."""
    if not domain or not isinstance(domain, str):
        return ""
    s = domain.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0]
    return s if s else ""


# Known company name -> domain (when LLM doesn't return company_domain)
COMPANY_TO_DOMAIN: dict[str, str] = {
    "h2o.ai": "h2o.ai",
    "h2o": "h2o.ai",
    "databricks": "databricks.com",
    "datarobot": "datarobot.com",
    "zendesk": "zendesk.com",
    "kaggle": "kaggle.com",
    "google": "google.com",
    "google cloud": "cloud.google.com",
    "amazon sagemaker": "aws.amazon.com",
    "aws": "aws.amazon.com",
    "microsoft": "microsoft.com",
    "microsoft azure": "azure.microsoft.com",
    "azure": "azure.microsoft.com",
    "alibaba cloud": "alibaba.com",
    "ibm": "ibm.com",
    "ibm watson": "ibm.com",
    "salesforce": "salesforce.com",
    "facebook": "meta.com",
    "meta": "meta.com",
    "intel": "intel.com",
    "stanford": "stanford.edu",
    "stripe": "stripe.com",
    "vercel": "vercel.com",
    "netlify": "netlify.com",
    "supabase": "supabase.com",
    "notion": "notion.so",
    "linear": "linear.app",
    "retool": "retool.com",
    "twilio": "twilio.com",
    "sendgrid": "sendgrid.com",
    "plausible": "plausible.io",
    "figma": "figma.com",
    "github": "github.com",
    "gitlab": "gitlab.com",
    "atlassian": "atlassian.com",
    "slack": "slack.com",
    "discord": "discord.com",
    "shopify": "shopify.com",
    "hubspot": "hubspot.com",
    "intercom": "intercom.com",
    "datadog": "datadoghq.com",
    "snyk": "snyk.io",
    "hashicorp": "hashicorp.com",
    "cloudflare": "cloudflare.com",
    "digital ocean": "digitalocean.com",
    "digitalocean": "digitalocean.com",
    "mongodb": "mongodb.com",
    "elastic": "elastic.co",
    "confluent": "confluent.io",
    "cockroach labs": "cockroachlabs.com",
    "planetscale": "planetscale.com",
    "neon": "neon.tech",
    "railway": "railway.app",
    "render": "render.com",
    "fly.io": "fly.io",
    "deno": "deno.com",
    "bun": "bun.sh",
}


def infer_domain_from_company_name(company_name: str) -> str:
    """
    Infer a likely website domain when the LLM doesn't provide company_domain.
    Uses a known map and simple heuristics.
    """
    if not company_name or not isinstance(company_name, str):
        return ""
    raw = company_name.strip()
    key_lower = raw.lower()
    key_slug = re.sub(r"[^a-z0-9]", "", key_lower)
    key_with_spaces = re.sub(r"[^a-z0-9\s]", " ", key_lower).strip()
    # Match when company name contains the map key or vice versa
    for k, d in COMPANY_TO_DOMAIN.items():
        k_slug = re.sub(r"[^a-z0-9]", "", k)
        if k in key_with_spaces or k in key_lower or k_slug in key_slug or key_slug in k_slug:
            return d
    # If name already looks like a domain (has .com, .io, .ai, etc.)
    if re.search(r"\.[a-z]{2,}$", raw, re.I):
        return _normalize_domain(raw)
    # Heuristic: slugify and try .com
    slug = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if len(slug) >= 2:
        return f"{slug}.com"
    return ""


async def _enrich_single_company(
    c: any, max_contacts: int, semaphore: asyncio.Semaphore
) -> None:
    """Enrich a single company limited by semaphore."""
    from .scraper_contacts import scrape_contacts_for_domain

    async with semaphore:
        company_name = getattr(c, "company_name", None) or "?"
        domain = getattr(c, "company_domain", None) or ""
        domain = _normalize_domain(domain)

        if not domain and company_name != "?":
            domain = infer_domain_from_company_name(company_name)
            if domain:
                setattr(c, "company_domain", domain)

        if not domain:
            logger.info("Skip enrichment for %s: no domain", company_name)
            return

        logger.info(">>> Scraping contacts: %s (%s)", company_name, domain)
        try:
            # Individual scraper timeout as safety net
            contacts = await asyncio.wait_for(
                scrape_contacts_for_domain(
                    domain,
                    max_results=max_contacts,
                    max_pages=3,  # Reduced from 5 for speed
                    delay_seconds=0.1,
                ),
                timeout=25.0,
            )
            setattr(c, "contacts", contacts)
            logger.info("<<< Finished %s: found %d", company_name, len(contacts))
        except asyncio.TimeoutError:
            logger.warning("Timed out scraping %s", domain)
            setattr(c, "contacts", [])
        except Exception as e:
            logger.warning("Scraper error for %s: %s", domain, e)
            setattr(c, "contacts", [])


async def enrich_suggested_companies(
    companies: list,
    max_contacts_per_company: int = 8,
    max_concurrent: int = 5,
) -> list:
    """
    Enrich multiple companies in parallel (throttled by semaphore).
    """
    if not companies:
        return []

    logger.info("Starting enrichment for %d companies (concurrency=%d)", len(companies), max_concurrent)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    tasks = [
        _enrich_single_company(c, max_contacts_per_company, semaphore)
        for c in companies
    ]
    
    await asyncio.gather(*tasks)
    logger.info("Enrichment complete for all companies")
    return companies