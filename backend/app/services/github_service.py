"""Fetch GitHub repo data using GITHUB_TOKEN."""
import base64
import logging
from typing import Optional

import httpx
from config import get_settings

from ..models.schemas import ProjectInput

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


async def fetch_repo(owner: str, repo: str) -> Optional[ProjectInput]:
    """
    Fetch repo metadata + README from GitHub. Returns ProjectInput or None on failure.
    Uses GITHUB_TOKEN for higher rate limits and private repo access.
    """
    s = get_settings()
    headers: dict = {"Accept": "application/vnd.github.v3+json"}
    if s.github_token:
        headers["Authorization"] = f"Bearer {s.github_token}"

    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # Repo metadata
        try:
            r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Repo not found: %s/%s", owner, repo)
            else:
                logger.exception("GitHub repo request failed")
            return None
        except Exception:
            logger.exception("GitHub request failed")
            return None

        repo_name = data.get("full_name") or f"{owner}/{repo}"
        description = (data.get("description") or "").strip()
        stars = int(data.get("stargazers_count") or 0)
        forks = int(data.get("forks_count") or 0)

        # Languages
        tech_stack: list[str] = []
        try:
            lang_r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}/languages")
            if lang_r.status_code == 200:
                tech_stack = list((lang_r.json() or {}).keys())
        except Exception:
            pass

        # README (raw preferred; fallback to base64)
        readme = ""
        try:
            readme_r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            if readme_r.status_code == 200:
                readme = (readme_r.text or "")[:12000]
            elif readme_r.status_code == 404:
                pass
            else:
                readme_r_json = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/readme",
                    headers=headers,
                )
                if readme_r_json.status_code == 200:
                    readme_data = readme_r_json.json()
                    content = readme_data.get("content")
                    if content:
                        readme = base64.b64decode(content).decode("utf-8", errors="replace")[:12000]
        except Exception:
            pass

        return ProjectInput(
            repo_name=repo_name,
            description=description,
            readme=readme,
            tech_stack=tech_stack,
            stars=stars,
            forks=forks,
        )


def parse_github_url(url_or_slug: str) -> Optional[tuple[str, str]]:
    """Parse 'owner/repo' or 'https://github.com/owner/repo' into (owner, repo)."""
    s = (url_or_slug or "").strip()
    if not s:
        return None
    if "github.com" in s:
        parts = s.rstrip("/").split("/")
        if len(parts) >= 2:
            return (parts[-2], parts[-1])
        return None
    if "/" in s:
        a, b = s.split("/", 1)
        return (a.strip(), b.strip())
    return None
