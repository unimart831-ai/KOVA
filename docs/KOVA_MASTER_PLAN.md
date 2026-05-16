# Kova Master Plan — Closing the Marketing-Engineering Gap

> The single tracking doc for everything coming out of the cofounder audit
> (Nov 2025 / May 2026). Sourced from three layered audits — nav tabs,
> functionality vs. promise, and a codebase scan of Adapt/Engage/Revenue.
>
> **Discipline:** all of it, in sequence. Each phase makes the next honest.
> Tabs and polish come last. Truth comes first.

---

## The Atom of Value (hold this against every commit)

> **Kova replaces the work of an 8-person marketing department for an African
> SME at KES 299/month, requiring 3 minutes a day of owner time.**

If a feature doesn't move us toward that promise, it waits. If a claim isn't
backed by code, we either build it or rename it.

---

## The Three Hollow Promises (the audit's central finding)

These are non-negotiable to fix. Everything else is downstream.

| Marketing claim | Code reality | Fix in plan |
|---|---|---|
| *"AI learns and adjusts."* | Adapt Agent is a scheduler — mutates only `Post.scheduled_at`. No recurring autonomous cycle. No mutation of UserProfile / pillars / cadence. | **Phase 1, Weeks 3-4** |
| *"AI runs your customer conversations."* | Engage Agent is suggest-only on social. WhatsApp auto-sends only at confidence ≥ 0.8. `auto_engage` flag misleads. | **Phase 1, Week 2** |
| *"We tell you which post made you money."* | Pixel + revenue models built. `get_revenue_summary()` exists. **No view renders it.** Daily Brief LLM asks for "1-2 generic sentences." Post→Pixel attribution fragile (most posts lack UTM params). | **Phase 1, Week 1** |

---

## Execution Order (and why)

```
PHASE 1 — Make the Central Claims True              (Month 1)
  W1   Revenue Dashboard
  W2   Engage Agent graduated autonomy
  W3-4 Adapt Agent v2 (real learning loop)

PHASE 2 — Africa-Native Moats                        (Month 2)
  W5-6 Walk-in / QR-code attribution
  W7-8 Booking integration (native + Calendly)

PHASE 3 — Polish, Subtract, Surface                  (Month 3)
  W9    Review request loop
  W10-11 Nav refactor (21 → 9 tabs)
  W12   Daily Brief 10× action-tense rewrite

PHASE 4 — Tier 3 Onboarding Polish                   (Sprint after)
  Silent URL inference on field blur
  WhatsApp Magic Fill (audit_profile for WABA)
  Queue → calendar view
  Performance → plain-English insights
```

**Why this order:**
- **Phase 1 first** — every claim becomes defensible. We can fundraise and sell without the marketing-engineering gap.
- **Phase 2 next** — Africa-native moats no Western tool has. The walk-in QR and booking are existential for our flagship industries (salon, restaurant, real estate, retail).
- **Phase 3 last** — nav reshape polishes an experience that's now honest. Reshaping before that is polishing a misleading product.
- **Phase 4 is polish** — nice-to-have only after the core is true.

---

## Phase 1 — Make the Central Claims True (Month 1)

### Week 1 — Revenue Dashboard

The lowest-risk, highest-leverage first move. The data already exists; we
just don't surface it. Fix that.

- [ ] **W1.1** UTM injection in publishing pipeline — every Kova-published post auto-appends `?utm_source=kova&utm_medium=<platform>&utm_content=<post_id>` to any link it carries, so Pixel can attribute clicks back to the originating post
- [ ] **W1.2** New view `/dashboard/revenue/` rendering `get_revenue_summary()` — top 10 posts by attributed revenue, top 3 channels, "post X drove KES Y" headline
- [ ] **W1.3** Daily Brief revenue prompt rewrite — replace "1-2 sentences if revenue data exists" with "Name the single highest-revenue post in the window. State the revenue. Recommend the next action."
- [ ] **W1.4** Add a stat-card on the home dashboard: last 7d attributed revenue, MoM delta
- [ ] **W1.5** Tests + smoke check + commit/push

**Deliverable:** A salon owner logs in, clicks Revenue, sees "Your IG post about the silk-press special drove KES 12,400 last week. 8 walk-ins attributed."

### Week 2 — Engage Agent Graduated Autonomy for Social

Port the WhatsApp confidence-graded auto-send to Instagram, Facebook, LinkedIn
comments + DMs.

- [ ] **W2.1** Add confidence scoring to `engage_agent.generate_reply()` for social platforms (same model as WhatsApp `whatsapp/tasks.py:35-172`)
- [ ] **W2.2** Replace `auto_engage` boolean with `engage_autonomy_level` enum: `OFF / SUGGEST / GRADUATED / AGGRESSIVE`
- [ ] **W2.3** GRADUATED mode = auto-send when confidence ≥ 0.85; queue 0.5-0.85 as drafts; escalate <0.5 — same thresholds as WhatsApp
- [ ] **W2.4** Plan tier gating: Starter = SUGGEST only; Growth+ unlocks GRADUATED; Agency unlocks AGGRESSIVE (≥0.70 threshold)
- [ ] **W2.5** Undo-with-correction loop: every auto-sent reply has 1-click "undo / I would have said this instead" — the correction feeds back as a learning signal in the prompt for that user
- [ ] **W2.6** Migration to remap existing `auto_engage=True` users → `engage_autonomy_level=SUGGEST` (no surprise auto-sends)
- [ ] **W2.7** Tests + commit/push

