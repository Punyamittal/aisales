"""ATS scoring engine for resume vs job description."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "you", "your", "are", "our", "will",
    "have", "has", "had", "not", "but", "all", "any", "job", "role", "work", "team", "years",
    "year", "plus", "can", "able", "into", "about", "their", "they", "them", "its", "his", "her",
}

STRONG_ACTION_VERBS = {
    "built", "implemented", "designed", "optimized", "led", "developed", "architected", "reduced",
    "improved", "scaled", "deployed", "automated", "delivered", "migrated", "launched", "increased",
    "boosted", "accelerated", "streamlined", "engineered", "created", "drove", "owned", "refactored",
}

WEAK_PHRASES = {
    "responsible for", "worked on", "helped with", "involved in", "participated in",
}

SECTION_PATTERNS = {
    "summary": r"\b(summary|profile|objective)\b",
    "skills": r"\b(skills|technical skills|core skills|technologies)\b",
    "experience": r"\b(experience|work experience|employment)\b",
    "projects": r"\b(projects|project experience)\b",
    "education": r"\b(education|academic)\b",
}

SYNONYMS = {
    "nodejs": "node.js",
    "node js": "node.js",
    "postgres": "postgresql",
    "js": "javascript",
    "ts": "typescript",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "k8s": "kubernetes",
}

SKILL_TOKENS = {
    "python", "java", "javascript", "typescript", "react", "next.js", "node.js", "fastapi",
    "django", "flask", "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes",
    "aws", "gcp", "azure", "git", "linux", "ci/cd", "graphql", "rest", "machine learning",
    "scikit-learn", "pandas", "numpy", "tensorflow", "pytorch",
}


@dataclass
class ScoreResult:
    score: int
    breakdown: dict
    suggestions: list[str]
    diagnostics: dict


def _normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    return t


def _tokenize(text: str) -> list[str]:
    parts = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#/-]{1,}", text.lower())
    return [SYNONYMS.get(p, p) for p in parts]


def _extract_keywords_from_jd(jd: str) -> tuple[set[str], set[str]]:
    tokens = _tokenize(jd)
    freq = Counter(t for t in tokens if t not in STOPWORDS and len(t) > 2)
    top_terms = [t for t, _ in freq.most_common(80)]

    required = set()
    nice = set()
    lines = [ln.strip() for ln in jd.split("\n") if ln.strip()]
    for ln in lines:
        l = ln.lower()
        line_tokens = [t for t in _tokenize(l) if t in top_terms or t in SKILL_TOKENS]
        if any(x in l for x in ["must", "required", "requirement", "need", "minimum", "mandatory"]):
            required.update(line_tokens)
        elif any(x in l for x in ["preferred", "plus", "good to have", "nice to have"]):
            nice.update(line_tokens)

    if not required:
        required = set(top_terms[:20])
    if not nice:
        nice = set(top_terms[20:40])

    # keep meaningful tokens only
    required = {x for x in required if x not in STOPWORDS and len(x) > 2}
    nice = {x for x in nice if x not in STOPWORDS and len(x) > 2 and x not in required}
    return required, nice


def _extract_skills(text: str) -> set[str]:
    t = _normalize_text(text)
    found: set[str] = set()
    for skill in SKILL_TOKENS:
        if skill in t:
            found.add(skill)
    for raw, canon in SYNONYMS.items():
        if raw in t and canon in SKILL_TOKENS:
            found.add(canon)
    return found


def _section_completeness(resume_text: str) -> tuple[float, dict]:
    txt = _normalize_text(resume_text)
    section_hits = {k: bool(re.search(p, txt)) for k, p in SECTION_PATTERNS.items()}
    presence = (sum(section_hits.values()) / len(section_hits)) * 100.0

    bullets = [ln for ln in resume_text.split("\n") if ln.strip().startswith(("-", "*", "•"))]
    has_bullets = bool(bullets)
    has_email = bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", resume_text))
    has_dates = bool(re.search(r"\b(20\d{2}|19\d{2})\b", resume_text))

    quality_checks = [has_bullets, has_email, has_dates]
    quality = (sum(1 for x in quality_checks if x) / len(quality_checks)) * 100.0

    score = (0.7 * presence) + (0.3 * quality)
    diag = {
        "section_hits": section_hits,
        "has_bullets": has_bullets,
        "has_email": has_email,
        "has_dates": has_dates,
    }
    return score, diag


def _readability_score(resume_text: str) -> tuple[float, dict]:
    lines = [ln.strip() for ln in resume_text.split("\n") if ln.strip()]
    bullets = [ln for ln in lines if ln.startswith(("-", "*", "•"))]
    bullet_words = [len(_tokenize(b)) for b in bullets] or [0]

    ideal = [1 for c in bullet_words if 12 <= c <= 28]
    too_long = [1 for c in bullet_words if c > 35]
    avg_len = sum(bullet_words) / max(1, len(bullet_words))

    good_ratio = len(ideal) / max(1, len(bullet_words))
    long_penalty = (len(too_long) / max(1, len(bullet_words))) * 30.0

    weird_chars = len(re.findall(r"[^\w\s.,:%@+\-/*()#&]", resume_text))
    weird_penalty = min(20.0, weird_chars / 60.0)

    score = max(0.0, min(100.0, (good_ratio * 100.0) - long_penalty - weird_penalty))
    diag = {
        "avg_bullet_words": round(avg_len, 2),
        "good_bullet_ratio": round(good_ratio, 3),
        "long_bullet_count": len(too_long),
    }
    return score, diag


def _action_verb_score(resume_text: str) -> tuple[float, dict]:
    bullets = [ln.strip().lower() for ln in resume_text.split("\n") if ln.strip().startswith(("-", "*", "•"))]
    if not bullets:
        return 0.0, {"verb_ratio": 0.0, "quantified_ratio": 0.0, "weak_phrase_count": 0}

    starts_strong = 0
    quantified = 0
    weak = 0
    for b in bullets:
        first_word = re.sub(r"^[-*•]\s*", "", b).split(" ")[0]
        if first_word in STRONG_ACTION_VERBS:
            starts_strong += 1
        if re.search(r"\b\d+%|\b\d+\+|\b\d+x|\b\d{2,}\b", b):
            quantified += 1
        if any(p in b for p in WEAK_PHRASES):
            weak += 1

    verb_ratio = starts_strong / len(bullets)
    quantified_ratio = quantified / len(bullets)
    weak_ratio = weak / len(bullets)

    score = (verb_ratio * 50.0) + (quantified_ratio * 40.0) + ((1.0 - weak_ratio) * 10.0)
    diag = {
        "verb_ratio": round(verb_ratio, 3),
        "quantified_ratio": round(quantified_ratio, 3),
        "weak_phrase_count": weak,
        "bullet_count": len(bullets),
    }
    return min(100.0, score), diag


def _keyword_and_skill_scores(resume_text: str, jd_text: str) -> tuple[float, float, dict]:
    required, nice = _extract_keywords_from_jd(jd_text)
    resume_tokens = Counter(_tokenize(resume_text))
    resume_set = set(resume_tokens.keys())

    req_matches = {t for t in required if t in resume_set}
    nice_matches = {t for t in nice if t in resume_set}

    req_total = max(1, len(required))
    nice_total = max(1, len(nice))

    stuffing_penalty = 0.0
    for term in req_matches.union(nice_matches):
        if resume_tokens[term] > 8:
            stuffing_penalty += min(3.0, (resume_tokens[term] - 8) * 0.4)

    keyword_score = ((2 * len(req_matches)) + len(nice_matches)) / ((2 * req_total) + nice_total) * 100.0
    keyword_score = max(0.0, min(100.0, keyword_score - stuffing_penalty))

    jd_skills = _extract_skills(jd_text)
    resume_skills = _extract_skills(resume_text)
    required_skill_matches = jd_skills.intersection(resume_skills)
    coverage = (len(required_skill_matches) / max(1, len(jd_skills))) * 100.0

    context_lines = [ln.lower() for ln in resume_text.split("\n") if ln.strip().startswith(("-", "*", "•"))]
    context_hits = 0
    for sk in required_skill_matches:
        if any(sk in ln and any(v in ln for v in STRONG_ACTION_VERBS) for ln in context_lines):
            context_hits += 1
    depth = (context_hits / max(1, len(required_skill_matches))) * 100.0
    skill_score = (0.6 * coverage) + (0.4 * depth)

    diag = {
        "required_keywords_total": len(required),
        "required_keywords_matched": sorted(req_matches),
        "missing_required_keywords": sorted(required - req_matches),
        "nice_keywords_matched_count": len(nice_matches),
        "jd_skills": sorted(jd_skills),
        "matched_skills": sorted(required_skill_matches),
        "missing_skills": sorted(jd_skills - required_skill_matches),
    }
    return keyword_score, skill_score, diag


def score_ats(resume_text: str, job_description: str) -> dict:
    resume = _normalize_text(resume_text)
    jd = _normalize_text(job_description)

    keyword_score, skill_score, ks_diag = _keyword_and_skill_scores(resume, jd)
    completeness_score, completeness_diag = _section_completeness(resume_text)
    readability, readability_diag = _readability_score(resume_text)
    action_score, action_diag = _action_verb_score(resume_text)

    final = (
        (0.30 * keyword_score)
        + (0.25 * skill_score)
        + (0.15 * completeness_score)
        + (0.15 * readability)
        + (0.15 * action_score)
    )
    final_int = int(round(max(0.0, min(100.0, final))))

    suggestions: list[str] = []
    missing_keywords = ks_diag["missing_required_keywords"][:8]
    if keyword_score < 70 and missing_keywords:
        suggestions.append(
            "Add missing required keywords in context: " + ", ".join(missing_keywords) + "."
        )
    missing_skills = ks_diag["missing_skills"][:6]
    if skill_score < 70 and missing_skills:
        suggestions.append(
            "Strengthen skill alignment with project bullets mentioning: " + ", ".join(missing_skills) + "."
        )
    if completeness_score < 80:
        suggestions.append("Ensure core sections exist: Summary, Skills, Experience, Projects, Education, and valid contact info.")
    if readability < 75:
        suggestions.append("Shorten long bullets (target 12-28 words) and reduce noisy formatting/symbols.")
    if action_score < 75:
        suggestions.append("Start bullets with strong action verbs and quantify impact (%, x, counts, latency, users).")
    if not suggestions:
        suggestions.append("Good ATS alignment. For further gains, add more quantified outcomes in recent experience bullets.")

    return {
        "score": final_int,
        "breakdown": {
            "keyword_match": round(keyword_score, 2),
            "skill_alignment": round(skill_score, 2),
            "section_completeness": round(completeness_score, 2),
            "readability": round(readability, 2),
            "action_verbs_usage": round(action_score, 2),
        },
        "diagnostics": {
            **ks_diag,
            **completeness_diag,
            **readability_diag,
            **action_diag,
        },
        "suggestions": suggestions,
    }

