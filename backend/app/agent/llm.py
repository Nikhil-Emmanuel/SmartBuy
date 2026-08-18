"""LLM provider abstraction.

The whole system is designed so this layer can fail without breaking the
product. Every call returns validated JSON or raises LLMUnavailable, and every
caller has a deterministic fallback. Revoking the API key must still produce a
complete shopping plan -- that is a tested requirement, not an aspiration.

Owner: Member 5 (Agentic AI).
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.core.errors import LLMUnavailable

log = logging.getLogger("smartbuy.llm")

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of a model response.

    Models wrap JSON in fences or add a sentence of preamble even when asked
    not to. Being liberal here is cheaper than a retry.
    """
    if not text or not text.strip():
        raise ValueError("empty response")

    candidate = text.strip()
    fenced = _JSON_BLOCK.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"no JSON object found in response: {text[:160]!r}") from None
        parsed = json.loads(candidate[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate_json(self, system: str, user: str, max_output_tokens: int = 1024) -> dict:
        ...

    @property
    def available(self) -> bool:
        return False


class NullProvider(LLMProvider):
    """Used when no API key is configured. Fails fast and predictably so the
    orchestrator takes its deterministic path."""

    name = "null"

    def generate_json(self, system: str, user: str, max_output_tokens: int = 1024) -> dict:
        raise LLMUnavailable("No LLM provider is configured.")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.GEMINI_MODEL
        self._client = None
        self._types = None
        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self._types = types
        except Exception:
            log.exception("Gemini client could not be initialised")
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_json(self, system: str, user: str, max_output_tokens: int = 1024) -> dict:
        if not self.available:
            raise LLMUnavailable("Gemini client is not initialised.")

        attempts = max(1, settings.LLM_MAX_RETRIES + 1)
        last_error: Exception | None = None

        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                config = self._types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=settings.LLM_TEMPERATURE,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                )
                response = self._client.models.generate_content(
                    model=self.model, contents=user, config=config
                )
                elapsed = (time.perf_counter() - started) * 1000
                payload = extract_json(response.text or "")
                log.debug("Gemini ok in %.0fms (attempt %d)", elapsed, attempt + 1)
                return payload
            except Exception as exc:
                last_error = exc
                log.warning("Gemini attempt %d/%d failed: %s", attempt + 1, attempts, exc)

        raise LLMUnavailable(f"Gemini failed after {attempts} attempt(s): {last_error}")


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if settings.LLM_PROVIDER == "gemini" and settings.llm_enabled:
            _provider = GeminiProvider()
            if not _provider.available:
                log.warning("Falling back to NullProvider: Gemini unavailable")
                _provider = NullProvider()
        else:
            if not settings.llm_enabled:
                log.warning(
                    "No GEMINI_API_KEY set -- deterministic fallback mode. "
                    "Every feature still works; language is templated."
                )
            _provider = NullProvider()
    return _provider


def reset_llm_provider() -> None:
    """Test hook -- lets the chaos test simulate a revoked key."""
    global _provider
    _provider = None
