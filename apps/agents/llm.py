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
    finish_reason: str = ""  # 'stop' = complete, 'length' = truncated
    raw: dict = field(default_factory=dict)

    @property
    def was_truncated(self) -> bool:
        """Return True if the response was cut off by the token limit."""
        return self.finish_reason == "length"


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

    # Strip common LLM reasoning preamble before the actual JSON.
    # Free models (e.g. stepfun/step-3.5-flash) sometimes emit "thinking"
    # text like "We need to output JSON..." before the object.
    if not cleaned.startswith(("{", "[")):
        # Look for <think>...</think> blocks and remove them
        cleaned = re.sub(r'<think>.*?</think>\s*', '', cleaned, flags=re.DOTALL)
        cleaned = cleaned.strip()

    # Detect prose that describes JSON instead of containing it —
    # e.g. "We need to output JSON with keys format, tone..."
    # If no { or [ exists at all, fail fast with a clear message.
    if not cleaned.startswith(("{", "[")) and "{" not in cleaned and "[" not in cleaned:
        raise json.JSONDecodeError(
            f"LLM returned prose instead of JSON. First 200 chars: {cleaned[:200]}",
            doc=text, pos=0,
        )

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

    # Stage 2: Fix unescaped newlines inside JSON string values.
    # The lookahead includes \] so strings ending before ] (last item in
    # a JSON array) are handled correctly, not just those before , or }.
    try:
        fixed = re.sub(
            r'(?<=": ")(.*?)(?="[,\s*}\]])',
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

    # Stage 5: Try to trim to the last complete object in a "posts" array.
    # Handles cases where the LLM truncated mid-post — salvage what we can.
    try:
        posts_match = re.search(r'"posts"\s*:\s*\[', cleaned)
        if posts_match:
            # Find all complete post objects {...} inside the array,
            # properly skipping string contents so embedded {/} don't
            # confuse the brace matcher.
            arr_start = posts_match.end() - 1  # the '['
            depth = 0
            last_complete = arr_start
            in_str = False
            esc = False
            i = arr_start
            while i < len(cleaned):
                ch = cleaned[i]
                if esc:
                    esc = False
                elif ch == '\\' and in_str:
                    esc = True
                elif ch == '"':
                    in_str = not in_str
                elif not in_str:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            last_complete = i + 1
                i += 1
            if last_complete > arr_start + 1:
                # Build a valid JSON with the complete posts we found
                salvaged = cleaned[:posts_match.start()] + '"posts": ' + cleaned[arr_start:last_complete] + ']}'
                # Ensure it starts with {
                brace = salvaged.find('{')
                if brace >= 0:
                    salvaged = salvaged[brace:]
                salvaged = re.sub(r',\s*([}\]])', r'\1', salvaged)
                return json.loads(salvaged)
    except (json.JSONDecodeError, IndexError):
        pass

    # Final: the raw text from the LLM (before our modifications)
    raise json.JSONDecodeError(
        f"Could not parse LLM JSON after cleanup. First 200 chars: {text[:200]}",
        doc=text, pos=0,
    )


def coerce_llm_dict(data) -> dict:
    """
    Normalize parse_llm_json output to a dict.

    Some models return a one-element list or bare array instead of an object.
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
        logger.warning("LLM JSON list had no dict items — using empty dict")
        return {}
    logger.warning("LLM JSON expected dict, got %s — using empty dict", type(data).__name__)
    return {}


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

    # If we're inside an unterminated string, close it while preserving
    # as much content as possible.  The old logic deleted the entire string
    # value when truncation landed mid-content — now we keep the partial
    # text (a truncated post is better than an empty one).
    if in_string:
        result = result.rstrip()
        # Strip a trailing backslash that would escape our closing quote
        if result.endswith('\\'):
            result = result[:-1]
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
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=45.0)


def _get_openrouter_client():
    from openai import OpenAI
    return OpenAI(
        api_key=getattr(settings, "OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
        timeout=45.0,
    )


def _get_anthropic_client():
    from anthropic import Anthropic
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=45.0)


def generate(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
    user=None,
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
        user: When provided, the call is metered against the user's daily
            LLM token budget (PLAN_LIMITS[...]['daily_llm_tokens']).
            Raises ``PlanLimitExceeded`` if the cap would be breached.
            ``user=None`` skips enforcement — used by background system
            tasks until they're migrated to per-user metering.

    Returns:
        LLMResponse with content, token counts, and timing.
    """
    # Plan-budget gate. Runs before any external call so a capped user
    # never costs us a single token on the upstream provider.
    if user is not None:
        from apps.agents.budget import check_budget
        check_budget(user, max_tokens)

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
            "nvidia/nemotron-3-super-120b-a12b:free",
            "openai/gpt-oss-120b:free",
            "minimax/minimax-m2.5:free",
            "z-ai/glm-4.5-air:free",
    ]

    # Paid escalation model — used as last resort when all free models fail.
    if config and config.pk:
        _PAID_FALLBACK = config.paid_fallback_model if config.paid_fallback_enabled else ""
        _PAID_FALLBACK_PROVIDER = config.paid_fallback_provider
    else:
        _PAID_FALLBACK = getattr(settings, "LLM_PAID_FALLBACK", "deepseek/deepseek-v3.2")
        _PAID_FALLBACK_PROVIDER = getattr(settings, "LLM_PAID_FALLBACK_PROVIDER", "openrouter")

    _MAX_MODELS = (config.max_retries if config and config.pk else 3)

    models_to_try = [model]
    if provider == "openrouter" and model.endswith(":free"):
        # Add fallback models (skip if already using one)
        for fb in _FREE_FALLBACKS:
            if fb != model and fb not in models_to_try:
                models_to_try.append(fb)
                if len(models_to_try) >= _MAX_MODELS:
                    break
    elif provider == "openrouter" and not model.endswith(":free"):
        # Paid models: retry same model once before falling back to
        # a different provider — transient errors (502/503) are common.
        models_to_try.append(model)

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
                if user is not None:
                    try:
                        from apps.agents.budget import record_usage
                        record_usage(
                            user, resp.model or try_model,
                            resp.input_tokens, resp.output_tokens,
                        )
                    except Exception as exc:
                        # Metering must never break the user-facing flow.
                        logger.warning("record_usage failed: %s", exc)
                return resp

            logger.warning(
                "LLM returned empty response (%s, attempt %d/%d)",
                try_model, attempt + 1, len(models_to_try),
            )
            last_exc = None  # not an exception, just empty
            # Brief backoff before trying next model
            if attempt < len(models_to_try) - 1:
                time.sleep(min(2 ** attempt, 2))

        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            logger.error(
                "LLM call failed (%s/%s) after %dms (attempt %d/%d): %s",
                model_providers.get(try_model, provider), try_model, duration, attempt + 1, len(models_to_try), exc,
            )
            last_exc = exc
            if attempt < len(models_to_try) - 1:
                time.sleep(min(2 ** attempt, 2))

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
    finish = getattr(choice, "finish_reason", "") or ""

    return LLMResponse(
        content=choice.message.content or "",
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        duration_ms=duration,
        finish_reason=finish,
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
            "\n\nCRITICAL FORMATTING RULE: Your ENTIRE response must be a single, "
            "valid JSON object. Do NOT include any thinking, reasoning, explanation, "
            "or commentary before or after the JSON. Do NOT wrap in markdown code "
            "fences. Do NOT describe what the JSON should contain — output it directly. "
            "Start your response with '{' and end with '}'."
        )
    if system:
        messages.append({"role": "system", "content": system + json_instruction})
    elif json_instruction:
        messages.append({"role": "system", "content": json_instruction.strip()})
    user_content = prompt
    if json_mode and is_free:
        # Prefix-force: add an assistant-priming message so the model
        # continues from '{' instead of generating reasoning text first.
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": "{"})
    else:
        messages.append({"role": "user", "content": user_content})

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

    content = choice.message.content or ""
    # If we used assistant-priming with '{', prepend it to the response
    if json_mode and is_free and not content.lstrip().startswith("{"):
        content = "{" + content
    finish = getattr(choice, "finish_reason", "") or ""

    return LLMResponse(
        content=content,
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        duration_ms=duration,
        finish_reason=finish,
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

    # Anthropic uses 'stop_reason' with values: 'end_turn', 'max_tokens', 'stop_sequence'
    stop_reason = getattr(response, "stop_reason", "") or ""
    finish = "length" if stop_reason == "max_tokens" else "stop"

    return LLMResponse(
        content=content,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        duration_ms=duration,
        finish_reason=finish,
        raw=response.model_dump() if hasattr(response, "model_dump") else {},
    )


# ── Vision AI ────────────────────────────────────────────────────────
def _record_vision_usage(user, resp: LLMResponse) -> None:
    try:
        from apps.agents.budget import record_usage
        record_usage(user, resp.model or "gpt-4o-mini", resp.input_tokens, resp.output_tokens)
    except Exception as exc:
        logger.warning("Vision record_usage failed: %s", exc)


def analyze_image(
    image_url: str,
    prompt: str = "What is in this image?",
    system: str = "",
    model: str = "",
    max_tokens: int = 1024,
    json_mode: bool = False,
    user=None,
) -> LLMResponse:
    """
    Send an image to a vision-capable LLM and get a text/JSON response.

    Supports OpenAI (gpt-4o, gpt-4o-mini) and OpenRouter vision models.
    The image can be a URL or a base64 data URI.

    Args:
        image_url: Public URL or base64 data URI (data:image/...;base64,...).
        prompt: Question or instruction about the image.
        system: Optional system message.
        model: Override model. Defaults to gpt-4o-mini (cheap, vision-capable).
        max_tokens: Max response tokens.
        json_mode: If True, request JSON output.
        user: When provided, metered against daily + monthly LLM token budgets.

    Returns:
        LLMResponse with the analysis content.
    """
    if user is not None:
        from apps.agents.budget import check_budget
        check_budget(user, max_tokens)

    config = _get_llm_config()

    if config and config.pk:
        provider = config.default_provider
        model = model or "gpt-4o-mini"
    else:
        provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")
        model = model or "gpt-4o-mini"

    # Vision requires OpenAI-compatible API (works with OpenAI and OpenRouter)
    if provider == "anthropic":
        resp = _analyze_image_anthropic(image_url, prompt, system, model, max_tokens)
        if user is not None:
            _record_vision_usage(user, resp)
        return resp

    # Use OpenAI or OpenRouter client
    if provider == "openrouter":
        client = _get_openrouter_client()
    else:
        client = _get_openai_client()

    start = time.monotonic()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    # Build the vision message with image + text
    user_content = [
        {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
        {"type": "text", "text": prompt},
    ]
    messages.append({"role": "user", "content": user_content})

    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
        duration = int((time.monotonic() - start) * 1000)

        if not response.choices:
            raise ValueError("Vision LLM returned no choices")
        choice = response.choices[0]
        usage = response.usage

        resp = LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            duration_ms=duration,
            finish_reason=getattr(choice, "finish_reason", "") or "",
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )
        if user is not None:
            _record_vision_usage(user, resp)
        return resp
    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        logger.error("Vision AI failed (%s/%s) after %dms: %s", provider, model, duration, exc)
        raise


def _analyze_image_anthropic(
    image_url: str, prompt: str, system: str, model: str, max_tokens: int,
) -> LLMResponse:
    """Anthropic vision uses a different message format for images."""
    import base64 as b64mod
    client = _get_anthropic_client()
    start = time.monotonic()

    # Anthropic needs base64 source or URL source
    if image_url.startswith("data:"):
        # Parse data URI: data:image/jpeg;base64,/9j/4AAQ...
        header, data = image_url.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]
        image_content = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        }
    else:
        image_content = {
            "type": "image",
            "source": {"type": "url", "url": image_url},
        }

    kwargs = {
        "model": model or "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": [image_content, {"type": "text", "text": prompt}]},
        ],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    duration = int((time.monotonic() - start) * 1000)

    content = ""
    for block in response.content:
        if hasattr(block, "text"):
            content += block.text

    stop_reason = getattr(response, "stop_reason", "") or ""
    finish = "length" if stop_reason == "max_tokens" else "stop"

    return LLMResponse(
        content=content,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        duration_ms=duration,
        finish_reason=finish,
        raw=response.model_dump() if hasattr(response, "model_dump") else {},
    )
