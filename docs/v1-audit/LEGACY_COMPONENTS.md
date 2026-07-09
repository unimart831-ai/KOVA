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
| Action | Remove from `INSTALLED_APPS`. Keep migration files for history unless squashed. |
| Risk if removed | None to application; ensure no FK references from other app migrations |

### 2. `media_queue` References

| Attribute | Detail |
|-----------|--------|
| Status | **REMOVED** — app no longer exists |
| Evidence | `media/tasks.py` contains a deprecated no-op task `media_queue.process_queues`. README historically mentioned it. |
| Action | Remove the no-op task from `media/tasks.py`. Remove Celery Beat schedule entry if one exists. |
| Risk if removed | None |

### 3. `memes` App References

| Attribute | Detail |
|-----------|--------|
| Status | **REMOVED** — app no longer exists |
| Evidence | README historically mentioned this app |
| Action | Remove any remaining references in documentation |
| Risk if removed | None |

---

## Duplicate / Redundant Components

### 4. `kova_page` App vs `links` App

| Attribute | Detail |
|-----------|--------|
| `kova_page` | Templates at `templates/kova_page/` (13 templates), `salesperson.py`, `urls.py` → `/p/<slug>/` |
| `links` | `KovaPage` model, `KovaLink`, forms, templates at `templates/links/` → `/k/<slug>/` |
| Overlap | Both serve as public business pages with product showcases |
| Distinction | `kova_page` renders the full business profile (hero, catalog, services, reviews, salesperson); `links` is link-in-bio with forms |
| Action | These serve different purposes but naming is confusing. Rename: `kova_page` → "Business Hub" (public conversion page), `links` → "Link Pages" (link-in-bio). The AI Salesperson should stay with `kova_page` as it's tied to the public business page. |

### 5. Three Inbox Implementations

| Component | Location | Purpose |
|-----------|----------|---------|
| WhatsApp Inbox | `whatsapp/views.py` + `templates/whatsapp/inbox.html` | WhatsApp conversations |
| Unified Inbox | `engage/` + `templates/engage/unified_inbox.html` | All platform interactions |
| DM Inbox | `engage/dm_inbox.py` + `templates/engage/dm_inbox.html` | Facebook/IG DMs only |

| Action | Consolidate into one inbox view with channel filters |

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
| `photoroom_batch.py` | Bulk processing | Keep |
| `photoroom_create_any.py` | Promo banners | V1.1 |
| `photoroom_visual_qa.py` | Quality audit | V2 |
| `photoroom_review.py` | Human review flags | V1.1 |
| `photoroom_brand_template.py` | Brand presets | Keep |
| `photoroom_food.py` | Food presets | V1.1 |
| `photoroom_local.py` | Local fallbacks | Keep |
| `media/photoroom_brief.py` | Brief → variants | V1.1 |

**Recommendation:** For V1, active files should be: `photoroom.py`, `photoroom_preflight.py`, `photoroom_photofix.py`, `photoroom_batch.py`, `photoroom_brand_template.py`, `photoroom_local.py`. The rest can be feature-flagged or deferred.

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

### 15. Remotion Video Rendering

| Location | `media_render/` (React/TypeScript subproject) |
| Purpose | Programmatic product reel video rendering |
| Status | Exists but unclear usage in production pipeline |
| Action | Assess whether `media/reel_bridge.py` actually invokes Remotion or if it's been superseded by Fal/Kling. If unused, archive. |

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
| **Remove from INSTALLED_APPS** | `campaigns` | P0 |
| **Remove dead code** | `media_queue` no-op task, `memes` references | P0 |
| **Rename for clarity** | Duplicate model names (4 pairs) | P1 |
| **Consolidate** | 3 inbox views → 1 | P1 |
| **Feature-flag/hide** | Partners, QR, competitors, A/B, Shopify, reviews | P1 |
| **Simplify** | Photoroom (18 → 6 active files) | P1 |
| **Move out of repo** | `fundraising/`, `marketing/` | P2 |
| **Assess and potentially archive** | Remotion, competitor screenshots | P2 |
| **Rename apps** | `kova_page` → clarify purpose | P2 |
