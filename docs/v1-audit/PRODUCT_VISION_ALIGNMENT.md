# Product Vision Alignment Assessment

**Date:** July 2026

---

## Product Statement

> Kova helps businesses create content, showcase products and services, publish everywhere, and manage customer conversations through WhatsApp, while the web platform serves as the orchestration and business management engine.

---

## Module-by-Module Assessment

### Core Modules

| Module | Alignment | Rating | Justification |
|--------|-----------|--------|---------------|
| **WhatsApp (14 models, 14 files)** | Fully Aligned | ★★★★★ | Central to the vision. Owner commands, customer commerce, FAQ autopilot, daily brief delivery — this IS the primary interface. |
| **Agents (6 agents)** | Fully Aligned | ★★★★★ | AI intelligence that powers the "business runs itself" promise. Research → Create → Publish → Analyze → Adapt loop is the core value. |
| **Content (10 models)** | Fully Aligned | ★★★★★ | Content generation and publishing pipeline is a primary pillar. Seeds → Posts → Publish → Metrics cycle delivers the "create content" promise. |
| **Business Brain** | Fully Aligned | ★★★★★ | Six-layer DNA model grounds all AI output in business context. Essential for personalized, relevant content and conversations. |
| **Products (9 models)** | Fully Aligned | ★★★★★ | "Showcase products and services" is an explicit part of the vision. Snap-to-Sell makes product creation WhatsApp-native. |
| **Briefs (2 models)** | Fully Aligned | ★★★★★ | Daily Brief delivered via WhatsApp is the primary touchpoint. Owner commands enable management without opening the web app. |
| **Platforms (1 model, 7 providers)** | Fully Aligned | ★★★★★ | "Publish everywhere" requires multi-platform OAuth and publishing. Core infrastructure. |

### Supporting Modules

| Module | Alignment | Rating | Justification |
|--------|-----------|--------|---------------|
| **Billing (9 models)** | Fully Aligned | ★★★★☆ | Business necessity. M-Pesa integration is Africa-native. Supports the target market. |
| **Leads (5 models)** | Partially Aligned | ★★★★☆ | Lead capture from storefront/WhatsApp aligns. However, the web-based CRM pipeline view and nurture sequences suggest web-first usage patterns. Should be simplified to WhatsApp-native lead notifications. |
| **Links (6 models)** | Partially Aligned | ★★★★☆ | Link-in-bio pages showcase the business online (aligned). But the management UI is web-heavy. Configuration-only web access is appropriate. |
| **Bookings (2 models)** | Partially Aligned | ★★★★☆ | Booking links are commerce infrastructure (aligned). Public booking page → WhatsApp confirmation is the right flow. Web management of availability is appropriate as configuration. |
| **Engage (3 models)** | Partially Aligned | ★★★☆☆ | AI auto-replies to social comments/DMs aligns with "manage customer conversations." However, the web-based inbox (dm_inbox, unified_inbox) competes with WhatsApp as the primary interface. Should route escalations to WhatsApp owner notifications instead. |
| **Analytics (13 models)** | Partially Aligned | ★★★☆☆ | Analytics supports the web platform's role as intelligence layer. However, 13 models suggest over-engineering. Competitor intel, Kova Pixel, Shopify integration, and conversion journeys add complexity beyond V1 needs. Simplify to: post metrics + revenue + growth. |
| **Notifications (2 models)** | Partially Aligned | ★★★☆☆ | In-app notifications serve web users — but WhatsApp should be the primary notification channel. The WebSocket/in-app system should be secondary. |
| **Emails (7 models)** | Partially Aligned | ★★★☆☆ | Transactional email is necessary. But email marketing (campaigns, sequences, subscriber lists) competes with WhatsApp's role as the communication channel. For African SMEs, WhatsApp broadcasts > email campaigns. |
| **Calendar Intel (0 models)** | Partially Aligned | ★★★☆☆ | Holiday awareness for content timing is smart. Lightweight, no overhead. Keep but don't emphasize. |
| **Media (0 models, 12 files)** | Partially Aligned | ★★★☆☆ | Media orchestration supports content creation. However, the complexity (Remotion, Fal, Bannerbear, Kling video) exceeds V1 needs. Simplify to Photoroom + AI image generation. |

### Needs Redesign

| Module | Alignment | Rating | Justification |
|--------|-----------|--------|---------------|
| **Admin Dashboard (141 templates)** | Needs Redesign | ★★☆☆☆ | The staff dashboard is enormous (~250 routes). It serves internal ops, not the product vision. Should be simplified to essential monitoring. Not user-facing but adds maintenance burden. |
| **Teams (5 models)** | Needs Redesign | ★★☆☆☆ | Multi-brand agency support is a V2 feature. Single business owners (the V1 target) don't need teams. Should be hidden/deferred. |
| **Profile Audit (0 models)** | Needs Redesign | ★★☆☆☆ | Social profile completeness audits are web-centric. Could be valuable as a WhatsApp-delivered insight ("Your Instagram bio is missing X") but currently assumes web interaction. |

### Future Version

| Module | Alignment | Rating | Justification |
|--------|-----------|--------|---------------|
| **Partners (10 models)** | Future Version | ★★☆☆☆ | Referral program + marketplace B2B is a growth feature, not core product. 10 models is significant infrastructure for a feature that doesn't serve the WhatsApp-first promise directly. Defer to V2. |
| **QR Attribution (3 models)** | Future Version | ★★☆☆☆ | Physical-to-digital attribution is innovative but premature. Doesn't serve the "manage via WhatsApp" core. Defer to V2. |
| **Reviews (1 model)** | Future Version | ★★★☆☆ | Review request loop after purchase is valuable but not core to V1. The WhatsApp delivery mechanism is aligned; defer the full loop to V1.1. |

### Remove

| Module | Alignment | Rating | Justification |
|--------|-----------|--------|---------------|
| **Campaigns (0 models)** | Remove | ☆☆☆☆☆ | Already emptied — migrations-only legacy app. Remove from INSTALLED_APPS after ensuring migration history is preserved. |
| **kova_page (0 models)** | Remove | ★☆☆☆☆ | Duplicates `links.KovaPage` functionality. The AI Salesperson feature (`salesperson.py`) is valuable but should be moved to the `products` or `links` app. |

---

## Vision Alignment Summary

```
FULLY ALIGNED (core V1):
  WhatsApp | Agents | Content | Products | Briefs | Platforms | Business Brain

PARTIALLY ALIGNED (simplify for V1):
  Billing | Leads | Links | Bookings | Engage | Analytics | Notifications | Emails | Calendar | Media

NEEDS REDESIGN:
  Admin Dashboard | Teams | Profile Audit

FUTURE VERSION:
  Partners | QR Attribution | Reviews

REMOVE:
  Campaigns (legacy) | kova_page (duplicate)
```

---

## Recommendations

1. **Strengthen the WhatsApp → everything flow.** Every business action should be initiatable from WhatsApp. Content approval, product listing, price updates, report requests — all via chat.

2. **Reduce web platform to configuration + analytics.** The web should feel like a settings panel, not a workspace. Business owners should rarely need to open it.

3. **Consolidate media pipeline.** 18 Photoroom files + Fal + Bannerbear + Remotion + Pillow = too many paths. Standardize on Photoroom + AI image generation for V1.

4. **Move email marketing to V1.1.** For African SMEs, WhatsApp broadcasts are more effective than email campaigns. The 7-model email system adds complexity without serving the primary channel.

5. **Defer partner/marketplace infrastructure.** 10 models + webhook delivery + seller provisioning is premature. Focus on direct B2C relationships in V1.
