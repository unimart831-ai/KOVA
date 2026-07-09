# Web Platform Audit

**Date:** July 2026

---

## Vision Check

The web platform should behave as an **orchestration engine** — not the primary workspace. Business owners should interact primarily via WhatsApp. The web exists for:
- Configuration
- Commerce management
- Brand management
- Analytics
- Administration
- AI orchestration

---

## Page Classification

### Business Configuration

Pages where the business owner configures their Kova setup. These are **appropriate** for the web platform.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Account settings | `accounts/settings.html` | `/accounts/settings/` | **Keep** |
| Business Brain | `accounts/business_brain.html` | `/accounts/settings/brain/` | **Keep** |
| AI Learning | `accounts/ai_learning.html` | `/accounts/settings/ai/` | **Keep** |
| CTA settings | `accounts/cta_settings.html` | `/accounts/settings/cta/` | **Keep** |
| Platform connections | `platforms/list.html` | `/platforms/` | **Keep** |
| WhatsApp connect | `platforms/whatsapp_connect.html` | `/platforms/whatsapp/` | **Keep** |
| TikTok connect | `platforms/tiktok_connect_notice.html` | `/platforms/tiktok/` | **Keep** |
| LinkedIn page select | `platforms/linkedin_select_page.html` | `/platforms/linkedin/` | **Keep** |
| Notification preferences | `notifications/preferences.html` | `/notifications/preferences/` | **Keep** |
| Calendar preferences | `calendar_intel/preferences.html` | `/calendar/preferences/` | **Keep** |
| Billing overview | `billing/overview.html` | `/billing/` | **Keep** |

---

### Commerce Management

Pages for managing products, storefront, and bookings. **Appropriate** as orchestration.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Product list | `products/product_list.html` | `/products/` | **Keep** |
| Product detail | `products/product_detail.html` | `/products/<id>/` | **Keep** |
| Product form | `products/product_form.html` | `/products/add/` | **Keep** |
| Category list | `products/category_list.html` | `/products/categories/` | **Keep** |
| Category form | `products/category_form.html` | `/products/categories/add/` | **Keep** |
| Stock alerts | `products/stock_alerts.html` | `/products/stock/` | **Keep** |
| Snap-to-Sell | `products/snap_to_sell.html` | `/products/snap/` | **Keep** (also WhatsApp) |
| Batch Snap | `products/snap_batch.html` | `/products/snap/batch/` | **Keep** |
| Restock Scan | `products/restock_scan.html` | `/products/restock/` | **Simplify** |
| Showcase assets | `products/showcase_assets.html` | `/products/showcase/` | **Keep** |
| Asset intake | `products/asset_intake.html` | `/products/assets/intake/` | **Keep** |
| Product import | `products/product_import.html` | `/products/import/` | **Keep** |
| Booking links | `bookings/list.html` | `/bookings/` | **Keep** |
| Booking detail | `bookings/detail.html` | `/bookings/<id>/` | **Keep** |
| Booking calendar | `bookings/link_calendar.html` | `/bookings/<id>/calendar/` | **Keep** |
| Booking form | `bookings/link_form.html` | `/bookings/add/` | **Keep** |

---

### Brand Management

Pages for managing online brand presence and link pages.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Link pages list | `links/page_list.html` | `/links/` | **Keep** |
| Link page detail | `links/page_detail.html` | `/links/<id>/` | **Keep** |
| Link page form | `links/page_form.html` | `/links/add/` | **Keep** |
| Link form | `links/link_form.html` | `/links/<id>/links/add/` | **Keep** |
| Form builder | `links/form_form.html` | `/links/<id>/forms/add/` | **Keep** |

---

### Analytics