**Deliverable:** A restaurant gets 30 DMs/day. Engage Agent auto-replies to 18 high-confidence ones ("What time you close?" → "Open till 11pm tonight 🙏"). Queues 9 as drafts. Escalates 3. Owner does 12 actions instead of 30.

### Weeks 3-4 — Adapt Agent v2 (the real learning loop)

This is the most ambitious piece of Phase 1 and the most damaging hollow
claim today.

- [ ] **W3.1** Spec doc — pin the exact behaviour list (what it watches, what it mutates, what thresholds trigger action) before code
- [ ] **W3.2** New Celery Beat entry: `run-adapt-cycle` every 12h
- [ ] **W3.3** Read last 30 days of Post performance grouped by Content DNA attribute (hook type, format, tone, length, pillar)
- [ ] **W3.4** Promote logic: any DNA combo with engagement ≥ 1.5× user median → flagged "high-performing"; bias future Create Agent system prompts toward it
- [ ] **W3.5** Retire logic: any DNA combo with engagement < 0.5× median after ≥5 posts → flagged "deprioritised"; exclude from generations
- [ ] **W3.6** Mutate `UserProfile.pillar_weights` (new field) so high-performing pillars rotate more
- [ ] **W3.7** Mutate `UserProfile.posting_frequency` when consistent under/over-performance detected
- [ ] **W3.8** Surface in Daily Brief: "I've started favouring [X] — last 3 posts using it got 3× average. I retired [Y] — last 5 posts averaged 0.2%."
- [ ] **W3.9** Audit log in `AgentAction` of every promote/retire decision (reversible)
- [ ] **W3.10** Rename `Adapt Agent` from "Optimize posting times" to "Learning Loop" in lifecycle docs once shipped
- [ ] **W3.11** Tests + commit/push

**Deliverable:** A user 60 days in opens Kova and sees "I've learned about your business: your transformation Reels get 2.4× your average. I'm posting more of them. Tuesday mornings outperform — I've shifted your scheduling there."

---

## Phase 2 — Africa-Native Moats (Month 2)

### Weeks 5-6 — Walk-in / QR-code Attribution

No Western tool does this. For our flagship industries (salon, restaurant,
retail), 70%+ of conversions are walk-ins.

- [x] **W5.1** New `qr_attribution` Django app
- [x] **W5.2** `QRCode` model linked to Campaign + Post optionally; carries `token`
- [x] **W5.3** Public `/qr/<token>/` endpoint — logs `QRScan`, sets visitor cookie, renders landing
- [x] **W5.4** Five landing templates (discount / menu / booking / follow / custom) — owner picks at QR creation
- [x] **W5.5** Generation UI at `/qr/new/` — one click + template-specific fields
- [x] **W5.6** Print-pack PDF (receipt sticker, counter sticker, A5 flyer)
- [x] **W5.7** Cashier UI at `/walkin/<slug>/` — phone-friendly button grid, no login
- [x] **W5.8** `WalkInEvent` rolls into `get_revenue_summary` (totals.walkin_revenue + merged platform_revenue)
- [x] **W5.9** 28 tests passing (`tests/test_qr_attribution.py`)
- [x] **W5.10** `apps/analytics/revenue.py` rollup (digital + walk-ins → unified `total_revenue`)
- [x] **W5.11** "Walk-ins" nav link under Money
- [x] **W5.12** Test suite — model invariants, all 5 templates, cashier UI, visitor_id → scan linkage, rollup
- [x] **W5.13** Django admin registration for `QRCode`, `QRScan`, `WalkInEvent`

**Deliverable:** Kawaida prints a flyer with a Kova QR code. Customer scans → lands on welcome page → walks in → stylist taps "Insta" on cashier UI → KES 3,500 service attributed to the Instagram campaign. Revenue dashboard shows it.

### Weeks 7-8 — Booking Integration

For Kawaida (salon), Makao (real estate), Amara (fitness) — the conversion
is a booking, not a click.

- [x] **W7.1** New `bookings` app
- [x] **W7.2** `BookingLink` + `Booking` models
- [x] **W7.3** Industry templates (salon / real_estate / fitness / consultant / clinic / generic)
- [x] **W7.4** Kova-hosted booking page at `/book/<slug>/` (mobile-first, slot picker)
- [x] **W7.5** WhatsApp template signals for customer + owner confirmations (soft-fail on send error)
- [x] **W7.6** Engage Agent booking intent detection + auto-link augmentation (`apps/agents/booking_intent.py`)
- [x] **W7.7** Booking revenue rolls into `get_revenue_summary` (totals.booking_revenue + total_revenue)
- [ ] **W7.8** Calendly OAuth provider — deferred to Phase 3 backlog (v2 ships Kova-hosted only)
- [x] **W7.9** 38 tests passing (`tests/test_bookings.py`)

