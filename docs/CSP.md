# Content Security Policy (CSP)

**Last updated:** June 11, 2026 (Phase 4)

Kova uses [django-csp](https://django-csp.readthedocs.io/) in production (`config/settings/production.py`).

## Current policy

| Directive | Value | Notes |
|-----------|-------|-------|
| `default-src` | `'self'` | |
| `script-src` | `'self'`, CDNs, Stripe + **nonce** | No `'unsafe-inline'` for scripts |
| `style-src` | `'self'`, `'unsafe-inline'`, fonts CDN | **`unsafe-inline` deferred removal** |
| `connect-src` | `'self'`, Stripe, `wss:` | WebSocket real-time (`/ws/updates/`) |
| `img-src` | `'self'`, `data:`, `https:`, `blob:` | |
| `frame-src` | `'self'`, Stripe | |

## Nonce support (live)

Production sets `CSP_INCLUDE_NONCE_IN = ["script-src"]`. Each request gets `request.csp_nonce`.

Inline scripts **must** use the nonce attribute:

```html
<script nonce="{{ request.csp_nonce }}">...</script>
```

`templates/base.html` theme bootstrap script already uses this pattern. External scripts (HTMX, Alpine, Stripe) load from `'self'` or allowlisted CDNs — no nonce required.

## Deferred: remove `unsafe-inline` from style-src

Alpine.js, HTMX swap animations, and some template inline `style=""` attributes depend on inline styles today. Removing `'unsafe-inline'` from `style-src` without a full audit will break UI interactions.

**Before tightening style-src:**

1. Audit templates for inline `style=` attributes and `<style>` blocks.
2. Confirm Alpine/HTMX do not inject inline styles at runtime.
3. Run E2E on Studio, Queue, Engage inbox, and checkout flows.

## Local development

CSP middleware is production-only. `DEBUG=True` does not enforce CSP — test CSP changes in staging before deploy.
