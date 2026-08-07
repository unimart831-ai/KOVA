# Legacy Components Register

**Date:** July 2026

---

## Confirmed Legacy / Deprecated

### 1. `campaigns` App

| Attribute | Detail |
|-----------|--------|
| Location | `apps/campaigns/` |
| Status | **DEPRECATED** — models removed, migrations-only |
| Evidence | `models.py` contains only a docstring: "Legacy Campaign removed; use content.MarketingCampaign" |
| Action | **Keep in `INSTALLED_APPS` until migrations are squashed.** `bookings`, `qr_attribution`, and `content` migrations historically FK to `campaigns.campaign`. |
| Risk if removed now | Fresh `migrate` fails resolving historical dependencies |

### 2. `media_queue` References

| Attribute | Detail |
|-----------|--------|
| Status | **CLEANED** (July 2026) |
| Evidence | App removed; no-op Celery task removed from `media/tasks.py`. |
| Action | Done. `prune_stale_beat_tasks` still disables leftover DB beat rows named `media_queue.process_queues`. |
| Risk if removed | None |

### 3. `memes` App References

| Attribute | Detail |
|-----------|--------|
| Status | **CLEANED** (July 2026) |
| Evidence | App removed; README + system map entry removed |
| Action | Done |
| Risk if removed | None |

---

## Duplicate / Redundant Components

### 4. `kova_page` App vs `links` App

| Attribute | Detail |
|-----------|--------|
| Status | **CONSOLIDATED** (July 2026) |
| Survivor | `apps.commerce.links` — link-in-bio at `/k/` plus Business Hub at `/p/` via `apps.commerce.links.hub` |
| Evidence | `apps.kova_page` removed from INSTALLED_APPS; hub/salesperson/views live under `apps/links/hub/` |
| URLs | Both `/p/<slug>/` and `/k/<slug>/` preserved; `{% url 'kova_page:...' %}` still works via hub urls `app_name` |
| Action | Done |

### 5. Three Inbox Implementations

| Attribute | Detail |
|-----------|--------|
| Status | **PARTIALLY CONSOLIDATED** (July 2026) |
| Survivor hub | `engage:unified_inbox` (Needs reply) — deep-links to specialists |
| WhatsApp | Kept as workspace (`whatsapp:conversation`); DM WhatsApp filter redirects here |
| Comments | `engage:inbox` with `?highlight=` for deep-links |
| Messages | `engage:dm_inbox` for FB/IG only |
| Billing | Plan gate covers unified + DM + auto-sent routes |
| Action | Remaining: optional UI merge of Comments+DM tabs into one Interaction filter view |

### 6. Two Weekly Digest Models

| Model | App | Purpose |
|-------|-----|---------|
| `help.WeeklyDigest` | `help` | Platform newsletter to all users |
| `whatsapp.WeeklyDigest` | `whatsapp` | WA performance digest per user |

| Action | Rename for clarity: `PlatformNewsletter` and `WhatsAppPerformanceDigest` |

### 7. Two SequenceEnrollment Models

| Model | App | Purpose |
|-------|-----|---------|
| `emails.SequenceEnrollment` | `emails` | Email drip sequence enrollment |
| `whatsapp.SequenceEnrollment` | `whatsapp` | WA broadcast sequence enrollment |

| Action | These are parallel implementations for different channels. Consider a shared abstract base or rename to `EmailSequenceEnrollment` / `BroadcastEnrollment`. |

### 8. Two PageView Models

| Model | App | Purpose |
|-------|-----|---------|
| `links.PageView` | `links` | Public KovaPage daily view aggregates |
| `analytics.PageView` | `analytics` | Authenticated user feature usage tracking |

| Action | Rename: `links.PublicPageView` and `analytics.FeatureUsageEvent` |

---

## Over-Engineered Components

### 9. Photoroom Integration (18 Files)

| Files | Purpose | Assessment |
|-------|---------|------------|
| `photoroom.py` | Core API client | Keep |
| `photoroom_api.py` | API helpers | Merge into core |
| `photoroom_plus.py` | Plus features catalog | Merge into core |
| `photoroom_basic.py` | Basic v1 routing | Remove (v2 replaces) |
| `photoroom_preflight.py` | Upload quality check | Keep (valuable) |
| `photoroom_guard.py` | Cutout fallback | Merge into core |
| `photoroom_photofix.py` | Lighting correction | Keep |
| `photoroom_composition.py` | Multi-product hero | Keep (V1.1) |
| `photoroom_virtual_models.py` | Virtual model shots | V1.1 |
| `photoroom_video.py` | Video animation | V1.1 |
| `photoroom_batch.py` | Bulk processing | **Deleted** (unused stub) |
| `photoroom_create_any.py` | Promo banners | **Deleted** (unused stub) |
| `photoroom_visual_qa.py` | Quality audit | **Deleted** (unused stub) |
| `photoroom_review.py` | Human review flags | V1.1 |
| `photoroom_brand_template.py` | Brand presets | Keep |
| `photoroom_food.py` | Food presets | V1.1 |
| `photoroom_local.py` | Local fallbacks | Keep |
| `media/photoroom_brief.py` | Brief → variants | V1.1 |

