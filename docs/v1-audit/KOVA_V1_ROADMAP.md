# Kova V1 Roadmap

**Date:** July 2026
**Target Launch:** August 2026

---

## Phase 1: Stabilization (Week 1-2)

**Goal:** Remove noise, fix debt, establish V1 baseline.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Remove `campaigns` from INSTALLED_APPS | P0 | 1h | Backend |
| Remove `media_queue` dead code | P0 | 30m | Backend |
| Hide non-V1 features from navigation | P0 | 4h | Frontend |
| Consolidate 3 inbox views into 1 | P1 | 8h | Frontend |
| Simplify dashboard homepage (brief-first) | P1 | 12h | Frontend |
| Simplify analytics to single page | P1 | 8h | Frontend |
| Remove profile audit from navigation | P0 | 30m | Frontend |
| Remove compare/campus pages from app routes | P0 | 1h | Backend |
| Exclude `fundraising/` and `marketing/` from Docker | P1 | 1h | DevOps |
| Squash stable app migrations | P2 | 4h | Backend |

**Milestone:** Clean codebase with V1-only UI surface.

---

## Phase 2: WhatsApp Flow Validation (Week 2-3)

**Goal:** End-to-end validation of all WhatsApp flows.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| E2E test: Customer browse → order → M-Pesa → confirmation | P0 | 8h | QA |
| E2E test: Owner STANDUP → APPROVE → SNAP workflow | P0 | 4h | QA |
| E2E test: Daily Brief generation + delivery | P0 | 4h | QA |
| E2E test: FAQ Autopilot accuracy | P0 | 4h | QA |
| E2E test: Snap-to-Sell photo → product → storefront | P0 | 4h | QA |
| Validate WhatsApp template approval flow | P0 | 4h | Backend |
| Test M-Pesa callback reliability (sandbox + live) | P0 | 8h | Backend |
| Validate token refresh for Facebook/Instagram | P0 | 4h | Backend |
| Load test: 100 concurrent WhatsApp conversations | P1 | 8h | Backend |
| Test commerce bot edge cases (out of stock, invalid input) | P1 | 4h | QA |

**Milestone:** All critical WhatsApp flows validated end-to-end.

---

## Phase 3: Publishing Pipeline Hardening (Week 3-4)

**Goal:** Ensure content generation and publishing is reliable.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Validate Create Agent output quality (10 businesses) | P0 | 8h | AI/QA |
| Test publish pipeline: seed → post → schedule → publish | P0 | 8h | Backend |
| Validate content safety gates (test with borderline content) | P0 | 4h | AI |
| Confirm Facebook Page publishing works for 5 test accounts | P0 | 4h | QA |
| Confirm Instagram publishing works for 5 test accounts | P0 | 4h | QA |
| Test token expiry + refresh recovery | P1 | 4h | Backend |
| Validate platform outage detection | P1 | 2h | Backend |
| Confirm metrics collection post-publish | P1 | 4h | Backend |
| Test Engage Agent reply quality | P1 | 4h | AI |
| Validate Adapt Agent doesn't diverge wildly | P1 | 4h | AI |

**Milestone:** Publishing pipeline proven reliable across Facebook + Instagram.

---

## Phase 4: Commerce & Payments (Week 3-4, parallel with Phase 3)

**Goal:** Validate the full commerce experience.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Test public storefront with 50+ products | P0 | 4h | QA |
| Validate M-Pesa STK Push → confirmation → receipt | P0 | 8h | Backend |
| Test booking flow: page → select → confirm → WhatsApp | P0 | 4h | QA |
| Validate Snap-to-Sell with varied product photos | P0 | 4h | AI |
| Test commerce bot with 10+ product catalogs | P1 | 4h | QA |
| Verify stock-aware ordering (out-of-stock handling) | P1 | 4h | Backend |
| Test lead capture from storefront → CRM | P1 | 2h | QA |
| Validate commerce link sharing (social preview/OG tags) | P1 | 2h | Frontend |

