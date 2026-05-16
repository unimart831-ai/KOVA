# Kova Navigation Guide — Where Did Everything Go?

> The sidebar was reduced from **21 tabs to 9** on 2026-05-15 as part of
> Phase 3 (W10-W11) of [KOVA_MASTER_PLAN.md](KOVA_MASTER_PLAN.md). Zero
> features were removed. Every old tab is still reachable. This doc
> tells you where each one moved.

---

## TL;DR — quick lookup

Looking for a specific feature you remember from the old nav? Use this
table.

| Old tab | Where it is now | How to reach it |
|---|---|---|
| Daily Brief | **Home** (renamed) | Top nav, always visible |
| Kova Studio | **Create** (renamed) | Top nav, "Work" section |
| Queue | **Schedule** (renamed) | Top nav, "Work" section |
| Visual Publisher | **Create → Visual Publisher** (subnav) | Click Create → subnav reveals |
| Timeline / Calendar | **Schedule → Calendar** (subnav) | Click Schedule → subnav reveals |
| A/B Tests | **Schedule → A/B Tests** (subnav, Growth+) | Click Schedule → subnav reveals |
| Trending / Memes | **Create → Trending / Memes** (subnav, Pro+) | Click Create → subnav reveals |
| Campaigns | **Schedule → Campaigns** (subnav) | Click Schedule → subnav reveals |
| Inbox | **Inbox** (unchanged) | Top nav, "Customers" section |
| WhatsApp | **WhatsApp** (unchanged) | Top nav, "Customers" section |
| Leads | **Leads** (unchanged) | Top nav, "Customers" section |
| Performance | **Performance** (unchanged) | Top nav, "Insights" section |
| Competitors | **Insights → Competitors** (subnav, Pro+) | Click Performance → subnav reveals |
| Kova Links | **Links** (renamed) | Top nav, "Money" section |
| Revenue | **Revenue** (unchanged) | Top nav, "Money" section |
| Products | **Money → Products** (industry-gated) | Visible by default for product industries; hidden otherwise |
| Kova Pixel | **Settings → Kova Pixel** (subnav, Pro+) | Click Settings → subnav reveals |
| Agents | **Settings → Agents** (subnav) | Click Settings → subnav reveals |
| Platforms | **Settings → Platforms** (subnav) | Click Settings → subnav reveals |
| Teams | **Settings → Teams** (subnav, Agency only) | Click Settings → subnav reveals |
| Billing | **Settings → Billing** (subnav) | Click Settings → subnav reveals |
| Help | **Settings → Help** (subnav) | Click Settings → subnav reveals |

Plus a new entry, added during the Engage v2 rework:

| New surface | Where | How to reach |
|---|---|---|
| AI auto-sent replies | **Inbox → AI auto-sent** (subnav) | Click Inbox → subnav reveals. Review what the Engage Agent sent on your behalf, undo within 5 min, leave corrections. |

---

## The new 9-tab structure

Default sidebar (always visible):

```
🏠  Home                              ← Daily Brief

WORK
  ✏️  Create                          ← Studio + Visual Publisher + Memes
  📅  Schedule                        ← Queue + Calendar + A/B Tests + Campaigns

CUSTOMERS
  💬  Inbox                           ← Engage Agent's inbox + auto-sent log
  🟢  WhatsApp                        ← WhatsApp Business inbox + status + drips
  👥  Leads                           ← Lead capture + CRM

MONEY
  💰  Revenue                         ← Revenue attribution dashboard
  📦  Products      (industry-gated)  ← Only shows for product industries
  🔗  Links                           ← Kova Links (link-in-bio + short URLs)

INSIGHTS
  📊  Performance                     ← Analytics + competitor view

SETTINGS
  ⚙️  Settings                        ← Platforms, Agents, Pixel, Teams, Billing, Help
```

That's it. **9 tabs grouped into 5 sections by user job**, not by feature
category. The grouping answers "what do I want to do?" rather than
"which feature module owns this?"

---

## The contextual subnav pattern

When you **click** any tab whose merged features live inside it, a small
indented submenu appears underneath. It only shows while you're on a
page in that tab's family — clicking away returns the sidebar to the
minimal 9-tab state.

This is the same pattern WhatsApp already used. Now it's applied
uniformly:

| Click on... | Subnav reveals |
|---|---|
| **Create** | Studio · Visual Publisher · Trending / Memes |
| **Schedule** | Queue · Calendar · A/B Tests · Campaigns |
| **Inbox** | Conversations · AI auto-sent |
| **WhatsApp** | Inbox · Status Studio · Broadcasts · Analytics · Channels · Templates |
| **Performance** | Performance · Competitors |
| **Settings** | Platforms · Agents · Kova Pixel · Teams · Billing · Help |

Result: **every feature surfaces with one click**. No URL knowledge
required. The default sidebar stays minimal — when you're on Home, you
see 9 tabs, not 21.

---

## Gating — features hidden conditionally

Some features only appear in nav for users who can actually use them.
This is intentional — showing a tab a user can't access is friction.

### Plan-tier gating

| Feature | Min plan | Where surfaced |
|---|---|---|
| A/B Tests | Growth | Schedule subnav |
| Memes / Trending | Pro | Create subnav |
| Inbox (Engage Agent) | Pro | Customers section |
| WhatsApp | Pro | Customers section |
| Competitors | Pro | Performance subnav |
| Kova Pixel | Pro | Settings subnav |
| Teams | Agency | Settings subnav |

