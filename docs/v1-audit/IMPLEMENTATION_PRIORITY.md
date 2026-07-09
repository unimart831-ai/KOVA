# Implementation Priority

**Date:** July 2026

---

## Priority Framework

Priorities are assigned based on:
- **Impact on V1 promise** — does this directly enable "manage via WhatsApp"?
- **Risk if not done** — what breaks or fails at launch?
- **Effort** — how long does this take?
- **Dependencies** — does other work depend on this?

---

## P0 — Critical (Must Complete Before Launch)

These items represent launch blockers. If any fails, the V1 promise cannot be delivered.

### Infrastructure & Cleanup

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 1 | Remove `campaigns` from INSTALLED_APPS | 1h | Dead weight; potential migration confusion |
| 2 | Remove `media_queue` dead code from `media/tasks.py` | 30m | Celery Beat may attempt to run non-existent task |
| 3 | Hide non-V1 features from navigation (teams, partners, QR, reviews, email marketing, competitors) | 4h | Prevents user confusion; focuses UX on V1 features |
| 4 | Validate environment variables for production (all API keys, tokens, secrets) | 2h | Missing keys = silent failures |
| 5 | Ensure health check endpoint validates all critical services | 2h | Railway deployment monitoring |

### WhatsApp

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 6 | End-to-end test: inbound message → AI reply → delivery confirmation | 4h | Core promise validation |
| 7 | End-to-end test: commerce flow (browse → order → M-Pesa → receipt) | 8h | Revenue-critical path |
| 8 | Validate WhatsApp template approval + delivery for all key templates | 4h | Templates must be pre-approved by Meta |
| 9 | Test Daily Brief generation + WhatsApp delivery for 10 test users | 4h | Primary engagement mechanism |
| 10 | Validate owner commands work (APPROVE, REJECT, LEADS, MONEY, SNAP) | 4h | Owner daily operations |

### Publishing

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 11 | Validate Facebook publishing with live page tokens | 4h | Primary publishing target |
| 12 | Validate Instagram publishing with live account tokens | 4h | Primary publishing target |
| 13 | Test token refresh works before expiry | 4h | Prevents silent publishing failures |
| 14 | Validate content safety gates catch explicit content | 2h | Brand reputation protection |
| 15 | Test scheduled post publishing (celery beat → publish task) | 4h | Autonomous operation |

### Commerce

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 16 | Validate M-Pesa STK Push in production sandbox | 8h | Payment reliability |
| 17 | Test public storefront loads correctly with products | 4h | Customer discovery surface |
| 18 | Validate Snap-to-Sell (photo → product creation) | 4h | WhatsApp-native product management |

### Onboarding

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 19 | Test full signup → onboarding → Business Brain → first brief flow | 8h | First-run experience |
| 20 | Validate onboarding intelligence chain (research → seeds → content) | 4h | Automated Day 1 value delivery |

---

## P1 — High (Should Complete Before Launch)

These items significantly improve the launch quality but aren't strict blockers.

### UX Simplification

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 21 | Redesign dashboard homepage (brief-first, 3 sections max) | 12h | Web should feel like orchestration, not workspace |
| 22 | Consolidate 3 inbox views into single unified inbox | 8h | Reduces confusion |
| 23 | Simplify analytics to single insights page | 8h | V1 doesn't need 13 analytics pages |
| 24 | Remove competitor pages from navigation | 1h | V2 feature |
| 25 | Remove pixel/attribution pages from navigation | 1h | V2 feature |

### Reliability

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 26 | Configure Sentry with proper alert thresholds | 4h | Error visibility |
| 27 | Validate Celery queue health (tasks not backing up) | 4h | Autonomous operations depend on task execution |
| 28 | Rate limit WhatsApp webhook endpoint | 2h | Prevent abuse |
| 29 | Rate limit public storefront endpoints | 2h | Prevent abuse |
| 30 | Validate token budget enforcement per plan tier | 4h | Cost control |

### Quality

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 31 | Review Create Agent output quality with 10 diverse businesses | 8h | Content must be good enough to auto-publish |
| 32 | Review Engage Agent reply quality with edge cases | 4h | Bad auto-replies damage brand |
| 33 | Test Business Brain extraction with varied onboarding answers | 4h | Brain quality drives all AI output |
| 34 | Validate WhatsApp commerce bot edge cases | 4h | Bad commerce UX = lost sales |
| 35 | Test notification delivery (WebSocket + in-app) | 2h | User awareness of system actions |

