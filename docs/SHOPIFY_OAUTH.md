# Shopify OAuth integration (P2)

## Environment variables

```bash
SHOPIFY_API_KEY=your_app_client_id
SHOPIFY_API_SECRET=your_app_client_secret
SHOPIFY_SCOPES=read_products,write_products,read_orders,read_inventory
SITE_URL=https://app.kovaagent.com
```

Generate credentials in [Shopify Partners](https://partners.shopify.com/) → Apps → Create app → Configuration.

Set **Allowed redirection URL(s)** to:

```
https://app.kovaagent.com/analytics/revenue/shopify/oauth/callback/
```

## Connect flow

1. User on **Pro+** opens Analytics → Revenue → **Connect with Shopify**
2. OAuth grants scopes; Kova stores an encrypted access token on `ShopifyStore`
3. Webhooks registered: `products/create`, `products/update`, `orders/create`
4. Full catalog import runs (cursor pagination, no 50-product cap)
5. Product webhooks upsert Kova `Product` rows by `external_id`

Manual Admin API token connect remains available under **Manual token (advanced)**.

## Webhook URLs

| Topic | URL |
|-------|-----|
| orders/create | `/analytics/webhooks/shopify/order/` |
| products/create, products/update | `/analytics/webhooks/shopify/products/` |

HMAC verification uses `SHOPIFY_API_SECRET` for OAuth installs, or per-store `webhook_secret` for manual tokens.

## Plan gate

`check_shopify_integration` in `apps/billing/enforcement.py` — requires Pro or Agency plan feature `shopify_integration`.

## v2 (deferred)

- Shopify App Store public listing
- Metafield write-back (Kova → Shopify product metafields)
- Inventory location–aware stock sync
- Automatic custom app uninstall cleanup

## App Store listing stub

Public listing is optional for v1. To publish later: complete Shopify app review checklist, add app icon/screenshots, and set `application_url` to the Kova revenue dashboard.
