import os
import time
import logging

import requests


logger = logging.getLogger(__name__)


class OllamaClient:
    """Reusable client for local Ollama LLM inference."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        base_url: str = "http://localhost:11434",
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
        configured_tokens = os.getenv("OLLAMA_MAX_OUTPUT_TOKENS")
        self.max_output_tokens = max_output_tokens or (int(configured_tokens) if configured_tokens else None)
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
    ) -> str:
        options = {
            "temperature": temperature,
        }
        if self.max_output_tokens is not None:
            options["num_predict"] = self.max_output_tokens

        started = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "keep_alive": self.keep_alive,
                "options": options,
            },
            timeout=(10, self.timeout_seconds),
        )

        response.raise_for_status()

        data = response.json()

        elapsed = time.perf_counter() - started
        logger.info("Ollama inference model=%s elapsed_s=%.2f prompt_chars=%d", self.model, elapsed, len(prompt))
        return data.get("response", "")
