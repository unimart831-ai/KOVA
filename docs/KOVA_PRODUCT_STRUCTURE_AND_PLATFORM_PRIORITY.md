# KOVA Product Structure & Platform Priority

**Status:** Phase 1 (copy + `data-nav-group` hooks) · Phase 2 (visual sidebar regroup)  
**Last updated:** June 2026  
**Code reference:** `apps/platforms/views.py` → `ACTIVE_PLATFORMS`, `COMING_SOON_PLATFORMS`  
**Nav template:** `templates/layouts/app.html`

---

## A. North-star positioning

### Tagline

> **The system that chases money for my business while I run the shop.**

### What each word means for product decisions

| Word / phrase | Product meaning |
|---------------|-----------------|
| **The system** | One connected loop (agents + channels + commerce), not a bag of tools. Onboarding, Daily Brief, and defaults should feel like one operating system. |
| **Chases money** | Outcomes over vanity metrics: leads captured, conversations replied, offers sent, M-Pesa collected, bookings confirmed. Prioritize features that move pipeline and revenue, not “more posts.” |
| **For my business** | Brand DNA, Kenya pricing (KES/M-Pesa), WhatsApp-first, SMB tone — not agency/generic SaaS. |
| **While I run the shop** | ≤5 min/day approval model; mobile-first; loud environments; owner is floor-facing, not at a desk. Automate chase; human approves exceptions. |
| **I / my** | First-person copy on landing and briefs — speaks to the owner, not “teams” or “marketers.” |

### Supporting subhead (marketing)

**Your AI team · Snap to Sell · WhatsApp · M-Pesa — approve in 5 minutes.**

Keeps the proven “AI team / 5 minutes” proof points while the H1 owns the money-chase frame.

---

## B. Recommended nav structure (Phase 2)

**Target:** 4 workflow groups + Home + Settings (max ~5 sidebar sections).

| Group | Job-to-be-done | Phase 2 label |
|-------|----------------|---------------|
| **Home** | “What needs my attention today?” | Today |
| **Sell** | List offers, snap products, schedule go-live | Sell |
| **Catch** | Bring strangers into the pipeline | Catch |
| **Close** | Conversations that turn into payment | Close |
| **Grow** | Publish, learn, compound | Grow |
| **Settings** | Connect platforms, pay, team, agents | Settings |

### Current sidebar → group mapping

| Nav item | Sub-items (when expanded) | Group | Recommendation | Notes |
|----------|---------------------------|-------|----------------|-------|
| **Today** | — | Home | **Retain** | Money dashboard; anchor the 5-min ritual |
| **Workspace** | Overview, Standup, Moments, Listen | Grow | **De-emphasize** | Power users; fold under Grow or Today insights in Phase 2 |
| **Studio** | Campaigns, Visual Publisher, Memes, Autopilot, Competitors | Grow | **Retain** | Primary “publish & create”; Competitors **de-emphasize** (plan-gated) |
| **Queue** | List, Calendar, Timeline | Grow | **Retain** | Merge mentally with Studio as “Publish” in Phase 2 |
| **Inbox** | Comments, Messages, AI auto-sent | Catch | **Retain** | Social catch; distinct from WA |
| **WhatsApp** | Inbox, Templates, Status, Broadcasts, Analytics | Close | **Retain (P0)** | Kenya wedge |
| **Email** | Overview, Campaigns, Subscribers, Lists | Close | **Retain** | Nurture after lead captured |
| **Bookings** | — | Close | **Retain** | Appointment close for services |
| **Revenue** | — | Grow | **Retain** | Money outcome reporting |
| **Performance** | — | Grow | **Retain** | Merge with Revenue in Phase 2? optional |
| **Commerce** | Snap to Sell, Batch, My offers | Sell | **Retain** | Rename section “Sell” in Phase 2 |
| **Reach** | Leads, Pipeline, Links, Walk-ins, Automations, Analytics | Catch | **Retain** | REACH bundle |
| **Settings** | Profile, Platforms, Agents, Teams, Billing, Help | Settings | **Retain** | Pixel / calendar intel stay under settings paths |

### Merge / hide guidance

| Item | Action |
|------|--------|
| Workspace vs Today | **Merge (Phase 2):** surface standup/moments as cards on Today; hide top-level Workspace for Starter |
| Studio + Queue | **Merge (Phase 2):** single “Publish” with Studio / Queue / Calendar tabs |
| Revenue + Performance | **Merge (Phase 2):** one “Results” under Grow |
| Memes & Trends, Autopilot | **De-emphasize:** behind “More” or plan upsell |
| Competitors, Screenshot Compete | **Hide until ready** or Growth+ only |
| Command → Listen | **De-emphasize** for SMB; retain for Pro |

### Phase 1 implementation (done)

- Landing/auth/marketing CTAs use north-star tagline.
- `data-nav-group` on sidebar links in `app.html` (`home`, `sell`, `catch`, `close`, `grow`, `settings`).
- Sidebar **labels unchanged** until Phase 2 regroup.

---

## C. Feature retain matrix

