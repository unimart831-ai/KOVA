# KOVA System Section Ratings

**Scan date:** June 11, 2026  
**Codebase:** `kova_agent` (27 apps, Phase 2 sidebar IA)  
**Positioning:** *"The system that chases money for my business while I run the shop."*

---

## Score legend

| Range | Meaning |
|-------|---------|
| **8–10** | Production-ready or near — core flows work, tests/docs exist, minor gaps only |
| **5–7** | Pilot-ready / Beta — usable with known gaps, external deps, or UX debt |
| **Below 5** | Stub, broken-risk, or misaligned with positioning — avoid leading with this in GTM |

**Status labels:** Production-ready · Pilot-ready · Beta · Stub · Broken-risk

---

## Executive summary

### Overall platform score: **7.6 / 10** (weighted) → **~8.4 / 10** post-P0 → **~8.9 / 10** post-Phase 2 (June 11, 2026)

*Updated post-Phase 2:* See `KOVA_SCORE_9_5_ROADMAP.md` for P0 + Phase 2 completion and path to 9.5.

**Weighting:** ~80% user-facing product sections, ~20% infrastructure.

KOVA is an unusually deep pre-launch SMB platform: full Sell → Catch → Close → Grow loop, Kenya-native billing, six AI agents, attribution, and a staff ops dashboard. Phase 2 sidebar IA (`Today → Sell → Catch → Close → Grow → Settings`) aligns well with the money-chase frame. The main drag is **complexity vs. shop-floor UX** (Workspace, Performance, plan gates on WhatsApp/Engage), **partial platform resilience**, and **Meta Live / Pro-tier dependencies** on the core wedge.

### Top 5 strengths

1. **Today money board + wedge checklist** — `apps/briefs/dashboard.py`, `apps/accounts/wedge_checklist.py`, `tests/test_money_board.py`, `tests/test_wedge_checklist.py`; sidebar mission strip in `app.html`.
2. **Full-funnel revenue attribution** — UTM → pixel → conversions; `tests/test_revenue_attribution.py`, `tests/test_qr_attribution.py`.
3. **Six-agent engine with safety rails** — Research/Create/Adapt/Engage/Analyst/Strategist; budget caps in `apps/agents/budget.py`; `tests/test_engage_routing.py` (53 tests).
4. **Africa-native billing** — M-Pesa STK + Stripe, Plan v2 in `apps/billing/models.py`; `tests/test_billing.py`, `tests/test_plan_limits_v2.py`.
5. **Ops maturity** — Content safety pipeline + admin dashboard (~100 routes in `apps/admin_dashboard/urls.py`); `tests/test_content_safety.py`, `tests/test_admin_dashboard_surfaces.py`.

### Top 5 fixes (prioritized)

1. **Unblock the 90-day wedge for Growth users** — WhatsApp is Pro-only (`whatsapp_enabled`); Engage is Starter-gated. Kenya wedge doc assumes WA + IG for all paying tiers.
2. **Close money-loop gaps** — QR scan → lead (deferred in `REACH_LEAD_AUTOMATION_AUDIT.md`), WA nurture step in Automations UI (`KOVA_USER_GUIDE` §8), money-board push notifications (deferred in `KOVA_AUTOPILOT.md`).
3. **Finish platform resilience** — Rate-limit 3-strike UX and outage queue hold still partial per `PLATFORM_RESILIENCE.md`.
4. **Reduce nav / positioning friction** — Merge Revenue + Performance; fold Workspace into Today for Starter; hide "10 platforms" on landing until X/YouTube/Threads ship (`COMING_SOON_PLATFORMS` in `apps/platforms/views.py`).
5. **Harden production security** — Cofounder audit issues (hardcoded secrets, CSP `unsafe-inline`, webhook signature enforcement) remain relevant despite CI security job.

### Comparison to positioning ("chases money while you run the shop")

