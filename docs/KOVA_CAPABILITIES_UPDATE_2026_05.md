# Kova — Capability & Value Update (May 2026)

> A founder-facing snapshot of what Kova can do for an African SME today,
> after the Phase 2-4 ship cycle (commits `a41a89b` → `c80c414`).
> For the static feature list see [KOVA_PLATFORM_CAPABILITIES.md](KOVA_PLATFORM_CAPABILITIES.md).
> For the agent lifecycle see [KOVA_LIFECYCLE.md](KOVA_LIFECYCLE.md).

---

## TL;DR

**Kova is an AI marketing operator built for SMEs whose customers
convert in person.**

It writes the posts, replies to the comments, learns what's working,
prints the QR codes, runs the booking page, recognises the walk-in,
asks for the review 24h after, and turns the praise into next week's
content. Every morning the AI tells the owner what it did, what it
learned, and the one thing it couldn't handle.

**What changed in May 2026:** Kova went from "AI that posts on social
media" to "AI that owns the conversion funnel." The post-publish
half of the loop — walk-ins, bookings, reviews, attribution — used
to fall off the end of the table. Now it lands back in the same
revenue dashboard. Western marketing tools don't touch this. We do.

---

## Six things Kova does that nothing else does for African SMEs

### 1. Closes the social → walk-in revenue loop

A salon, restaurant, or retail shop posts to Instagram. A customer
sees it, scans the QR on the door, walks in, pays cash.

Without Kova that sequence is invisible — the post is in one tool,
the till is in another, the owner has no idea which post drove the
KES 3,500 service.

With Kova:

- One-click **QR creation** tied to a campaign or specific post
- Five landing templates (discount, menu, booking, follow, custom)
- **Print-ready PDF** with three sticker sizes (receipt corner, counter, A5 flyer)
- Scans capture a `visitor_id` cookie that survives the walk to the till
- Mobile-first **cashier UI** at `/walkin/<slug>/` where staff tap
  "Where did you hear about us?" — no login, the URL is the auth
- A walk-in recorded within 30 min of a scan auto-attributes back
  to the QR and the originating post
- Revenue Dashboard now shows: *"Jamhuri Day IG post → 47 scans →
  23 walk-ins → KES 18,400 attributed"*

This is the loop Western SaaS won't build because their TAM is
e-commerce. For Kawaida-the-salon-owner it's the *only* loop that matters.

### 2. Booking-as-conversion

For salons, real estate, fitness, clinics, consultants — the
conversion isn't a click. It's a confirmed appointment with a name
and a time. Kova now ships the full path:

- **One BookingLink = one calendar** (slug, services, working hours,
  advance notice, max horizon)
- Slot engine subtracts already-booked time + respects advance notice
  and max-advance-days
- Mobile-first **public booking page** at `/book/<slug>/` — pick service,
  pick day, pick slot, leave WhatsApp number
- Booking confirmed → WhatsApp confirmation auto-fires to both customer
  and owner (template-based; soft-fails if WA not yet wired)
- Owner sees a 14-day calendar with all bookings, can mark completed
  or cancelled in one tap
- Booking revenue **rolls into the same `total_revenue` totals** as
  Pixel-tracked digital sales and walk-ins. The dashboard stops being
  half a story.

### 3. Engage Agent recognises booking intent

The AI replier (Engage Agent v2, already in production) now reads
incoming comments and DMs through an intent classifier:

> "can I book braids saturday?"
> "are you open thursday?"
> "any time available tomorrow?"
> "nataka kuja saturday" — Swahili "I want to come Saturday"

When booking intent is detected *and* the owner has an active
BookingLink, Engage's draft reply auto-appends:

> Tap to book: kova.link/book/kawaida/?src=engage_agent

The `?src=engage_agent` param means every booking made this way is
attributed back to the AI's reply — closing yet another loop: post →
DM → AI reply → confirmed booking → revenue.

### 4. Auto review-request loop after every conversion

When a Lead converts or a Booking flips to `completed`, Kova
**schedules a review request 24h out** without the owner doing anything.

24 hours later:

- WhatsApp goes out first; falls back to email if no WA send
- Customer replies with their review text via WhatsApp inbound webhook
  (or a public response form for email links)
- Sentiment classifier (EN + Swahili keyword/emoji) categorises the
  response
- **Positive (≥0.7):** auto-creates a `ContentSeed` with the
  testimonial idea, ready for the Create Agent to turn into a
  social proof post or carousel
- **Negative (≤0.3):** flagged `escalated_in_brief` so it surfaces
  in tomorrow's Daily Brief under "I couldn't handle — your call"
- **Neutral:** logged, no action

Reviews become a flywheel: positive ones write next week's content
without the owner lifting a finger, negative ones trigger a
follow-up the owner actually has time for.

### 5. The Daily Brief is now the AI talking

Kova rewrote the morning brief into **AI-first-person, action-tense
voice**. Instead of "Your engagement was up 12% yesterday" the
owner reads:

> Sarah,
>
> I auto-replied to 7 comments, scheduled 2 review requests, and
> turned a 5-star testimonial from Mary into a content seed for you.
>
> I retired the "Friday motivation quote" pattern — 5 posts averaged
> 0.2% engagement. I couldn't handle Mary's review reply — her tone
> shifted negative. She's at /reviews/abc-123/.
>
> Your move today: open Mary's review and decide if it needs a call.

Three panels render automatically:

- **I handled** — concrete count of auto-sent replies, walk-ins,
  bookings, content seeds
- **I learned** — single most impactful Adapt v2 change (pattern
  promotion, retirement, pillar reweight, frequency change)
- **I couldn't handle — your call** — clickable escalations linking
  straight to the right URL

