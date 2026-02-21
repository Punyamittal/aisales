"""
Scrape company websites for contact emails using Beautiful Soup.
This is the PRIMARY and ONLY contact enrichment method (no Hunter/Apollo dependency).

Strategy (ordered by reliability):
1. Sitemap.xml → discover contact/team/about pages
2. Common paths (/contact, /about, /team, /people, /leadership, etc.)
3. mailto: links in HTML
4. Structured data (JSON-LD, microdata) → Person, Organization emails
5. Plain-text email regex + deobfuscation
6. Team page parsing → extract names, titles, LinkedIn URLs
7. Meta tags and headers
"""
import asyncio
import json
import logging
import random
import re
from typing import Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup, Tag

from ..models.schemas import SuggestedContact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User-Agent rotation (avoid getting blocked by always sending the same UA)
# ---------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# ---------------------------------------------------------------------------
# Paths to crawl for contact info (ordered by likelihood of having emails)
# ---------------------------------------------------------------------------
CONTACT_PATHS = [
    "",                  # homepage
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/people",
    "/leadership",
    "/company",
    "/careers",
    "/jobs",
    "/support",
    "/help",
    "/impressum",
    "/imprint",
    "/legal",
    "/privacy",
    "/founders",
    "/management",
    "/staff",
    "/directory",
    "/who-we-are",
    "/meet-the-team",
    "/about/team",
    "/about/leadership",
    "/company/team",
    "/company/about",
]

# ---------------------------------------------------------------------------
# Email patterns
# ---------------------------------------------------------------------------
# RFC 5322-style email regex (simplified but practical)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Skip generic/useless emails
SKIP_EMAIL_PATTERNS = re.compile(
    r"^(newsletter|noreply|no-reply|donotreply|do-not-reply|unsubscribe|"
    r"notifications?|alerts?|bounce|mailer-daemon|postmaster|webmaster|"
    r"hostmaster|abuse|spam|test|example|admin@|root@|nobody@|null@|"
    r"support@|help@|feedback@|privacy@|security@|compliance@|"
    r"info@|contact@|hello@|hi@|press@|media@|marketing@|"
    r"jobs@|careers@|recruiting@|hr@|billing@|invoice|receipts?@|"
    r"sales@|deals@|offers@|promo@|promotions@)@|"
    r"@(sentry\.io|wixpress|example\.com|test\.com|email\.com|"
    r"localhost|127\.0\.0|sentry|github\.com|npmjs\.com|"
    r"w3\.org|schema\.org|googleapis\.com|placeholder)",
    re.I,
)

# Emails we PREFER (likely personal/business, not generic)
GOOD_EMAIL_PATTERNS = re.compile(
    r"^[a-z]+(\.[a-z]+)*@",  # firstname.lastname@ style
    re.I,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_domain(domain: str) -> str:
    """Strip protocol/path, lowercase."""
    if not domain or not isinstance(domain, str):
        return ""
    s = domain.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0].split("?")[0]
    return s if s else ""


def _is_same_domain(email: str, domain: str) -> bool:
    """Email must be @domain or a subdomain."""
    if not domain or "@" not in email:
        return False
    _, email_domain = email.rsplit("@", 1)
    email_domain = email_domain.lower()
    domain = domain.lower()
    return email_domain == domain or email_domain.endswith("." + domain)


def _should_skip_email(email: str) -> bool:
    if not email or len(email) > 120 or len(email) < 5:
        return True
    if SKIP_EMAIL_PATTERNS.search(email):
        return True
    # Skip image/file extension in email-like strings
    if re.search(r"\.(png|jpg|jpeg|gif|svg|css|js|woff|ttf)$", email, re.I):
        return True
    return False


def _email_quality_score(email: str, has_name: bool = False) -> int:
    """Rate how useful this email is (higher = better). Used for sorting."""
    score = 0
    if GOOD_EMAIL_PATTERNS.match(email):
        score += 10  # firstname.lastname style
    if has_name:
        score += 5
    if "." in email.split("@")[0]:
        score += 3  # has dot in local part → likely a real person
    if email.split("@")[0].isalpha():
        score += 1
    return score


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


