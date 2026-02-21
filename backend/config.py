"""Application configuration."""
import os
import re
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache


def _env_file_paths() -> list[str]:
    """Load .env from backend/ first, then project root, so keys in root .env are used when running from backend/."""
    backend_dir = Path(__file__).resolve().parent
    root_dir = backend_dir.parent
    paths = []
    for d in (backend_dir, root_dir):
        p = d / ".env"
        if p.is_file():
            paths.append(str(p))
    return paths if paths else [".env"]


class Settings(BaseSettings):
    """Load from environment."""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    email_from: str = "outreach@example.com"
    email_from_name: str = "AI Sales"
    # SMTP (e.g. Gmail): use when RESEND_API_KEY is not set
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""  # e.g. your@gmail.com
    smtp_password: str = ""  # Gmail app password (spaces are stripped)
    api_secret_key: str = "dev-secret"
    environment: str = "development"
    github_token: str = ""
    hunter_api_key: str = ""  # Hunter.io — fetch contact emails by company domain
    apollo_api_key: str = ""  # Apollo.io — find people by company + title (optional)

    model_config = {
        "env_file": _env_file_paths(),
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def use_appolo_typo(self):
        """Accept common typo APPOLO_API_KEY if APOLLO_API_KEY is not set."""
        if not self.apollo_api_key and os.environ.get("APPOLO_API_KEY"):
            object.__setattr__(self, "apollo_api_key", os.environ.get("APPOLO_API_KEY", ""))
        return self

    @model_validator(mode="after")
    def fallback_hunter_from_env(self):
        """Ensure HUNTER_API_KEY is read from os.environ if still empty (e.g. .env at project root)."""
        if not (self.hunter_api_key and self.hunter_api_key.strip()) and os.environ.get("HUNTER_API_KEY"):
            object.__setattr__(self, "hunter_api_key", (os.environ.get("HUNTER_API_KEY") or "").strip())
        return self

    @model_validator(mode="after")
    def use_mail_and_app_password(self):
        """Accept MAIL and APP_PASSWORD for SMTP (e.g. Gmail)."""
        if not self.smtp_user and os.environ.get("MAIL"):
            object.__setattr__(self, "smtp_user", os.environ.get("MAIL", ""))
        if not self.smtp_password and os.environ.get("APP_PASSWORD"):
            # Aggressively clean: remove spaces, hyphens, and quotes
            raw_pass = os.environ.get("APP_PASSWORD", "")
            clean_pass = re.sub(r"[\s\-\'\"]", "", raw_pass)
            object.__setattr__(self, "smtp_password", clean_pass)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
