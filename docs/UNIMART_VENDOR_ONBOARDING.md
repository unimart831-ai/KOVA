# UNIMART Vendor Onboarding on Kova

> **Audience:** UNIMART engineering + ops  
> **API base:** `https://app.kova.co.ke/api/v1/partner/`  
> **Auth header:** `X-Kova-Partner-Key: <your_api_key>`

---

## How UNIMART vendors get on Kova today

UNIMART uses the **Marketplace Partner API**. Kova does not mirror UNIMART’s Django models (Campus, Seller, etc.). Instead, UNIMART pushes sellers and products via REST; Kova stores campus codes and UNIMART-specific fields in JSON metadata.

### Identity strategy (UNIMART config)

| Setting | UNIMART value | Meaning |
|---------|---------------|---------|
| `seller_identity_field` | `external_id` | Primary key is UNIMART’s USK-prefixed seller ID |
| `email` | Optional on provision | If omitted → `{external_seller_id}@unimart.marketplace.kova.co.ke` |
| `auto_activate_sellers` | `true` | Seller can sync products immediately |
| `seller_default_plan` | `growth` | Growth tier for AI content |

**Rule:** Always send `external_seller_id` (e.g. `USK-00123`). Email is optional but recommended if the seller already has a real address.

---

## One vendor, end-to-end (< 15 min)

### 0. Prerequisites

- UNIMART `MarketplacePartner` created in Kova admin (slug e.g. `unimart` or `unimart-africa` — must match self-serve join URL)
- API key copied at creation (shown once)
- Celery worker running (for welcome email, Snap/Autopilot, webhooks)
- For staging: enable **Sandbox mode** on the partner (posts dry-run, no live publish)

### 1. Verify connection

```bash
curl -s -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  "https://app.kova.co.ke/api/v1/partner/info/"
```

Expected: `"slug": "<your-slug>"` (e.g. `unimart-africa`), `"seller_identity_field": "external_id"`.

### 2. Provision the seller

```bash
curl -s -X POST \
  -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "external_seller_id": "USK-00123",
    "full_name": "Jane Kamau",
    "email": "jane@usiu.ac.ke",
    "business_name": "Jane Electronics",
    "business_url": "https://unimartafrica.com/stores/jane-electronics",
    "business_description": "Electronics and accessories for USIU students",
    "location": "Nairobi",
    "seller_metadata": {
      "campus_codes": ["USIU", "KU"],
      "delivery_zones": ["same_campus", "same_city"],
      "seller_tier": "gold"
    }
  }' \
  "https://app.kova.co.ke/api/v1/partner/sellers/"
```

**201 response:**

```json
{
  "status": "provisioned",
  "external_seller_id": "USK-00123",
  "email": "jane@usiu.ac.ke",
  "business_name": "Jane Electronics",
  "seller_status": "active",
  "plan": "growth",
  "auto_activated": true
}
```

**Side effects (if configured):**

- `seller.activated` webhook → UNIMART callback URL
- Welcome email with magic password-reset link (if `seller_welcome_email` is on)

### 3. Sync products (batch up to ~50 per call)

```bash
curl -s -X POST \
  -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "external_id": "PROD-001",
        "name": "Samsung Galaxy A54",
        "description": "Great phone for students",
        "price": 45000,
        "image_url": "https://cdn.unimartafrica.com/products/a54.jpg",
        "product_url": "https://unimartafrica.com/products/samsung-a54",
        "category": "Electronics",
        "condition": "refurbished",
        "old_price": 52000,
        "vendor_net_price": 42000,
        "campus_codes": ["USIU", "KU"],
        "variants": [
          {"attribute": "Color", "value": "Black"},
          {"attribute": "Storage", "value": "128GB", "additional_price": 3000}
        ],
        "specifications": [
          {"key": "Screen Size", "value": "6.4 inches"},
          {"key": "Battery", "value": "5000mAh"}
        ],
        "stock_status": "in_stock",
        "quantity": 15,
        "tags": ["bestseller", "samsung"]
      }
    ]
  }' \
  "https://app.kova.co.ke/api/v1/partner/sellers/USK-00123/products/sync/"
```

**201 response:**

```json
{
  "created": 1,
  "updated": 0,
  "errors": [],
  "snap_triggered": true,
  "autopilot_queued": 1
}
```

With `auto_snap_on_sync=true`, products that include `image_url` queue Snap/Autopilot automatically. Captions use enriched descriptions (condition, specs, variants) and CTAs point to `product_url` when `enforce_marketplace_cta=true`.

### 4. Confirm seller status

```bash
curl -s -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  "https://app.kova.co.ke/api/v1/partner/sellers/USK-00123/"
```

Check `products_synced`, `content_generated`, and listed products.

### 5. Poll aggregate stats (ops dashboard)