---

## P2 — Medium (Complete in V1.1)

Valuable improvements that can wait until after launch.

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 36 | Add product management WhatsApp commands (PRICE, STOCK) | 12h | Enhances WhatsApp-first experience |
| 37 | Add customer message forwarding to owner WhatsApp | 8h | Reduces need to check web inbox |
| 38 | Implement voice note → content/product creation | 12h | Transcription exists; needs routing |
| 39 | Add TikTok publishing (validate app approval) | 8h | Growing platform in Africa |
| 40 | Add LinkedIn publishing | 4h | Provider exists; needs testing |
| 41 | Implement WhatsApp broadcast sequence management | 8h | Advanced engagement |
| 42 | Add performance recycle (republish best content) | 4h | Growth feature |
| 43 | Implement review request loop | 8h | Post-purchase engagement |
| 44 | Enable email marketing (campaigns) | 8h | Secondary channel |
| 45 | Rename duplicate models for clarity | 8h | Technical debt reduction |
| 46 | Consolidate Photoroom files (18 → 6) | 12h | Maintenance reduction |

---

## P3 — Low (Complete in V2)

Strategic features for platform maturity.

| # | Task | Effort | Rationale |
|---|------|--------|-----------|
| 47 | Implement Teams/multi-brand support | 40h | Agency use case |
| 48 | Launch partner marketplace | 40h | B2B growth channel |
| 49 | Implement QR attribution + walk-in tracking | 20h | Physical retail bridge |
| 50 | Build A/B testing workflow | 20h | Optimization feature |
| 51 | Integrate Shopify | 20h | E-commerce bridge |
| 52 | Implement Kova Pixel analytics | 12h | Website attribution |
| 53 | Build advanced CRM (pipeline, kanban) | 20h | Full CRM feature |
| 54 | Move Django project package from `docs/config/` to `config/` | 8h | Architecture cleanup |
| 55 | Extract Business Brain to dedicated model | 12h | Data architecture |

---

## Sprint Allocation (4-Week Pre-Launch)

### Sprint 1 (Week 1)

| Developer | Tasks |
|-----------|-------|
| Backend 1 | P0 #1-5 (cleanup), P0 #6-7 (WhatsApp E2E) |
| Backend 2 | P0 #11-15 (publishing validation) |
| Frontend | P0 #3 (hide features), P1 #21 (dashboard redesign) |
| QA | P0 #9-10 (brief + commands testing) |

### Sprint 2 (Week 2)

| Developer | Tasks |
|-----------|-------|
| Backend 1 | P0 #8 (templates), P0 #16-18 (commerce) |
| Backend 2 | P0 #19-20 (onboarding), P1 #26-30 (reliability) |
| Frontend | P1 #22-25 (inbox consolidation, nav cleanup) |
| QA | P1 #31-35 (quality validation) |

### Sprint 3 (Week 3)

| Developer | Tasks |
|-----------|-------|
| All | Bug fixes from Sprint 1-2 testing |
| Backend | Performance optimization (response times) |
| Frontend | Final UI polish |
| QA | Full regression pass |

### Sprint 4 (Week 4)

| Developer | Tasks |
|-----------|-------|
| All | Pilot onboarding, monitoring, bug fixes |
| Ops | Production environment validation |
| Product | Pilot feedback collection |

---

## Definition of Done (Per Task)

A task is complete when:
1. Code is implemented and passes lint/type checks
2. Relevant tests pass (existing + new if applicable)
3. Manually verified in staging environment
4. No regressions in smoke test suite
5. Deployed to production (after Sprint 3)

---

## Risk Mitigation

| Risk | Mitigation | Owner |
|------|------------|-------|
| Meta WhatsApp API instability | Test with sandbox first; have template fallbacks | Backend |
| M-Pesa sandbox ≠ production behavior | Allocate extra testing time for live M-Pesa | Backend |
| LLM quality regression | A/B test agent outputs with pilot users | AI |
| Feature scope creep | Strict adherence to V1 scope doc; all additions go to V1.1 | Product |
| Token expiry during launch | Run token health check daily; alert on expiring tokens | Ops |
| Celery task backlog at scale | Monitor queue depth; auto-scale workers | DevOps |