# ---------------------------------------------------------------------------
# Deobfuscation
# ---------------------------------------------------------------------------

def _deobfuscate_email(text: str) -> list[str]:
    """Find emails in obfuscated text (e.g. 'contact at company dot com')."""
    out: list[str] = []
    t = text
    for pattern, repl in [
        (r"\s*\[at\]\s*", "@"),
        (r"\s*\(at\)\s*", "@"),
        (r"\s+at\s+", "@"),
        (r"\s*\[dot\]\s*", "."),
        (r"\s*\(dot\)\s*", "."),
        (r"\s+dot\s+", "."),
        (r"\s*\(\s*at\s*\)\s*", "@"),
        (r"\s*\(\s*dot\s*\)\s*", "."),
        (r"\s*&#64;\s*", "@"),       # HTML entity for @
        (r"\s*&#x40;\s*", "@"),      # HTML hex entity for @
        (r"\s*%40\s*", "@"),         # URL-encoded @
    ]:
        t = re.sub(pattern, repl, t, flags=re.I)
    for m in EMAIL_RE.finditer(t):
        email = m.group(0).lower()
        if not _should_skip_email(email):
            out.append(email)
    return out


# ---------------------------------------------------------------------------
# HTML Parsers
# ---------------------------------------------------------------------------

def _extract_json_ld_emails(soup: BeautifulSoup, base_domain: str) -> list[tuple[str, str, str]]:
    """Extract emails from JSON-LD structured data (schema.org Person, Organization)."""
    results: list[tuple[str, str, str]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        # Handle both single objects and arrays
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            _extract_from_schema_item(item, base_domain, results)
            # Check @graph
            for graph_item in (item.get("@graph") or []):
                if isinstance(graph_item, dict):
                    _extract_from_schema_item(graph_item, base_domain, results)
    return results


def _extract_from_schema_item(
    item: dict, base_domain: str, results: list[tuple[str, str, str]]
) -> None:
    """Extract email/name/title from a schema.org JSON-LD item."""
    item_type = (item.get("@type") or "").lower()
    email = (item.get("email") or "").strip().lower().replace("mailto:", "")
    name = (item.get("name") or "").strip()
    title = (item.get("jobTitle") or item.get("title") or "").strip()

    if email and EMAIL_RE.match(email) and _is_same_domain(email, base_domain):
        if not _should_skip_email(email):
            results.append((email, name, title))

    # Check contactPoint
    for cp in (item.get("contactPoint") or []):
        if isinstance(cp, dict):
            cp_email = (cp.get("email") or "").strip().lower().replace("mailto:", "")
            if cp_email and EMAIL_RE.match(cp_email) and _is_same_domain(cp_email, base_domain):
                if not _should_skip_email(cp_email):
                    cp_name = (cp.get("name") or name or "").strip()
                    results.append((cp_email, cp_name, title))

    # Check members / employee / founder
    for key in ("member", "members", "employee", "employees", "founder", "founders"):
        people = item.get(key) or []
        if isinstance(people, dict):
            people = [people]
        for p in people:
            if not isinstance(p, dict):
                continue
            p_email = (p.get("email") or "").strip().lower().replace("mailto:", "")
            p_name = (p.get("name") or "").strip()
            p_title = (p.get("jobTitle") or p.get("title") or "").strip()
            if p_email and EMAIL_RE.match(p_email) and _is_same_domain(p_email, base_domain):
                if not _should_skip_email(p_email):
                    results.append((p_email, p_name, p_title))


def _extract_team_members(soup: BeautifulSoup, base_domain: str) -> list[tuple[str, str, str]]:
    """
    Extract names, titles, and emails from team/about pages.
    Looks for common HTML patterns:
    - Cards with headings (h2/h3/h4) + paragraphs
    - Lists with structured info
    - Elements with common class names (team-member, person, staff, etc.)
    """
    results: list[tuple[str, str, str]] = []
    seen_emails: set[str] = set()

    # Common CSS class/id patterns for team member cards
    team_selectors = [
        "[class*='team-member']",
        "[class*='team_member']",
        "[class*='person']",
        "[class*='staff']",
        "[class*='member']",
        "[class*='leader']",
        "[class*='founder']",
        "[class*='executive']",
        "[class*='bio']",
        "[class*='profile']",
        "[class*='card']",
        "[itemtype*='schema.org/Person']",
    ]

    for selector in team_selectors:
        try:
            cards = soup.select(selector)
        except Exception:
            continue
        for card in cards:
            if not isinstance(card, Tag):
                continue
            card_text = card.get_text(" ", strip=True)
            # Try to find email in this card
            emails_in_card: list[str] = []
            for a in card.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                if href.startswith("mailto:"):
                    em = href[7:].split("?")[0].strip().lower()
                    if EMAIL_RE.match(em) and _is_same_domain(em, base_domain) and not _should_skip_email(em):
                        emails_in_card.append(em)
            # Also regex the card text
            for m in EMAIL_RE.finditer(card_text):
                em = m.group(0).lower()
                if _is_same_domain(em, base_domain) and not _should_skip_email(em) and em not in emails_in_card:
                    emails_in_card.append(em)

            if not emails_in_card:
                continue

            # Try to find name (usually in a heading)
            name = ""
            for tag in ("h2", "h3", "h4", "h5", "strong", "b"):
                el = card.find(tag)
                if el:
                    candidate = el.get_text(strip=True)
                    # Name heuristic: 2-4 words, no numbers, not too long
                    if candidate and len(candidate) < 60 and not re.search(r"\d", candidate):
                        words = candidate.split()
                        if 1 <= len(words) <= 5:
                            name = candidate
                            break

            # Try to find title
            title = ""
            for el in card.find_all(["p", "span", "div"]):
                txt = el.get_text(strip=True)
                if txt and txt != name and len(txt) < 80:
                    # Title heuristics
                    title_keywords = [
                        "ceo", "cto", "cfo", "coo", "vp", "vice president",
                        "director", "head of", "manager", "lead", "chief",
                        "founder", "co-founder", "partner", "engineer",
                        "developer", "designer", "president", "officer",
                    ]
                    if any(kw in txt.lower() for kw in title_keywords):
                        title = txt
                        break

            for em in emails_in_card:
                if em not in seen_emails:
                    seen_emails.add(em)
                    results.append((em, name, title))

    return results


def _extract_linkedin_urls(soup: BeautifulSoup) -> dict[str, str]:
    """Find LinkedIn profile URLs, keyed by profile name if detectable."""
    linkedin: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if "linkedin.com/in/" in href:
            # Normalize
            parsed = urlparse(href)
            path = parsed.path.rstrip("/")
            slug = path.split("/")[-1] if "/" in path else ""
            if slug and len(slug) > 1:
                url = f"https://www.linkedin.com/in/{slug}"
                # Try to get name from link text or parent
                name = (a.get_text(strip=True) or "").strip()
                if name and len(name) < 60 and not name.startswith("http"):
                    linkedin[name] = url
                else:
                    linkedin[slug] = url
    return linkedin


def _extract_emails_from_html(
    html: str, base_domain: str
) -> list[tuple[str, str, str, str]]:
    """
    Parse HTML, extract emails with optional name/title/linkedin.
    Returns list of (email, name, title, linkedin_url).
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    results: list[tuple[str, str, str, str]] = []

    # Get LinkedIn URLs for merging later
    linkedin_map = _extract_linkedin_urls(soup)

    def _add(email: str, name: str, title: str, linkedin: str = ""):
        if email in seen:
            return
        seen.add(email)
        # Try to match LinkedIn by name
        if not linkedin and name:
            linkedin = linkedin_map.get(name, "")
        results.append((email, name, title, linkedin))

    # 1. JSON-LD structured data (highest quality)
    for email, name, title in _extract_json_ld_emails(soup, base_domain):
        _add(email, name, title)

    # 2. Team member cards (structured HTML)
    for email, name, title in _extract_team_members(soup, base_domain):
        _add(email, name, title)

    # 3. mailto: links
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if href.lower().startswith("mailto:"):
            part = href[7:].split("?")[0].strip().split(",")[0].strip()
            if EMAIL_RE.match(part):
                email = part.lower()
                if not _is_same_domain(email, base_domain):
                    continue
                if _should_skip_email(email):
                    continue
                # Try to get name from link text
                name = (a.get_text(strip=True) or "").strip()
                if name and (EMAIL_RE.search(name) or len(name) > 80):
                    name = ""
                _add(email, name, "")

    # 4. Plain emails in text
    text = soup.get_text(" ", strip=True)
    for m in EMAIL_RE.finditer(text):
        email = m.group(0).lower()
        if not _is_same_domain(email, base_domain):
            continue
        if _should_skip_email(email):
            continue
        _add(email, "", "")

    # 5. Obfuscated emails (contact [at] company [dot] com)
    for elem in soup.find_all(string=True):
        s = (elem if isinstance(elem, str) else str(elem)).strip()
        if len(s) < 8 or "@" in s:
            continue
        if re.search(r"\b(at|dot|&#64;|&#x40;|%40)\b", s, re.I):
            for email in _deobfuscate_email(s):
                if _is_same_domain(email, base_domain) and not _should_skip_email(email):
                    _add(email, "", "")

    # 6. Check meta tags
    for meta in soup.find_all("meta"):
        content = (meta.get("content") or "").strip()
        if content and "@" in content:
            for m in EMAIL_RE.finditer(content):
                email = m.group(0).lower()
                if _is_same_domain(email, base_domain) and not _should_skip_email(email):
                    _add(email, "", "")

    return results


# ---------------------------------------------------------------------------
# Sitemap parser
# ---------------------------------------------------------------------------

async def _fetch_sitemap_urls(
    client: httpx.AsyncClient, base_url: str, base_domain: str
) -> list[str]:
    """
    Try to fetch sitemap.xml and extract URLs that likely contain contact info.
    Returns a list of URLs to crawl.
    """
    contact_keywords = [
        "contact", "about", "team", "people", "leadership", "staff",
        "founders", "management", "who-we-are", "our-team", "meet",
        "directory", "bio", "executive",
    ]
    urls: list[str] = []
    sitemap_locations = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap-0.xml",
    ]

    for sitemap_url in sitemap_locations:
        try:
            r = await client.get(sitemap_url, timeout=8.0)
            if r.status_code != 200:
                continue
            ct = (r.headers.get("content-type") or "").lower()
            if "xml" not in ct and "text" not in ct:
                continue
            root = ElementTree.fromstring(r.text)
            # Handle namespace
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", ns):
                url = (loc.text or "").strip()
                if not url:
                    continue
                path_lower = urlparse(url).path.lower()
                if any(kw in path_lower for kw in contact_keywords):
                    urls.append(url)
            # Also try without namespace (some sitemaps don't use it)
            if not urls:
                for loc in root.iter():
                    if loc.tag.endswith("loc") and loc.text:
                        url = loc.text.strip()
                        path_lower = urlparse(url).path.lower()
                        if any(kw in path_lower for kw in contact_keywords):
                            urls.append(url)
            if urls:
                break  # Found sitemap with relevant URLs
        except Exception:
            continue

    return urls[:10]  # Cap at 10 relevant URLs


# ---------------------------------------------------------------------------
# robots.txt → find sitemaps
# ---------------------------------------------------------------------------

async def _find_sitemaps_from_robots(
    client: httpx.AsyncClient, base_url: str
) -> list[str]:
    """Check robots.txt for Sitemap: directives."""
    try:
        r = await client.get(f"{base_url}/robots.txt", timeout=5.0)
        if r.status_code != 200:
            return []
        sitemaps = []
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    sitemaps.append(url)
        return sitemaps[:3]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Fetch helper with retry
# ---------------------------------------------------------------------------

async def _fetch_url(
    client: httpx.AsyncClient, url: str, retries: int = 2
) -> Optional[str]:
    """Fetch a URL with retry logic and random User-Agent."""
    for attempt in range(retries + 1):
        try:
            headers = {"User-Agent": _random_ua()}
            r = await client.get(
                url,
                follow_redirects=True,
                timeout=12.0,
                headers=headers,
            )
            if r.status_code == 200:
                ct = (r.headers.get("content-type") or "").lower()
                if "text/html" in ct or "text/plain" in ct or "xhtml" in ct:
                    return r.text
            elif r.status_code == 403 and attempt < retries:
                # Try with different UA
                await asyncio.sleep(0.5)
                continue
            elif r.status_code == 429:
                # Rate limited, wait and retry
                await asyncio.sleep(2.0)
                continue
            else:
                return None
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            logger.debug("Fetch %s failed after %d attempts: %s", url, retries + 1, e)
            return None
    return None


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_contacts_for_domain(
    domain: str,
    max_results: int = 15,
    max_pages: int = 12,
    delay_seconds: float = 0.5,
) -> list[SuggestedContact]:
    """
    Scrape a company website for contact emails using multiple strategies.
    Returns list of SuggestedContact (email always set; name/title when extractable).

    Strategies:
    1. Check sitemap.xml for contact/team/about pages
    2. Crawl common paths (e.g. /contact, /about, /team)
    3. Extract from mailto: links, JSON-LD, team cards, meta tags
    4. Deobfuscate hidden emails (e.g. "user [at] company [dot] com")
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []

    # Try HTTPS first, fallback to HTTP
    base_urls_to_try = [f"https://{domain}", f"https://www.{domain}"]

    all_contacts: list[tuple[str, str, str, str]] = []  # (email, name, title, linkedin)
    seen_emails: set[str] = set()
    pages_crawled = 0

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        },
    ) as client:
        base_url = base_urls_to_try[0]
        # Quick check: which base URL works?
        for candidate in base_urls_to_try:
            try:
                r = await client.head(candidate, timeout=5.0)
                if r.status_code < 400:
                    base_url = str(r.url).rstrip("/")  # follow redirects
                    break
            except Exception:
                continue

        # Build URL list to crawl
        urls_to_crawl: list[str] = []

        # From sitemap
        sitemap_urls = await _fetch_sitemap_urls(client, base_url, domain)
        urls_to_crawl.extend(sitemap_urls)

        # From common paths
        for path in CONTACT_PATHS:
            url = urljoin(base_url + "/", path.lstrip("/"))
            if url not in urls_to_crawl:
                urls_to_crawl.append(url)

        # Deduplicate and cap
        seen_urls: set[str] = set()
        unique_urls: list[str] = []
        for url in urls_to_crawl:
            normalized = url.rstrip("/").lower()
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                unique_urls.append(url)
        urls_to_crawl = unique_urls[:max_pages]

        # Crawl pages
        for url in urls_to_crawl:
            if pages_crawled > 0:
                await asyncio.sleep(delay_seconds)

            html = await _fetch_url(client, url)
            if not html:
                continue
            pages_crawled += 1

            contacts = _extract_emails_from_html(html, domain)
            for email, name, title, linkedin in contacts:
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                all_contacts.append((email, name, title, linkedin))

            # Early exit if we have enough
            if len(all_contacts) >= max_results:
                break

    # Sort by quality: prioritize emails with names and firstname.lastname pattern
    all_contacts.sort(
        key=lambda x: _email_quality_score(x[0], has_name=bool(x[1])),
        reverse=True,
    )

    # Build output
    out: list[SuggestedContact] = []
    for email, name, title, linkedin in all_contacts[:max_results]:
        if not name:
            # Infer name from email if it looks like firstname.lastname@
            local = email.split("@")[0]
            if "." in local:
                parts = local.split(".")
                name = " ".join(p.capitalize() for p in parts[:2])
            else:
                name = "Sir/Ma'am"
        out.append(
            SuggestedContact(
                name=name,
                email=email,
                title=title or "",
                linkedin_url=linkedin or "",
            )
        )

    if out:
        logger.info(
            "Scraper found %d contacts for %s (crawled %d pages)",
            len(out), domain, pages_crawled,
        )
    else:
        logger.info(
            "Scraper found 0 contacts for %s (crawled %d pages). "
            "Site may use contact forms or hide email addresses.",
            domain, pages_crawled,
        )

    return out