```bash
curl -s -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  "https://app.kova.co.ke/api/v1/partner/stats/"
```

---

## Bulk vendor onboarding (many sellers)

Use **`POST /api/v1/partner/sellers/bulk/`** (max 100 sellers per request):

```bash
curl -s -X POST \
  -H "X-Kova-Partner-Key: $KOVA_PARTNER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sellers": [
      {
        "external_seller_id": "USK-00123",
        "full_name": "Jane Kamau",
        "business_name": "Jane Electronics",
        "seller_metadata": {"campus_codes": ["USIU"]}
      },
      {
        "external_seller_id": "USK-00456",
        "full_name": "Brian Ochieng",
        "business_name": "Campus Snacks",
        "seller_metadata": {"campus_codes": ["UON"]}
      }
    ]
  }' \
  "https://app.kova.co.ke/api/v1/partner/sellers/bulk/"
```

**Response:**

```json
{
  "summary": {"provisioned": 2, "already_exists": 0, "failed": 0},
  "results": [
    {"index": 0, "status": "provisioned", "external_seller_id": "USK-00123", "email": "USK-00123@unimart.marketplace.kova.co.ke", ...},
    {"index": 1, "status": "provisioned", "external_seller_id": "USK-00456", ...}
  ]
}
```

Then sync products per seller with the same `/products/sync/` endpoint. Run product sync in parallel per seller, batches of 50 products.

---

## UNIMART ops playbook (campus launch)

### Phase A — Kova admin setup (Kova team, once)

1. **Admin Dashboard → Partners → Marketplaces → Create**
   - Name: `UNIMART Africa`, slug: `unimart-africa` (or legacy `unimart` — slug drives join URL and CLI `--partner-slug`)
   - Seller identity: **External ID**
   - Plan: **Growth**, auto-activate: **on**
   - Webhook URL: UNIMART endpoint (e.g. `https://api.unimartafrica.com/webhooks/kova/`)
   - Webhook secret: shared HMAC key
   - Enable: enforce marketplace CTA, auto Autopilot on sync, enrich descriptions, seller welcome email
2. Copy API key → share with UNIMART backend (secrets manager only)
3. Start with **Sandbox mode ON** for a pilot campus; flip off for production

### Phase B — UNIMART backend (per campus or batch)

1. Export active sellers for campus (USK ID, name, shop name, campus codes, store URL)
2. `POST /sellers/bulk/` for that batch
3. For each seller, push catalog via `POST /sellers/{USK-ID}/products/sync/`
4. Handle webhooks:
   - `seller.activated` → mark vendor “Kova live” in UNIMART admin
   - `product.synced` → update sync timestamp
   - `content.generated` / `post.published` → show in UNIMART seller dashboard (future UI)
5. `GET /stats/` daily for ops review

### Phase C — Single vendor going live (< 15 min)

| Step | Who | Action | Time |
|------|-----|--------|------|
| 1 | UNIMART ops | Confirm seller is active on UNIMART with ≥1 product + image | 2 min |
| 2 | UNIMART backend | `POST /sellers/` with USK ID + metadata | 1 min |
| 3 | UNIMART backend | `POST .../products/sync/` (seller’s catalog) | 5 min |
| 4 | Vendor | Open welcome email → set password → connect Instagram/TikTok in Kova | 5 min |
| 5 | UNIMART ops | `GET /sellers/{id}/` — verify `products_synced` > 0 | 1 min |

---

## Onboarding modes ranked (easiest → hardest)

| Mode | Status | Best for |
|------|--------|----------|
| **Bulk Partner API** (`POST /sellers/bulk/`) | ✅ Built | Campus launches, 10–1000 vendors |
| **Single Partner API** (`POST /sellers/`) | ✅ Built | One-off fixes, testing |
| **Product sync API** | ✅ Built | Catalog push after provision |
| **Welcome email + magic link** | ✅ Built | Vendor self-serve login (password reset) |
| **Webhooks** (`seller.activated`, `product.synced`, `content.generated`, `post.published`) | ✅ Built | UNIMART status dashboard |
| **Sandbox mode** | ✅ Built | Pilot without live posts |
| **Admin integration dashboard** | ✅ Built | Kova staff: sellers, webhooks, config |
| **CSV admin import (sellers)** | ✅ Built | Manual ops without API |
| **Self-serve seller invite link** | ✅ Built | Vendor opts in without UNIMART push |
| **Management command CSV import** | ✅ Built | `python manage.py import_unimart_vendors` |
| **UNIMART dashboard iframe** | ❌ Not built | Embedded Kova analytics in UNIMART |
| **Catalog export → auto sync job** | ❌ Not built | Nightly UNIMART → Kova sync |

---

## When UNIMART has no API

