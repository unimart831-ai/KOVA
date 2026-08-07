# Apps domains

Kova Agent code is grouped into **5 domains**. Django app **labels** (and migrations) are unchanged.

| Domain | Path | Contains |
|--------|------|----------|
| **core** | `apps/core/` | accounts, platforms (+ profile audit), billing, teams, partners, admin_dashboard, campaigns (legacy), utils, system |
| **create** | `apps/create/` | content, agents, media, briefs (+ calendar prefs) |
| **messaging** | `apps/messaging/` | engage (inbox hub), whatsapp, emails, notifications |
| **commerce** | `apps/commerce/` | products, links (+ hub), leads, bookings*, reviews*, qr_attribution* |
| **insight** | `apps/insight/` | analytics, api, help |

\* Optional surfaces gated by `KOVA_FEATURES` / env (`FEATURE_BOOKINGS`, `FEATURE_QR_ATTRIBUTION`, `FEATURE_REVIEWS`, `FEATURE_PARTNERS`). Defaults: **on**. Apps stay installed for migrations; URLs/nav/beat/middleware are gated.

## Imports

```python
from apps.core.accounts.models import UserProfile
from apps.messaging.whatsapp.models import WhatsAppConversation
from apps.commerce.products.models import Product
from apps.core.features import feature_enabled
```

## URL names

Unchanged (`engage:unified_inbox`, `whatsapp:conversation`, `kova_page:page`, `calendar_intel:preferences`, `profile_audit:list`, …).
