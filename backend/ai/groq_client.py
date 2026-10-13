"""Groq API client for meeting analysis inference."""

import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClient:
    """Reusable client for cloud-hosted Groq LLM inference."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self.base_url = (base_url or GROQ_API_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
        configured_tokens = os.getenv("GROQ_MAX_OUTPUT_TOKENS")
        self.max_output_tokens = max_output_tokens or (int(configured_tokens) if configured_tokens else None)
        self.pipeline_name = "groq_application"

    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Call Groq chat completion API requesting structured JSON output."""
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured. Please set the GROQ_API_KEY environment variable "
                "or pass api_key to GroqClient."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        if self.max_output_tokens is not None:
            payload["max_tokens"] = self.max_output_tokens

        started = time.perf_counter()
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=(10, self.timeout_seconds),
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Groq request timed out after %.1fs", self.timeout_seconds)
            raise TimeoutError(f"Groq API request timed out after {self.timeout_seconds} seconds.") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Groq connection failure: %s", exc)
            raise RuntimeError(f"Failed to communicate with Groq API: {exc}") from exc

        if response.status_code == 401:
            raise PermissionError("Groq API authorization failed: Invalid API key provided.")
        if response.status_code == 429:
            raise RuntimeError("Groq API rate limit exceeded. Please retry after a brief delay.")
        if not response.ok:
            error_body = response.text[:300]
            raise RuntimeError(f"Groq API returned HTTP {response.status_code}: {error_body}")

        data = response.json()
        elapsed = time.perf_counter() - started
        logger.info("Groq inference model=%s elapsed_s=%.2f prompt_chars=%d", self.model, elapsed, len(prompt))

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Groq returned empty completion choices.")

        return choices[0].get("message", {}).get("content", "")
