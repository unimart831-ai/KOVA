"""
LLM service layer — thin abstraction over OpenAI / Anthropic / OpenRouter.

All agent code calls these functions instead of importing vendor SDKs directly.
Supports structured output, streaming, and token tracking.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)


def get_model_for_task(task: str) -> str:
    """
    Resolve the best LLM model for a specific agent task.

    Uses AGENT_MODELS config from settings for tiered routing.
    Falls back to DEFAULT_LLM_MODEL if the task isn't mapped.

    Args:
        task: Dot-notation task key, e.g. "create.generate", "engage.reply"

    Returns:
        Model identifier string for the configured provider.
    """
    agent_models = getattr(settings, "AGENT_MODELS", {})
    return agent_models.get(task, getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini"))


@dataclass
class LLMResponse:
    """Standard response from any LLM call."""
    content: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    raw: dict = field(default_factory=dict)


def parse_llm_json(text: str) -> dict:
    """
    Parse JSON from LLM output, handling common quirks.

    Handles: markdown fences, trailing commas, smart quotes,
    embedded JSON in prose, unescaped newlines in strings.

    Raises json.JSONDecodeError if all repair attempts fail.
    """
    if not text or not text.strip():
        raise json.JSONDecodeError("LLM returned an empty response", doc="", pos=0)

    cleaned = text.strip().lstrip("\ufeff")

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # If text doesn't start with { or [, extract JSON from prose
    if not cleaned.startswith(("{", "[")):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

    # Replace smart/curly quotes
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")

    # Fix trailing commas before } or ]
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: fix unescaped newlines inside JSON string values
    try:
        fixed = re.sub(
            r'(?<=": ")(.*?)(?="[,\s*}])',
            lambda m: m.group(0).replace("\n", "\\n"),
            cleaned,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Final attempt: the raw text from the LLM (before our modifications)
    raise json.JSONDecodeError(
        f"Could not parse LLM JSON after cleanup. First 200 chars: {text[:200]}",
        doc=text, pos=0,
    )


def get_llm_client():
    """Return the configured LLM client based on settings."""
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")
    if provider == "anthropic":
        return _get_anthropic_client()
    if provider == "openrouter":
        return _get_openrouter_client()
    return _get_openai_client()


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _get_openrouter_client():
    from openai import OpenAI
    return OpenAI(
        api_key=getattr(settings, "OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
    )


def _get_anthropic_client():
    from anthropic import Anthropic
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def generate(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> LLMResponse:
    """
    Generate a completion from the configured LLM provider.

    Args:
        prompt: The user message / main prompt.
        system: System message (instructions, persona).
        model: Override model name. Defaults to settings.DEFAULT_LLM_MODEL.
        temperature: Creativity control (0.0-1.0).
        max_tokens: Maximum response tokens.
        json_mode: If True, request JSON output format.

    Returns:
        LLMResponse with content, token counts, and timing.
    """
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")
    model = model or getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini")

    start = time.monotonic()

    try:
        if provider == "anthropic":
            return _generate_anthropic(prompt, system, model, temperature, max_tokens)
        if provider == "openrouter":
            return _generate_openrouter(prompt, system, model, temperature, max_tokens, json_mode)
        return _generate_openai(prompt, system, model, temperature, max_tokens, json_mode)
    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        logger.error("LLM call failed (%s/%s) after %dms: %s", provider, model, duration, exc)
        raise


def _generate_openai(
    prompt: str, system: str, model: str,
    temperature: float, max_tokens: int, json_mode: bool,
) -> LLMResponse:
    client = _get_openai_client()
    start = time.monotonic()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    duration = int((time.monotonic() - start) * 1000)

    choice = response.choices[0]
    usage = response.usage

    return LLMResponse(
        content=choice.message.content or "",
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        duration_ms=duration,
        raw=response.model_dump() if hasattr(response, "model_dump") else {},
    )


def _generate_openrouter(
    prompt: str, system: str, model: str,
    temperature: float, max_tokens: int, json_mode: bool,
) -> LLMResponse:
    """OpenRouter uses the OpenAI-compatible API with a different base_url."""
    client = _get_openrouter_client()
    start = time.monotonic()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    duration = int((time.monotonic() - start) * 1000)

    choice = response.choices[0]
    usage = response.usage

    return LLMResponse(
        content=choice.message.content or "",
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        duration_ms=duration,
        raw=response.model_dump() if hasattr(response, "model_dump") else {},
    )


def _generate_anthropic(
    prompt: str, system: str, model: str,
    temperature: float, max_tokens: int,
) -> LLMResponse:
    client = _get_anthropic_client()
    start = time.monotonic()

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    duration = int((time.monotonic() - start) * 1000)

    content = ""
    for block in response.content:
        if hasattr(block, "text"):
            content += block.text

    return LLMResponse(
        content=content,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        duration_ms=duration,
        raw=response.model_dump() if hasattr(response, "model_dump") else {},
    )
