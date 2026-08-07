# Technical Debt Register

**Date:** July 2026

---

## Critical Debt (Fix Before Launch)

### 1. Legacy `campaigns` App Still in INSTALLED_APPS

| Item | Detail |
|------|--------|
| Location | `apps/core/campaigns/` (via `config/settings/base.py`) |
| Issue | App has no models (all dropped in migration 0003) but is still registered. Comment says "migrations only — legacy tables dropped" |
| Risk | Confusing for new developers; migration dependency chains |
| Action | Remove from INSTALLED_APPS after squashing migrations. Keep migration files only if other apps reference `campaigns` in FK history. |
| Effort | Low |

### 2. Duplicate `kova_page` App — RESOLVED

| Item | Detail |
|------|--------|
| Status | **DONE** (July 2026) |
| Resolution | Folded into `apps/commerce/links/hub`. URL namespace `kova_page:` preserved. |

### 3. Django Project Package at `docs/config/` — RESOLVED

| Item | Detail |
|------|--------|
| Status | **DONE** (July 2026) |
| Resolution | Live package is `kova_agent/config/`. Stale `docs/config/` removed. |

### 4. Duplicate Model Names Across Apps

| Model Name | App 1 | App 2 | Issue |
|------------|-------|-------|-------|
| `PageView` | `links` (public page views) | `analytics` (feature usage) | Different purposes but same name |
| `WeeklyDigest` | `help` (platform newsletter) | `whatsapp` (WA performance) | Unrelated features sharing a name |
| `SequenceEnrollment` | `emails` (email drip) | `whatsapp` (WA broadcast drip) | Parallel implementations |

| Risk | Django admin confusion, import errors when not fully qualified |
| Action | Rename to disambiguate: `LinkPageView`/`FeatureUsageEvent`, `PlatformDigest`/`WhatsAppDigest`, etc. |
| Effort | Medium (requires migrations) |

---

## High Debt (Fix in V1 Timeline)

### 5. Photoroom module sprawl

| Item | Detail |
|------|--------|
| Location | `apps/commerce/products/photoroom*.py` |
| Issue | Still more files than ideal after stub deletes + thin-helper merges (photofix/local/food folded). |
| Risk | Maintenance burden; single-vendor dependency |
| Action | Further consolidate toward `client` / `pipeline` / config-presets when safe. |
| Effort | Medium |

### 6. Multiple Inbox Implementations

| Item | Detail |
|------|--------|
| Locations | `whatsapp/views.py` (WA inbox), `engage/dm_inbox.py` (DM inbox), `engage/` (unified inbox) |
| Templates | `whatsapp/inbox.html`, `engage/unified_inbox.html`, `engage/dm_inbox.html` |
| Issue | Three separate inbox views for what should be one unified messaging interface |
| Risk | UX confusion; duplicate code for message display/actions |
| Action | Consolidate into single inbox view with source filters (WhatsApp/Facebook/Instagram DMs/Comments) |
| Effort | Medium |

### 7. Scattered API Endpoints

| Item | Detail |
|------|--------|
| Formal API | `apps/api/` — DRF views at `/api/v1/` |
| Informal APIs | `accounts/urls.py` has `api/profile-industry/`, `api/ai-brand-builder/`, `api/infer-from-url/`; many apps have JSON-returning views |
| Issue | API surface is inconsistent — mix of DRF + raw JSON views + HTMX partials |
| Risk | No consistent auth/throttling/schema for non-DRF endpoints |
| Action | For V1: document which endpoints are public API vs internal HTMX. Long-term: move all external APIs under `/api/v1/`. |
| Effort | Medium |

### 8. No Formal Service Layer Pattern

| Item | Detail |
|------|--------|
| Issue | Only 5 files named `services.py`. Business logic is split across views, tasks, standalone modules, and model methods. |
| Example | WhatsApp commerce logic in `whatsapp/commerce.py` (not a service); billing in `billing/services.py` + `billing/mpesa_services.py` + `billing/mpesa.py` (three files for one integration) |
| Risk | Inconsistent patterns make it hard to find business logic |
| Action | Not a V1 blocker. Document the conventions. Gradually extract services in V1.1+. |
| Effort | High (ongoing) |