| Aligned | Misaligned |
|---------|------------|
| Today money board (needs reply, hot leads, approve) | Workspace / Command buried but still power-user heavy |
| Wedge checklist (WA → IG → Snap → publish → lead) | WhatsApp + full Engage require Pro/Growth gates |
| REACH + WA inbox + M-Pesa commerce | Studio/Queue/Performance compete for attention vs. 5-min ritual |
| Sidebar "Money chase" strip | Landing claims "10 platforms" vs. 7 active connect |
| Autopilot safe-defaults-off | Content Autopilot + Ops Autopilot split across Studio vs Settings |

---

## Core / Today

### Home / Today (money board, brief, wedge checklist)
**Score: 8/10** → **8.7/10** post-P0 → **9.0/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- Money board aggregates WA escalations + Engage inbox + hot leads + approvals (`get_money_board_stats` in `apps/briefs/dashboard.py`).
- Five-step wedge checklist with 30-day TTL (`apps/accounts/wedge_checklist.py`).
- Cached home extras, revenue stat card, operations report, daily brief integration.

**Weaknesses**
- No proactive money-board push/email (explicitly deferred in `KOVA_AUTOPILOT.md`).
- Home still dense for true 5-min ritual (momentum, profile health, value summary alongside money board).
- Brief delivery depends on Celery + user timezone configuration.

**Recommendations**
1. Ship daily WhatsApp/email digest: "X need reply, Y hot leads" (P0 for positioning).
2. For Starter users, collapse non-money widgets below the fold.
3. Add E2E test: signup → wedge step 1 visible on Today.
4. Surface M-Pesa pending payments on money board when commerce enabled.
5. Link each money-board card to filtered views (WA escalated only, not generic inbox).

**Dependencies / blockers:** Celery beat `briefs.generate_all_daily_briefs`; optional WhatsApp brief channel (Pro+).

---

## Sell

### Snap / Snap2sell / Commerce
**Score: 8/10**  
**Status:** Production-ready (wedge demo)

**Strengths**
- Full pipeline: snap launch, batch, vision, carousel, reel compose (`apps/products/views.py`, `tests/test_snap_pipeline.py`, `tests/test_batch_snap_market_day.py`).
- Photoroom polish with metering (`tests/test_photoroom_*.py`, `apps/billing/visual_credits.py`).
- Content safety gates on upload (`docs/CONTENT_SAFETY.md`).

**Weaknesses**
- Snap block / strike UX is punitive without in-app education.
- Commerce reel/autopilot paths add complexity beyond "photo → offer → WA."
- Platform-specific publish gaps (e.g. FB Reels per `docs/platform-audits/FACEBOOK.md`).

**Recommendations**
1. Default post-snap CTA: share to WhatsApp Status + IG (one-tap wedge path).
2. Gate advanced reel director behind Pro or "More."
3. Add snap-to-WA deep link on product detail.
4. Run `seed_test_businesses` Mara & Moto scenario as quarterly regression.
5. Show time-to-listing metric on Today after first snap.

**Dependencies / blockers:** OpenRouter/vision for analyze; Meta publish for go-live; Photoroom API credits.

### Products / catalog (My offers)
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- Catalog, categories, stock, M-Pesa commerce (`mpesa_commerce` plan flag).
- Shopify webhook tests (`tests/test_shopify_integration.py`).
- SEO and showcase tests (`tests/test_commerce_seo.py`, `tests/test_catalog_showcase.py`).

**Weaknesses**
- Catalog management is secondary to snap flow in nav/UX.
- Starter plan limits may frustrate multi-SKU retailers.
- Inventory alerts Celery task exists but user-facing surfacing is thin.

**Recommendations**
1. Unify "Commerce" subnav: Snap, Batch, Offers, Orders in one expanded group.
2. Promote low-stock alerts on Today money board.
3. Simplify M-Pesa STK flow copy for non-technical shop owners.
4. Add catalog → REACH link generator per product.
5. Document Shopify vs. native catalog decision in onboarding.

**Dependencies / blockers:** M-Pesa production credentials; Shopify OAuth app approval.

---

## Catch

### REACH (Leads, pipeline, links, QR, walk-in)
**Score: 7.5/10** → **8.2/10** post-P0  
**Status:** Pilot-ready

