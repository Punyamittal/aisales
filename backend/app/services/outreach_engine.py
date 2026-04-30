"""Cold outreach engine: discovery, generation, sending, and tracking."""
from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Any

from app.services.emailfinder_adapter import scrape_with_emailfinder_folder, scrape_with_search_dork_style
from app.services.email_service import send_email
from app.services.email_scraper_adapter import scrape_with_email_scraper_folder_style
from app.services.scraper_contacts import scrape_contacts_for_domain


OUTREACH_TYPES = ("referral_request", "internship_inquiry", "networking_message")
TONES = ("formal", "casual")

_TRACKING_STORE: dict[str, dict[str, Any]] = {}
PUBLIC_EMAIL_POOL = [
    "trademark-permissions@mozilla.com",
    "community@debian.org",
    "debian-boot@lists.debian.org",
    "debian-devel@lists.debian.org",
    "debian-events-eu@lists.debian.org",
    "debian-project@lists.debian.org",
    "debian-user@lists.debian.org",
    "debian-www@lists.debian.org",
    "events@debian.org",
    "listmaster@lists.debian.org",
    "mirrors@debian.org",
    "owner@bugs.debian.org",
    "press@debian.org",
    "security@debian.org",
    "webmaster@debian.org",
    "ecadmin@icann.org",
    "exec-director@ietf.org",
    "liaison-coordination@iab.org",
    "media@ietf.org",
    "privacy@ietf.org",
    "sponsorship@ietf.org",
    "support@ietf.org",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _company_to_domain(company: str) -> str:
    cleaned = (company or "").strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = cleaned.split("/")[0]
    if "." in cleaned:
        return cleaned
    base = re.sub(r"[^a-z0-9]+", "", cleaned)
    return f"{base}.com" if base else ""


def _matches_role(employee_role: str, target_role: str) -> bool:
    if not employee_role:
        return False
    emp = employee_role.lower()
    for token in re.findall(r"[a-zA-Z]{3,}", (target_role or "").lower()):
        if token in emp:
            return True
    return False


async def find_employees(company: str, role: str, max_results: int = 8) -> list[dict[str, str]]:
    domain = _company_to_domain(company)
    # Primary sources: EmailFinder folder + Email-Scraper folder strategy.
    ef = await scrape_with_emailfinder_folder(domain, max_results=max_results * 2)
    dork = await scrape_with_search_dork_style(domain, max_results=max_results * 2)
    es = await scrape_with_email_scraper_folder_style(domain, max_results=max_results * 2, max_pages=20)
    discovered = []
    seen: set[str] = set()
    for c in ef + dork + es:
        email = (c.email or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        discovered.append(c)
        if len(discovered) >= max_results * 2:
            break
    if not discovered:
        discovered = await scrape_contacts_for_domain(domain, max_results=max_results * 2, max_pages=8)

    employees = [
        {
            "name": c.name or "Sir/Ma'am",
            "email": c.email,
            "role": c.title or "",
            "linkedin": c.linkedin_url or "",
            "source": "emailfinder/email-scraper",
        }
        for c in discovered
    ]
    prioritized = [e for e in employees if _matches_role(e.get("role", ""), role)]
    fallback = [e for e in employees if e not in prioritized]
    ordered = (prioritized + fallback)[:max_results]

    if ordered:
        return ordered

    # Fallback when website has no visible employee emails.
    return [
        {
            "name": " ".join([p.capitalize() for p in re.split(r"[._-]+", email.split("@")[0])[:2] if p]) or "Contact",
            "email": email,
            "role": "Public Contact",
            "linkedin": "",
            "source": "public-contact-pool-fallback",
        }
        for email in PUBLIC_EMAIL_POOL[:max_results]
    ]


def _tone_line(tone: str) -> str:
    return (
        "I would be grateful for any guidance you can share."
        if tone == "formal"
        else "Would love your quick advice if you have a minute."
    )


def _build_subject(outreach_type: str, tone: str, company: str, employee_role: str) -> str:
    if outreach_type == "referral_request":
        return (
            f"Referral request for {company} ({employee_role})"
            if tone == "formal"
            else f"Could you refer me to {company}?"
        )
    if outreach_type == "internship_inquiry":
        return (
            f"Internship inquiry - {company}"
            if tone == "formal"
            else f"Any internship openings at {company}?"
        )
    return (
        f"Networking request - {employee_role} at {company}"
        if tone == "formal"
        else f"Quick networking note ({company})"
    )


def _build_email_body(
    outreach_type: str,
    tone: str,
    company: str,
    employee: dict[str, str],
    candidate_profile: dict[str, str],
    job_description: str,
) -> str:
    candidate_name = candidate_profile.get("name", "Candidate")
    candidate_intro = candidate_profile.get("headline", "software engineer candidate")
    candidate_skills = (candidate_profile.get("skills") or "").strip() or "Python, FastAPI, SQL, ML pipelines"
    employee_name = employee.get("name", "there")
    employee_role = employee.get("role") or "team member"
    jd_line = (job_description or "").strip()[:180]

    opening = (
        f"Dear {employee_name},"
        if tone == "formal"
        else f"Hi {employee_name},"
    )
    close = (
        f"Sincerely,\n{candidate_name}"
        if tone == "formal"
        else f"Thanks,\n{candidate_name}"
    )

    if outreach_type == "referral_request":
        core = (
            f"I am reaching out regarding opportunities at {company}. "
            f"I am a {candidate_intro} with hands-on work in {candidate_skills}. "
            f"I noticed your role as {employee_role}, and I would value your perspective on fit."
        )
        ask = "If suitable, I would appreciate a referral for relevant openings."
    elif outreach_type == "internship_inquiry":
        core = (
            f"I am interested in internship opportunities at {company}. "
            f"My background includes {candidate_skills}, and I am actively building production-ready projects."
        )
        ask = "Could you share if your team is considering interns in the coming cycle?"
    else:
        core = (
            f"I admire the work your team is doing at {company}. "
            f"I am a {candidate_intro} focusing on {candidate_skills}."
        )
        ask = "Would you be open to a short networking chat to share your journey and advice?"

    context = f"Role context: {employee_role}. Job context: {jd_line}" if jd_line else f"Role context: {employee_role}."
    body = "\n".join([opening, "", core, context, _tone_line(tone), ask, "", close])
    return body


def generate_email_variants(
    outreach_type: str,
    company: str,
    employee: dict[str, str],
    candidate_profile: dict[str, str],
    job_description: str,
) -> dict[str, Any]:
    if outreach_type not in OUTREACH_TYPES:
        raise ValueError(f"Unsupported outreach_type: {outreach_type}")
    variants: dict[str, dict[str, str]] = {}
    for tone in TONES:
        variants[tone] = {
            "subject": _build_subject(outreach_type, tone, company, employee.get("role", "")),
            "body": _build_email_body(
                outreach_type=outreach_type,
                tone=tone,
                company=company,
                employee=employee,
                candidate_profile=candidate_profile,
                job_description=job_description,
            ),
        }
    return {
        "outreach_type": outreach_type,
        "employee": employee,
        "tone_options": variants,
    }


def create_campaign_tracking(company: str, role: str, outreach_type: str, employees: list[dict[str, str]]) -> str:
    campaign_id = f"cmp_{uuid.uuid4().hex[:10]}"
    _TRACKING_STORE[campaign_id] = {
        "campaign_id": campaign_id,
        "company": company,
        "role": role,
        "outreach_type": outreach_type,
        "status": "drafted",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "events": [{"status": "drafted", "timestamp": _utc_now_iso(), "message": "Campaign generated"}],
        "recipients": [
            {
                "email": e.get("email", ""),
                "name": e.get("name", ""),
                "role": e.get("role", ""),
                "status": "pending",
                "last_event_at": None,
            }
            for e in employees
        ],
    }
    return campaign_id


def _push_campaign_event(campaign_id: str, status: str, message: str) -> None:
    campaign = _TRACKING_STORE.get(campaign_id)
    if not campaign:
        return
    now = _utc_now_iso()
    campaign["status"] = status
    campaign["updated_at"] = now
    campaign["events"].append({"status": status, "timestamp": now, "message": message})


async def send_campaign(
    campaign_id: str,
    generated_messages: list[dict[str, Any]],
    tone: str = "formal",
    sender_name: str = "AI Sales Bot",
) -> dict[str, Any]:
    campaign = _TRACKING_STORE.get(campaign_id)
    if not campaign:
        raise ValueError("campaign_id not found")
    if tone not in TONES:
        raise ValueError("tone must be formal or casual")

    _push_campaign_event(campaign_id, "sending", "Email delivery started")
    sent = 0
    failed = 0
    for msg in generated_messages:
        recipient_email = msg["employee"]["email"]
        recipient_name = msg["employee"].get("name", "")
        variant = msg["tone_options"][tone]
        ok = await send_email(recipient_email, variant["subject"], variant["body"], from_name=sender_name)

        recipient_row = next((r for r in campaign["recipients"] if r["email"] == recipient_email), None)
        if recipient_row:
            recipient_row["status"] = "sent" if ok else "failed"
            recipient_row["last_event_at"] = _utc_now_iso()

        if ok:
            sent += 1
        else:
            failed += 1

    final_status = "sent" if failed == 0 else ("partial" if sent > 0 else "failed")
    _push_campaign_event(campaign_id, final_status, f"Delivery complete. sent={sent}, failed={failed}")
    return {"campaign_id": campaign_id, "sent": sent, "failed": failed, "status": final_status}


def get_campaign_tracking(campaign_id: str) -> dict[str, Any]:
    campaign = _TRACKING_STORE.get(campaign_id)
    if not campaign:
        raise ValueError("campaign_id not found")
    return campaign


async def build_outreach_package(
    company: str,
    role: str,
    candidate_profile: dict[str, str],
    job_description: str,
    outreach_types: list[str] | None = None,
) -> dict[str, Any]:
    selected_types = outreach_types or list(OUTREACH_TYPES)
    employees = await find_employees(company=company, role=role, max_results=5)
    campaign_id = create_campaign_tracking(company=company, role=role, outreach_type="mixed", employees=employees)

    generated: list[dict[str, Any]] = []
    for employee in employees:
        for outreach_type in selected_types:
            generated.append(
                generate_email_variants(
                    outreach_type=outreach_type,
                    company=company,
                    employee=employee,
                    candidate_profile=candidate_profile,
                    job_description=job_description,
                )
            )
    return {
        "campaign_id": campaign_id,
        "company": company,
        "role": role,
        "employees_found": employees,
        "emails_generated": generated,
        "tracking": get_campaign_tracking(campaign_id),
    }


def sample_outreach_input() -> dict[str, Any]:
    return {
        "company": "Acme AI",
        "role": "Software Engineer",
        "candidate_profile": {
            "name": "Punya Mittal",
            "headline": "backend-focused software engineer",
            "skills": "Python, FastAPI, SQL, automation, API integrations",
        },
        "job_description": "Looking for an engineer to build backend APIs, automate workflows, and collaborate cross-functionally.",
        "outreach_types": ["referral_request", "internship_inquiry", "networking_message"],
    }

