# Kova Strategic Execution Roadmap

Last updated: 2026-06-23  
Owner: Product + Engineering

## North Star

Kova becomes an AI marketing employee that runs primarily through WhatsApp.

Primary loop:

1. Send asset
2. Kova creates content
3. Approve
4. Publish
5. Leads arrive
6. Kova drafts replies
7. Booking or payment
8. Revenue summary

## Guardrails

- Ship only features that increase revenue, retention, or activation.
- Hide complexity by default.
- Keep web for setup/deep controls, move daily operations into WhatsApp.
- Do not expand platform breadth until core loop metrics improve.

## Wave Plan

### Wave 1 (Weeks 1-2): System Cleanup

Goals:
- Reduce cognitive load in primary UX.
- Remove non-core navigation noise.
- Create delivery safety baseline.

Deliverables:
- Simplified sidebar and mobile IA around Today/Sell/Catch/Close/Grow.
- Hide advanced controls from non-staff users.
- Remove stale feature references from user-facing docs/UI.
- Add CI smoke pipeline for migrations + tests.

Primary modules:
- `templates/layouts/app.html`
- `config/urls.py`
- `apps/*/urls.py`
- CI config

Success metrics:
- -25% clicks into non-core pages.
- +15% completion of daily core loop (brief -> approval -> publish).
- Green CI on all PRs.

---

### Wave 2 (Weeks 3-5): BusinessAsset Foundation

Goals:
- Replace product-only domain assumptions.
- Support product/service/professional workflows through one model.

Deliverables:
- New `BusinessAsset` domain model and API.
- Migration path from `products.Product` with dual-write period.
- Asset lifecycle states (draft, pending_approval, published, archived).

Primary modules:
- `apps/products/models.py` (bridge)
- New asset domain app or module (to be decided)
- `apps/api/urls.py` + serializers/views
- `apps/content/models.py` relations

Success metrics:
- 95%+ migration integrity.
- No regression in Snap-to-Sell and shop checkout path.

---

### Wave 3 (Weeks 6-8): WhatsApp-First Foundation

Goals:
- Move core owner operations into WhatsApp.

Deliverables:
- Asset intake from WhatsApp images/text.
- WhatsApp approval actions with preview context.
- Daily money summary command payloads.
- Lead quick actions via WhatsApp.

Primary modules:
- `apps/whatsapp/webhook.py`
- `apps/whatsapp/services.py`
- `apps/briefs/whatsapp_commands.py`
- `apps/products/tasks.py`

Success metrics:
- >=60% content approvals from WhatsApp.
- >=40% weekly active owners using WA commands.

---

### Wave 4 (Weeks 9-10): Content Engine Redesign

Goals:
- Standardize platform-specific output from one asset-centric input.

Deliverables:
- Content blueprint schema by objective and platform.
- Renderers for Facebook, Instagram, TikTok, LinkedIn.
- Quality scoring and retry/fallback logic.

Status (2026-06-23):
- [x] Blueprint schema + seed attachment
- [x] Platform renderers (`apps/content/renderers.py`)
- [x] Quality score stored on `Post.content_dna.blueprint_quality`
- [x] Auto-retry on low score (`apps/content/blueprint_retry.py`)

Primary modules:
- `apps/agents/create_agent.py`
- `apps/content/services.py`
- `apps/platforms/providers/*`

Success metrics:
- +20% approval rate.
- -25% regenerate rate.

---

### Wave 5 (Weeks 11-12): Service Workflow Support

Goals:
- Make service businesses first-class citizens.

Deliverables:
- Service asset setup + booking mapping.
- Service content templates (transformation/testimonial/offer).
- Inquiry-to-booking automation enhancements.

Primary modules:
- `apps/bookings/*`
- asset model integrations
- `apps/content/*`

Success metrics:
- +20% service-business activation.
- +15% booking conversion from inbound leads.

---

### Wave 6 (Month 4-5): Professional Workflow Support

Goals:
- Support agencies/consultants/lawyers/designers.

Deliverables:
- [x] Portfolio and case-study asset types (Snap + `BusinessAsset`).
- [x] Consultation CTA on LinkedIn/Facebook posts (`professional_cta.py`).
- [x] Professional content pack (portfolio / case study / thought leadership templates).
- [x] Studio UI for managing portfolio & case-study assets (beyond Snap).
- [x] Lead pipeline automation for professional consult funnel.

### Sprint J (Wave 7 kickoff)
- [x] Revenue board asset attribution (top portfolio/case study this week).
- [x] Professional nurture sequence template (consultation follow-up).
- [x] MONEY command copy tuned per `business_model`.
- [x] Studio bulk-approve with professional post preview labels.

### Sprint K (Wave 7 continue)
- [x] Revenue analytics page: asset-type breakdown chart.
- [x] Standup line uses top asset type for professionals.
- [x] WhatsApp MONEY digest opt-in copy per business model.
- [x] Studio asset manager (portfolio list beyond Snap).

### Sprint L (Wave 7 — next)
- [x] Revenue analytics: export asset-type breakdown CSV.
- [x] Showcase → one-click "Create authority post" from portfolio item.
- [x] Consult funnel stage labels on Leads list for professionals.
- [x] Wave 7 success metrics dashboard (attribution confidence score).
- [x] Product voice system + core-loop template copy revamp.