**Milestone:** Commerce flow proven from discovery to payment.

---

## Phase 5: Production Readiness (Week 4-5)

**Goal:** Ensure system is ready for real users.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Sentry error monitoring configured + tested | P0 | 2h | DevOps |
| Rate limiting validated (WhatsApp, API, auth) | P0 | 4h | Backend |
| Celery queue health monitoring | P0 | 4h | DevOps |
| Database backup + restore procedure tested | P0 | 4h | DevOps |
| SSL/security headers validated | P0 | 2h | DevOps |
| Token budget limits validated per plan | P1 | 4h | Backend |
| Onboarding flow tested (signup → Business Brain → first brief) | P0 | 8h | QA |
| Performance: page load < 2s for all V1 pages | P1 | 8h | Frontend |
| Performance: WhatsApp message response < 5s | P0 | 4h | Backend |
| Admin dashboard: critical monitoring views work | P1 | 4h | QA |

**Milestone:** Production environment validated.

---

## Phase 6: Soft Launch (Week 5-6)

**Goal:** Controlled rollout to pilot businesses.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Onboard 5-10 pilot businesses | P0 | 20h | Product |
| Monitor WhatsApp delivery rates | P0 | Ongoing | Ops |
| Monitor AI quality (content, replies) | P0 | Ongoing | AI |
| Monitor M-Pesa payment success rates | P0 | Ongoing | Ops |
| Collect pilot feedback (WhatsApp-first experience) | P0 | Ongoing | Product |
| Fix critical bugs from pilot feedback | P0 | Variable | Backend |
| Validate Daily Brief engagement rates | P1 | Ongoing | Product |
| Monitor LLM costs vs. token budgets | P1 | Ongoing | Ops |

**Milestone:** Pilot businesses actively using Kova via WhatsApp.

---

## Phase 7: Public Launch (Week 6-8)

**Goal:** Open registration + marketing push.

### Tasks

| Task | Priority | Effort | Owner |
|------|----------|--------|-------|
| Open public registration | P0 | 2h | Backend |
| Launch marketing (landing page, social) | P0 | Variable | Marketing |
| Scale infrastructure (Railway autoscaling) | P0 | 4h | DevOps |
| Customer support workflow established | P0 | 8h | Ops |
| Monitor signup → activation funnel | P0 | Ongoing | Product |
| Scale Celery workers based on load | P1 | 4h | DevOps |
| LLM cost monitoring at scale | P1 | Ongoing | Ops |

**Milestone:** Kova V1 publicly available.

---

## Timeline Summary

```
Week 1-2:  Stabilization (remove debt, simplify UI)
Week 2-3:  WhatsApp flow validation
Week 3-4:  Publishing + Commerce hardening
Week 4-5:  Production readiness
Week 5-6:  Pilot launch (5-10 businesses)
Week 6-8:  Public launch
```

---

## Success Metrics for V1

| Metric | Target |
|--------|--------|
| WhatsApp message response time | < 5 seconds |
| Publishing success rate | > 95% |
| M-Pesa payment completion | > 80% |
| Daily Brief delivery rate | > 95% |
| Owner WhatsApp engagement | > 60% open brief daily |
| Content quality (owner approval rate) | > 70% |
| System uptime | > 99.5% |
| Time from signup to first published post | < 24 hours |

---

## Post-V1 Roadmap Preview

### V1.1 (Month 2-3 post-launch)
- TikTok publishing
- LinkedIn publishing
- WhatsApp broadcast sequences
- Email marketing basics
- Advanced analytics
- Review request loop
- Video/Reel generation

### V2 (Month 4-6 post-launch)
- Teams / Multi-brand
- Partner marketplace
- QR attribution
- A/B testing
- Shopify integration
- Advanced CRM
- WhatsApp-editable Brain
- Voice-note-to-action
