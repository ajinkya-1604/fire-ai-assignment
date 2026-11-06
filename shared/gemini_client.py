"""
Resilient Google Gemini API Client wrapper.
Handles configuration, structured JSON responses, token tracking,
cost estimation, error handling, and graceful degradation when API keys are absent.
"""

import json
import re
import time
from typing import Any, Dict, Optional, Tuple

from shared.config import (
    GEMINI_API_KEY,
    GEMINI_INPUT_COST_PER_M,
    GEMINI_MODEL,
    GEMINI_OUTPUT_COST_PER_M,
)
from shared.logging_config import get_logger

logger = get_logger("gemini_client")

# Lazy import flag
_GENAI_INITIALIZED = False
_GENAI_MODULE = None


def is_gemini_available() -> bool:
    """Return True if a valid Gemini API key is configured."""
    return bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")


def _init_genai():
    """Safely initialize the google.generativeai SDK if available and key exists."""
    global _GENAI_INITIALIZED, _GENAI_MODULE
    if _GENAI_INITIALIZED:
        return _GENAI_MODULE

    if not is_gemini_available():
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        _GENAI_MODULE = genai
        _GENAI_INITIALIZED = True
        logger.info(f"Gemini API configured successfully with model {GEMINI_MODEL}")
        return _GENAI_MODULE
    except Exception as e:
        logger.warning(f"Failed to initialize google.generativeai: {e}")
        return None


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and extraneous text around JSON."""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def estimate_tokens(text: str) -> int:
    """Estimate token count when API usage metadata is unavailable (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class GeminiClient:
    """
    Production-ready wrapper around Google Gemini API.
    Provides structured JSON responses, latency tracking, token accounting,
    and automatic fallback when unconfigured.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or GEMINI_MODEL
        self.genai = _init_genai()

    def is_configured(self) -> bool:
        """Check if client is ready to make live API calls."""
        return is_gemini_available() and self.genai is not None

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Send a prompt to Gemini expecting a valid JSON object in return.

        Args:
            prompt: User prompt content.
            system_instruction: Optional system level context/instruction.
            temperature: Sampling temperature (0.0 for deterministic calculations).
            max_output_tokens: Maximum tokens in response.

        Returns:
            Tuple of:
            - parsed_json (Dict or None)
            - metadata (Dict with keys: latency_ms, input_tokens, output_tokens,
                        cost_usd, model, status, error)
        """
        metadata: Dict[str, Any] = {
            "model": self.model_name,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "status": "NOT_CONFIGURED",
            "error": None,
        }

        if not self.is_configured():
            metadata["error"] = (
                "GEMINI_API_KEY is not set or invalid. Running in offline/unconfigured mode."
            )
            return None, metadata

        start_time = time.perf_counter()
        try:
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": "application/json",
            }

            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config=generation_config,
            )

            response = model.generate_content(prompt)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            metadata["latency_ms"] = round(latency_ms, 2)

            raw_text = response.text if hasattr(response, "text") else ""

            # Extract token usage if available in SDK response
            in_tokens = 0
            out_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                in_tokens = getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ) or estimate_tokens(prompt)
                out_tokens = getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ) or estimate_tokens(raw_text)
            else:
                in_tokens = estimate_tokens(prompt)
                out_tokens = estimate_tokens(raw_text)

            metadata["input_tokens"] = in_tokens
            metadata["output_tokens"] = out_tokens

            # Calculate cost estimate in USD
            cost_usd = (in_tokens / 1_000_000 * GEMINI_INPUT_COST_PER_M) + (
                out_tokens / 1_000_000 * GEMINI_OUTPUT_COST_PER_M
            )
            metadata["cost_usd"] = round(cost_usd, 7)

            # Parse JSON
            cleaned_text = clean_json_text(raw_text)
            parsed = json.loads(cleaned_text)
            metadata["status"] = "SUCCESS"
            return parsed, metadata

        except json.JSONDecodeError as jde:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            metadata["latency_ms"] = round(latency_ms, 2)
            metadata["status"] = "JSON_PARSE_ERROR"
            metadata["error"] = f"Failed to parse model output as JSON: {jde}"
            logger.error(f"Gemini JSON decode error: {jde}")
            return None, metadata

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            metadata["latency_ms"] = round(latency_ms, 2)
            metadata["status"] = "API_ERROR"
            metadata["error"] = str(e)
            logger.error(f"Gemini API call failed: {e}")
            return None, metadata