This is a quiet but big shift. Kova is no longer reporting *on* the
work. It's reporting *its* work. That changes the relationship from
"tool you check" to "operator you trust."

### 6. Plain-English performance over charts

The Performance page used to lead with bar charts and engagement
percentages. Now it leads with sentences:

> "Instagram is your strongest channel — 3.2× the engagement of Twitter."
> "Tuesday is your strongest day (4.1% avg engagement)."
> "Your behind-the-scenes posts outperform product shots by 2.4×."
> "You drove 23 saves (1.8% save rate) — that's strong intent."
> "Only 4 posts this month — consistency matters more than perfection."

Charts are still there for the analyst — but the front door is now
plain English the owner can act on in 30 seconds.

---

## The four loops Kova now closes

| Loop | Without Kova | With Kova |
|---|---|---|
| **Social → walk-in** | Invisible. SME guesses. | QR + cashier UI + visitor cookie = real attribution |
| **Social → booking** | Manual WhatsApp ping-pong | Intent detection + booking link + auto WA confirmation |
| **Conversion → review** | Forgotten | Auto-scheduled 24h out, WA-first, sentiment-routed |
| **Praise → content** | Never happens | Positive review auto-creates ContentSeed for the Create Agent |

Each loop closes into the **same revenue total**: walk-ins,
bookings, and Pixel-tracked digital sales all roll up into
`total_revenue` in `get_revenue_summary`. The ROI number on the
Revenue Dashboard finally reflects all of the money.

---

## What an SME owner actually does in a day

After May 2026 the typical morning looks like this:

1. **Open WhatsApp** → 2-line Daily Brief from Kova: what it did,
   what it learned, what it couldn't handle
2. **Tap one link** → that one thing Kova flagged for them (a
   negative review, a flagged comment, a lead that asked about pricing)
3. **Reply in <2 minutes** → done; Kova handles everything else

The Engage Agent auto-replies on safe-zone comments. The Adapt Agent
shifts which patterns Kova favours. The Create Agent drafts the
week's posts from positive reviews and trending angles. The booking
page collects the appointments. The QR codes catch the walk-ins.

The owner's job has stopped being "do social media" and started
being "decide the 1-3 things only you can decide."

---

## Who this is for

**Tier 1 — flagship industries where the moats matter most:**

- Salons / barbershops / beauty / nails / spa
- Restaurants / cafes / bakeries / cloud kitchens
- Retail / boutiques / wholesale
- Fitness / yoga studios / personal training
- Real estate agents / property viewings
- Clinics / dental / wellness
- Consultants / coaches with booked services

For these SMEs, **70%+ of conversions happen offline** — Western
tools literally cannot see that revenue. Kova does.

**Tier 2 — works fine, fewer moats apply:**

- Pure e-commerce (Pixel covers most of it)
- B2B SaaS / consulting where conversion = email contact
- Creators / influencers (uses Create + Engage; less booking, no walk-in)
- Nonprofits / NGOs (uses every agent but no revenue dashboard)

Tier 1 is the wedge. Tier 2 is the spread.

---

## Onboarding is finally tight

The Tier 3 polish that just shipped removes the last three
"why hasn't the AI started yet?" moments:

- **Paste a website URL, tab out, fields populate.** No "Auto-fill"
  button to click. The infer-from-URL flow used to need an opt-in;
  now it just happens.
- **Connect WhatsApp Business → industry, contact, brand voice
  pre-populate.** Magic Fill now supports WABA via
  `audit_profile` on the WhatsApp provider. SMEs who connect WA
  first (which most do — WA is universal in Africa) get a fully
  populated brand profile.
- **Drag to reschedule on the calendar.** New `/content/<id>/reschedule/`
  endpoint accepts ISO datetime; calendar UI wires to it via drag-and-drop.

The remaining onboarding friction is now **template approval by
Meta** — which is a manual step at Meta Business Suite, not a
Kova code gap. The `docs/WHATSAPP_TEMPLATES.md` catalog lists
every template the codebase expects so the founder can submit
them all in one sitting.

---

## What's still ahead (Phase 5+)

| Item | Why we haven't done it yet |
|---|---|
| Calendly OAuth provider | v2 ships Kova-hosted; Calendly users have their own flow |
| Lipa Na M-Pesa deposits on bookings | Phase 3 backlog — requires Daraja API integration |
| iCal / Google Calendar sync | Phase 3 — bookings are durable now, sync is a luxury |
| Multi-staff calendars with internal conflict resolution | v2 says: one BookingLink per staff member; salons solve this with multiple links |
| Recurring appointments / packages (10-class fitness packs) | Phase 3 — model is ready, UI is not |
| POS integration (Square, Loyverse, Lipa Na till) | Phase 4 — v2 cashier UI is manual entry |
| Multi-touch attribution graph (visitor journey > first/last touch) | Already exists in `ConversionJourney`; needs UI surface |
| NFC tag support on QR codes | Phase 5 — niche but real for retail |

---

## What Kova's value proposition reads as today

If you had to pitch Kova in one paragraph at a market in Eastlands:

> Kova runs your social media like an agency would, but for the
> price of a Netflix subscription. It writes your posts, replies
> to comments, prints your QR codes, takes bookings on a phone-
> friendly page, recognises the walk-in customer at the till,
> follows up for a review 24h after, and turns the praise into
> next week's posts. Every morning the AI tells you what it did
> and the one thing only you can decide. It's built for Kenyan
> businesses — Swahili replies, M-Pesa-aware revenue, WhatsApp-
> first everything. Western tools can't see your walk-ins. Kova can.

That's the product after May 2026. The next ship cycle is about
turning the wedge into a stack — payments on bookings, multi-touch
attribution, POS integrations. The moats stay; the conversion path
just gets shorter.
