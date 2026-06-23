# Route Inventory

Last updated: 2026-06-23  
Purpose: ownership tags for navigation, de-scope, and on-call routing.

## Ownership tags

| Tag | Meaning |
|-----|---------|
| **core-loop** | Daily owner workflow: brief → sell → approve → close |
| **commerce** | Shop, snap, M-Pesa, products |
| **engage** | Leads, inbox, replies |
| **service** | Bookings, service businesses |
| **grow** | Content studio, publish |
| **setup** | Onboarding, settings, billing |
| **staff** | Internal / agency tools (hide from SMB nav) |
| **legacy** | Kept for power users; candidate to hide |
| **public** | No auth required |
| **api** | Pro/Agency REST API |

## Core loop (SMB default)

| Path | Name | Tag | Module |
|------|------|-----|--------|
| `/brief/` | `brief:home` | core-loop | `apps/briefs` |
| `/products/snap/` | `products:snap` | core-loop, commerce | `apps/products` |
| `/products/` | `products:list` | commerce | `apps/products` |
| `/content/studio/` | `content:studio` | core-loop, grow | `apps/content` |
| `/engage/` | `engage:*` | core-loop, engage | `apps/engage` |
| `/leads/` | `leads:*` | engage | `apps/leads` |
| `/bookings/` | `bookings:list` | service | `apps/bookings` |
| `/book/<slug>/` | `bookings:public_book` | service, public | `apps/bookings` |
| Master WA webhook | `whatsapp:webhook` | core-loop | `apps/whatsapp` |

## WhatsApp owner commands (no route — master number)

| Command | Tag | Handler |
|---------|-----|---------|
| Photo | core-loop, commerce | `owner_snap_whatsapp` |
| STANDUP, BRIEF, SCORE | core-loop | `whatsapp_commands` |
| APPROVE / REJECT | core-loop, grow | `content.approval` |
| MONEY | core-loop, commerce | `briefs.revenue_summary` |
| LEADS | engage | `leads.models` |
| BOOK | service | `bookings.service_setup` |

## Setup & account

| Path | Tag | Module |
|------|-----|--------|
| `/accounts/onboarding/*` | setup | `apps/accounts` |
| `/accounts/settings/` | setup | `apps/accounts` |
| `/platforms/` | setup | `apps/platforms` |
| `/billing/` | setup | `apps/billing` |

## Staff / legacy (hidden from default SMB nav)

| Path | Tag | Module | Notes |
|------|-----|--------|-------|
| `/agents/` | staff | `apps/agents` | Staff-only redirect |
| `/whatsapp/analytics/` | legacy | `apps/whatsapp` | Hidden sub-nav |
| `/whatsapp/channels/` | legacy | `apps/whatsapp` | Hidden sub-nav |
| `/emails/` | legacy | `apps/emails` | Email marketing depth |
| `/dashboard/` | staff | `apps/admin_dashboard` | Ops / pilot |
| `/analytics/` (deep) | legacy | `apps/analytics` | Attribution detail |

## Public & commerce surfaces

| Path | Tag | Module |
|------|-----|--------|
| `/shop/<slug>/` | public, commerce | `apps/products` |
| `/k/<slug>/` | public | `apps/links` |
| `/p/<slug>/` | public | `apps/kova_page` |
| `/health/` | public | `config.urls` |

## API (Pro / Agency)

| Path | Tag | Module |
|------|-----|--------|
| `/api/v1/assets/` | api, commerce | `apps/api` |
| `/api/v1/products/` | api, commerce | `apps/api` |
| `/api/v1/posts/` | api, grow | `apps/api` |
| `/api/v1/conversions/` | api | `apps/api` |
| `/api/schema/` | api, public | `apps/api` |

## De-scope guidance

Hide or defer routes that are **not** tagged `core-loop`, `commerce`, `engage`, or `service` until:

- Time to first published content improves
- WhatsApp command adoption ≥ 40% WAU
- Service booking conversion baseline established

## CI validation

`python manage.py core_smoke` resolves critical routes listed above.  
Extend `CRITICAL_ROUTES` in `apps/accounts/management/commands/core_smoke.py` when adding core-loop paths.