---

## Medium Debt (V1.1)

### 9. Unused/Experimental Features in Production Code

| Feature | Location | Issue |
|---------|----------|-------|
| Remotion video rendering | ~~`media_render/`~~ | **REMOVED** — FFmpeg is the reel backend |
| Performance Recycle | `analytics/models.py` | Auto-republish old content; experimental |
| Competitor Screenshots | `analytics/models.py` | Screenshot-based competitor analysis |
| A/B Testing | `content/models.py` (ABTest, PostVersion) | Partial implementation |
| Shopify integration | `analytics/shopify_oauth.py`, `ShopifyStore` model | Stub; no active usage |
| Walk-in events | `qr_attribution/models.py` (WalkInEvent) | Niche physical-retail feature |

### 10. Dead/Deprecated Code Indicators

| Indicator | Location | Evidence |
|-----------|----------|----------|
| `media_queue` references | README mentions it | App doesn't exist; `media/tasks.py` has deprecated no-op |
| `memes` app | README mentions it | App doesn't exist |
| `campaigns` app | `apps/campaigns/` | Empty models, migrations-only |
| Deprecated task | `media/tasks.py` | **Removed** — no-op `media_queue.process_queues` deleted; prune command still cleans DB beat rows |

### 11. Test Coverage Gaps

| Item | Detail |
|------|--------|
| Config | `pyproject.toml` sets 70% coverage threshold |
| Tests | `tests/` has ~138 pytest files |
| Risk | 70% threshold may mask gaps in critical paths (WhatsApp commerce, M-Pesa callbacks) |
| Action | Audit test coverage for: WhatsApp webhook, commerce state machine, M-Pesa callbacks, publishing pipeline |

### 12. Migration History Accumulation

| Item | Detail |
|------|--------|
| Issue | 27 apps × many migrations = slow `migrate` on fresh deploys |
| Action | Consider squashing migrations for stable apps before V1 launch |
| Effort | Low-Medium |

---

## Low Debt (V2)

### 13. UserProfile Field Bloat

| Item | Detail |
|------|--------|
| Issue | `UserProfile` stores Business Brain (6 layers), commerce settings, autopilot config, WhatsApp settings, and more. It's becoming a God Object. |
| Action | Extract Business Brain into dedicated model in V2. |

### 14. Partner/Marketplace Over-Engineering

| Item | Detail |
|------|--------|
| Issue | 10 models + webhook delivery + seller provisioning + API for a feature that has no active users yet |
| Action | Keep code but hide from UI. Revisit when marketplace is actively needed. |

### 15. Fundraising/Marketing Directories

| Item | Detail |
|------|--------|
| Location | `fundraising/`, `marketing/` |
| Issue | Non-runtime content (legal docs, pitch deck, brochures) lives alongside application code |
| Action | Move to a separate repository or cloud storage. Not a runtime concern. |

---

## Debt Prioritization Matrix

| Priority | Items | Effort | Impact |
|----------|-------|--------|--------|
| **P0 (before launch)** | #1 (campaigns), #2 (kova_page), #4 (model names) | Low-Medium | Reduces confusion |
| **P1 (V1 timeline)** | #5 (Photoroom), #6 (inbox), #7 (APIs) | Medium | Reduces maintenance surface |
| **P2 (V1.1)** | #9 (unused features), #10 (dead code), #11 (tests), #12 (migrations) | Medium | Improves reliability |
| **P3 (V2)** | #3 (docs/config), #8 (services), #13 (UserProfile), #14 (partners), #15 (fundraising) | High | Architecture improvement |

---

## Quick Wins (Can Do This Week)

1. Remove `campaigns` from INSTALLED_APPS with a comment about migration history
2. Add `# DEPRECATED` comments to unused code paths (`media_queue`, `memes` references)
3. Hide non-V1 features from navigation (feature flags or simple template conditionals)
4. Document the `docs/config/` convention in README
5. Remove `fundraising/` and `marketing/` from production Docker builds
