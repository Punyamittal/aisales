"""End-to-end job application pipeline orchestration."""
from __future__ import annotations

import asyncio
import json
import math
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from app.db.supabase_client import get_supabase
from config import get_settings

SECTION_HEADINGS = ("summary", "experience", "projects", "skills", "education")
STOPWORDS = {
    "and",
    "the",
    "with",
    "for",
    "from",
    "that",
    "this",
    "your",
    "you",
    "our",
    "are",
    "will",
    "have",
    "has",
    "about",
    "into",
    "their",
    "its",
}

EMBEDDING_DIM = 64
_MEMORY_VECTOR_DB: dict[str, list[dict[str, Any]]] = {"jobs": [], "resumes": []}


def _normalize_tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\+\#\-]{1,}", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def _embed_text_local(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """
    Lightweight deterministic embedding fallback.
    This keeps RAG functional even without external embedding providers.
    """
    vec = [0.0] * dim
    for token in _normalize_tokens(text):
        idx = hash(token) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


async def _embed_text(text: str) -> list[float]:
    """
    Local-first embedding providers:
    1) Ollama embeddings API if available (local model)
    2) Deterministic local embedding fallback
    """
    s = get_settings()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{s.ollama_base_url.rstrip('/')}/api/embeddings",
                json={"model": s.ollama_model, "prompt": text[:8000]},
            )
            if resp.status_code == 200:
                emb = resp.json().get("embedding")
                if isinstance(emb, list) and emb:
                    return [float(v) for v in emb]
    except Exception:
        pass

    return _embed_text_local(text)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    num = sum(a[i] * b[i] for i in range(length))
    denom_a = math.sqrt(sum(a[i] * a[i] for i in range(length))) or 1.0
    denom_b = math.sqrt(sum(b[i] * b[i] for i in range(length))) or 1.0
    return num / (denom_a * denom_b)


def _upsert_vector_memory(collection: str, item_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
    bucket = _MEMORY_VECTOR_DB.setdefault(collection, [])
    bucket[:] = [row for row in bucket if row["id"] != item_id]
    bucket.append({"id": item_id, "vector": vector, "metadata": metadata})


async def _upsert_vector_store(collection: str, item_id: str, vector: list[float], metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Store vectors in Supabase table `rag_vectors` when present; always keep memory fallback.
    """
    _upsert_vector_memory(collection, item_id, vector, metadata)
    supabase = get_supabase()
    if not supabase:
        return {"storage": "memory", "stored": True}

    try:
        payload = {
            "collection": collection,
            "item_id": item_id,
            "embedding": vector,
            "metadata": metadata,
        }
        supabase.table("rag_vectors").upsert(payload).execute()
        return {"storage": "supabase", "stored": True}
    except Exception as exc:
        return {"storage": "memory", "stored": True, "warning": f"supabase_upsert_failed: {exc}"}


async def _query_vector_store(collection: str, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """
    Query vectors from memory fallback first for speed; intended to be replaced by pgvector RPC.
    """
    bucket = _MEMORY_VECTOR_DB.get(collection, [])
    scored = [
        {
            **row,
            "score": round(_cosine_similarity(query_vector, row["vector"]), 6),
        }
        for row in bucket
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, top_k)]


def _escape_latex(value: str) -> str:
    escape_map = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(escape_map.get(ch, ch) for ch in value)


def _latex_resume_template() -> str:
    return r"""
\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{enumitem}
\setlist[itemize]{topsep=2pt,itemsep=2pt,leftmargin=16pt}
\begin{document}
\begin{center}
{\LARGE \textbf{%%CANDIDATE_NAME%%}}\\
\vspace{4pt}
LinkedIn: %%LINKEDIN%% \quad | \quad GitHub: %%GITHUB%%\\
\vspace{6pt}
\end{center}

\section*{Target Role}
%%TARGET_ROLE%%

\section*{Professional Summary}
%%SUMMARY%%

\section*{Core Skills}
\begin{itemize}
%%SKILLS_BULLETS%%
\end{itemize}

\section*{Relevant Experience}
\begin{itemize}
%%EXPERIENCE_BULLETS%%
\end{itemize}

\section*{Selected Projects}
\begin{itemize}
%%PROJECT_BULLETS%%
\end{itemize}
\end{document}
""".strip()