**Strengths**
- Consolidated sidebar Reach group (`app.html`); pipeline kanban (`/leads/pipeline/`).
- Walk-in → lead bridge, nurture router with WhatsApp (`REACH_LEAD_AUTOMATION_AUDIT.md`).
- Strong automation tests (`tests/test_reach_lead_automation.py`, `tests/test_qr_attribution.py`).

**Weaknesses**
- QR scan → lead without phone still deferred.
- Pipeline is read-only kanban (no drag-and-drop).
- `SEND_WHATSAPP` nurture step not in Automations form UI (user guide §8).

**Recommendations**
1. Add phone capture on QR landing pages (P0 wedge).
2. Expose WA nurture step in Automations builder UI.
3. Default hot-lead badge sync with Today money board counts.
4. Cashier walk-in mobile UX audit for thumb-zone.
5. Merge lead analytics into Revenue attribution view.

**Dependencies / blockers:** `leads` + `qr_attribution` migrations; Celery `reengage-stale-leads`.

### Social Inbox / Engage
**Score: 8/10** → **8.4/10** post-P0 → **8.8/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- Comments, DMs, AI auto-sent subnav; plan-gated PRO badge for Starter.
- Extensive safety rails and routing tests (`tests/test_engage_routing.py`).
- Celery `run_engage_cycle` every 30 min.

**Weaknesses**
- Starter users hit pricing redirect — weak for trial wedge.
- Many Meta capabilities unimplemented (hide comment, DM images per `KOVA_PLATFORM_CAPABILITY_CHECKLIST.md`).
- Real-time Engage updates depend on WebSocket adoption (polling fallback).

**Recommendations**
1. Allow Starter trial limited Engage (e.g. 5 auto-replies/week) to prove catch value.
2. Prioritize "price?" comment → lead bridge on Today.
3. Wire Engage new events to WebSocket (`engage_new` in `notifications/consumers.py`).
4. Hide unimplemented actions in UI rather than silent no-ops.
5. Unified "needs reply" inbox spanning Engage + WA (today split).

**Dependencies / blockers:** Meta App Review for Instagram messaging; token health (`PLATFORM_RESILIENCE.md`).

---

## Close

### WhatsApp (inbox, templates, broadcasts, sequences, channels)
**Score: 7.5/10** → **8.5/10** post-P0 → **8.8/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- Full subnav: Inbox, Templates, Status Studio, Broadcasts, Analytics.
- Ops autopilot: 24h follow-up, FAQ, auto-create leads (`docs/KOVA_AUTOPILOT.md`, `tests/test_autopilot.py`).
- Marketing conversation metering (`apps/billing/whatsapp_marketing.py`).

**Weaknesses**
- **Pro-only** (`whatsapp_enabled`) conflicts with Kenya wedge on Growth tier.
- Channels at `/whatsapp/channels/` not in sidebar (user guide §8).
- Large API surface documented but not built (documents, reactions, profile PATCH per capability checklist).

**Recommendations**
1. **P0:** Growth-tier WA inbox (cap marketing convos) for wedge GTM.
2. Add Channels to sidebar or remove route until ready.
3. Template sync failure UX when Meta approved but Kova stuck.
4. Surface marketing convo cap on broadcast launch screen.
5. M-Pesa payment message templates user-editable (guide lists as gap).

**Dependencies / blockers:** Meta Embedded Signup / WABA verification; live WhatsApp system user token; Pro plan for full module.

### Email (campaigns, sequences, lists, subscribers)
**Score: 8/10**  
**Status:** Pilot-ready

**Strengths**
- 101 tests in `tests/test_email.py` — strongest module test signal.
- Subnav: Overview, Campaigns, Subscribers, Lists; lead sync documented.
- Sequences complement REACH nurture for non-WA leads.

**Weaknesses**
- Custom sending domain not self-serve (Resend platform-managed).
- Two "sequence" concepts (REACH vs Email) confuse SMB users.
- Resend webhook signature enforcement flagged in security audit.

