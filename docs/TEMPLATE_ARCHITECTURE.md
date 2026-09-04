# Template architecture

How Django templates are organized so developers can find chrome, shared partials, and page bodies without hunting.

## Pattern

Each **template family** (landing, legal, account, dashboard, …) lives in its own folder under `templates/` and follows:

```
templates/<family>/
  base.html           # Family chrome
  includes/           # Shared partials for that family
  <page or area>/     # Page bodies (+ their partials)
```

**Rules**

1. **Family `base.html` is the control point** for chrome.
2. **Tailwind first.** Prefer utilities in HTML. Add a style include only when Tailwind cannot express the rule cleanly (keyframes, complex selectors).
3. **Page templates only fill blocks** (`page_title`, `content`, …).
4. **Views render family paths** — e.g. `dashboard/brief.html`, not nested feature folders for rewritten pages.
5. **Public / marketing / auth stay outside `dashboard/`** (landing, legal, account, `*/public*`, onboarding).

## Landing (`templates/landing/`)

Public site chrome + homepage. See earlier sections; base owns nav/footer.

## Legal / Account

Unchanged pattern: extend `landing/base.html`, pages live under `legal/` and `account/`.

## Dashboard (`templates/dashboard/`) — user product only

Signed-in SME dashboard (not admin). Prefer a **flat** page layout as we rewrite each nav link:

```
dashboard/
  base.html
  includes/
    _header.html
    _sidebar.html
    _brief_stream.html
    _studio_create_modal.html
  brief.html                # Home (/brief/)
  business.html             # Business (/accounts/business-brain/)
  studio.html               # Studio posts list + Create modal
  results.html              # Results (/analytics/revenue/) — money outcomes
  analytics.html            # Analytics (/analytics/) — reach & engagement
  leads.html                # Leads inbox (/leads/)
  settings.html             # Settings (/accounts/settings/) — tabbed
  channels.html             # Channels (/platforms/)
  content/                  # post detail/edit, schedule, HTMX partials
  leads/                    # pipeline, detail, form, HTMX partials
  platforms/                # WhatsApp connect + secondary OAuth flows
  analytics/                # campaign drill-down, pixel, attribution (secondary)
  accounts/                 # CTA settings, AI learning (secondary)
  …                         # flatten link-by-link
```

- **Chrome** is Tailwind on dark canvas. Custom CSS only when utilities are not enough.
- **One page file per nav surface** when we rewrite it (combine former partials into the page; keep only serious shared fragments in `includes/`).
- **Sidebar:** Main (Home, Business, Studio) · Growth (Results, Analytics, Leads*) · General (Channels, Settings, Log out).
- **Studio:** posts list + Create Post modal; open a post for approve/edit.
- **Results:** revenue, funnel, campaigns, conversions.
- **Analytics:** engagement metrics and top posts.
- **Leads:** inbox list + Add Lead; Pipeline / Stats as secondary.
- **Channels:** connected accounts list + connect grid.
- **Settings:** tabbed sections (Account → Danger); Save on each editable tab.
- **Shim:** `layouts/app.html` → `dashboard/base.html`.

Example (Home):

```django
{% extends "dashboard/base.html" %}

{% block page_title %}Home{% endblock %}

{% block content %}
…
{% include "dashboard/includes/_brief_stream.html" %}
…
{% endblock %}
```

## Layouts vs families

| Path | Role |
|------|------|
| `templates/landing/base.html` | Public chrome |
| `templates/dashboard/base.html` | User dashboard chrome |
| `templates/layouts/marketing.html` | Shim → landing |
| `templates/layouts/app.html` | Shim → dashboard |
| `templates/components/brand/` | Brand-wide CTAs / shared bits |

## Do not

- Put public shop / campaign pages under `dashboard/` — keep `products/public`, `content/public`, `links/public_page.html`.
- Extend `layouts/app.html` or `layouts/marketing.html` for new pages.
- Reintroduce large custom CSS sheets for chrome when Tailwind utilities suffice.
- Change admin (`/dashboard/` admin app) when working on the user dashboard family.