**Deliverable:** Kawaida's customer DMs "can I book braids Saturday?" Engage Agent replies "Yes — Saturday 10am or 2pm work. Tap to confirm: kova.link/book/kawaida". Customer taps, picks 2pm, booking created, customer + Kawaida both get WhatsApp confirmation. Revenue Dashboard tracks it as Engage Agent → Booking conversion.

---

## Phase 3 — Polish, Subtract, Surface (Month 3)

### Week 9 — Review Request Loop

- [ ] **W9.1** Trigger on `Lead.status = converted` OR `Booking.status = completed`
- [ ] **W9.2** WhatsApp template review request (24h after conversion)
- [ ] **W9.3** Email fallback if no WhatsApp
- [ ] **W9.4** Positive responses (sentiment ≥ 0.7) → auto-create content seed: "Customer says…"
- [ ] **W9.5** Negative responses → escalate to owner via Daily Brief
- [ ] **W9.6** Tests + commit/push

### Weeks 10-11 — Nav Refactor (21 → 9 Tabs)

From the nav audit, with autonomy now real behind it:

- [ ] **W10.1** Promote Daily Brief to home (`/`)
- [ ] **W10.2** Merge: Visual Publisher → Studio
- [ ] **W10.3** Merge: Timeline → Queue (filter: scheduled/published/failed)
- [ ] **W10.4** Merge: Trending → Studio (auto-suggested seeds)
- [ ] **W10.5** Merge: Competitors → Performance (as a view)
- [ ] **W10.6** Move to Settings: Agents, Pixel, Platforms, Billing, Help
- [ ] **W10.7** Tier-gate: Teams (Agency only), Products (industry-conditional), A/B Tests (Growth+)
- [ ] **W10.8** Group remaining 9 by user job: Home / Create / Schedule / Conversations / Money / Insights / Settings
- [ ] **W11.1** Update all internal links + navigation tests
- [ ] **W11.2** Commit/push

### Week 12 — Daily Brief 10× Rewrite

- [ ] **W12.1** Rewrite Daily Brief LLM system prompt: action-tense, AI-first-person
- [ ] **W12.2** Structure: "I did X. I replied to Y. I learned Z. Here's the lead I couldn't handle. Recommended next move."
- [ ] **W12.3** Surface Adapt Agent v2 learnings prominently
- [ ] **W12.4** Surface Engage autonomy results (auto-sent count + escalations)
- [ ] **W12.5** Tests + commit/push

---

## Phase 4 — Tier 3 Onboarding Polish (after Phase 3)

Less urgent than the central work but committed to:

- [ ] **P4.1** Silent URL inference on `website_url` field blur (no opt-in button)
- [ ] **P4.2** WhatsApp into Magic Fill — `audit_profile` for WABA provider
- [ ] **P4.3** Queue → calendar view (drag-to-reschedule, per-platform preview)
- [ ] **P4.4** Performance → plain-English insights, not charts
- [ ] **P4.5** Founder bandwidth: WhatsApp template approval for completion ping (currently no-op without it)

---

## Things We're STOPPING Today

From the cofounder audit:

- [ ] **S.1** Stop calling Adapt Agent "autonomous learning" in marketing/docs until W3-4 ships — rename to "Smart Scheduler" in the interim
- [ ] **S.2** Stop adding nav tabs — anything new ships inside an existing tab until Phase 3
- [ ] **S.3** Stop using `auto_engage` boolean in any new code; will be deprecated in W2
- [ ] **S.4** Stop weighting 9 platforms equally in UI — IG/FB/WhatsApp surface first in any new UX
- [ ] **S.5** Stop adding more data-capture features until consumers (dashboards) are built

---

## Out of Scope (acknowledged, not in this 90 days)

These are real gaps but not on this plan. Adding them now spreads us thin.

- [ ] **OOS.1** Customer CRM depth beyond Lead model improvements
- [ ] **OOS.2** Reels-first / vertical-video generation pipeline
- [ ] **OOS.3** Voice / Spaces / audio room support
- [ ] **OOS.4** Influencer / affiliate tracking layer
- [ ] **OOS.5** Sheng / Swahili SEO layer
- [ ] **OOS.6** Group / community management (WhatsApp groups, FB groups)
- [ ] **OOS.7** Direct-message broadcasts on Instagram (when API supports)

---

## Tracking

- **Started:** 2026-05-13
- **Target completion:** 2026-08-13 (3 months from start)
- **Update cadence:** check off items as PRs merge; review weekly
- **Single source of truth:** this file. If it's not here, it's not in the plan.

---

## Cofounder Note

The temptation will be to do all of this in parallel. We won't. Each phase
makes the next one honest. Marketing claims can't be defended until Phase 1
is shipped. Africa-native moats can't be sold until they exist. Nav cleanup
polishes an experience that needs to be true first.

**The order is the discipline.**
