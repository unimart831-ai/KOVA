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


def _get_llm_config():
    """Load LLMConfig from DB (cached). Returns None if table doesn't exist yet."""
    try:
        from apps.agents.models import LLMConfig
        return LLMConfig.load()
    except Exception:
        return None


def _get_user_plan(user) -> str:
    """Safely extract plan tier from a user object."""
    if user is None:
        return None
    try:
        return user.profile.plan
    except Exception:
        return None


def get_model_for_task(task: str, plan: str = None, user=None) -> str:
    """
    Resolve the best LLM model for a specific agent task.

    Checks DB-backed LLMConfig first, then falls back to settings.AGENT_MODELS.
    When *plan* or *user* is provided, uses plan-specific tier models if configured.

    Args:
        task: Dot-notation task key, e.g. "create.generate", "engage.reply"
        plan: Optional plan tier, e.g. "starter", "growth", "pro", "agency"
        user: Optional user object — plan is extracted from user.profile.plan

    Returns:
        Model identifier string for the configured provider.
    """
    if plan is None and user is not None:
        plan = _get_user_plan(user)

    config = _get_llm_config()
    if config and config.pk:
        task_models = config.get_task_models(plan=plan)
        model = task_models.get(task)
        if model:
            return model
        return config.default_model

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
    embedded JSON in prose, unescaped newlines in strings,
    truncated JSON, control characters.

    Raises json.JSONDecodeError if all repair attempts fail.
    """
    if not text or not text.strip():
        raise json.JSONDecodeError("LLM returned an empty response", doc="", pos=0)

    cleaned = text.strip().lstrip("\ufeff")

    # Remove control characters (except newlines and tabs)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # If text doesn't start with { or [, extract JSON from prose
    if not cleaned.startswith(("{", "[")):
        # Try to find a JSON object
        obj_start = cleaned.find("{")
        obj_end = cleaned.rfind("}")
        # Try to find a JSON array
        arr_start = cleaned.find("[")
        arr_end = cleaned.rfind("]")

        if obj_start != -1 and obj_end > obj_start:
            if arr_start != -1 and arr_start < obj_start and arr_end > obj_end:
                cleaned = cleaned[arr_start:arr_end + 1]
            else:
                cleaned = cleaned[obj_start:obj_end + 1]
        elif arr_start != -1 and arr_end > arr_start:
            cleaned = cleaned[arr_start:arr_end + 1]

    # Replace smart/curly quotes
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    # Replace other unicode dashes/hyphens that break JSON
    cleaned = cleaned.replace("\u2013", "-").replace("\u2014", "-")
    cleaned = cleaned.replace("\u2026", "...")

    # Fix trailing commas before } or ]
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

    # Stage 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Stage 2: Fix unescaped newlines inside JSON string values
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

    # Stage 3: Fix single quotes used as JSON delimiters
    try:
        single_q_fixed = cleaned.replace("'", '"')
        return json.loads(single_q_fixed)
    except json.JSONDecodeError:
        pass

    # Stage 4: Try to repair truncated JSON (close open brackets/braces)
    try:
        repaired = _repair_truncated_json(cleaned)
        if repaired != cleaned:
            return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Final: the raw text from the LLM (before our modifications)
    raise json.JSONDecodeError(
        f"Could not parse LLM JSON after cleanup. First 200 chars: {text[:200]}",
        doc=text, pos=0,
    )


def _repair_truncated_json(text: str) -> str:
    """Attempt to close truncated JSON by matching open brackets/braces."""
    in_string = False
    escape_next = False
    stack = []

    for char in text:
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in ('{', '['):
            stack.append('}' if char == '{' else ']')
        elif char in ('}', ']'):
            if stack and stack[-1] == char:
                stack.pop()

    if not stack and not in_string:
        return text

    # Remove any trailing incomplete key-value pair
    result = text.rstrip()

    # If we're inside an unterminated string, close it
    if in_string:
        # Remove trailing partial word/content back to last clean break
        result = result.rstrip()
        result += '"'

    if result.endswith(','):
        result = result[:-1]

    # Close all open structures
    for closer in reversed(stack):
        result += closer

    return result


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

    Includes automatic retry with backoff for empty responses and transient
    errors.  Free-tier OpenRouter models frequently return empty — this
    retries up to 2 times with increasing delay and, optionally, falls back
    to alternative free models.

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
    # Load runtime config from DB (cached), fall back to settings
    config = _get_llm_config()

    if config and config.pk:
        provider = config.default_provider
        model = model or config.default_model
    else:
        provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")
        model = model or getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini")

    # Fallback models for free-tier OpenRouter when primary returns empty
    if config and config.pk and config.free_fallback_models:
        _FREE_FALLBACKS = config.free_fallback_models
    else:
        _FREE_FALLBACKS = [
            "stepfun/step-3.5-flash:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3.6-plus:free",
        "minimax/minimax-m2.5:free",
    ]

    # Paid escalation model — used as last resort when all free models fail.
    if config and config.pk:
        _PAID_FALLBACK = config.paid_fallback_model if config.paid_fallback_enabled else ""
        _PAID_FALLBACK_PROVIDER = config.paid_fallback_provider
    else:
        _PAID_FALLBACK = getattr(settings, "LLM_PAID_FALLBACK", "gpt-4o-mini")
        _PAID_FALLBACK_PROVIDER = "openai"

    _MAX_MODELS = (config.max_retries if config and config.pk else 3)

    models_to_try = [model]
    if provider == "openrouter" and model.endswith(":free"):
        # Add fallback models (skip if already using one)
        for fb in _FREE_FALLBACKS:
            if fb != model and fb not in models_to_try:
                models_to_try.append(fb)
                if len(models_to_try) >= _MAX_MODELS:
                    break

    # Track which provider each model should use
    model_providers = {m: provider for m in models_to_try}

    # Append paid fallback as last resort
    if _PAID_FALLBACK:
        has_api_key = (
            (_PAID_FALLBACK_PROVIDER == "openai" and getattr(settings, "OPENAI_API_KEY", ""))
            or (_PAID_FALLBACK_PROVIDER == "anthropic" and getattr(settings, "ANTHROPIC_API_KEY", ""))
            or (_PAID_FALLBACK_PROVIDER == "openrouter" and getattr(settings, "OPENROUTER_API_KEY", ""))
        )
        if has_api_key and _PAID_FALLBACK not in models_to_try:
            models_to_try.append(_PAID_FALLBACK)
            model_providers[_PAID_FALLBACK] = _PAID_FALLBACK_PROVIDER

    last_exc = None
    for attempt, try_model in enumerate(models_to_try):
        start = time.monotonic()
        try:
            use_provider = model_providers.get(try_model, provider)
            if use_provider == "anthropic":
                resp = _generate_anthropic(prompt, system, try_model, temperature, max_tokens)
            elif use_provider == "openrouter":
                resp = _generate_openrouter(prompt, system, try_model, temperature, max_tokens, json_mode)
            else:
                resp = _generate_openai(prompt, system, try_model, temperature, max_tokens, json_mode)

            # Guard against empty responses from free models
            if resp.content and resp.content.strip():
                if use_provider != provider:
                    logger.info("Paid fallback used: %s (original: %s/%s)", try_model, provider, model)
                return resp

            logger.warning(
                "LLM returned empty response (%s, attempt %d/%d)",
                try_model, attempt + 1, len(models_to_try),
            )
            last_exc = None  # not an exception, just empty
            # Brief backoff before trying next model
            if attempt < len(models_to_try) - 1:
                time.sleep(min(2 ** attempt, 4))

        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            logger.error(
                "LLM call failed (%s/%s) after %dms (attempt %d/%d): %s",
                model_providers.get(try_model, provider), try_model, duration, attempt + 1, len(models_to_try), exc,
            )
            last_exc = exc
            if attempt < len(models_to_try) - 1:
                time.sleep(min(2 ** attempt, 4))

    # All attempts exhausted — return empty LLMResponse so the caller's
    # own retry loop can handle it (create_agent checks for empty content).
    # Raising here would bypass the caller's retry/error-message logic.
    if last_exc:
        logger.error(
            "All %d LLM model attempts failed. Last error: %s",
            len(models_to_try), last_exc,
        )
    return LLMResponse(content="", model=model)


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

    if not response.choices:
        raise ValueError("LLM returned no choices")
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


# Free models on OpenRouter are routed through various providers, and
# response_format support depends on the provider — not just the model.
# Safest: skip the API param for all free models, use prompt injection.
_NO_JSON_MODE_MODELS: set[str] = set()  # unused now; keeping for reference


def _generate_openrouter(
    prompt: str, system: str, model: str,
    temperature: float, max_tokens: int, json_mode: bool,
) -> LLMResponse:
    """OpenRouter uses the OpenAI-compatible API with a different base_url."""
    client = _get_openrouter_client()
    start = time.monotonic()

    messages = []
    # Free models on OpenRouter go through rotating providers — some reject
    # response_format entirely (400 error).  Always use prompt injection for
    # free-tier models; only send the API param for paid models.
    is_free = model.endswith(":free")
    use_json_param = json_mode and not is_free
    json_instruction = ""
    if json_mode and not use_json_param:
        json_instruction = (
            "\n\nIMPORTANT: You MUST respond with valid JSON only. "
            "No markdown fences, no prose, no explanation. Just the raw JSON object."
        )
    if system:
        messages.append({"role": "system", "content": system + json_instruction})
    elif json_instruction:
        messages.append({"role": "system", "content": json_instruction.strip()})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if use_json_param:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    duration = int((time.monotonic() - start) * 1000)

    if not response.choices:
        raise ValueError("LLM returned no choices")
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
