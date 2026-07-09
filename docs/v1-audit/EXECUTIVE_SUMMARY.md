# KOVA V1 — Executive Summary

**Date:** July 2026
**Scope:** Complete architectural audit of the Kova platform
**Purpose:** Define a tightly scoped Version 1 launch

---

## The Vision

Kova is the **AI Business Operating System for African SMEs**, with WhatsApp as the primary user interface. Business owners run their businesses by talking to Kova on WhatsApp. The web platform exists to configure, orchestrate, and provide intelligence — not as the primary daily interface.

---

## What Exists Today

Kova is a **Django 5.1 modular monolith** deployed on Railway with:

| Dimension | Count |
|-----------|-------|
| Django apps | 27 |
| Database models | 115 |
| HTML templates | 528 |
| AI agents | 6 + Educator |
| Celery task files | 14 |
| Management commands | 16 |
| Webhook handlers | 8 |
| Platform integrations | 9 social + payments + image APIs |
| WhatsApp modules | 14 dedicated files |
| Photoroom/image files | 18 |

**Tech stack:** Django 5.1, PostgreSQL 16, Redis, Celery, Django Channels, HTMX/Alpine/Tailwind, DRF API, LangChain/LangGraph, M-Pesa + Stripe, WhatsApp Cloud API.

---

## Key Findings

### Strengths

1. **WhatsApp infrastructure is advanced.** Conversational commerce state machine, owner commands (approve/reject/score/brief/snap), customer memory, FAQ autopilot, broadcast sequences, and daily brief delivery are all implemented.

2. **AI agent system is sophisticated.** Six specialized agents (Research, Create, Strategist, Analyst, Adapt, Engage) plus an Educator agent form a coordinated intelligence pipeline with budget tracking and outcome measurement.

3. **Commerce is functional.** Product catalog, public storefront, Snap-to-Sell (photo → product), M-Pesa payments, WhatsApp ordering, booking links, and revenue funnels exist.

4. **Business Brain is implemented.** Six-layer DNA model (business, brand, customer, growth, market, learning) with completeness scoring and LLM grounding.

5. **Social publishing pipeline works.** Multi-platform publishing (Facebook, Instagram, TikTok, LinkedIn) with OAuth, scheduling, metrics collection, and content safety gates.

### Concerns

1. **Feature breadth exceeds depth.** 27 apps covering commerce, CRM, email marketing, QR attribution, walk-in tracking, partner marketplace, competitor intelligence, A/B testing, and more. Many features are partially implemented or experimental.

2. **Web platform behaves as the primary workspace.** 528 templates, complex dashboards, studio workflows — contradicting the WhatsApp-first vision.

3. **Technical debt is accumulating.** Legacy apps (campaigns), duplicate model names across apps, 18 Photoroom files for what should be a simple integration, and scattered API-like endpoints outside the formal API.

4. **Some features are premature for V1.** Partner marketplace, QR walk-in attribution, Shopify integration, competitor screenshots, email marketing sequences, and A/B testing add complexity without delivering the core WhatsApp-first promise.

---

## Readiness Assessment

| Area | Status | V1 Ready? |
|------|--------|-----------|
| WhatsApp conversational commerce | Implemented | Yes |
| Owner WhatsApp commands | Implemented | Yes |
| Daily Brief (WhatsApp delivery) | Implemented | Yes |
| Business Brain | Implemented | Yes |
| AI content generation | Implemented | Yes |
| Social publishing (FB/IG) | Working | Yes |
| Product catalog + storefront | Implemented | Yes |
| M-Pesa payments | Implemented | Yes |
| Lead capture + CRM | Partial | Yes (simplified) |
| TikTok publishing | Working prototype | V1.1 |
| LinkedIn publishing | Working prototype | V1.1 |
| Email marketing | Partial | V1.1 |
| Partner marketplace | Stub | V2 |
| QR/Walk-in attribution | Implemented | V2 |
| A/B testing | Partial | V2 |
| Competitor intelligence | Partial | V2 |
| Shopify integration | Prototype | V2 |

---

## Recommended V1 Scope

Version 1 should deliver exactly one promise:

> **A business owner can manage their online presence by chatting with Kova on WhatsApp, while the web platform quietly handles orchestration, commerce management, integrations, analytics, and configuration.**

### V1 Core (Must Ship)

1. **WhatsApp Business Operations** — owner commands, daily brief, content approval, snap-to-sell, customer conversations, FAQ autopilot
2. **AI Content Engine** — Business Brain, content generation, scheduling, multi-platform publishing (Facebook + Instagram)
3. **Commerce** — product catalog, public storefront, WhatsApp ordering, M-Pesa payments, booking links
4. **Web Orchestration** — simplified dashboard (brief-first), platform connections, business settings, analytics overview
5. **Lead Management** — capture from storefront/WhatsApp, basic CRM, WhatsApp follow-up

### Defer to V1.1

- TikTok/LinkedIn publishing
- Email marketing sequences
- Broadcast sequences
- WhatsApp Channels
- Advanced analytics (competitor, attribution)
- Teams/multi-brand

### Defer to V2

- Partner marketplace
- QR/Walk-in attribution
- Shopify integration
- A/B testing
- Profile audit
- Advanced nurture sequences

### Remove/Archive

- Legacy `campaigns` app (already empty)
- `media_queue` references
- Duplicate `kova_page` app (use `links.KovaPage`)
- Unused `fundraising/` and `marketing/` directories from runtime

---

## Critical Path to Launch

1. **Simplify the web dashboard** — replace the 16-section brief/dashboard with a clean orchestration view
2. **Validate WhatsApp commerce flow end-to-end** — browse → order → pay → confirm
3. **Harden the publishing pipeline** — Facebook + Instagram must be rock-solid
4. **Remove non-V1 UI** — hide features deferred to V1.1/V2
5. **Production deployment hardening** — Sentry, rate limits, token refresh reliability

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| WhatsApp API rate limits | Blocked commerce | Implement backoff + queue priority |
| Meta token expiry | Publishing fails silently | Token health monitoring already exists |
| LLM cost overrun | Budget exceeded | Token bucket system exists; tune limits |
| Feature scope creep | Launch delay | Strict V1 scope gate |
| Single-point-of-failure (Railway) | Downtime | Health checks + alerting exist |

---

## Conclusion

Kova has a remarkably complete foundation for a WhatsApp-first AI business OS. The core intelligence, commerce, and messaging infrastructure exists. The primary risk is not missing functionality — it is **excess complexity** from features that don't serve the V1 promise. A disciplined scope reduction, combined with end-to-end validation of the WhatsApp commerce flow, will yield a launch-ready product within the target timeline.
