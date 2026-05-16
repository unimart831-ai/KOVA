# Walk-in / QR-code Attribution Spec

> Phase 2 Weeks 5-6 of [KOVA_MASTER_PLAN.md](../KOVA_MASTER_PLAN.md).
> The first of two Africa-native moats. No Western marketing tool does
> this for SMEs whose conversions happen physically.

---

## Goal

Close the loop from **social post → walk-in customer → KES revenue**
for SMEs whose customers convert in person (salons, restaurants,
retail). Today, Kova Pixel tracks the digital half of the funnel
(post → click → web event). For a Kawaida-the-salon-owner with no
e-commerce site, the Pixel is useless. Most conversions happen when
someone scans a QR on a flyer, walks in, and pays cash.

This spec defines the system that captures that other half:

1. SME creates a **QR code** tied to a campaign or a post
2. Customer **scans** the QR → lands on a thin Kova-hosted page
3. **Click event** logged with full attribution chain (campaign / post / channel)
4. Customer **walks in** to the physical business
5. Staff opens **cashier UI** on a phone, taps "Where did you hear about us?"
6. **WalkInEvent** created, linked back to the scan via session token
7. **Revenue Dashboard** now shows: "Jamhuri Day IG post → 47 scans → 23 walk-ins → KES 18,400 attributed"

---

## What's NOT in scope for v2

- POS integration (Square / Loyverse / Lipa Na M-Pesa Till APIs). For
  v2 the cashier UI is manual entry.
- Multiple QR codes per scan (split traffic test). Phase 3.
- NFC tag support. Phase 4+.
- Custom-branded landing pages with images / logo upload. v2 uses a
  small set of industry templates; brand colors only.
- A/B testing of QR landing copy. Adapt Agent v3 territory.

---

## Data model

### New app: `apps/qr_attribution/`

Three new models. All in one app so the domain is contained.

```python
class QRCode(models.Model):
    """A printed / displayable QR that ties scans back to a campaign / post."""
    id = UUIDField(primary_key=True)
    user = FK(User)
    token = SlugField(max_length=12, unique=True, db_index=True)  # for /qr/<token>/
    label = CharField(max_length=200)  # human name: "Jamhuri flyer", "Door sticker", "Receipt corner"
    campaign = FK(Campaign, null=True, blank=True)
    post = FK(Post, null=True, blank=True)
    landing_template = CharField(20, choices=...)  # "discount" | "menu" | "booking" | "follow" | "custom"
    landing_payload = JSONField(default=dict)  # discount %, menu link, booking link, etc.
    is_active = BooleanField(default=True)
    created_at + updated_at
    
class QRScan(models.Model):
    """One row per QR scan (click on /qr/<token>/)."""
    id = UUIDField
    qr_code = FK(QRCode)
    scanned_at = DateTimeField
    visitor_id = CharField  # cookie set on landing page so we can match WalkInEvent later
    user_agent = CharField
    ip = GenericIPAddressField  # for geo-rough-tagging
    
class WalkInEvent(models.Model):
    """A walk-in attributed (manually) to a QR scan."""
    id = UUIDField
    user = FK(User)
    scan = FK(QRScan, null=True, blank=True)  # null = "walk-in but didn't scan" entry
    qr_code = FK(QRCode, null=True, blank=True)
    attribution_label = CharField(50, blank=True)  # "Instagram", "Word of mouth", "Saw flyer", etc.
    revenue = DecimalField(null=True, blank=True)  # optional — manual entry
    notes = TextField(blank=True)
    recorded_by = FK(User, ...)  # which staff member tapped the button
    recorded_at = DateTimeField
```

Why `attribution_label` is a free-text CharField, not a FK to source:
the cashier UI uses a simple set of taps (Instagram / Facebook / Flyer
/ Word of mouth / Other). Each maps to a label string. Storing the
label preserves the original tap even if the QRCode is later deleted.

---

## URL surface

