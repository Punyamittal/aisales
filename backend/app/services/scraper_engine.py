"""Local scraping engine with retries, delays, and anti-block headers."""
from __future__ import annotations

import asyncio
import random
import re
from urllib.parse import urljoin, urlparse

import httpx


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/124.0",
]


def normalize_company_domain(company_or_domain: str) -> str:
    clean = (company_or_domain or "").strip().lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = clean.split("/")[0]
    if "." in clean:
        return clean
    return re.sub(r"[^a-z0-9]", "", clean) + ".com"


async def fetch_html(url: str, retries: int = 2, delay_seconds: float = 0.5) -> str:
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            ) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text
                if response.status_code in {403, 429} and attempt < retries:
                    await asyncio.sleep(delay_seconds * (attempt + 1))
                    continue
        except Exception:
            if attempt < retries:
                await asyncio.sleep(delay_seconds * (attempt + 1))
                continue
            return ""
    return ""


def extract_links_by_keywords(base_url: str, html: str, keywords: list[str]) -> list[str]:
    links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    out: list[str] = []
    for href in links:
        absolute = urljoin(base_url, href)
        path = (urlparse(absolute).path or "").lower()
        if any(k in path for k in keywords):
            if absolute not in out:
                out.append(absolute)
    return out


def strip_html_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