If UNIMART cannot call Kova's Partner API yet, use **file-based onboarding**. Kova provisions sellers and products from CSV exports — no REST integration required on the UNIMART side.

### Onboarding paths ranked (no API)

| Path | Effort | Best for |
|------|--------|----------|
| **1. Kova-side CSV import** | Lowest | Campus launch — UNIMART exports spreadsheet → Kova imports |
| **2. Vendor self-serve invite** | Low | Vendors opt in via link; USK pre-loaded or approval queue |
| **3. Manual ops + bulk tools** | Medium | Kova staff: admin upload + management command |
| **4. Future: UNIMART daily export** | Higher (UNIMART builds) | Automated CSV to SFTP/email; optional Kova webhook consumer |

### Path 1 — CSV import (recommended v1)

**Who runs it:** Kova ops or UNIMART ops with Kova admin access.

**Management command:**

```bash
python manage.py import_unimart_vendors path/to/sellers.csv --partner-slug unimart-africa
python manage.py import_unimart_vendors sellers.csv --products-csv products.csv --partner-slug unimart-africa
python manage.py import_unimart_vendors sellers.csv --dry-run   # parse only
python manage.py import_unimart_vendors sellers.csv --create-partner  # if slug missing
```

**Admin UI (recommended):**

1. **Admin Dashboard → Partners → Marketplaces** → open your marketplace (e.g. UNIMART Africa)
2. Click **Import vendors (CSV)** (green button), or go directly to:
   - `/dashboard/partners/marketplaces/<id>/import/`
3. Upload **Sellers CSV**; optionally **Products CSV** on the same form

The import block also appears at the top of the marketplace detail page (`/dashboard/partners/marketplaces/<id>/`). CSV upload requires **superuser** (senior staff); viewing the page is available to all staff.

**Slug note:** Docs and examples often use `unimart`; if you created the partner with slug `unimart-africa`, use that slug everywhere — API `info` response, CLI `--partner-slug`, and self-serve join URL `/partners/unimart-africa/join/`.

Uses the same `provision_marketplace_seller()` logic as the Partner API — welcome emails, webhooks, and auto-activation still apply.

#### Sellers CSV template

```csv
external_seller_id,full_name,email,business_name,business_url,campus_codes
USK-00123,Jane Kamau,jane@usiu.ac.ke,Jane Electronics,https://unimartafrica.com/stores/jane-electronics,"USIU,KU"
USK-00456,Brian Ochieng,,Campus Snacks,https://unimartafrica.com/stores/campus-snacks,USIU
```

| Column | Required | Notes |
|--------|----------|-------|
| `external_seller_id` | Yes | UNIMART USK ID (e.g. `USK-00123`) |
| `full_name` | Recommended | Seller display name |
| `email` | Optional | If omitted → `{USK}@unimart.marketplace.kova.co.ke` |
| `business_name` | Recommended | Shop name |
| `business_url` | Optional | UNIMART store URL (used in post CTAs) |
| `campus_codes` | Optional | Comma-separated or JSON array `["USIU","KU"]` |
| `pending_only` | Optional | `true` = add to invite list only (no provision) |

#### Products CSV template (optional second file)

```csv
external_seller_id,external_id,name,description,price,image_url,product_url,campus_codes,stock_status
USK-00123,PROD-001,Samsung Galaxy A54,Great phone for students,45000,https://cdn.unimartafrica.com/a54.jpg,https://unimartafrica.com/products/a54,"USIU,KU",in_stock
```

Import sellers first, then products. Rows are grouped by `external_seller_id`.

### Path 2 — Vendor self-serve invite

Share this link with UNIMART sellers (campus email, WhatsApp, in-app banner):

```
https://app.kova.co.ke/partners/<slug>/join/
https://app.kova.co.ke/partners/unimart-africa/join/?usk=USK-00123
```

Replace `<slug>` with your marketplace slug (`unimart` or `unimart-africa`).

**Flow:**

1. Vendor enters USK ID, name, email, business name
2. If USK is on the **pending invite list** (from CSV with `pending_only=true`) → provisioned immediately
3. If **open join** is enabled (default) → account created as **Invited** (Kova staff approves in admin)
4. Vendor receives welcome email → sets password → connects Instagram/TikTok at `/platforms/`

**Configure in marketplace `settings` JSON:**

```json
{
  "allow_open_vendor_join": true,
  "vendor_join_pending_usks": ["USK-00123", "USK-00456"],
  "vendor_join_usk_pattern": "^USK-[A-Za-z0-9-]+$"
}
```

### Path 3 — Manual ops playbook (first campus, no API)