def _mock_job_listings(role: str, company: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "job-001",
            "title": f"Senior {role}",
            "company": company,
            "description": (
                "Looking for engineers with Python, FastAPI, SQL, API integration, "
                "automation, async programming, and cloud deployment experience. "
                "Must collaborate with product and write maintainable code."
            ),
            "location": "Remote",
            "source": "mock",
        },
        {
            "id": "job-002",
            "title": f"{role} - AI Platforms",
            "company": company,
            "description": (
                "Build AI products using LLM orchestration, prompt engineering, "
                "TypeScript, Next.js, analytics, and A/B testing. Experience with "
                "MLOps and model evaluation is a plus."
            ),
            "location": "Hybrid",
            "source": "mock",
        },
        {
            "id": "job-003",
            "title": f"Backend {role}",
            "company": company,
            "description": (
                "Own backend services in Python, design REST APIs, optimize Postgres "
                "queries, and maintain CI/CD pipelines. Strong debugging and testing "
                "skills required."
            ),
            "location": "Onsite",
            "source": "mock",
        },
    ]


async def index_jobs_for_rag(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    indexed = 0
    for job in jobs:
        text = f"{job.get('title', '')}\n{job.get('description', '')}\n{job.get('location', '')}"
        emb = await _embed_text(text)
        result = await _upsert_vector_store(
            collection="jobs",
            item_id=str(job.get("id") or f"job-{indexed}"),
            vector=emb,
            metadata=job,
        )
        indexed += 1 if result.get("stored") else 0
    return {"indexed": indexed, "collection": "jobs"}


async def index_resume_for_rag(resume_id: str, resume_text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    emb = await _embed_text(resume_text)
    result = await _upsert_vector_store(
        collection="resumes",
        item_id=resume_id,
        vector=emb,
        metadata=metadata or {},
    )
    return {"resume_id": resume_id, "result": result}


async def retrieve_top_matching_jobs(candidate_text: str, top_k: int = 3) -> list[dict[str, Any]]:
    query_vector = await _embed_text(candidate_text)
    hits = await _query_vector_store(collection="jobs", query_vector=query_vector, top_k=top_k)
    return [
        {
            "job_id": hit["id"],
            "score": hit["score"],
            "job": hit.get("metadata", {}),
        }
        for hit in hits
    ]


def _score_job_match(role: str, candidate_text: str, job_description: str) -> dict[str, Any]:
    role_tokens = set(_normalize_tokens(role))
    candidate_tokens = set(_normalize_tokens(candidate_text))
    jd_tokens = set(_normalize_tokens(job_description))

    role_overlap = sorted(role_tokens.intersection(jd_tokens))
    skill_overlap = sorted(candidate_tokens.intersection(jd_tokens))
    missing = sorted(jd_tokens.difference(candidate_tokens))

    role_score = min(25, len(role_overlap) * 8)
    skill_score = min(60, len(skill_overlap) * 3)
    coverage_score = min(15, int((len(skill_overlap) / max(1, len(jd_tokens))) * 100))
    total_score = min(100, role_score + skill_score + coverage_score)

    return {
        "score": total_score,
        "role_overlap": role_overlap,
        "skill_overlap": skill_overlap,
        "missing_keywords": missing[:15],
    }


def _extract_required_skills(job_description: str) -> list[str]:
    tokens = _normalize_tokens(job_description)
    freq = Counter(tokens)
    ranked = [token for token, _ in freq.most_common(20)]
    return _unique(ranked[:12])


def _parse_candidate_profile(role: str, company: str, links: dict[str, str]) -> dict[str, Any]:
    linkedin = (links.get("linkedin") or "").strip()
    github = (links.get("github") or "").strip()
    github_user = github.rstrip("/").split("/")[-1] if github else "candidate"
    candidate_name = github_user.replace("-", " ").replace("_", " ").title()

    raw_profile = (
        f"Applying for {role} at {company}. LinkedIn: {linkedin}. GitHub: {github}. "
        "Experience: Python, FastAPI, SQL, APIs, automation, testing, and cloud basics. "
        "Projects: AI outreach automation and backend orchestration."
    )
    tokens = _normalize_tokens(raw_profile)
    return {
        "candidate_name": candidate_name or "Candidate",
        "linkedin": linkedin,
        "github": github,
        "raw_text": raw_profile,
        "tokens": tokens,
        "skills": _unique(tokens)[:20],
    }


def _generate_resume_content(
    role: str,
    company: str,
    candidate_profile: dict[str, Any],
    required_skills: list[str],
    matched_job: dict[str, Any],
    rag_context: str = "",
) -> dict[str, Any]:
    candidate_skills = set(candidate_profile.get("skills", []))
    aligned = [s for s in required_skills if s in candidate_skills]
    gaps = [s for s in required_skills if s not in candidate_skills]

    summary = (
        f"Backend-focused engineer targeting {role} at {company}, with production "
        "experience delivering API-driven systems, automation workflows, and maintainable services."
    )
    if rag_context:
        summary += f" Context focus: {rag_context[:180]}"
    experience_bullets = [
        "Built and maintained Python/FastAPI services with async workflows and observability.",
        "Integrated third-party APIs and automated outreach/data pipelines to reduce manual work.",
        "Improved reliability with defensive error handling, structured logging, and tests.",
    ]
    project_bullets = [
        "AI sales orchestration platform: transformed GitHub project data into lead intelligence and outreach.",
        "Automated resume tailoring workflow with job matching, ATS scoring, and PDF generation.",
    ]
    skills = _unique((aligned + candidate_profile.get("skills", [])))[:14]

    return {
        "target_role": role,
        "summary": summary,
        "experience_bullets": experience_bullets,
        "project_bullets": project_bullets,
        "skills": skills,
        "alignment": {
            "matched_skills": aligned,
            "missing_skills": gaps[:10],
            "job_title": matched_job.get("title", ""),
        },
    }


def _fill_latex_template(candidate_profile: dict[str, Any], resume_content: dict[str, Any]) -> str:
    template = _latex_resume_template()
    skills_bullets = "\n".join(
        [r"\item " + _escape_latex(skill) for skill in resume_content.get("skills", [])]
    )
    exp_bullets = "\n".join(
        [r"\item " + _escape_latex(item) for item in resume_content.get("experience_bullets", [])]
    )
    proj_bullets = "\n".join(
        [r"\item " + _escape_latex(item) for item in resume_content.get("project_bullets", [])]
    )

    filled = (
        template.replace("%%CANDIDATE_NAME%%", _escape_latex(candidate_profile.get("candidate_name", "Candidate")))
        .replace("%%LINKEDIN%%", _escape_latex(candidate_profile.get("linkedin", "")))
        .replace("%%GITHUB%%", _escape_latex(candidate_profile.get("github", "")))
        .replace("%%TARGET_ROLE%%", _escape_latex(resume_content.get("target_role", "")))
        .replace("%%SUMMARY%%", _escape_latex(resume_content.get("summary", "")))
        .replace("%%SKILLS_BULLETS%%", skills_bullets or r"\item N/A")
        .replace("%%EXPERIENCE_BULLETS%%", exp_bullets or r"\item N/A")
        .replace("%%PROJECT_BULLETS%%", proj_bullets or r"\item N/A")
    )
    return filled


async def _compile_latex_to_pdf(latex_content: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="resume_build_") as tmpdir:
        tmp_path = Path(tmpdir)
        tex_path = tmp_path / "resume.tex"
        pdf_path = tmp_path / "resume.pdf"
        tex_path.write_text(latex_content, encoding="utf-8")

        try:
            process = await asyncio.create_subprocess_exec(
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "resume.tex",
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return {
                "compiled": False,
                "pdf_path": "",
                "message": "pdflatex not found on system; LaTeX generated successfully.",
            }

        stdout, stderr = await process.communicate()
        if process.returncode != 0 or not pdf_path.exists():
            logs = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
            return {
                "compiled": False,
                "pdf_path": "",
                "message": f"PDF compilation failed: {logs[:500]}",
            }

        target_dir = Path(__file__).resolve().parents[2] / "artifacts"
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / "tailored_resume.pdf"
        output_path.write_bytes(pdf_path.read_bytes())
        return {"compiled": True, "pdf_path": str(output_path), "message": "PDF compiled successfully."}


def _run_ats_scoring(resume_content: dict[str, Any], job_description: str) -> dict[str, Any]:
    jd_tokens = _normalize_tokens(job_description)
    resume_text = " ".join(
        [
            resume_content.get("summary", ""),
            " ".join(resume_content.get("skills", [])),
            " ".join(resume_content.get("experience_bullets", [])),
            " ".join(resume_content.get("project_bullets", [])),
        ]
    )
    resume_tokens = _normalize_tokens(resume_text)
    if not jd_tokens:
        return {
            "ats_score": 0,
            "keyword_density": 0,
            "section_score": 0,
            "matched_keywords": [],
            "missing_keywords": [],
        }

    jd_set = set(jd_tokens)
    resume_set = set(resume_tokens)
    matched = sorted(jd_set.intersection(resume_set))
    missing = sorted(jd_set.difference(resume_set))
    keyword_density = int((len(matched) / max(1, len(jd_set))) * 100)

    section_presence = {
        "summary": bool(resume_content.get("summary")),
        "experience": bool(resume_content.get("experience_bullets")),
        "projects": bool(resume_content.get("project_bullets")),
        "skills": bool(resume_content.get("skills")),
        "education": bool(resume_content.get("education")),
    }
    sections_present = sum(1 for key in SECTION_HEADINGS if section_presence.get(key, False))
    section_score = int((sections_present / len(SECTION_HEADINGS)) * 100)

    ats_score = int((keyword_density * 0.7) + (section_score * 0.3))
    return {
        "ats_score": min(100, ats_score),
        "keyword_density": keyword_density,
        "section_score": section_score,
        "matched_keywords": matched[:25],
        "missing_keywords": missing[:25],
    }


async def run_job_application_pipeline(role: str, company: str, links: dict[str, str]) -> dict[str, Any]:
    """Run first working pipeline for job-tailored resume generation."""
    jobs = _mock_job_listings(role=role, company=company)
    candidate_profile = _parse_candidate_profile(role=role, company=company, links=links)
    candidate_text = candidate_profile.get("raw_text", "")

    await index_jobs_for_rag(jobs)

    scored_jobs: list[dict[str, Any]] = []
    for job in jobs:
        match = _score_job_match(role=role, candidate_text=candidate_text, job_description=job["description"])
        scored_jobs.append({**job, "match": match})

    rag_hits = await retrieve_top_matching_jobs(candidate_text=candidate_text, top_k=3)
    rag_top_job = rag_hits[0]["job"] if rag_hits else {}
    best_job = rag_top_job or (max(scored_jobs, key=lambda x: x["match"]["score"]) if scored_jobs else {})
    required_skills = _extract_required_skills(best_job.get("description", ""))
    rag_context = f"Top semantic matches: {[hit.get('job', {}).get('title', '') for hit in rag_hits]}"
    resume_content = _generate_resume_content(
        role=role,
        company=company,
        candidate_profile=candidate_profile,
        required_skills=required_skills,
        matched_job=best_job,
        rag_context=rag_context,
    )
    await index_resume_for_rag(
        resume_id=f"resume-{role.lower().replace(' ', '-')}-{company.lower().replace(' ', '-')}",
        resume_text=json.dumps(resume_content),
        metadata={"role": role, "company": company, "best_job_id": best_job.get("id", "")},
    )
    latex_content = _fill_latex_template(candidate_profile=candidate_profile, resume_content=resume_content)
    compile_result = await _compile_latex_to_pdf(latex_content=latex_content)
    ats = _run_ats_scoring(resume_content=resume_content, job_description=best_job.get("description", ""))

    return {
        "input": {"role": role, "company": company, "links": links},
        "jobs_fetched": jobs,
        "retrieved_jobs": rag_hits,
        "best_job": best_job,
        "required_skills": required_skills,
        "candidate_profile": {
            "candidate_name": candidate_profile["candidate_name"],
            "linkedin": candidate_profile["linkedin"],
            "github": candidate_profile["github"],
            "skills": candidate_profile["skills"],
        },
        "resume_content": resume_content,
        "latex_preview": latex_content[:1200],
        "pdf_result": compile_result,
        "ats_scoring": ats,
    }


def sample_pipeline_input() -> dict[str, Any]:
    return {
        "role": "Software Engineer",
        "company": "Acme AI",
        "links": {
            "linkedin": "https://linkedin.com/in/sample-candidate",
            "github": "https://github.com/sample-candidate",
        },
    }


def sample_pipeline_output() -> dict[str, Any]:
    sample = {
        "input": sample_pipeline_input(),
        "best_job": {"id": "job-001", "title": "Senior Software Engineer"},
        "required_skills": ["python", "fastapi", "sql", "automation", "apis"],
        "resume_content": {
            "target_role": "Software Engineer",
            "summary": "Backend-focused engineer targeting Software Engineer at Acme AI.",
            "skills": ["python", "fastapi", "sql", "automation", "apis"],
        },
        "pdf_result": {"compiled": False, "pdf_path": "", "message": "pdflatex not found on system; LaTeX generated successfully."},
        "ats_scoring": {"ats_score": 78, "keyword_density": 74, "section_score": 86},
    }
    return json.loads(json.dumps(sample))


def rag_architecture_overview() -> dict[str, Any]:
    return {
        "architecture": {
            "services": [
                "profile-service",
                "job-service",
                "resume-service",
                "ats-service",
                "employee-service",
                "email-service",
                "pipeline-orchestrator",
                "rag-index-layer",
            ],
            "components": [
                "embedding provider (OpenAI/Ollama/local fallback)",
                "vector store (Supabase pgvector via rag_vectors table or in-memory fallback)",
                "semantic retriever",
                "resume tailoring generator",
            ],
        },
        "flow_diagram": [
            "candidate profile/resume -> embeddings -> vector index",
            "job descriptions -> embeddings -> vector index",
            "query candidate embedding -> retrieve top matching jobs",
            "build RAG context from top jobs + candidate strengths",
            "generate tailored resume -> ATS analyze -> outreach",
        ],
        "tech_stack": {
            "local_models": {
                "usage": "Ollama /api/embeddings for private-local embedding generation",
                "fallback": "deterministic local token embedding for offline mode",
            },
            "vector_db": {
                "primary": "Supabase Postgres + pgvector (rag_vectors)",
                "fallback": "in-memory vector index for development",
            },
        },
    }
