# Marketplace Partner System — Technical Documentation

> **Version:** 1.0  
> **Last Updated:** April 18, 2026  
> **Commits:** `4122ae1` (initial), `c5825c7` (UNIMART compatibility)

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [How the Connection Works](#2-how-the-connection-works)
3. [Architecture Overview](#3-architecture-overview)
4. [Models & Data Structure](#4-models--data-structure)
5. [API Authentication](#5-api-authentication)
6. [API Endpoints Reference](#6-api-endpoints-reference)
7. [Seller Provisioning Flow](#7-seller-provisioning-flow)
8. [Product Sync Flow](#8-product-sync-flow)
9. [Marketplace Configuration Examples](#9-marketplace-configuration-examples)
10. [UNIMART Integration Specifics](#10-unimart-integration-specifics)
11. [Billing Models](#11-billing-models)
12. [Admin Dashboard](#12-admin-dashboard)
13. [Security](#13-security)
14. [Integration Guide for Marketplace Developers](#14-integration-guide-for-marketplace-developers)

---

## 1. What Is This?

The Marketplace Partner System is Kova's **B2B API layer** that lets external marketplaces (Jumia, Jiji, UNIMART Africa, etc.) connect their seller bases to Kova's AI content engine.

**The core idea:** A marketplace has thousands of sellers with products. Instead of each seller signing up individually, the marketplace provisions Kova accounts for their sellers via API and syncs product catalogs. Kova then generates social media content (captions, visuals, scheduling) for those products — powered by AI.

**Who benefits:**
- **Marketplace sellers** get professional social media content without lifting a finger
- **Marketplaces** increase seller engagement and GMV (sellers sell more when they market more)
- **Kova** gets bulk seller onboarding through one integration instead of one-by-one signups

---

## 2. How the Connection Works

```
┌──────────────────────┐         HTTPS/REST API         ┌──────────────────────┐
│                      │  ────────────────────────────▶  │                      │
│   MARKETPLACE        │     X-Kova-Partner-Key auth     │       KOVA           │
│   (Jumia, UNIMART,   │                                 │                      │
│    Jiji, etc.)        │  1. Provision sellers           │   Creates user       │
│                      │  2. Sync products               │   accounts + product │
│   Has: sellers,      │  3. Get stats                   │   catalogs           │
│   products, orders   │                                 │                      │
│                      │  ◀────────────────────────────  │   AI generates       │
│                      │     JSON responses + webhooks    │   social content     │
└──────────────────────┘                                 └──────────────────────┘
```

### Connection Flow (Step by Step):

1. **Kova admin creates a MarketplacePartner** in the admin dashboard — this generates a unique API key (shown once, stored hashed)
2. **Marketplace dev receives the API key** and includes it in every request as `X-Kova-Partner-Key` header
3. **Marketplace calls `POST /api/v1/partner/sellers/`** to provision seller accounts — Kova creates a user + profile for each seller
4. **Marketplace calls `POST /api/v1/partner/sellers/{id}/products/sync/`** to push product data — Kova creates/updates products in the seller's catalog
5. **Kova's AI engine** picks up the products and generates social media content (captions, visuals, scheduled posts)
6. **Marketplace can poll `GET /api/v1/partner/stats/`** to see how many sellers are active, products synced, content generated

### What happens behind the scenes:

```
Marketplace API Call                         Kova Internal Actions
─────────────────────                        ─────────────────────
POST /sellers/                          →    1. Find or create Django User
  { email, external_seller_id, ... }         2. Set plan on UserProfile
                                             3. Create MarketplaceSellerAccount
                                             4. (Optional) Send welcome email

POST /sellers/{id}/products/sync/       →    1. Apply field mapping (marketplace → Kova fields)
  { products: [...] }                        2. Validate each product
                                             3. Create/update Product records
                                             4. Build marketplace_metadata
                                             5. Enrich descriptions (if enabled)
                                             6. Trigger Snap to Sell AI (if enabled)
                                             7. Update seller sync stats
```

---

## 3. Architecture Overview

### Files Involved

| File | Purpose |
|------|---------|
| `apps/partners/models.py` | MarketplacePartner + MarketplaceSellerAccount models |
| `apps/products/models.py` | Product model (with source tracking + marketplace_metadata) |
| `apps/api/partner_auth.py` | API key authentication (X-Kova-Partner-Key) |
| `apps/api/partner_views.py` | All API endpoints + serializers |
| `apps/api/partner_urls.py` | URL routing (`/api/v1/partner/...`) |
| `apps/admin_dashboard/views/partners.py` | Admin UI for managing marketplace partners |
| `templates/admin_dashboard/partners/` | Admin templates (list, detail, create) |

### Relationship Map

```
MarketplacePartner (Jumia Kenya)
  │
  ├── api_key_hash (authentication)
  ├── seller_identity_field (email / phone / external_id)
  ├── product_field_mapping (marketplace fields → Kova fields)
  ├── billing_model (per_seller / flat / revenue_share)
  ├── enrich_descriptions (auto-enhance product descriptions)
  ├── seller_data_mapping (map marketplace seller fields)
  │
  ├── MarketplaceSellerAccount (seller_1)
  │     ├── user → Django User (auto-created)
  │     ├── external_seller_id (marketplace's ID)
  │     ├── business_name, business_url
  │     ├── seller_metadata (flexible JSON)
  │     └── status (invited → active → suspended → churned)
  │
  ├── MarketplaceSellerAccount (seller_2)
  │     └── ...
  │
  └── Product (via marketplace_partner FK)
        ├── source = "marketplace"
        ├── marketplace_partner → MarketplacePartner
        ├── marketplace_metadata (condition, variants, specs, etc.)
        └── last_synced_at
```

---

## 4. Models & Data Structure

### MarketplacePartner

The central configuration model. One per marketplace.

| Field | Type | Purpose |
|-------|------|---------|
| `name` | CharField | Display name (e.g. "Jumia Kenya") |
| `slug` | SlugField | URL-safe ID (e.g. "jumia-ke") — unique |
| `partner` | FK → Partner | Links to referral system for commission tracking |
| `api_key_hash` | CharField | SHA-256 of the API key (raw key never stored) |
| `api_key_prefix` | CharField | First 8 chars for identification |
| `seller_identity_field` | Choice | How sellers are identified: `email`, `phone`, or `external_id` |
| `auto_activate_sellers` | Boolean | Skip invitation step? |
| `seller_default_plan` | CharField | Plan assigned to new sellers (starter/growth/pro/agency) |
| `max_sellers` | Integer | Contract limit on provisioned sellers |
| `sync_direction` | Choice | push / pull / both |
| `auto_snap_on_sync` | Boolean | Auto-trigger Snap to Sell AI on product sync |
| `enforce_marketplace_cta` | Boolean | Force CTAs to link back to marketplace product pages |
| `product_field_mapping` | JSONField | Maps marketplace product fields to Kova fields |
| `enrich_descriptions` | Boolean | Auto-append specs/variants/condition to descriptions |
| `seller_data_mapping` | JSONField | Maps marketplace seller fields to metadata keys |
| `billing_model` | Choice | per_seller / flat_fee / revenue_share / free_pilot |
| `settings` | JSONField | Catch-all for marketplace-specific config |
| `webhook_url` | URLField | Event notification URL |
| `webhook_secret` | CharField | HMAC-SHA256 signing secret |

### MarketplaceSellerAccount

Links a marketplace seller to their Kova user account.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `marketplace` | FK → MarketplacePartner | Which marketplace |
| `user` | FK → User | The Kova user account (auto-created if needed) |
| `external_seller_id` | CharField | Marketplace's identifier for this seller |
| `status` | Choice | invited / active / suspended / churned |
| `business_name` | CharField | Seller's shop/business name |
| `business_url` | URLField | URL to seller's store on the marketplace |
| `seller_metadata` | JSONField | Flexible marketplace-specific seller data |
| `products_synced` | Integer | Count of synced products |
| `content_generated` | Integer | Count of AI-generated content pieces |
| `last_product_sync` | DateTime | Last sync timestamp |

**Unique constraints:** One user per marketplace, one external_seller_id per marketplace.

### Product (Source Tracking Fields)

| Field | Type | Purpose |
|-------|------|---------|
| `source` | Choice | manual / snap / csv / api / **marketplace** |
| `marketplace_partner` | FK → MarketplacePartner | Which marketplace synced this product |
| `last_synced_at` | DateTime | When the marketplace last updated this product |
| `marketplace_metadata` | JSONField | Marketplace-specific data (condition, variants, specs, campus_codes, vendor_net_price, etc.) |

---

## 5. API Authentication

Every marketplace partner gets a unique API key on creation. Authentication works via a custom DRF backend.

### How It Works

1. **Key generation:** `secrets.token_hex(20)` → 40-char hex string (e.g. `kmp_a3x7...`)
2. **Storage:** Only the SHA-256 hash is stored in `api_key_hash`. The raw key is shown **once** at creation and never again
3. **Prefix:** First 8 chars stored in `api_key_prefix` for identification in logs/admin

### Request Authentication

```
GET /api/v1/partner/info/
X-Kova-Partner-Key: kmp_a3x7e9f2b1c4d8a6e3f7b2c5d9a1e4f8b3c6d0
```

### Authentication Flow

```
Request with X-Kova-Partner-Key header
        │
        ▼
MarketplaceAPIKeyAuthentication.authenticate()
        │
        ├── No header? → Pass to next auth backend (returns None)
        ├── Empty header? → 401 "Empty API key"
        │
        ▼
MarketplacePartner.authenticate(raw_key)
        │
        ├── SHA-256 hash the raw key
        ├── Lookup by api_key_hash + is_active=True
        │
        ├── Not found? → 401 "Invalid or inactive API key"
        │
        ▼
Success: Returns MarketplacePartnerUser object
        │
        ├── Updates api_key_last_used timestamp
        └── Request proceeds to view
```

The view accesses the marketplace via `request.user.marketplace_partner`.

---

## 6. API Endpoints Reference

**Base URL:** `https://app.kova.co.ke/api/v1/partner/`  
**Auth:** `X-Kova-Partner-Key: <your_api_key>` on every request

### GET `/info/`
Returns marketplace configuration and current stats.

**Response:**
```json
{
  "name": "UNIMART Africa",
  "slug": "unimart",
  "seller_identity_field": "external_id",
  "seller_default_plan": "growth",
  "max_sellers": 1000,
  "active_sellers": 47,
  "total_sellers": 52,
  "total_products_synced": 1203,
  "billing_model": "per_seller",
  "enforce_marketplace_cta": true,
  "auto_snap_on_sync": true,
  "product_field_mapping": { "title": "name", "sku": "external_id" },
  "settings": { "allowed_platforms": ["instagram", "facebook"] }
}
```

### POST `/sellers/`
Provision a new seller account.

**Request:**
```json
{
  "email": "jane@example.com",
  "external_seller_id": "USK-00123",
  "full_name": "Jane Kamau",
  "business_name": "Jane Electronics",
  "business_url": "https://unimart.africa/stores/jane-electronics",
  "business_description": "Electronics and accessories for students",
  "location": "Nairobi",
  "seller_metadata": {
    "seller_tier": "gold",
    "campus_codes": ["USIU", "KU"],
    "delivery_zones": ["same_campus", "same_city"]
  }
}
```

**Response (201):**
```json
{
  "status": "provisioned",
  "external_seller_id": "USK-00123",
  "email": "jane@example.com",
  "business_name": "Jane Electronics",
  "seller_status": "active",
  "plan": "growth",
  "auto_activated": true
}
```

### GET `/sellers/`
List all sellers. Optional `?status=active` filter.

### GET `/sellers/{external_seller_id}/`
Get seller details + their synced products.

### POST `/sellers/{external_seller_id}/suspend/`
Suspend a seller (marketplace-initiated).

### POST `/sellers/{external_seller_id}/activate/`
Reactivate a suspended seller.

### POST `/sellers/{external_seller_id}/products/sync/`
Sync products for a seller.

**Request:**
```json
{
  "products": [
    {
      "external_id": "PROD-001",
      "name": "Samsung Galaxy A54",
      "description": "Latest Samsung phone with great camera",
      "price": 45000,
      "image_url": "https://cdn.unimart.africa/products/a54.jpg",
      "product_url": "https://unimart.africa/products/samsung-a54",
      "category": "Electronics",
      "condition": "new",
      "old_price": 52000,
      "vendor_net_price": 42000,
      "variants": [
        { "attribute": "Color", "value": "Black" },
        { "attribute": "Storage", "value": "128GB", "additional_price": 3000 }
      ],
      "specifications": [
        { "key": "Screen Size", "value": "6.4 inches" },
        { "key": "Battery", "value": "5000mAh" }
      ],
      "campus_codes": ["USIU", "KU", "UON"],
      "stock_status": "in_stock",
      "quantity": 15,
      "tags": ["bestseller", "samsung"]
    }
  ]
}
```

**Response (201):**
```json
{
  "created": 1,
  "updated": 0,
  "errors": [],
  "snap_triggered": true
}
```

### GET `/stats/`
Aggregate stats for the marketplace.

**Response:**
```json
{
  "marketplace": "UNIMART Africa",
  "sellers": { "total": 52, "active": 47, "invited": 3, "suspended": 2 },
  "products": {
    "total_synced": 1203,
    "by_stock_status": { "in_stock": 980, "low_stock": 123, "out_of_stock": 100 }
  },
  "content_generated": 4521,
  "billing": {
    "model": "per_seller",
    "rate_per_seller_kes": 150.0,
    "estimated_monthly_kes": 7050.0
  }
}
```

---

## 7. Seller Provisioning Flow

This is what happens when a marketplace calls `POST /sellers/`:

```
1. Marketplace sends seller data
        │
        ▼
2. Check seller limit (max_sellers)
        │ Exceeded? → 403 "Seller limit reached"
        ▼
3. Validate via SellerProvisionSerializer
        │ Ensures required identity field (email/phone/external_id)
        ▼
4. Check if seller already exists (by external_seller_id)
        │ Already exists? → 200 with current status
        ▼
5. Find or create Kova User
        │
        ├── seller_identity_field = "email"
        │     → Look up User by email, create if not found
        │
        ├── seller_identity_field = "phone"
        │     → Look up User by phone_number, create if not found
        │     → Auto-generates placeholder email: {ext_id}@{slug}.marketplace.kova.co.ke
        │
        └── seller_identity_field = "external_id"
              → Check existing links, fall back to email lookup, then create
              → Auto-generates placeholder email if no email provided
        │
        ▼
6. Set plan on UserProfile (seller_default_plan from marketplace config)
        │
        ▼
7. Build enriched seller_metadata
        │ Merges: provided metadata + business_description + location
        │ Applies: seller_data_mapping (renames keys per marketplace config)
        │
        ▼
8. Create MarketplaceSellerAccount
        │ Sets: business_name, business_url, seller_metadata
        │ Status: "active" (if auto_activate) or "invited" (if not)
        │
        ▼
9. Return 201 with seller details
```

### Identity Strategies

Different marketplaces identify sellers differently:

| Marketplace | `seller_identity_field` | How it works |
|-------------|------------------------|--------------|
| Jumia | `email` | Sellers identified by email — matches existing Kova users |
| UNIMART | `external_id` | Uses USK-prefixed IDs — Kova creates accounts with placeholder emails |
| WhatsApp-based | `phone` | Phone number lookup — placeholder email auto-generated |

---

## 8. Product Sync Flow

This is what happens when a marketplace calls `POST /sellers/{id}/products/sync/`:

```
1. Validate seller exists and is "active"
        │
        ▼
2. Apply product_field_mapping
        │ E.g. marketplace sends "title" → Kova receives "name"
        │      marketplace sends "sku"   → Kova receives "external_id"
        │      marketplace sends "amount" → Kova receives "price"
        │
        ▼
3. Validate each product via ProductSyncItemSerializer
        │
        ▼
4. For each valid product:
        │
        ├── Build marketplace_metadata from:
        │     condition, old_price, vendor_net_price, variants,
        │     specifications, campus_codes, extra
        │
        ├── Enrich description (if mp.enrich_descriptions = true):
        │     "Great phone" → "Great phone\n\nCondition: refurbished |
        │      Specs: Screen: 6.4in, Battery: 5000mAh |
        │      Available in: Color: Black, Storage: 128GB"
        │
        ├── Upsert: find by (user + external_id) or create new
        │     Sets: source="marketplace", marketplace_partner=mp
        │
        └── Check per-seller product limit (default: 500)
        │
        ▼
5. Update seller sync stats (products_synced, last_product_sync)
        │
        ▼
6. Trigger Snap to Sell AI (if auto_snap_on_sync = true and new products created)
        │ Sends newly synced products to vision AI for image analysis
        │
        ▼
7. Return results: { created: N, updated: N, errors: [...], snap_triggered: bool }
```

### Field Mapping Example

If UNIMART sends products with different field names:

**Marketplace config:**
```json
{
  "product_field_mapping": {
    "title": "name",
    "sku": "external_id",
    "amount": "price",
    "photo": "image_url",
    "link": "product_url"
  }
}
```

**What UNIMART sends:**
```json
{ "title": "iPhone 15", "sku": "PROD-001", "amount": 150000, "photo": "https://..." }
```

**What Kova receives after mapping:**
```json
{ "name": "iPhone 15", "external_id": "PROD-001", "price": 150000, "image_url": "https://..." }
```

---

## 9. Marketplace Configuration Examples

### Jumia Kenya

```python
MarketplacePartner(
    name="Jumia Kenya",
    slug="jumia-ke",
    seller_identity_field="email",       # Jumia sellers have verified emails
    auto_activate_sellers=True,
    seller_default_plan="growth",
    billing_model="per_seller",
    rate_per_seller_kes=150,
    max_sellers=5000,
    enforce_marketplace_cta=True,        # CTAs must link to Jumia product pages
    auto_snap_on_sync=True,
    enrich_descriptions=True,
    product_field_mapping={
        "title": "name",
        "sku": "external_id",
        "amount": "price",
        "photo": "image_url",
        "link": "product_url",
    },
    settings={
        "allowed_platforms": ["instagram", "facebook", "tiktok"],
        "max_products_per_seller": 200,
        "branding": {"accent_color": "#F68B1E", "powered_by_text": "Powered by Kova × Jumia"},
    },
)
```

### Jiji Nigeria

```python
MarketplacePartner(
    name="Jiji Nigeria",
    slug="jiji-ng",
    seller_identity_field="phone",       # Jiji sellers use phone numbers
    auto_activate_sellers=False,         # Sellers must opt-in
    seller_default_plan="starter",
    billing_model="revenue_share",
    revenue_share_pct=15,
    max_sellers=10000,
    enforce_marketplace_cta=True,
    auto_snap_on_sync=True,
    enrich_descriptions=True,
    settings={
        "allowed_platforms": ["instagram", "whatsapp", "facebook"],
        "content_approval_required": True,
    },
)
```

### UNIMART Africa

```python
MarketplacePartner(
    name="UNIMART Africa",
    slug="unimart",
    seller_identity_field="external_id",  # Uses USK-prefixed IDs
    auto_activate_sellers=True,
    seller_default_plan="growth",
    billing_model="flat_fee",
    flat_fee_kes=25000,
    max_sellers=2000,
    enforce_marketplace_cta=True,
    auto_snap_on_sync=True,
    enrich_descriptions=True,
    product_field_mapping={
        "title": "name",
        "sku": "external_id",
        "amount": "price",
    },
    seller_data_mapping={
        "business_name": "shop_name",
        "seller_tier": "tier",
        "campus_codes": "locations",
    },
    settings={
        "allowed_platforms": ["instagram", "facebook", "tiktok", "whatsapp"],
        "max_products_per_seller": 500,
    },
)
```

---

## 10. UNIMART Integration Specifics

UNIMART Africa has a unique data model (campus-based e-commerce for universities). Here's how we handle their specifics:

### UNIMART's Structure vs. Kova's

| UNIMART Has | Kova Stores It As |
|-------------|-------------------|
| `CustomUser` with USK-prefixed ID | `User.email` = placeholder, `MarketplaceSellerAccount.external_seller_id` = USK ID |
| Separate `Seller` model with OneToOne to user | `MarketplaceSellerAccount` + `business_name`/`business_url` fields |
| `Campus` + `Country` location hierarchy | `seller_metadata.campus_codes` + `marketplace_metadata.campus_codes` on products |
| `ProductCondition` (new/used/refurbished) | `marketplace_metadata.condition` |
| `old_price` (original before discount) | `marketplace_metadata.old_price` |
| `vendor_net_price` (before commission) | `marketplace_metadata.vendor_net_price` |
| `ProductVariant` (size, color + additional_price) | `marketplace_metadata.variants` as JSON array |
| `ProductSpecification` (key-value pairs) | `marketplace_metadata.specifications` as JSON array |
| Commission-based pricing | Kova stores final customer `price`; vendor_net_price in metadata |
| Campus-based delivery zones | `seller_metadata.delivery_zones` |

### Why Not Replicate UNIMART's Models?

We deliberately don't create Campus, Country, Seller models in Kova because:

1. **Kova is marketplace-agnostic** — every marketplace has different location/seller hierarchies
2. **JSONField gives flexibility** — UNIMART's campus codes are stored alongside Jumia's vendor tiers, Jiji's location tags
3. **No migration debt** — adding a new marketplace doesn't require new models
4. **The AI doesn't need relational data** — it needs text context (specs, variants, condition) which we embed in enriched descriptions

### How Description Enrichment Works for UNIMART

When `enrich_descriptions = True`, product descriptions are auto-enhanced:

**Input from UNIMART:**
```
"Samsung Galaxy A54 - Great phone for students"
```

**After enrichment (stored in Kova):**
```
Samsung Galaxy A54 - Great phone for students

Condition: refurbished | Specs: Screen Size: 6.4 inches, Battery: 5000mAh | Available in: Color: Black, Storage: 128GB
```

This enriched description feeds into Kova's AI content generation — so when AI writes an Instagram caption, it has specs and variants to work with.

---

## 11. Billing Models

| Model | How It Works | Example |
|-------|-------------|---------|
| `per_seller` | Monthly fee × active sellers | 47 active sellers × KES 150 = KES 7,050/month |
| `flat_fee` | Fixed monthly payment regardless of seller count | KES 25,000/month |
| `revenue_share` | % of seller subscription revenue | 15% of what Kova charges each seller |
| `free_pilot` | Time-limited free access (expires at `pilot_expires_at`) | 90-day pilot, then convert to paid |

The billing model is tracked on the `MarketplacePartner` but **billing execution is manual for now** — the stats endpoint shows estimated monthly costs for invoicing.

---

## 12. Admin Dashboard

### Pages

| URL | What It Shows |
|-----|---------------|
| `/admin-dashboard/partners/marketplaces/` | List of all marketplace partners with stats |
| `/admin-dashboard/partners/marketplaces/create/` | Create new marketplace + generate API key |
| `/admin-dashboard/partners/marketplaces/{slug}/` | Detail view: config, sellers, products, billing |

### Creating a New Marketplace Partner

1. Go to **Admin Dashboard → Partners → Marketplaces → Create**
2. Fill in: name, slug, contact info, seller identity field, billing model, etc.
3. Submit → **API key is displayed once** — copy it immediately
4. Share the API key with the marketplace's dev team
5. They start calling the API endpoints

---

## 13. Security

### API Key Security

- **Raw keys are never stored** — only SHA-256 hashes
- **Keys are shown once** at creation, then never again
- **Key prefix** (8 chars) stored for identification without exposing the full key
- **Last used timestamp** tracked for monitoring
- **Per-request authentication** — every call re-validates the key

### Access Scoping

- Every API endpoint is **scoped to the authenticated marketplace** — a marketplace can only see/manage its own sellers and products
- `IsMarketplacePartner` permission class ensures only API-key-authenticated requests can access partner endpoints
- Seller lookups are always filtered by `marketplace=mp` — no cross-marketplace data leaks

### Input Validation

- All inputs validated through DRF serializers
- `IntegrityError` caught for duplicate seller provisioning (race condition safe)
- Product sync validates each item individually — bad items don't block good ones
- Per-seller product limits enforced server-side

---

## 14. Integration Guide for Marketplace Developers

### Quick Start

**Step 1:** Get your API key from the Kova team (or admin dashboard).

**Step 2:** Test the connection:
```bash
curl -H "X-Kova-Partner-Key: YOUR_KEY" \
     https://app.kova.co.ke/api/v1/partner/info/
```

**Step 3:** Provision your first seller:
```bash
curl -X POST \
     -H "X-Kova-Partner-Key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "seller@example.com",
       "external_seller_id": "SELLER-001",
       "full_name": "Test Seller",
       "business_name": "Test Shop"
     }' \
     https://app.kova.co.ke/api/v1/partner/sellers/
```

**Step 4:** Sync products for that seller:
```bash
curl -X POST \
     -H "X-Kova-Partner-Key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "products": [{
         "external_id": "PROD-001",
         "name": "Test Product",
         "description": "A great product",
         "price": 5000,
         "image_url": "https://your-cdn.com/product.jpg",
         "product_url": "https://your-marketplace.com/product/001"
       }]
     }' \
     https://app.kova.co.ke/api/v1/partner/sellers/SELLER-001/products/sync/
```

### Best Practices

1. **Sync products in batches** — send up to 50 products per request for reliability
2. **Use idempotent external_ids** — calling sync twice with the same external_id updates instead of duplicating
3. **Map your fields** — if your product schema differs from Kova's, configure `product_field_mapping` so you can send native data
4. **Monitor via stats endpoint** — poll `/stats/` periodically to track adoption
5. **Handle errors per-product** — the sync response includes per-item errors; retry only the failed ones

### Error Handling

| HTTP Code | Meaning |
|-----------|---------|
| `200` | Success (or seller already exists for provisioning) |
| `201` | Created (new seller or new products) |
| `400` | Validation error (check `errors` array in response) |
| `401` | Invalid or missing API key |
| `403` | Seller limit reached, or seller not active |
| `404` | Seller not found by external_seller_id |
| `409` | Conflict (e.g. seller ID already linked to different user) |

---

## Summary

The Marketplace Partner System turns Kova from a B2C SaaS into a **B2B2C platform**. Instead of acquiring sellers one-by-one, entire marketplaces can plug their seller bases into Kova's AI content engine with a few API calls. The system is designed to be **marketplace-agnostic** — whether it's Jumia's email-based sellers, UNIMART's campus-based USK-ID sellers, or Jiji's phone-based vendors, the same API handles them all through flexible configuration (identity fields, field mappings, metadata JSONFields).