Pages for viewing business performance. **Appropriate** as intelligence layer.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Insights | `analytics/insights.html` | `/analytics/` | **Keep** |
| Revenue | `analytics/revenue.html` | `/analytics/revenue/` | **Keep** |
| Attribution | `analytics/attribution.html` | `/analytics/attribution/` | **Simplify** |
| Content intelligence | `analytics/content_intelligence.html` | `/analytics/content/` | **Merge** with insights |
| Campaign revenue | `analytics/campaign_revenue.html` | `/analytics/campaigns/` | **Simplify** |
| Competitors | `analytics/competitors.html` | `/analytics/competitors/` | **Future Version** |
| Competitor detail | `analytics/competitor_detail.html` | `/analytics/competitors/<id>/` | **Future Version** |
| Competitor add/edit | `analytics/competitor_add.html` | `/analytics/competitors/add/` | **Future Version** |
| Competitor landscape | `analytics/competitor_landscape.html` | `/analytics/landscape/` | **Future Version** |
| Pixel settings | `analytics/pixel_settings.html` | `/analytics/pixel/` | **Future Version** |
| Pixel events | `analytics/pixel_events.html` | `/analytics/pixel/events/` | **Future Version** |
| Screenshot compete | `analytics/screenshot_compete.html` | — | **Remove** |
| Performance recycle | `analytics/performance_recycle.html` | — | **Simplify** |

---

### Administration

Internal staff pages. Not user-facing.

| Page Group | Templates | Route | Verdict |
|------------|-----------|-------|---------|
| Admin dashboard | 141 templates | `/dashboard/` | **Keep** (staff only) |
| Django admin | Default | `/admin/` | **Keep** (staff only) |

---

### AI Orchestration

Pages for managing AI behavior. **Appropriate** as orchestration.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Agent control | `agents/control.html` | `/agents/` | **Keep** |
| Agent detail | `agents/detail.html` | `/agents/<type>/` | **Keep** |
| Agent activity log | `agents/activity_log.html` | `/agents/activity/` | **Simplify** |
| Strategist dashboard | `agents/strategist_dashboard.html` | `/agents/strategist/` | **Merge** into control |

---

### Legacy Dashboard (Needs Rethinking)

Pages that position the web as the primary daily workspace — contradicting the WhatsApp-first vision.

| Page | Template | Route | Issue | Verdict |
|------|----------|-------|-------|---------|
| Home/Brief | `briefs/home.html` | `/brief/` | Complex multi-section dashboard | **Redesign** |
| Decision stream | `briefs/_decision_stream.html` | — | Real-time activity feed | **Simplify** |
| Morning standup | `briefs/_morning_standup.html` | — | Should be WhatsApp-primary | **Keep** (secondary view) |
| Pending approvals | `briefs/_pending_approvals.html` | — | Should be WhatsApp-primary | **Keep** (secondary view) |
| Money board | `briefs/_money_board.html` | — | Revenue widget | **Keep** |
| Customer pulse | `briefs/_customer_pulse.html` | — | Customer activity | **Simplify** |
| Wedge checklist | `briefs/_wedge_checklist.html` | — | Onboarding tasks | **Remove** after onboarding |
| Operations report | `briefs/_operations_report.html` | — | Ops summary | **Simplify** |

---

### Content Studio (Needs Simplification)

These pages create a full content workspace — drawing users to the web instead of WhatsApp.

| Page | Template | Route | Verdict |
|------|----------|-------|---------|
| Content studio | `content/studio.html` | `/content/` | **Simplify** — overview only |
| Content queue | `content/queue.html` | `/content/queue/` | **Keep** — approval queue |
| Content calendar | `content/calendar.html` | `/content/calendar/` | **Keep** — scheduling view |
| Post detail | `content/detail.html` | `/content/<id>/` | **Keep** |
| Post edit | `content/edit.html` | `/content/<id>/edit/` | **Keep** — but de-emphasize |
| Post preview | `content/preview.html` | `/content/<id>/preview/` | **Keep** |
| Campaign proposals | `content/campaign_proposals.html` | `/content/campaigns/` | **Simplify** |

---

### Needs Removal

Pages that add complexity without serving the vision.

