# Agency white-label (P6) — v1

Agency plan teams can manage multiple **Brands** (client accounts) under **Teams**.

## Client sub-accounts

- Invite team members with role **Client** and assign a **Brand**
- Clients see dashboard content filtered to that brand (`filter_posts_by_brand_scope`)
- Agency owners/admins manage brands, theming, and invites

## Custom domain

Set `custom_domain` on a Brand (Teams → Brand → Edit). v1 uses **display domain** on commerce canonical URLs and shows CNAME instructions in settings:

```
shop.client.com  CNAME  shops.kovaagent.com
```

DNS verification is manual (`custom_domain_verified` flag) — no multi-tenant Host routing in v1.

## Branded client reports

PDF attribution reports use agency `logo_url` and `theme_primary_color` when the user is an agency client or has an active themed brand.

## Agency theming

- **Commerce shop pages**: CSS `--shop-accent` from brand color
- **App sidebar**: optional accent via `agency_brand_theme` context processor

## v2 (deferred)

- Automatic DNS verification + Host header routing
- Per-brand Kova Link subdomains
- Client-only billing views
