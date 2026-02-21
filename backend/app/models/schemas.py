"""Pydantic schemas for agent outputs and API."""
from pydantic import BaseModel, Field, field_validator
from typing import Any


def _ensure_str_list(v: Any) -> list[str]:
    """Accept list[str] or a single str (comma/semicolon split) from LLM output."""
    if isinstance(v, list):
        return [str(x).strip() for x in v if x]
    if isinstance(v, str):
        if not v.strip():
            return []
        return [s.strip() for s in v.replace(";", ",").split(",") if s.strip()]
    return []


# --- Project Analyzer ---
class ProjectAnalysis(BaseModel):
    project_summary: str = ""
    problem: str = ""
    solution: str = ""
    industries: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    business_value: str = ""
    monetization_score: int = Field(ge=0, le=10, default=0)

    @field_validator("industries", "target_users", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Researcher ---
class CompanyAnalysis(BaseModel):
    company_summary: str = ""
    industry: str = ""
    products: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    growth_stage: str = ""
    budget_estimate: str = ""
    strategic_value: int = Field(ge=0, le=10, default=0)

    @field_validator("products", "pain_points", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Matcher ---
class MatchResult(BaseModel):
    fit_score: int = Field(ge=0, le=100, default=0)
    match_reasoning: str = ""
    recommended_pitch_angle: str = ""
    risk_factors: list[str] = Field(default_factory=list)

    @field_validator("match_reasoning", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> str:
        if isinstance(v, (list, dict)):
            import json
            return json.dumps(v, indent=2)
        return str(v) if v is not None else ""

    @field_validator("risk_factors", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Deck Designer ---
class Slide(BaseModel):
    title: str = ""
    bullet_points: list[str] = Field(default_factory=list)

    @field_validator("bullet_points", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


class PitchDeck(BaseModel):
    title: str = ""
    subtitle: str = ""
    slides: list[Slide] = Field(default_factory=list)


# --- Sender ---
class EmailSendPlan(BaseModel):
    send_time: str = ""
    strategy: str = ""
    include_attachment: bool = False
    daily_limit: int = Field(ge=1, le=100, default=20)
    risk_level: str = "low"  # low | medium | high


# --- Reply Analyzer ---
class ReplyAnalysis(BaseModel):
    category: str = "neutral"  # no_reply|neutral|interested|meeting|reject|deal
    sentiment: str = "neutral"  # positive|neutral|negative
    key_points: list[str] = Field(default_factory=list)
    recommended_action: str = ""

    @field_validator("key_points", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Learner ---
class LearnerOutput(BaseModel):
    updated_preferences: dict = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)
    strategy_changes: list[str] = Field(default_factory=list)

    @field_validator("insights", "strategy_changes", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Manager ---
class ManagerOutput(BaseModel):
    next_tasks: list[str] = Field(default_factory=list)
    priority_level: str = ""
    risk_alerts: list[str] = Field(default_factory=list)
    optimization_goals: list[str] = Field(default_factory=list)

    @field_validator("next_tasks", "risk_alerts", "optimization_goals", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- Company suggester + lead enrichment ---
class SuggestedContact(BaseModel):
    name: str = ""
    email: str = ""
    title: str = ""
    linkedin_url: str = ""  # optional; set when source is Apollo or similar


class SuggestedCompany(BaseModel):
    company_name: str = ""
    company_description: str = ""
    company_domain: str = ""  # e.g. stripe.com — used to fetch contacts when HUNTER_API_KEY is set
    why_fit: str = ""
    recommended_roles: list[str] = Field(default_factory=list)
    contacts: list["SuggestedContact"] = Field(default_factory=list)  # filled by lead enrichment
    personalized_email: str = ""  # AI generated pitch for this specific company

    @field_validator("recommended_roles", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str]:
        return _ensure_str_list(v)


# --- API inputs ---
class ProjectInput(BaseModel):
    repo_name: str
    description: str = ""
    readme: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0


class CompanyInput(BaseModel):
    name: str
    website: str = ""
    news: str = ""
    product_info: str = ""
    funding_info: str = ""
    job_postings: str = ""


# --- Reward model ---
REWARD_VALUES = {
    "no_reply": 0,
    "opened": 1,
    "reply": 3,
    "interested": 7,
    "meeting": 10,
    "deal": 20,
}
