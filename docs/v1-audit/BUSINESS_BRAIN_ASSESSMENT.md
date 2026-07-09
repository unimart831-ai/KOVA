# Business Brain Assessment

**Date:** July 2026

---

## Overview

The "Business Brain" is Kova's persistent intelligence model for each business. It captures who the business is, how it communicates, who its customers are, and how it grows — then uses this knowledge to ground all AI outputs.

---

## Implementation Status: IMPLEMENTED

The Business Brain exists as a structured 6-layer DNA model stored in `UserProfile` fields, with a dedicated module at `accounts/business_brain.py`.

---

## Architecture

### Six DNA Layers

| Layer | Fields | Purpose |
|-------|--------|---------|
| **Business** | `company_name`, `industry`, `business_model`, `key_offerings`, `website_url` | What the business does |
| **Brand** | `brand_voice`, `tone_attributes`, `founder_story`, `brand_restrictions` | How it communicates |
| **Customer** | `target_audience`, `customer_problems`, `buy_triggers`, `common_questions` | Who it serves |
| **Growth** | `goals`, `success_vision`, `posting_frequency` | Where it's going |
| **Market** | `country`, `city`, `content_language` | Where it operates |
| **Learning** | `pillar_weights`, `dna_preferences`, `optimal_schedule` | What Kova has learned (evolves over time) |

### Key Functions

| Function | Purpose |
|----------|---------|
| `build_brain_snapshot(profile)` | Returns the Brain as nested dict for display and AI grounding |
| `brain_completeness(profile)` | Weighted completeness score (0-100%) |
| `enrich_brain_from_onboarding(profile, answers)` | Extracts DNA from conversational onboarding answers |
| `_extract_brain_fields_llm(answers, profile)` | LLM-powered extraction of structured fields from free-text |
| `_deterministic_fallback(answers, profile)` | Non-LLM fallback if extraction fails |

### Completeness Scoring

Fields are weighted by importance to AI understanding:

| Field | Weight |
|-------|--------|
| `brand_voice` | 12 |
| `target_audience` | 12 |
| `founder_story` | 10 |
| `customer_problems` | 10 |
| `industry` | 8 |
| `business_model` | 8 |
| `buy_triggers` | 8 |
| `key_offerings` | 8 |
| `company_name` | 6 |
| `tone_attributes` | 6 |
| `common_questions` | 6 |
| `success_vision` | 6 |

---

## How the Brain is Populated

### 1. Onboarding (Primary)

The onboarding flow asks three conversational questions:
- What does your business do?
- Why did you start it?
- What does success look like?

Plus a business model selection.

These answers are processed by `enrich_brain_from_onboarding()` which:
1. Attempts LLM extraction of structured fields
2. Falls back to deterministic extraction if LLM fails
3. Never overwrites existing fields — only enriches empties
4. Never blocks onboarding on LLM response

### 2. Post-Onboarding Intelligence Chain

`agents/onboarding_tasks.py` runs a Celery chain after signup:
1. Research Agent discovers industry trends
2. Strategist creates initial ContentSeeds
3. Create Agent generates first content drafts
4. Welcome brief sent via WhatsApp

### 3. Adapt Agent (Continuous Learning)

The `learning` layer evolves over time:
- `pillar_weights` — content type distribution (adjusted by Adapt Agent)
- `dna_preferences` — refined by Analyst Agent based on what performs
- `optimal_schedule` — posting times tuned by engagement timing

### 4. Industry Playbooks (Cold Start)

`agents/playbooks.py` provides industry-specific defaults:
- Content pillar suggestions
- Seed ideas
- Content calendars
- DNA starting points

These accelerate the learning layer for new businesses.

---

## Where the Brain is Used

| Consumer | How It Uses the Brain |
|----------|----------------------|
| **Create Agent** | Grounds content generation in brand voice, audience, offerings |
| **Strategist Agent** | Informs strategy decisions based on goals and growth vision |
| **AI Salesperson** | Answers customer questions using business knowledge |
| **Daily Brief** | Contextualizes recommendations |
| **WhatsApp Autopilot** | FAQ answers grounded in business context |
| **Engage Agent** | Replies in brand voice with business awareness |
| **Content Safety** | Validates content against brand restrictions |
| **First Business Report** | Displays "here's what Kova understands about you" |
| **Platform Rewrite** | Adapts tone per platform while maintaining brand voice |

---

## Storage Architecture

The Brain is stored directly on `UserProfile` (no separate model):

```python
class UserProfile(models.Model):
    # Business layer
    company_name = ...
    industry = ...
    business_model = ...
    key_offerings = ...
    website_url = ...
    
    # Brand layer
    brand_voice = ...
    tone_attributes = ...
    founder_story = ...
    brand_restrictions = ...
    
    # Customer layer
    target_audience = ...
    customer_problems = ...
    buy_triggers = ...
    common_questions = ...
    
    # Growth layer
    goals = ...
    success_vision = ...
    posting_frequency = ...
    
    # Market layer
    country = ...
    city = ...
    content_language = ...
    
    # Learning layer (evolves)
    pillar_weights = JSONField(...)
    dna_preferences = JSONField(...)
    optimal_schedule = JSONField(...)
```

---

## Web Interface

- `templates/accounts/business_brain.html` — Full Brain view/edit page
- `templates/accounts/ai_learning.html` — Learning layer visualization
- `templates/accounts/_first_business_report.html` — Post-onboarding Brain report

---

## Assessment

### Strengths

1. **Design philosophy is excellent.** "Never block onboarding on LLM" + "never overwrite existing" = resilient and respectful of user data.

2. **Six-layer model is comprehensive.** Covers identity, voice, audience, goals, market, and learned patterns.

3. **Self-improving.** The learning layer evolves via Adapt Agent without manual intervention.

4. **Cold-start mitigation.** Industry playbooks provide Day 1 intelligence.

5. **Used pervasively.** Nearly every AI component consumes the Brain snapshot — it's not decorative.

### Weaknesses

1. **Stored on UserProfile.** As fields accumulate, the profile model becomes bloated. Not a V1 problem but consider extraction to a dedicated `BusinessBrain` model in V2.

2. **No versioning.** Brain state isn't timestamped — can't answer "what did Kova understand last month?"

3. **FAQ answers are separate.** `wa_faq_answers` on UserProfile isn't part of the formal Brain layers but logically belongs to the Customer layer.

4. **WhatsApp-accessible but not editable.** Owners can view the Brain via the BRIEF command but can't update it via WhatsApp (e.g., "my target audience is now millennials").

5. **No multi-brand Brain.** The Brain is per-user, not per-brand. The `teams.Brand` model exists but isn't integrated with the Brain system.

---

## Recommendations for V1

1. **The Brain is V1-ready as-is.** No structural changes needed. It works and is well-integrated.

2. **Add Brain completeness to Daily Brief.** If completeness is below 70%, prompt the owner to fill gaps via WhatsApp ("Tell me more about your customers — who's your ideal buyer?").

3. **Wire FAQ answers into the Brain formally.** Move `wa_faq_answers` into the Customer layer's `common_questions` field, or reference both in the Brain snapshot.

4. **Consider WhatsApp-editable Brain.** "UPDATE AUDIENCE [description]" or conversational Brain refinement would reinforce WhatsApp-first.

5. **Defer multi-brand Brain to V2.** Teams feature is V2; Brain per brand can wait.

---

## Business Brain Readiness Score: 9/10

The Business Brain is one of Kova's strongest implemented subsystems. It's well-designed, pervasively used, resilient to failures, and self-improving. Ready for V1 launch.