**Recommendation:** Active Photoroom modules: `photoroom.py`, `photoroom_api.py`, `photoroom_plus.py`, `photoroom_basic.py`, `photoroom_preflight.py`, `photoroom_photofix.py`, `photoroom_brand_template.py`, `photoroom_local.py`, `photoroom_guard.py`, `photoroom_review.py`, plus feature modules (`composition`, `video`, `virtual_models`, `food`).

### 10. Partner/Marketplace System (10 Models)

Built for a B2B marketplace feature that has no active users:
- `PartnerApplication`, `Partner`, `Referral`, `Commission`, `MilestoneAward`
- `ReferralClick`, `PayoutRequest`
- `MarketplacePartner`, `MarketplaceSellerAccount`, `WebhookDeliveryLog`

Plus: full API (`api/partner_views.py`), management command (`import_unimart_vendors.py`), webhook dispatch.

**Recommendation:** Code is clean and well-structured. Keep but hide from all UI. Revisit when marketplace partnerships are actively pursued.

---

## Experimental / Unvalidated Features

### 11. Competitor Screenshots

| Location | `analytics/models.py` (CompetitorScreenshot), tasks, admin views |
| Purpose | Screenshot competitor social profiles for visual comparison |
| Status | Implemented but value unclear |
| Action | Defer to V2. Remove from V1 UI. |

### 12. Performance Recycle

| Location | `analytics/models.py` (PerformanceRecycle), `analytics/performance_recycle.html` |
| Purpose | Auto-republish high-performing old content |
| Status | Implemented |
| Action | Interesting but unvalidated. Defer to V1.1. |

### 13. A/B Testing

| Location | `content/models.py` (ABTest), admin dashboard templates |
| Purpose | Test content variants for engagement |
| Status | Partial implementation — models exist but workflow incomplete |
| Action | Defer to V2. Too complex for V1 launch. |

### 14. Shopify Integration

| Location | `analytics/shopify_oauth.py`, `analytics/models.py` (ShopifyStore), webhooks |
| Purpose | Sync products/orders from Shopify stores |
| Status | Stub — OAuth flow exists but integration untested |
| Action | Defer to V2. African SME target is unlikely to use Shopify. |

### 15. Remotion Video Rendering — REMOVED

| Location | Was `media_render/` |
| Status | **REMOVED** (July 2026). Reels use FFmpeg (`REEL_RENDER_BACKEND=ffmpeg`). |
| Note | `apps/create/media/remotion_bridge.py` remains as a no-op fallback if env is set to `remotion`. |

---

## Non-Runtime Artifacts in Codebase

### 16. `fundraising/` Directory

Business documents (legal, financial, pitch deck) that shouldn't be in the application repository:
- Corporate docs, NDA, ToS, privacy policy templates
- Cap table, financial projections
- Pitch deck, investor FAQ, data room index
- Grant narratives
- PDF build scripts

**Action:** Move to separate repository or cloud storage. Exclude from Docker builds.

### 17. `marketing/` Directory

Sales brochure HTML/PDF assets.

**Action:** Move to separate repository. Exclude from Docker builds.

---

## Summary: Actions Required

| Action | Items | Priority |
|--------|-------|----------|
| **Keep until migration squash** | `campaigns` in INSTALLED_APPS | P2 |
| **Remove dead code** | `media_queue` no-op, `memes` system map, unused Photoroom stubs | **Done** |
| **Rename for clarity** | Duplicate model names (4 pairs) | P1 |
| **Consolidate** | 3 inbox views → 1 | P1 |
| **Feature-flag/hide** | Partners, QR, competitors, A/B, Shopify, reviews | P1 |
| **Simplify** | Photoroom (deleted 3 unused stubs; remaining are live) | **Partial** |
| **Move out of repo** | `fundraising/`, `marketing/` | **Done** |
| **Assess and potentially archive** | Remotion, competitor screenshots | P2 |
| **Rename apps** | `kova_page` → clarify purpose | P2 |