### Sprint M (Wave 7 — next)
- [ ] Attribution confidence tips → one-click setup actions.
- [ ] Showcase bulk-create posts for whole portfolio.
- [ ] Consult funnel kanban column on Pipeline view.
- [ ] WhatsApp AUTHORITY command for showcase → post flow.

Success metrics:
- Professional segment trial-to-paid conversion increase.

---

### Wave 7 (Month 5-6): Revenue Operating System

Goals:
- Make money visibility and action the default behavior.

Deliverables:
- Unified money surface (web + WhatsApp parity).
- Next-best action recommendations tied to revenue.
- Revenue summaries tied to assets, not just posts.

Success metrics:
- +25% attributed revenue per active account.
- +15% 30-day retention.

## Agent Simplification Target

User-facing: one Kova experience.  
Internal services:

- Content Agent
- Sales Agent
- Revenue Agent
- (Optional) Market Intelligence Agent

Legacy agent controls remain staff-only until fully migrated.

## De-scope Rules

Defer or hide if feature does not directly improve:

- Time to first published content
- Time to first lead response
- Time to first booking/payment
- Revenue attribution confidence

## Sprint Backlog Starter (Immediate)

Sprint A:
- [x] Simplify sidebar and hide low-signal items from default UX.
- [x] WhatsApp owner Snap-to-Sell intake (send photo → listing + content pipeline).
- [x] BusinessAsset model foundation + Product bridge sync.
- [x] MONEY WhatsApp command for weekly revenue summary.
- [x] CI smoke job (`smoke` workflow) + `core_smoke` management command.
- [x] Route inventory with ownership tags (`docs/ROUTE_INVENTORY.md`).

Sprint B:
- [x] BusinessAsset model + Product bridge sync (see Wave 2).
- [x] Introduce Asset API scaffolding (`/api/v1/assets/`).
- [x] Build Product -> Asset adapter layer (`business_assets.sync_asset_from_product`).
- [x] `backfill_business_assets` management command.

Sprint C:
- [x] WhatsApp asset ingestion (owner image on master number).
- [x] WhatsApp approve/reject command flow.
- [x] Daily revenue summary command (`MONEY`).
- [x] LEADS WhatsApp command (hot leads + need reply).

Sprint D (onboarding + content engine):
- [x] `business_model` field on UserProfile (product / service / professional).
- [x] Onboarding 3-path branch UI.
- [x] ContentBlueprint schema foundation (`apps/content/blueprints.py`).
- [x] Blueprint → Create Agent prompt wiring (`ContentSeed.blueprint` + `blueprint_pipeline`).
- [x] Agents control center staff-only route guard.

Sprint E (service workflow):
- [x] Auto booking link on service onboarding (`service_setup.py`).
- [x] Service asset → BookingLink services sync.
- [x] Service post-onboarding redirect to bookings.
- [x] Setup mission booking checklist for service businesses.
- [x] Service content templates (transformation / testimonial / offer).
- [x] WhatsApp BOOK command (booking link + services).

Sprint F (content engine + ops):
- [x] Blueprint post-renderers (`apps/content/renderers.py`).
- [x] Blueprint quality scoring (alignment score on `Post.content_dna`).
- [x] Route inventory with ownership tags (`docs/ROUTE_INVENTORY.md`).
- [x] Blueprint auto-retry on low alignment score.

Sprint G (professional + revenue OS):
- [x] Professional asset helpers (`professional_assets.py`).
- [x] Professional content templates (portfolio / case study / thought leadership).
- [x] Unified revenue summary (`revenue_summary.py`) — MONEY + standup parity.
- [x] Revenue next-best-action in MONEY command.
- [x] WhatsApp quick buttons: BOOK (service), MONEY (commerce).

Sprint H (UX + lead close):
- [x] Today board "Your move" next-action card.
- [x] Professional Snap modes (portfolio / case study) on Snap to Sell.
- [x] WA booking → Lead bridge (`create_lead_from_booking` on confirm).
- [x] Engage booking intent → HOT lead + booking URL metadata.
- [x] LinkedIn/Facebook consultation CTA auto-fill (`professional_cta.py`).

### Sprint I (Wave 6 polish)
- [x] Studio asset type picker (portfolio / case study / product) on edit.
- [x] Professional Today board copy when `business_model=professional`.
- [x] Consultation CTA on `first_comment` for link-in-comments platforms.
- [x] Lead nurture sequence trigger for booking-intent Engage leads.

### Sprint N (media orchestration foundation)
- [x] `apps/media` — Brand DNA resolver (`brand_dna.py`)
- [x] Asset intelligence + content format recommendations (`asset_intelligence.py`)
- [x] Media router (Photoroom / Fal Kling / Bannerbear / FFmpeg)
- [x] Fal.ai client — Kling reels + Flux kontext edits (`fal_client.py`)
- [x] Bannerbear carousel bridge (`bannerbear_client.py`, `carousel_bridge.py`)
- [x] Snap pipeline media plan persistence on BusinessAsset
- [x] `compose_reel_video` Kling backend path (`reel_bridge.py`)
- [x] Plan gates: `kling_reels_enabled`, `bannerbear_carousels_enabled`, `fal_flux_edits_per_month`
- [ ] Bannerbear template UIDs in production `.env`
- [ ] Fal Kling/Flux production keys + cost ledger entries
- [ ] Studio UI: before/after polish proof + format preview strip
- [ ] WhatsApp offer card renderer (Brand DNA driven)
