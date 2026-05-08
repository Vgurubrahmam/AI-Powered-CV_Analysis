"""Structured output parser — validate and coerce LLM JSON responses.

Handles the common patterns of LLM responses that wrap JSON in markdown
code fences, include explanatory text, or return malformed JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any, Type, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_json_block(text: str) -> str:
    """Strip markdown fences and extract the first JSON object or array.

    Handles:
    - ```json ... ``` fences
    - ``` ... ``` fences
    - Leading/trailing prose before/after the JSON
    """
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Find the first JSON object {...} or array [...]
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)

    if obj_match and arr_match:
        # Return whichever starts first
        if obj_match.start() < arr_match.start():
            return obj_match.group(0)
        return arr_match.group(0)
    if obj_match:
        return obj_match.group(0)
    if arr_match:
        return arr_match.group(0)

    return text  # return as-is and let json.loads raise


def parse_json_response(text: str) -> Any:
    """Parse a JSON object or array from LLM response text.

    Args:
        text: Raw LLM response string.

    Returns:
        Parsed Python object (dict or list).

    Raises:
        ValueError: If the response cannot be parsed as JSON.
    """
    cleaned = extract_json_block(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.warning("json_parse_failed", error=str(exc), snippet=cleaned[:200])
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc


def parse_into_model(text: str, model: Type[T]) -> T:
    """Parse LLM response and validate against a Pydantic model.

    Args:
        text: Raw LLM response string.
        model: Pydantic BaseModel class to validate against.

    Returns:
        Validated model instance.

    Raises:
        ValueError: If JSON parsing or Pydantic validation fails.
    """
    data = parse_json_response(text)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        log.warning("pydantic_validation_failed", model=model.__name__, errors=exc.errors())
        raise ValueError(f"LLM response failed schema validation: {exc}") from exc


def parse_json_array(text: str) -> list[Any]:
    """Parse a JSON array from LLM response.

    Returns an empty list rather than raising if parsing fails,
    making it safe to use in non-critical pipeline stages.
    """
    try:
        result = parse_json_response(text)
        if isinstance(result, list):
            return result
        # LLM sometimes wraps array in object: {"items": [...]}
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, list):
                    return val
        log.warning("expected_json_array_got_other", type=type(result).__name__)
        return []
    except Exception as exc:
        log.warning("json_array_parse_failed", error=str(exc))
        return []


def safe_parse_dict(text: str, default: dict | None = None) -> dict:
    """Parse a JSON object from LLM response, returning default on failure."""
    try:
        result = parse_json_response(text)
        if isinstance(result, dict):
            return result
        return default or {}
    except Exception:
        return default or {}