| Feature | Retain? | Why | Tier |
|---------|---------|-----|------|
| Daily Brief (Today) | Yes | 5-min approval ritual; money chase dashboard | P0 |
| Snap to Sell | Yes | 90-day wedge demo; photo → offer → WA | P0 |
| WhatsApp inbox + templates | Yes | Primary close channel in Kenya | P0 |
| M-Pesa commerce | Yes | Local payment close | P0 |
| REACH (leads, links, QR) | Yes | Catch demand from foot traffic & bio | P0 |
| Engage inbox (comments/DMs) | Yes | Catch social intent | P0 |
| Studio + Queue | Yes | Grow visibility; feeds discovery | P0 |
| Email nurture | Yes | Close loop for non-WA leads | P1 |
| Bookings | Yes | Service SMB close | P1 |
| Products / Commerce catalog | Yes | Sell backbone | P0 |
| Revenue & attribution | Yes | Prove money chase | P0 |
| Performance analytics | Yes | Optimize what sells | P1 |
| 6 AI agents | Yes | Differentiator; compounding | P0 |
| Platforms connect UI | Yes | Must match ACTIVE_PLATFORMS | P0 |
| Workspace / Command | De-emphasize | Operator power tools; not shop-floor | P2 |
| Memes & Trends | De-emphasize | Nice-to-have vs revenue | P2 |
| Autopilot | De-emphasize | Risk/complexity for SMB | P2 |
| Competitor tracking | Hide/plan-gate | Pro niche | P2 |
| Pinterest / Bluesky connect | Retain in code | P2 discovery niches; don't lead marketing | P2 |
| X / YouTube / Threads | Hide in UI | `COMING_SOON_PLATFORMS` until OAuth shipped | — |

---

## D. Platform priority (Kenya SMB)

Aligned with founder wedge and `ACTIVE_PLATFORMS` / `COMING_SOON_PLATFORMS` in `apps/platforms/views.py`.

| Priority | Platform | UI today | Rationale (Kenya SMB) |
|----------|----------|----------|------------------------|
| **P0** | WhatsApp | Active | Default sales & support; M-Pesa links; where deals close |
| **P0** | Instagram | Active | Discovery, reels, DMs; visual retail & services |
| **P0** | Facebook Page | Active (`facebook`) | Local community, groups, older buyers |
| **P1** | TikTok | Active | Youth retail, food, fashion; short video demand |
| **P1** | LinkedIn | Active | B2B, consultants, professional services |
| **P2** | Pinterest | Active | Visual catalog niches (home, fashion, food) |
| **P2** | Bluesky | Active | Early adopter / diaspora; low volume |
| **Soon** | X (Twitter) | Coming soon | OAuth pending; don't market until live |
| **Soon** | YouTube | Coming soon | Long-form; secondary for typical SMB |
| **Soon** | Threads | Coming soon | Meta ecosystem extension when stable |

### Code ↔ marketing alignment

**Active connect (ship messaging):** Facebook, Instagram, TikTok, LinkedIn, WhatsApp, Pinterest, Bluesky.

**Coming soon (landing: “on the way,” no connect CTA):** YouTube, X, Threads.

**Landing copy order:** WhatsApp → Instagram → Facebook → TikTok → LinkedIn → (Pinterest/Bluesky optional) → coming soon.

---

## E. 90-day wedge (founder discussion)

**Primary path:** WhatsApp → lead → follow-up → M-Pesa

1. Connect **WhatsApp** + **Instagram** (or Facebook) in onboarding.
2. **Snap to Sell** demo: photo → product → share to WA/status.
3. **REACH** link/QR on shop counter → lead inbox.
4. Nurture: WA templates + email for non-responders.
5. Close: M-Pesa STK or payment link in conversation.
6. Prove loop on **Today** + **Revenue** screens.

**Demo script (15 min):** Snap product → publish IG/FB → QR lead → WA reply → M-Pesa request.

**Defer for wedge:** Workspace standup, memes, competitor screenshots, Pinterest/Bluesky unless ICP needs them.

---

## F. Phase 2 sidebar regroup (checklist)

- [ ] Rename sections: Sell / Catch / Close / Grow / Settings
- [ ] Move Studio + Queue under **Grow** (or split Studio create vs Queue schedule)
- [ ] Move Commerce under **Sell**; elevate Snap to Sell first sub-link
- [ ] Collapse **Workspace** into Today or remove from default nav
- [ ] Platform picker: sort by §D; hide coming-soon behind “More platforms”
- [ ] Mobile bottom nav: align 5 tabs to Home / Sell / Catch / Close / Grow

---

## Related files

| Area | Path |
|------|------|
| Public landing | `templates/pages/landing.html` |
| Auth mission panel | `templates/components/brand/_mission_panel.html` |
| Tagline partial | `templates/components/brand/_north_star_tagline.html` |
| Marketing CTAs | `templates/components/brand/_public_cta_*.html` |
| Brochures | `marketing/brochures/html/KOVA_Product_Overview.html`, `KOVA_Complete_Guide_2Page.html` |
| Platforms | `apps/platforms/views.py` |
