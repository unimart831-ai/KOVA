"""Unified LLM pricing registry — single source for cost dashboards and budget enforcement.

All costs are stored internally as USD per 1M tokens. ``settings.MODEL_TOKEN_COSTS``
(USD per 1K) is the canonical list of exact model IDs; additional substring patterns
cover provider aliases logged in ``AgentAction.model_used``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings

# Conservative estimate when a model ID is not in the registry (avoid $0 surprises).
UNKNOWN_MODEL_INPUT_PER_1M = 0.26
UNKNOWN_MODEL_OUTPUT_PER_1M = 0.38

# Extra substring patterns not covered by exact MODEL_TOKEN_COSTS keys.
# Longer patterns are matched first.
EXTRA_MODEL_PATTERNS: list[tuple[str, float, float, str]] = [
    ("gemini-3.1-flash-lite", 0.25, 1.50, "Gemini 3.1 Flash Lite"),
    ("gemini-3-flash", 0.50, 3.00, "Gemini 3 Flash"),
    ("gemini-2.5-flash", 0.15, 0.60, "Gemini 2.5 Flash"),
    ("deepseek-v3.2", 0.26, 0.38, "DeepSeek V3.2"),
    ("deepseek-v3", 0.26, 0.38, "DeepSeek V3"),
    ("deepseek-r1", 0.55, 2.19, "DeepSeek R1"),
    ("step-3.5-flash", 0.10, 0.30, "Step 3.5 Flash"),
    ("claude-3-5-haiku", 0.80, 4.00, "Claude 3.5 Haiku"),
    ("claude-3-5-sonnet", 3.00, 15.00, "Claude 3.5 Sonnet"),
    ("claude-sonnet-4", 3.00, 15.00, "Claude Sonnet 4"),
    ("gpt-4o-mini", 0.15, 0.60, "GPT-4o Mini"),
    ("gpt-4o", 2.50, 10.00, "GPT-4o"),
    ("gpt-4-turbo", 10.00, 30.00, "GPT-4 Turbo"),
    ("o3-mini", 1.10, 4.40, "o3-mini"),
    ("qwen/qwen3", 0.00, 0.00, "Qwen 3 (Free)"),
    ("minimax/minimax", 0.00, 0.00, "MiniMax (Free)"),
    ("nvidia/nemotron", 0.00, 0.00, "Nemotron (Free)"),
    ("mistralai/mistral", 0.00, 0.00, "Mistral (Free)"),
    (":free", 0.00, 0.00, "Free tier"),
]


@dataclass(frozen=True)
class ModelPricing:
    input_per_1m: float
    output_per_1m: float
    label: str
    matched_key: str
    is_free: bool
    is_unknown: bool

    @property
    def input_per_1k(self) -> float:
        return self.input_per_1m / 1000

    @property
    def output_per_1k(self) -> float:
        return self.output_per_1m / 1000


def _registry_entries() -> list[tuple[str, float, float, str, bool]]:
    """Return (pattern, input/1M, output/1M, label, exact_only)."""
    entries: list[tuple[str, float, float, str, bool]] = []
    token_costs = getattr(settings, "MODEL_TOKEN_COSTS", {})
    for model_id, (in_1k, out_1k) in token_costs.items():
        label = model_id.split("/")[-1] if "/" in model_id else model_id
        entries.append((
            model_id.lower(),
            float(in_1k) * 1000,
            float(out_1k) * 1000,
            label,
            True,
        ))
    for pattern, in_1m, out_1m, label in EXTRA_MODEL_PATTERNS:
        entries.append((pattern.lower(), in_1m, out_1m, label, False))
    return entries


@lru_cache(maxsize=1)
def _sorted_patterns() -> list[tuple[str, float, float, str, bool]]:
    """Exact keys first (longest), then substring patterns (longest)."""
    exact = sorted(
        [e for e in _registry_entries() if e[4]],
        key=lambda e: len(e[0]),
        reverse=True,
    )
    fuzzy = sorted(
        [e for e in _registry_entries() if not e[4]],
        key=lambda e: len(e[0]),
        reverse=True,
    )
    return exact + fuzzy


def lookup_model_pricing(model_name: str | None) -> ModelPricing:
    """Resolve pricing for a model identifier logged on AgentAction."""
    if not model_name:
        return ModelPricing(0, 0, "No model", "", True, False)

    model_lower = model_name.strip().lower()

    for pattern, in_1m, out_1m, label, exact_only in _sorted_patterns():
        if exact_only:
            if model_lower == pattern:
                is_free = in_1m == 0 and out_1m == 0
                return ModelPricing(in_1m, out_1m, label, pattern, is_free, False)
        elif pattern in model_lower:
            is_free = in_1m == 0 and out_1m == 0
            return ModelPricing(in_1m, out_1m, label, pattern, is_free, False)

    return ModelPricing(
        UNKNOWN_MODEL_INPUT_PER_1M,
        UNKNOWN_MODEL_OUTPUT_PER_1M,
        "Unknown (conservative est.)",
        "",
        False,
        True,
    )


def get_cost_per_1k(model: str) -> tuple[float, float]:
    """Budget enforcement helper — USD per 1K input/output tokens."""
    p = lookup_model_pricing(model)
    return p.input_per_1k, p.output_per_1k


def calculate_token_cost(model_name: str | None, input_tokens: int, output_tokens: int) -> dict:
    """Return cost breakdown for a token usage record."""
    pricing = lookup_model_pricing(model_name)
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    cost = (
        (input_tokens / 1_000_000) * pricing.input_per_1m
        + (output_tokens / 1_000_000) * pricing.output_per_1m
    )
    return {
        "cost_usd": round(cost, 6),
        "is_free": pricing.is_free,
        "is_unknown": pricing.is_unknown,
        "matched_key": pricing.matched_key,
        "label": pricing.label,
        "input_per_1m": pricing.input_per_1m,
        "output_per_1m": pricing.output_per_1m,
    }


def get_pricing_display_registry() -> dict[str, dict]:
    """Admin UI: model → {input, output, label} per 1M tokens."""
    registry: dict[str, dict] = {}
    seen: set[str] = set()
    for pattern, in_1m, out_1m, label, _exact in _sorted_patterns():
        if pattern in seen:
            continue
        seen.add(pattern)
        registry[pattern] = {
            "input": in_1m,
            "output": out_1m,
            "label": label,
        }
    registry["_unknown_fallback"] = {
        "input": UNKNOWN_MODEL_INPUT_PER_1M,
        "output": UNKNOWN_MODEL_OUTPUT_PER_1M,
        "label": "Unknown models (conservative estimate)",
    }
    return registry
