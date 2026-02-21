"""Ollama API client."""
import httpx
import json
import logging
from pathlib import Path
from typing import Any, Optional

from config import get_settings

logger = logging.getLogger(__name__)

# Prompts dir: repo root = parent of backend/ (file in backend/app/agents -> 4 parents up = repo)
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load prompt from prompts/<name>.txt."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def extract_json(text: str) -> dict[str, Any]:
    """Extract first JSON object from model output. Tolerates markdown, prefix/suffix text."""
    text = text.strip()
    # 1. Try to find content between ```json and ```
    if "```json" in text:
        try:
            content = text.split("```json")[1].split("```")[0].strip()
            return json.loads(content)
        except (json.JSONDecodeError, IndexError):
            pass

    # 2. Try to find content between ``` and ```
    if "```" in text:
        try:
            sections = text.split("```")
            for section in sections:
                s = section.strip()
                if s.startswith("{") and s.endswith("}"):
                    return json.loads(s)
                # If some specific marker was used (e.g. ```markdown)
                if "\n" in s:
                    s_clean = s.split("\n", 1)[1].strip()
                    if s_clean.startswith("{") and s_clean.endswith("}"):
                        return json.loads(s_clean)
        except (json.JSONDecodeError, IndexError):
            pass

    # 3. Last resort: find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # If standard parsing fails, try to find a balanced object
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            pass
    return {}


class OllamaClient:
    """Thin wrapper around Ollama API with prompt loading."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        s = get_settings()
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.model = model or s.ollama_model

    async def generate(
        self,
        system: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
        format_json: bool = False,
    ) -> str:
        """Generate completion. Returns raw string. num_predict increases max output tokens."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"
            
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if num_predict is not None:
            options["num_predict"] = num_predict
        if options:
            payload["options"] = options
            
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message") or {}
        return (msg.get("content") or "").strip()

    async def generate_json(
        self,
        system: str,
        user_message: str,
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
    ) -> dict[str, Any]:
        """Generate and parse first JSON object from response."""
        raw = await self.generate(
            system, user_message, temperature=temperature, num_predict=num_predict, format_json=True
        )
        out = extract_json(raw)
        if not out and raw.strip():
            preview = raw[:200] + "..." if len(raw) > 200 else raw
            logger.warning("Failed to parse JSON from Ollama. Raw preview: %s", preview)
        return out


ollama_client = OllamaClient()