**Recommendations**
1. Onboarding copy: "Email catches leads who won't use WhatsApp."
2. Cross-link REACH enrollments to email subscriber on lead detail.
3. Enforce webhook signatures in production (`billing`/`emails` webhooks).
4. Starter-friendly single campaign wizard.
5. Show email nurture performance on Revenue screen.

**Dependencies / blockers:** Resend DNS/domain for production sender reputation.

### Bookings
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- 30 tests (`tests/test_bookings.py`); spec in `docs/specs/BOOKING_SPEC.md`.
- Public booking pages in E2E (`tests/e2e/test_critical_paths.py`).
- Post-booking attribution signals (`apps/bookings/signals.py`).

**Weaknesses**
- Single top-level nav item — no subnav for calendar vs. settings.
- Service-SMB focus less prominent than retail wedge in marketing.
- WA booking confirm templates utility-tier — testing burden on Meta templates.

**Recommendations**
1. Add "Today's appointments" card on money board for service verticals.
2. Booking link generator inside REACH Links flow.
3. WA reminder sequence template pack for salons/coaches (test business #12).
4. Mobile booking page audit (375px E2E exists — extend to full flow).
5. Connect booking confirmed → Revenue attribution event.

**Dependencies / blockers:** Meta utility templates for confirmations.

---

## Grow

### Studio / content creation
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- Studio hub with Campaigns, Visual Publisher, Memes (plan-gated), Autopilot, Competitors.
- Voice-to-campaign, reel director, calendar intel integration.
- Content safety at approval (`apps/content/approval.py`).

**Weaknesses**
- Feature-rich vs. "approve in 5 minutes" — cognitive load.
- Memes/Competitors are P2 per product structure doc but still in Studio subnav when expanded.
- FB Reels/Stories gaps may cause failed publishes.

**Recommendations**
1. Phase 2 merge Studio + Queue tabs per `KOVA_PRODUCT_STRUCTURE` §B.
2. Default Studio view: "Approve these 3 posts" not full campaign builder.
3. Gate competitor tracking more aggressively (Growth+ only).
4. Pre-flight publish checklist per platform token health.
5. Voice campaign as Pro upsell, not default Studio entry.

**Dependencies / blockers:** LLM daily/monthly caps; studio polish credits; Meta publish scopes.

### Queue / scheduled publish
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- List, Calendar, Timeline subnav; failed post `publish_error` surfaced (`PLATFORM_RESILIENCE.md`).
- Stuck publishing recovery Celery task; badge `nav_badge_queue`.
- A/B test evaluation hourly.

**Weaknesses**
- Rate-limit reschedule UX partial.
- Calendar drag-and-drop not shipped (admin plan mentions as improvement).
- Queue + Studio mental merge still incomplete.

**Recommendations**
1. One-click reschedule on `rate_limited` posts.
2. Token-expired platform: block approve with inline reconnect CTA (Stage 2 resilience).
3. Show next 3 publishes on Today quick actions.
4. Unify failed count from home stats with Queue filter.
5. Mobile calendar week view for shop owners.

**Dependencies / blockers:** Per-platform rate limits; token refresh for FB/IG (60-day re-auth).

### Revenue / analytics
**Score: 8/10**  
**Status:** Pilot-ready

**Strengths**
- Dedicated Revenue nav; attribution tests strong.
- Revenue stat on Today home (cached).
- Pixel + conversion journey for proving money chase.

**Weaknesses**
- Requires pixel install + UTM discipline — SMB adoption friction.
- Shopify-only for some commerce attribution paths.
- KES display depends on conversion data quality.

**Recommendations**
1. Wedge onboarding step: install pixel OR use Kova Link UTMs only.
2. "Money proved this week" single KPI on Today above Performance.
3. Simplified Revenue view for Starter (leads + WA orders only).
4. QR/walk-in revenue attribution prominent for physical retail.
5. Export PDF weekly money report for owner.

**Dependencies / blockers:** Customer site pixel deployment; Shopify partner approval.

### Performance
**Score: 7/10**  
**Status:** Pilot-ready

**Strengths**
- Insights dashboard at `/analytics/`; metrics fetch every 6h.
- Profile audit nightly Celery integration.
- Separated from Revenue in IA (clarity for operators).

**Weaknesses**
- Overlaps Revenue for SMB mental model ("Results" merge planned but not done).
- LinkedIn/TikTok analytics hit app-level rate limits at scale.
- Vanity metrics risk vs. money-chase positioning.

**Recommendations**
1. Merge with Revenue into "Results" per product structure Phase 2.
2. Default view: posts that drove leads/sales, not impressions.
3. Hide Performance for Starter tier.
4. Defer competitor analytics to Pro.
5. Add "so what?" AI summary from Analyst agent on Performance home.

**Dependencies / blockers:** Platform analytics API quotas.

### Workspace (Command)
**Score: 6/10** → **7.0/10** post-Phase 2  
**Status:** Beta

**Strengths**
- Overview, Standup, Moments, Listen subnav under Grow → More.
- Listen launch tests (`tests/test_listen_launch.py`); moment pack pipeline.
- Segment-specific CTAs in `apps/accounts/segments.py`.

**Weaknesses**
- Hidden under "More" — discoverability poor.
- Misaligned with shop-floor owner persona (P2 in retain matrix).
- Overlaps Today brief/standup concepts.

**Recommendations**
1. Fold Standup/Moments cards into Today for Pro users only.
2. Remove top-level Workspace from default IA for Starter/Growth.
3. Rename "Listen" to industry-plain language if retained.
4. Single entry: "Record a voice memo" on Today quick actions.
5. Document Workspace as agency/operator mode in Help center.

**Dependencies / blockers:** Voice transcription (Whisper) costs; calendar intel data.

### AI Agents (6 agents, adapt, briefs)
**Score: 8/10**  
**Status:** Pilot-ready

**Strengths**
- Control center at `/agents/` with ordered pipeline (`apps/agents/views.py`).
- Token budget enforcement (`apps/agents/budget.py`); adapt v2 tests (40).
- Scheduled research, engage, strategy cycles in Celery beat.

**Weaknesses**
- Agent toggles require user sophistication — no "money chase mode" preset.
- LangGraph installed but underused (cofounder audit).
- Strategist value hard to see on Today vs. Studio.

**Recommendations**
1. Preset: "Chase money" enables Engage + Analyst + Adapt only.
2. Agent activity digest on Today operations report (exists — promote).
3. Emergency pause more prominent in Settings (not buried).
4. Per-agent ROI metrics tied to leads/revenue.
5. Onboarding: auto-enable recommended agents per industry segment.

**Dependencies / blockers:** OpenRouter API; monthly LLM caps per Plan v2.

---

## Settings / infra (user-facing)

### Platforms (OAuth connect, FB page picker)
**Score: 7.5/10** → **8.0/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- `ACTIVE_PLATFORMS` (7) + `COMING_SOON` (3) in `apps/platforms/views.py`.
- FB page picker `facebook_select_page`; LinkedIn page select.
- Token warnings + auto-refresh shipped (`PLATFORM_RESILIENCE.md`).

**Weaknesses**
- YouTube/X/Threads marketed as "10 platforms" on landing but not connectable.
- FB Messenger real-time not implemented (`KOVA_PLATFORM_SETUP_GUIDE.md`).
- 60-day FB/IG re-auth still churn risk.

**Recommendations**
1. Landing: "7 connected today, 3 on the way."
2. Onboarding magic connect: WA + IG only (wedge), defer Pinterest/Bluesky.
3. Stage 2 resilience: block approve on expiring token (1-day urgent).
4. In-app reconnect deep links from failed publish notifications.
5. TikTok sandbox → production checklist before scaling.

**Dependencies / blockers:** Meta App Review (pages_manage_posts, instagram_manage_messages, whatsapp_business_management).

### Billing / plans / Stripe / M-Pesa
**Score: 8/10**  
**Status:** Pilot-ready

**Strengths**
- Plan v2 authoritative in `apps/billing/models.py`; public KES/USD pricing.
- Stripe checkout + portal + M-Pesa STK (`tests/test_billing.py`).
- Agency gated by `is_agency_approved`; trial = Starter limits.

**Weaknesses**
- Live Stripe price IDs / M-Pesa production keys are external config deps.
- Growth users may expect WA on invoice — plan matrix says no.
- M-Pesa subscription expiry push notification still TODO (`MPESA_SETUP.md`).

**Recommendations**
1. Pricing page explicit: "WhatsApp Business from Pro (Biashara)."
2. In-app upgrade prompt when user taps gated WA nav.
3. M-Pesa renewal warnings (email + WA) before grace expiry.
4. Billing overview: show all cap meters (WA marketing, seeds, polish).
5. Agency sales inquiry flow — verify ops SLA in admin dashboard.

**Dependencies / blockers:** Stripe live mode; Safaricom M-Pesa production passkey; `PlanPrice` DB rows.

### Teams / agency
**Score: 7/10** → **7.6/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- Teams nav agency-plan only; roles, invitations, brand scoping (`apps/teams/`).
- Agency tier 25 members; white-label doc exists (`AGENCY_WHITELABEL.md`).

**Weaknesses**
- Pro gets 5 members but Teams link only for `plan == 'agency'` in sidebar.
- Multi-brand agency UX still maturing vs. single-shop positioning.
- Scoped post querysets add complexity — edge-case bugs possible.

**Recommendations**
1. Show Teams under Settings for Pro with member cap badge.
2. Agency onboarding separate from SMB express path.
3. Test Neon Wave agency scenario from `TEST_BUSINESSES.md` end-to-end.
4. Client-switcher UX for agency dashboard.
5. Billing: per-seat clarity for Agency tier.

**Dependencies / blockers:** `is_agency_approved` manual gate.

### Autopilot settings
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- Operations autopilot toggles in Settings `#settings-autopilot` (all off by default).
- Tests: `tests/test_autopilot.py` (11 tests).
- Separate content autopilot in Studio; plan gates on WA automations (Pro+).

**Weaknesses**
- Two autopilot concepts (ops vs content) confuse users.
- Money board notifications not implemented.
- FAQ rules JSON shape is power-user unfriendly.

**Recommendations**
1. Rename sections: "Follow-up autopilot" vs "Content autopilot."
2. Simple FAQ rule builder UI (keyword → reply).
3. After enabling auto-enroll, show confirmation on REACH Automations.
4. Pro gate WA automations with inline upgrade on Settings save.
5. Admin dashboard: autopilot adoption funnel.

**Dependencies / blockers:** Celery `whatsapp.send_followup_nudges`, `content.check_and_publish_due_posts`.

### Content safety (user-facing + admin)
**Score: 8.5/10**  
**Status:** Production-ready

**Strengths**
- Fail-closed moderation pipeline (`docs/CONTENT_SAFETY.md`); 23 tests.
- Admin review queue, global toggles, strike/suspend workflow.
- Snap block with 72h duration; `publish_error` on blocked posts.

**Weaknesses**
- No dedicated user-facing "content policy" settings — only block messages.
- OpenRouter dependency for vision moderation.
- Staff review queue may backlog at scale.

**Recommendations**
1. User Settings: policy summary + strike count visibility.
2. Appeal flow for false positives (support ticket template).
3. Pre-upload client-side hint for common rejection reasons.
4. Metrics: block rate by industry in admin dashboard.
5. Document `CONTENT_SAFETY_ENABLED` kill-switch in runbooks.

**Dependencies / blockers:** `OPENROUTER_API_KEY`; Meta policy alignment for publish.

### Admin dashboard
**Score: 8.5/10**  
**Status:** Production-ready

**Strengths**
- ~100 routes: users, billing, LLM costs, WhatsApp, content safety, partners, search.
- Tests: `test_admin_dashboard_surfaces.py`, `test_admin_dashboard_search.py`.
- Onboarding funnel, operations overview, seed quota hub.

**Weaknesses**
- Staff-only — no delegated support role granularity.
- HTMX polling vs. WebSocket for live ops (plan doc notes 30–60s polling).
- Cofounder audit security items may affect staff-facing routes.

**Recommendations**
1. Role-based staff permissions (support vs. superadmin).
2. Live Celery task health panel (Flower or custom).
3. Money-chase KPI dashboard: WA reply SLA, lead conversion, M-Pesa GMV.
4. One-click impersonate user for support (audit-logged).
5. Partner/UNIMART provisioning status board.

**Dependencies / blockers:** `is_staff` gate; Sentry for error triage.

### Partners / UNIMART / marketplace
**Score: 7/10**  
**Status:** Pilot-ready

**Strengths**
- B2B API documented (`MARKETPLACE_PARTNER_SYSTEM.md`).
- `import_unimart_vendors` command; tests for CSV import and partner billing.
- Seller provisioning + product sync architecture.

**Weaknesses**
- Production-scale partner onboarding unproven.
- UNIMART strategy doc exists but live integration status unclear.
- Marketplace billing models add support surface area.

**Recommendations**
1. Run UNIMART pilot with 10 vendors before marketing marketplace.
2. Partner health dashboard in admin (sync errors, content gen backlog).
3. API rate limits and partner key rotation documented.
4. Separate partner SLA from SMB support queue.
5. Webhook retry/idempotency audit for product sync.

**Dependencies / blockers:** Partner API keys; marketplace dev integration capacity.

### Onboarding / signup (FB, wizard)
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- Express onboarding with path choice (magic connect, manual, sell intent).
- Facebook OAuth signup tests (`tests/test_facebook_signup_oauth.py` — 22 tests).
- Onboarding automation tests (43 in `test_onboarding_automation.py`).

**Weaknesses**
- Multiple paths (choose path, magic connect, express steps) — drop-off risk.
- FB signup depends on Meta app live mode.
- Wedge checklist starts after signup — not integrated into wizard steps 1–2.

**Recommendations**
1. Single happy path: FB signup → connect WA + IG → first snap.
2. Embed wedge checklist into onboarding step 3.
3. Funnel analytics in admin onboarding-funnel (route exists).
4. Skip "Workspace/Listen" prompts for retail segments.
5. Phone collection before plan checkout (M-Pesa readiness).

**Dependencies / blockers:** Meta Facebook Login; WhatsApp Embedded Signup.

### Landing / marketing site
**Score: 7.5/10** → **8.2/10** post-P0  
**Status:** Pilot-ready

**Strengths**
- North-star H1 in `templates/pages/landing.html`.
- Plan v2 pricing on page; simple steps component.
- E2E landing tests (desktop + mobile).

**Weaknesses**
- "10 platforms" stat vs. 7 active connects.
- Subhead still lists "AI team" — good but secondary to money chase.
- CDN Alpine without SRI on landing (security audit flag).

**Recommendations**
1. Update platform count to 7 + "3 coming."
2. Hero CTA: "Connect WhatsApp free trial" not generic signup.
3. 15-min wedge demo video/script on landing.
4. Social proof from test businesses (fictional labeled as examples).
5. Self-host or SRI-hash CDN scripts.

**Dependencies / blockers:** None technical — copy/design.

### Legal / privacy
**Score: 8/10**  
**Status:** Production-ready

**Strengths**
- Routes: privacy, terms, cookies, acceptable-use, DPA (`config/urls.py`).
- Facebook data deletion flow + status page; tests (`test_facebook_data_deletion.py`).
- Signup links Terms + Privacy.

**Weaknesses**
- GDPR/DPA enterprise sales may need localized Kenya DPA variant.
- Cookie consent UX not audited here.
- Campus rep legal page — niche.

**Recommendations**
1. Cookie banner if EU traffic expected.
2. Annual legal review aligned to Meta/WhatsApp policy changes.
3. In-app link to data deletion from Settings.
4. M-Pesa payment terms clarity on checkout.
5. Fundraising checklist doc cross-link from footer.

**Dependencies / blockers:** Legal counsel review for fundraising (`KOVA_FUNDRAISING_AND_LEGAL_DOCUMENT_CHECKLIST.md`).

---

## Infrastructure (rated separately)

### Celery / beat / tasks
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- 30+ beat entries in `config/settings/base.py` (publish, tokens, briefs, engage, partners, analytics).
- DatabaseScheduler via django-celery-beat.
- Task coverage across WA, leads, content, billing.

**Weaknesses**
- Broad try/except in tasks — observability gaps (cofounder audit).
- No dead-letter queue documented.
- Beat + worker must run on Railway separately.

**Recommendations**
1. Structured task logging + Sentry breadcrumbs per task.
2. Admin Celery health: last success timestamp per critical task.
3. Alert on `generate-daily-briefs` failures.
4. Document worker/beat Railway services in deploy runbook.
5. Idempotency keys for payment webhooks and publish.

**Dependencies / blockers:** Redis broker; Railway worker service.

### Redis / Channels / WebSockets
**Score: 7/10**  
**Status:** Pilot-ready

**Strengths**
- ASGI wired (`config/asgi.py`); `UpdatesConsumer` at `/ws/updates/`.
- Client JS in `static/js/kova-realtime.js` + `base.html` WebSocket connect.
- Railway Redis timeout config tests (`test_channels_redis_config.py`).

**Weaknesses**
- Cofounder audit claimed partial adoption — HTMX polling still fallback.
- WebSocket closes cleanly if Redis unavailable — degraded UX.
- Daphne required; dev uses InMemoryChannelLayer.

**Recommendations**
1. Audit templates: replace 2–30s HTMX polls with WS events where implemented.
2. Connection status indicator in app chrome.
3. Load-test WS on Railway Redis internal URL.
4. Document when polling is intentional vs. legacy.
5. Engage inbox real-time as P0 WS consumer.

**Dependencies / blockers:** `REDIS_URL` on web + worker; Daphne on Railway.

### Deploy / migrations / Railway
**Score: 7.5/10**  
**Status:** Pilot-ready

**Strengths**
- `railway.toml` with `scripts/release.sh` migrate on deploy.
- CI checks `makemigrations --check`.
- Production settings deploy check in CI security job.

**Weaknesses**
- Docker Compose / Dockerfile gap noted in cofounder audit.
- Environment variable surface large (15+ missing from `.env.example` per audit).
- No blue/green or canary documented.

**Recommendations**
1. Refresh `.env.example` with all production vars.
2. Staging environment on Railway for migration rehearsal.
3. Release script: post-migrate smoke test hook.
4. Fix or remove broken Docker Compose for local dev.
5. Migration rollback playbook for hotfixes.

**Dependencies / blockers:** Railway Postgres + Redis services; `DATABASE_URL`.

### Tests / CI
**Score: 7.5/10** → **8.0/10** post-Phase 2  
**Status:** Pilot-ready

**Strengths**
- GitHub Actions: ruff lint, pytest with **70% coverage gate**, Playwright E2E, security job.
- ~791 pytest functions across 82 files + 14 E2E; strong module coverage for email, engage, billing.
- `tests/e2e/test_critical_paths.py` includes wedge checklist on Today post-signup.

**Weaknesses**
- May 2026 audit said "0 CI" — now fixed but audit docs stale.
- E2E does not cover full wedge (snap → publish → lead → WA).
- Security job soft-fails pip-audit/bandit (`|| true`).
- No Locust load tests in CI (locustfile exists).

**Recommendations**
1. Add E2E critical path: connect mock platform → approve post → lead list.
2. Fail CI on bandit medium+ findings (remove `|| true` when clean).
3. Update `KOVA_TESTING_GUIDE.md` with real counts.
4. Nightly full pytest on main (in addition to PR).
5. Contract tests for Meta/WhatsApp webhook payloads.

**Dependencies / blockers:** Playwright in CI (already configured); test DB Postgres 16.

---

## Weighted score calculation

| Category | Avg | Weight | Contribution |
|----------|-----|--------|--------------|
| User-facing (24 sections) | 7.77 | 80% | 6.22 |
| Infrastructure (4 sections) | 7.38 | 20% | 1.48 |
| **Overall** | | | **7.6 / 10** (baseline) · **~8.4 / 10** post-P0 · **~8.9 / 10** post-Phase 2 |
