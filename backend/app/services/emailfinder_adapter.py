"""Adapter to pull emails via local EmailFinder folder."""
from __future__ import annotations

import asyncio
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ..models.schemas import SuggestedContact

EMAIL_RE = re.compile(r"[a-z0-9.\-+_]+@[a-z0-9.\-+_]+\.[a-z]+", re.I)


def _normalize_domain(domain: str) -> str:
    clean = (domain or "").strip().lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = clean.split("/")[0]
    return clean


def _extract_from_emailfinder_sync(domain: str) -> list[str]:
    repo_root = Path(__file__).resolve().parents[3]
    emailfinder_root = repo_root / "EmailFinder"
    if not emailfinder_root.exists():
        return []

    if str(emailfinder_root) not in sys.path:
        sys.path.insert(0, str(emailfinder_root))

    found: set[str] = set()
    try:
        from emailfinder.utils.library import (  # type: ignore
            get_emails_from_baidu,
            get_emails_from_bing,
            get_emails_from_google,
        )
    except Exception:
        return []

    for fn in (get_emails_from_bing, get_emails_from_google, get_emails_from_baidu):
        try:
            emails = fn(domain) or []
            for email in emails:
                e = str(email).strip().lower()
                if domain in e and EMAIL_RE.fullmatch(e):
                    found.add(e)
        except Exception:
            continue
    return sorted(found)


async def scrape_with_emailfinder_folder(domain: str, max_results: int = 10) -> list[SuggestedContact]:
    """
    Use local EmailFinder folder (search-engine indexed emails) as a source.
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []

    try:
        emails = await asyncio.wait_for(asyncio.to_thread(_extract_from_emailfinder_sync, domain), timeout=10.0)
    except asyncio.TimeoutError:
        emails = []

    out: list[SuggestedContact] = []
    for email in emails[:max_results]:
        local = email.split("@")[0]
        name = " ".join([p.capitalize() for p in re.split(r"[._-]+", local)[:2] if p]) or "Hiring Team"
        out.append(
            SuggestedContact(
                name=name,
                email=email,
                title="",
                linkedin_url="",
            )
        )
    return out


def _extract_google_result_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls: list[str] = []

    # Direct absolute links.
    for link in soup.find_all("a", attrs={"href": re.compile(r"^https?://")}):
        href = (link.get("href") or "").strip()
        if href and href not in urls:
            urls.append(href)

    # Google redirect links: /url?q=https://target...
    for link in soup.find_all("a"):
        href = (link.get("href") or "").strip()
        if not href.startswith("/url?q="):
            continue
        target = href.split("/url?q=", 1)[1].split("&", 1)[0]
        if target.startswith("http") and target not in urls:
            urls.append(target)
    return urls


async def scrape_with_search_dork_style(domain: str, max_results: int = 10) -> list[SuggestedContact]:
    """
    Supportive addition inspired by search-dork based email discovery.
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []

    query = quote_plus(f'inurl:"{domain}" AND intext:"@{domain}"')
    search_url = f"https://www.google.com/search?q={query}&num=20"
    request = urllib.request.Request(search_url)
    request.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    )

    try:
        raw = urllib.request.urlopen(request, timeout=8).read()
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        return []

    urls = [
        u
        for u in _extract_google_result_urls(html)
        if "google.com" not in u and "webcache.googleusercontent.com" not in u
    ][:25]

    found: set[str] = set()
    email_re = EMAIL_RE
    timeout = httpx.Timeout(8.0, connect=6.0)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for target_url in urls:
            try:
                resp = await client.get(target_url)
            except Exception:
                continue
            page = resp.text or ""
            for mail in email_re.findall(page):
                e = mail.lower().strip()
                if domain in e:
                    found.add(e)
                    if len(found) >= max_results:
                        break
            if len(found) >= max_results:
                break

    out: list[SuggestedContact] = []
    for email in sorted(found)[:max_results]:
        local = email.split("@")[0]
        name = " ".join([p.capitalize() for p in re.split(r"[._-]+", local)[:2] if p]) or "Hiring Team"
        out.append(
            SuggestedContact(
                name=name,
                email=email,
                title="",
                linkedin_url="",
            )
        )
    return out
