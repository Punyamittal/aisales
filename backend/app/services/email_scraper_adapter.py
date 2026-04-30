"""Adapter that uses Email-Scraper folder crawling strategy."""
from __future__ import annotations

import asyncio
import re
from collections import deque
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from ..models.schemas import SuggestedContact


EMAIL_RE = re.compile(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", re.I)
OBFUSCATED_RE = re.compile(
    r"([a-z0-9._%+-]+)\s*(?:\(|\[)?\s*(?:@|at)\s*(?:\)|\])?\s*([a-z0-9.-]+)\s*(?:\(|\[)?\s*(?:\.|dot)\s*(?:\)|\])?\s*([a-z]{2,})",
    re.I,
)


def _normalize_domain(domain: str) -> str:
    clean = (domain or "").strip().lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = clean.split("/")[0]
    return clean


async def scrape_with_email_scraper_folder_style(
    domain: str,
    max_results: int = 10,
    max_pages: int = 40,
) -> list[SuggestedContact]:
    """
    Port of strategy used in Email-Scraper/code.py:
    BFS crawl links from seed URL and regex extract emails.
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []

    seed = f"https://{domain}"
    seed_urls = [
        seed,
        f"{seed}/contact",
        f"{seed}/contact-us",
        f"{seed}/about",
        f"{seed}/about-us",
        f"{seed}/team",
        f"{seed}/careers",
        f"{seed}/jobs",
        f"{seed}/press",
        f"{seed}/privacy",
    ]
    queue = deque(seed_urls)
    scraped_urls: set[str] = set()
    found_emails: set[str] = set()

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        count = 0
        while queue and count < max_pages and len(found_emails) < max_results:
            url = queue.popleft()
            if url in scraped_urls:
                continue
            scraped_urls.add(url)
            count += 1
            try:
                response = await client.get(url)
            except Exception:
                continue
            html = response.text or ""

            for mail in EMAIL_RE.findall(html):
                if domain in mail.lower():
                    found_emails.add(mail.lower())
                    if len(found_emails) >= max_results:
                        break
            # Catch common obfuscation patterns like "name [at] company [dot] com"
            for local, host, tld in OBFUSCATED_RE.findall(html):
                candidate = f"{local}@{host}.{tld}".lower()
                if domain in candidate:
                    found_emails.add(candidate)
                    if len(found_emails) >= max_results:
                        break

            soup = BeautifulSoup(html, "html.parser")
            parts = urlsplit(url)
            base_url = f"{parts.scheme}://{parts.netloc}"
            path = url[: url.rfind("/") + 1] if "/" in parts.path else url
            for anchor in soup.find_all("a"):
                href = anchor.attrs.get("href", "").strip()
                if not href:
                    continue
                if href.lower().startswith("mailto:"):
                    mail = href.split(":", 1)[1].split("?", 1)[0].strip().lower()
                    if domain in mail and EMAIL_RE.fullmatch(mail):
                        found_emails.add(mail)
                    continue
                if href.startswith("/"):
                    nxt = urljoin(base_url, href)
                elif href.startswith("http"):
                    nxt = href
                else:
                    nxt = urljoin(path, href)
                if domain not in nxt.lower():
                    continue
                if any(skip in nxt.lower() for skip in [".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", "#"]):
                    continue
                if nxt not in scraped_urls:
                    queue.append(nxt)
            await asyncio.sleep(0.15)

    contacts: list[SuggestedContact] = []
    for email in sorted(found_emails)[:max_results]:
        local = email.split("@")[0]
        name = " ".join([p.capitalize() for p in local.split(".")[:2]]) if "." in local else "Hiring Team"
        contacts.append(
            SuggestedContact(
                name=name,
                email=email,
                title="",
                linkedin_url="",
            )
        )
    return contacts