```
/qr/<token>/                      Public scan landing (no auth required)
/qr/                              User: list of QR codes
/qr/new/                          User: create a new QR
/qr/<id>/edit/                    User: edit a QR
/qr/<id>/print/                   User: print-ready PDF (poster + flyer + receipt sticker formats)
/qr/<id>/                         User: stats for one QR — scans + walk-ins + revenue
/walkin/                          Cashier UI — public-but-tokened (one URL per business)
/walkin/record/                   POST endpoint the cashier UI posts to
```

The `/walkin/` cashier URL is per-business and unguessable (slug). It
opens a phone-friendly screen with 5 big buttons ("Instagram",
"Facebook", "Flyer", "Word of mouth", "Other") and an optional revenue
input. Staff doesn't log in — the URL is the auth.

---

## User flow

### Setup (one-time, ~2 minutes)
1. Kawaida opens **Money → Walk-ins** (new sub-link under Money)
2. Clicks "Create QR code", picks a campaign or post to attribute to,
   picks a landing template ("Show discount" / "Book appointment" /
   "Follow on Instagram")
3. Clicks "Generate" → gets a QR PNG she can save + a print-ready PDF
4. Prints the flyer / sticker / poster, puts it where customers see it

### Each scan
1. Customer points phone camera → opens `kova.link/qr/abc123/`
2. Page renders the chosen landing template (e.g., "Show this to claim
   10% off braids — valid today only")
3. Sets a cookie with `visitor_id` so we can tie a later walk-in back
4. `QRScan` row created, tied to the post / campaign

### Each walk-in
1. Customer walks in, asks for the discount
2. Stylist opens `/walkin/` on the salon iPad / phone
3. Taps "Instagram" (if she said she saw it there)
4. Optionally enters revenue (KES 3,500 for braids)
5. `WalkInEvent` row created with the attribution label

### Each daily brief
- Revenue Dashboard surfaces: "Jamhuri Day IG post: 47 scans → 23
  walk-ins (49% conversion) → KES 18,400 attributed"
- Daily Brief's revenue line now says: "Your top revenue source
  yesterday was walk-ins from your Friday IG post — KES 3,200."

---

## Integration with existing systems

### Revenue Dashboard (`get_revenue_summary`)
Extend the existing function to also pull WalkInEvent rows. They roll
up alongside Conversion (Pixel-attributed) rows under the same
"top_posts" / "platform_revenue" / etc. keys, just with `source=walk_in`.

### Daily Brief (`get_revenue_headline_insight`)
Already branches on data state — add a new branch when most revenue
is walk-ins, surface that pattern.

### Engage Agent
Doesn't directly read walk-in data, but the Adapt Agent v2 may in
Phase 3 (e.g., "Posts with discount QR codes drive 3× the walk-ins
of posts without"). Out of scope for v2.

### Campaigns
The new Walk-in attribution UI lives inside the Campaigns surface so
SMEs creating a "Jamhuri Day Sale" campaign get a "Generate QR for
this campaign" button right where they're thinking about it.

---

## Industry-aware landing templates

Five templates for v2. The user picks one; the page renders.

| Template | Best for | Payload schema |
|---|---|---|
| `discount` | Salon, restaurant, retail | `{discount_pct: int, valid_until: date, terms: str}` |
| `menu` | Restaurant, café | `{menu_image_url: str, today_special: str}` |
| `booking` | Salon, real estate, consultant | `{booking_link: str OR null, contact_whatsapp: str}` |
| `follow` | Any | `{instagram_handle: str, facebook_url: str}` |
| `custom` | Power users | `{headline: str, body: str, cta_text: str, cta_url: str}` |

All templates share the same chrome:
- Brand logo + colors from `UserProfile` (Magic Fill / industry pack
  defaults already populate this)
- Big tap-friendly buttons
- "Powered by Kova" footer (small, dismissable)
- Mobile-first (most QR scans are phone-only)

---

## Print-ready PDF generation

Three formats per QR code, in one PDF:

1. **Receipt sticker** — 5cm × 5cm square, just the QR + a tiny "Scan
   me!" line. For taping to receipts, packaging, business cards.
2. **Counter sticker** — 10cm × 10cm, QR + headline + 1 line of body.
   For tills, mirrors, doors.
3. **Flyer** — A5 (15cm × 21cm), QR + full headline + body + brand
   logo. For handouts at events.

Generated server-side with `reportlab` (already a Django ecosystem
staple, no JS canvas hacks needed). PDF served as a download from
`/qr/<id>/print/`.

---

## Privacy + safety

- The public `/qr/<token>/` page does NOT collect PII. It logs only
  the scan event + a visitor cookie. No email, no name.
- The cashier UI is per-business unguessable URL — anyone with the
  URL can record walk-ins. SMEs are advised to keep it private.
- WalkInEvent `revenue` is optional. Many salons don't want to track
  per-visit revenue; they want the conversion count.
- All data is scoped to the user. Admin team can see aggregate via
  the existing admin_dashboard surface (TBD whether we add a Walk-in
  report there in v2 — defer).

---

## Acceptance criteria — when is W5-6 done?

- [ ] `apps/qr_attribution/` exists with three models + migrations
- [ ] `/qr/<token>/` renders one of 5 landing templates by name
- [ ] `QRScan` row created on every scan, with visitor_id cookie set
- [ ] `/qr/` index page lists user's QR codes with scan + walk-in counts
- [ ] `/qr/new/` form: pick campaign/post, pick template, fill payload
- [ ] `/qr/<id>/print/` returns a PDF with all 3 sticker formats
- [ ] `/walkin/<business-slug>/` renders a phone-friendly cashier UI
- [ ] `/walkin/record/` POST creates a WalkInEvent
- [ ] Walk-ins roll up into `get_revenue_summary()`'s top_posts +
      platform_revenue (alongside Conversion rows)
- [ ] Revenue Dashboard shows walk-in attribution alongside Pixel
- [ ] Money section gets a new "Walk-ins" sub-link
- [ ] Tests cover: scan → walkin chain, landing template rendering,
      PDF generation, cashier UI POST flow, revenue rollup
- [ ] Default scope: 1 cashier URL per user (Agency adds team support
      later if needed)

---

## File-level work plan

| Step | File | Change |
|---|---|---|
| W5.1 | `apps/qr_attribution/__init__.py` + apps.py | New Django app |
| W5.2 | `apps/qr_attribution/models.py` | QRCode + QRScan + WalkInEvent |
| W5.3 | `apps/qr_attribution/migrations/0001_initial.py` | Initial schema |
| W5.4 | `apps/qr_attribution/views.py` | Scan landing + index + create + edit + print + cashier |
| W5.5 | `apps/qr_attribution/urls.py` + `config/urls.py` | Route wiring |
| W5.6 | `templates/qr_attribution/landing/*.html` | 5 landing templates (discount, menu, booking, follow, custom) |
| W5.7 | `templates/qr_attribution/list.html` + `create.html` + `detail.html` | User-side management |
| W5.8 | `templates/qr_attribution/cashier.html` | Phone-friendly button grid |
| W5.9 | `apps/qr_attribution/pdf.py` | reportlab PDF generation (3 formats per QR) |
| W5.10 | `apps/analytics/revenue.py` | Extend `get_revenue_summary` to roll up WalkInEvent alongside Conversion |
| W5.11 | `templates/layouts/app.html` | "Walk-ins" sub-link under Money |
| W5.12 | `tests/test_qr_attribution.py` | New file, ~15 tests |
| W5.13 | `apps/qr_attribution/admin.py` | Django admin registration (debugging + support) |

---

## Rollout

Unlike Engage v2 and Adapt v2, this is **additive only** — no
existing feature changes behavior. Ship it on, no feature flag
needed. Plan-tier-gate the feature itself: Walk-ins is **Pro+**
(matches Kova Pixel's gating, same "physical conversion" feature
class).

If a Starter user hits `/qr/`, they get the same upgrade prompt
pattern as other Pro+ features.