When the user is on a plan below the threshold:
- The visible tab clicks through to the **pricing page** instead of the feature
- The submenu item is **not rendered at all** (no "locked" placeholder)
- A small "PRO" / "GROWTH" / "AGENCY" badge appears on the visible
  parent tab so they know it exists

### Industry gating

| Feature | Shown when industry is... |
|---|---|
| Products | `fashion_beauty`, `salon_beauty`, `food_restaurant`, `wholesale_retail`, `ecommerce`, `health`, `real_estate`, `travel_tourism`, `agriculture` |

A SaaS founder, NGO, or consulting firm doesn't see Products in nav by
default — it would be clutter. Direct URL still works for anyone who
wants it (`/products/`).

---

## URL escape hatches — every feature reachable directly

The contextual subnav pattern means a user who's on Home can't see
deep features without clicking into a parent tab first. For power
users, deep linking, documentation, and admin scripts, every feature
has a stable URL:

| Feature | URL |
|---|---|
| Daily Brief / Home | `/` |
| Kova Studio | `/content/studio/` |
| Visual Publisher | `/media-queue/` |
| Queue | `/content/queue/` |
| Calendar / Timeline | `/content/calendar/` |
| A/B Tests | `/content/ab-tests/` |
| Trending / Memes | `/memes/` |
| Campaigns | `/campaigns/` |
| Engage Inbox | `/engage/` |
| AI auto-sent replies | `/engage/auto-sent/` |
| WhatsApp Inbox | `/whatsapp/` |
| Leads | `/leads/` |
| Revenue Dashboard | `/analytics/revenue/` |
| Products | `/products/` |
| Kova Links | `/links/` |
| Performance | `/analytics/` |
| Competitors | `/analytics/competitors/` |
| Kova Pixel | `/analytics/pixel/` |
| Agents (config) | `/agents/` |
| Platforms (OAuth) | `/platforms/` |
| Teams | `/teams/` |
| Billing | `/billing/` |
| Help | `/help/` |
| Account Settings | `/accounts/settings/` |

URLs are stable. If you bookmarked or scripted against any of these
before the nav reshape, your bookmarks and scripts still work.

---

## Why this change

The old 21-tab sidebar contradicted Kova's product promise:
**"AI runs your marketing — you check it once a day."**

A user who feels the second can't experience it in front of the first.
21 tabs scream "powerful tool with many features." 9 tabs grouped by
user job whisper "the AI is doing the work, here's where you check on
it." Same features, different framing.

The principle from the audit: **subtraction is the highest-leverage
move in UX design when a product's promise is automation.** Every tab
hidden from the default view is a tab the AI is implicitly claiming
to handle on the user's behalf. The contextual subnav lets the
features stay one click away when the user needs them, while keeping
the default state honest about what Kova claims to do.

For the full strategic rationale see the [audit thread in the Master
Plan](KOVA_MASTER_PLAN.md) and the original nav audit notes.

---

## "I clicked Settings but I'm looking for [X]"

If the sub-link you expected isn't in the Settings submenu, check the
gating section above — it may be a Pro/Agency/industry-only feature
your current plan or industry doesn't enable. Settings is also the
catch-all for anything that's:

- Plumbing the user installs once and forgets (Platforms, Pixel)
- Money/legal (Billing)
- Help / docs (Help)
- Multi-user (Teams)
- Agent configuration (Agents)
- AI Learning / Adapt preferences (coming in Phase 3 of the Master Plan)

If you reach a dead end and the table at the top doesn't show your
feature: it may have been deferred to a later phase. Check
`docs/KOVA_MASTER_PLAN.md` for the roadmap.

---

## For developers — the template that drives this

The nav lives in [`templates/layouts/app.html`](../templates/layouts/app.html).
The pattern for every contextual subnav is:

```django
<a href="{% url 'parent:tab' %}" class="...nav-link...">
  ... parent icon + label ...
</a>

{% comment %}
  When the user is on any path that belongs to this parent, render
  the indented submenu of sub-features. Multi-line — must use
  {% comment %} not {# #}.
{% endcomment %}
{% if '/parent-path/' in request.path or '/related-path/' in request.path %}
<div class="ml-8 space-y-0.5 mb-1">
  <a href="{% url 'child:default' %}"
     class="block text-xs py-1 px-2 rounded ...">Default Child</a>
  {% if request.plan_limits.some_gate %}
    <a href="{% url 'child:gated' %}" class="...">Gated Child</a>
  {% endif %}
</div>
{% endif %}
```

To add a new feature to the nav:

1. Decide which parent it belongs under (or whether it deserves its own
   top-level tab — the bar is high; the default 9 should rarely grow)
2. Add it to the parent's `if` condition path-matcher so the parent
   stays highlighted when on the feature's URL
3. Add the `<a>` inside the parent's `{% if %}` subnav block
4. Plan-gate or industry-gate it with another `{% if %}` if applicable

Never use `{# ... #}` for a multi-line comment. It will render as
literal text in the sidebar. Use `{% comment %} ... {% endcomment %}`.
This bug shipped twice during the May 2026 nav refactor. Don't be the
third.
