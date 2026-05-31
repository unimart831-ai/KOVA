# Plan v2 — Pricing, Caps & Metering

Authoritative source: `apps/billing/models.py` → `PLAN_LIMITS`. DB `PlanPrice` rows override `price_kes` / `price_usd` only.

Effective: May 2026 (founder decision).

## Public pricing

| Tier | KES/mo | USD/mo | Public checkout |
|------|--------|--------|-----------------|
| **Starter** (Jipange) | 499 | 4 | Yes |
| **Growth** (Kazi) | 1,499 | 11 | Yes |
| **Pro** (Biashara) | 2,999 | 22 | Yes |
| **Agency** (Wakala) | 7,999 | 59 | No — requires `UserProfile.is_agency_approved` |

## Trial

- **7 days**, no payment required.
- Trial users receive **Starter-tier limits** (`TRIAL_FEATURE_PLAN = "starter"`), not full Growth.
- Label in UI: "Starter trial".

## Core limits matrix

| Limit | Starter | Growth | Pro | Agency |
|-------|---------|--------|-----|--------|
| Social accounts | 2 | 4 | 5 (+ WA) | 25 |
| Posts/month | 18 | 60 | 150 | 300 |
| Seeds/month | 8 | 30 | 60 | 120 |
| Daily LLM tokens | 50K | 200K | 500K | 2M |
| **Monthly LLM tokens** | 1M | 4M | 10M | 40M |
| Studio polish/month | 8 | 30 | 100 | 150 |
| AI images/month | 0 | 50 | 100 | 200 |
| WhatsApp marketing convos/month | 0 | 50 | 300 | 1,000 |
| WhatsApp Business | No | No | Yes | Yes |
| Max campaigns | 2 | 5 | 15 | 25 |
| Team members | 0 | 0 | 5 | 25 |

Pro and Agency no longer use `999999` “unlimited” placeholders — all caps are finite.

## Metering & enforcement

### LLM tokens

- **Daily + monthly** caps enforced in `apps/agents/budget.py` → `check_budget()`.
- Called from `apps/agents/llm.py` → `generate()` and `analyze_image()` when `user` is passed.
- Celery paths updated to pass `user` (WhatsApp, briefs, campaigns, leads, media queue, memes adapt, product vision).

### Studio polish (Photoroom)

- Field: `visual_enhancements_per_month` (studio polish credits).
- **One debit per API call** via `record_studio_polish()`; in-progress session markers excluded from counts.
- Platform pool fair-share: **Growth throttled when platform pool > 80%** used (`apps/billing/visual_credits.py`).

### WhatsApp marketing

- Field: `whatsapp_marketing_conversations_per_month`.
- Counts distinct conversations contacted via **marketing** templates only.
- **Utility** (e.g. booking confirm) and **authentication** templates do **not** count.
- Enforced in broadcast launch + `execute_broadcast` + drip sequence steps (`apps/billing/whatsapp_marketing.py`).

### Agency self-serve

- Removed from public checkout (`PUBLIC_PLAN_TIERS`).
- `is_agency_approved` on `UserProfile` gates sales onboarding.
- Finite caps replace all former `999999` unlimited limits.

## Hard stops

At **100%** of any cap, actions block with upgrade messaging via existing `PlanLimitExceeded` / `plan_limit_redirect` patterns.

## Code map

| Concern | Path |
|---------|------|
| Plan limits & prices | `apps/billing/models.py` |
| LLM budget | `apps/agents/budget.py` |
| Vision metering | `apps/agents/llm.py` → `analyze_image(user=...)` |
| Photoroom credits | `apps/billing/visual_credits.py` |
| WhatsApp marketing | `apps/billing/whatsapp_marketing.py` |
| Pricing UI | `templates/billing/pricing.html` |
| Tests | `tests/test_billing.py`, `tests/test_plan_limits_v2.py`, `tests/test_visual_credits.py` |