| Step | Who | Action | Time |
|------|-----|--------|------|
| 1 | Kova team | Create `MarketplacePartner` (e.g. slug `unimart-africa`) in admin (sandbox ON) | 10 min |
| 2 | UNIMART ops | Export active USIU sellers to CSV (USK, name, shop, email, campus) | 15 min |
| 3 | Kova / UNIMART ops | Upload CSV in marketplace admin **or** run `import_unimart_vendors` | 2 min |
| 4 | UNIMART ops | Export product catalog CSV; upload products file | 30 min |
| 5 | Vendors | Welcome email → password → connect social | 5 min each |
| 6 | Kova ops | Admin marketplace detail → verify sellers active, products synced | 5 min |

For vendors not in the bulk CSV, share the self-serve join link (Path 2).

### Path 4 — Future: UNIMART lightweight export

When UNIMART adds a scheduled export (no live API):

- **Daily CSV** to SFTP or shared email → Kova cron runs `import_unimart_vendors`
- **Optional:** Kova webhook *outbound only* (seller.activated, content.generated) so UNIMART can poll or receive status without calling Kova's provision API

This keeps UNIMART's integration surface minimal (file drop only) while Kova handles provisioning.

---

## Recommended next builds (UNIMART-specific)

1. **UNIMART webhook consumer** — persist Kova events to show “Content ready” / “Posted to Instagram” in seller admin
2. **Campus batch job** — UNIMART cron: export sellers by `campus_code` → bulk provision + product sync
3. **Onboarding status API** — UNIMART calls `GET /sellers/?status=active` + content endpoints for a campus dashboard
4. **Seller magic link endpoint** — Kova returns one-time login URL in provision response (today: welcome email only)
5. **Scheduled CSV sync job** — cron wrapper around `import_unimart_vendors` for daily UNIMART exports

---

## Environment & setup

### Kova (server)

| Variable | Purpose |
|----------|---------|
| `SITE_URL` | Base URL for welcome email password-reset links |
| Celery broker + worker | Webhooks, welcome email, Snap/Autopilot |
| Resend (or email backend) | Welcome emails |

### Create UNIMART marketplace partner (Django shell)

```python
from apps.partners.models import MarketplacePartner, Partner
from apps.partners.models import generate_api_key, hash_api_key

partner = Partner.objects.get(referral_code="...")  # or create one
raw_key = generate_api_key()
mp = MarketplacePartner.objects.create(
    name="UNIMART Africa",
    slug="unimart",
    partner=partner,
    api_key_hash=hash_api_key(raw_key),
    api_key_prefix=raw_key[:8],
    seller_identity_field="external_id",
    auto_activate_sellers=True,
    seller_default_plan="growth",
    seller_welcome_email=True,
    billing_model="flat_fee",
    flat_fee_kes=25000,
    max_sellers=2000,
    enforce_marketplace_cta=True,
    auto_snap_on_sync=True,
    enrich_descriptions=True,
    product_field_mapping={"title": "name", "sku": "external_id", "amount": "price"},
    seller_data_mapping={"business_name": "shop_name", "seller_tier": "tier", "campus_codes": "locations"},
    settings={
        "allowed_platforms": ["instagram", "facebook", "tiktok", "whatsapp"],
        "max_products_per_seller": 500,
        "webhook_events": ["seller.activated", "product.synced", "content.generated", "post.published"],
        "branding": {"accent_color": "#0d8474", "powered_by_text": "Powered by Kova × UNIMART"},
    },
    webhook_url="https://api.unimartafrica.com/webhooks/kova/",
    is_sandbox=True,  # pilot only
)
print("API KEY (save once):", raw_key)
```

### UNIMART backend

```bash
export KOVA_PARTNER_KEY="kmp_..."
export KOVA_API_BASE="https://app.kova.co.ke/api/v1/partner"
```

Verify webhook signature on incoming POSTs: header `X-Kova-Signature` = HMAC-SHA256 of raw JSON body using `webhook_secret`.

---

## Webhook payload examples

**seller.activated**

```json
{
  "event": "seller.activated",
  "marketplace": "unimart",
  "timestamp": "2026-04-18T10:00:00+00:00",
  "data": {
    "external_seller_id": "USK-00123",
    "seller_email": "jane@usiu.ac.ke",
    "business_name": "Jane Electronics",
    "seller_status": "active",
    "auto_activated": true,
    "is_sandbox": false
  }
}
```

**product.synced**

```json
{
  "event": "product.synced",
  "data": {
    "external_seller_id": "USK-00123",
    "created": 5,
    "updated": 2,
    "product_ids": ["uuid-1", "uuid-2"]
  }
}
```

---

## Related docs

- [MARKETPLACE_PARTNER_SYSTEM.md](./MARKETPLACE_PARTNER_SYSTEM.md) — full API reference
- [UNIMART_KOVA_STRATEGY.md](./UNIMART_KOVA_STRATEGY.md) — UNIMART brand social strategy on Kova (separate from vendor API)