| Page | Template | Route | Reason | Verdict |
|------|----------|-------|--------|---------|
| Profile audit list | `profile_audit/list.html` | `/profile-audit/` | Web-centric feature | **Remove** |
| Profile audit detail | `profile_audit/detail.html` | `/profile-audit/<id>/` | Web-centric feature | **Remove** |
| Campus rep | `pages/campus_rep.html` | `/campus-rep/` | Marketing page, not product | **Remove** from app |
| Compare pages (3) | `pages/compare_*.html` | `/compare/` | Marketing, not product | **Remove** from app |

---

### Needs Simplification

| Page | Template | Current State | Recommendation |
|------|----------|---------------|----------------|
| WhatsApp inbox | `whatsapp/inbox.html` | Full web inbox | Simplify to history/search only |
| Unified inbox | `engage/unified_inbox.html` | Separate from WA inbox | Merge into single inbox view |
| DM inbox | `engage/dm_inbox.html` | Third inbox variant | Merge |
| Email dashboard | `emails/dashboard.html` | Full email marketing UI | Defer to V1.1 |
| Email campaigns | `emails/campaign_list.html` | Campaign management | Defer to V1.1 |
| Email sequences | `emails/sequence_list.html` | Sequence builder | Defer to V1.1 |
| Lead pipeline | `leads/lead_pipeline.html` | Kanban board | Simplify to list view |
| Lead analytics | `leads/lead_analytics.html` | Dashboard | Merge into main analytics |
| Nurture sequences | `leads/nurture_list.html` | Sequence builder | Defer to V1.1 |
| Teams management | `teams/*.html` (6 templates) | Full team/brand UI | Defer to V2 |
| Partner dashboard | `partners/dashboard.html` | Partner portal | Defer to V2 |
| QR management | `qr_attribution/*.html` (12) | QR creation/analytics | Defer to V2 |
| Reviews | `reviews/*.html` (2) | Review management | Defer to V1.1 |

---

## Summary: Page Verdict Distribution

| Verdict | Count | Description |
|---------|-------|-------------|
| **Keep** | ~45 | Configuration, commerce management, analytics (appropriate for web) |
| **Simplify** | ~12 | Too complex for orchestration role; reduce to essentials |
| **Merge** | ~6 | Duplicate/overlapping pages that should be consolidated |
| **Redesign** | ~3 | Home/dashboard needs to reflect WhatsApp-first reality |
| **Future Version** | ~15 | Competitor intel, pixel, QR, teams, partners |
| **Remove** | ~8 | Profile audit, compare pages, campus rep, legacy |

---

## Web Platform Design Principles for V1

1. **Brief-first homepage** — When a user opens the web, show them a clean summary + any pending actions. Not a complex multi-panel dashboard.

2. **Configuration over creation** — The web is where you set things up (products, platforms, settings), not where you create daily content.

3. **Read-heavy, write-light** — Analytics, history, and search are web-appropriate. Daily operations (approve, post, respond) should feel like they belong on WhatsApp.

4. **Progressive disclosure** — Don't show everything at once. Simple overview → drill into details when needed.

5. **No duplicate daily workflows** — If something can be done via WhatsApp commands, the web version should be clearly secondary (history view, not action center).

---

## Recommendations

1. **Redesign the home page (`/brief/`)** — Currently 8+ sections (decision stream, standup, approvals, money, pulse, wedge, ops report, agent activity). Replace with a clean 3-section layout: (1) Pending actions count, (2) This week's performance, (3) Quick links to configuration.

2. **Consolidate inbox views** — Three separate inbox pages (WhatsApp, Engage unified, DM) should be one view with tabs/filters.

3. **Hide V1.1/V2 features** — Email marketing, teams, partners, QR, competitor analysis should be completely hidden from navigation, not just de-emphasized.

4. **Simplify analytics to one page** — Currently 13+ analytics pages. For V1: one insights page with post performance + revenue + growth metrics.

5. **Remove profile audit** — Doesn't serve the vision. Can return as a WhatsApp-delivered insight in V2.
