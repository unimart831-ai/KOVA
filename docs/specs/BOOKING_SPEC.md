# Booking Integration Spec

> Phase 2 Weeks 7-8 of [KOVA_MASTER_PLAN.md](../KOVA_MASTER_PLAN.md).
> The second Africa-native moat. For industries where conversion =
> a confirmed booking, not a click or a sale: salons, real estate
> agents, fitness trainers, clinics, consultants.

---

## Goal

Close the loop from **social post → DM intent → confirmed booking →
KES revenue** for SMEs whose conversion is an appointment.

Today the path stops at "customer DMs us 'can I book Saturday?'" and
the SME owner does the rest in WhatsApp manually. Engage Agent v2
can already reply, but it can't *commit* a slot. So the moment a
customer expresses booking intent, the conversion stalls into chat
ping-pong.

After this spec ships:

1. Owner sets up a **BookingLink** — a short slug like `kova.link/book/kawaida`
   with their service catalog + working hours
2. Engage Agent **detects booking intent** in replies and embeds the
   link automatically
3. Customer taps, picks service + time on a **mobile-first booking
   page**, leaves phone number
4. **Booking** is created. WhatsApp confirmation fires to both parties
   via the existing template system
5. Booking links back to the originating Post / Campaign / QR
6. **Revenue Dashboard** rolls up booking revenue alongside Conversion
   and WalkInEvent, so ROI reflects the full physical-conversion world

---

## What's NOT in scope for v2

- **Payment collection at booking time.** v2 books slots, doesn't
  charge. Owners collect at arrival. v3 will add Lipa Na M-Pesa deposits.
- **Multi-staff calendars with conflict resolution across stylists.**
  v2 assumes one calendar per BookingLink. Salons with multiple
  stylists get one BookingLink each, or use Calendly.
- **Recurring appointments / packages** (10-class fitness packs). Phase 3.
- **Group booking** (3 friends at the same time). Phase 3.
- **iCal / Google Calendar sync.** Phase 3.
- **Auto reminders 24h / 1h before.** Falls out of Phase 3 W12 brief work.

---

## Data model

### New app: `apps/bookings/`

Two new models. The domain stays contained.

```python
class BookingLink(models.Model):
    """A bookable surface tied to a user.

    One BookingLink = one calendar. SMEs with multiple staff create
    multiple BookingLinks (e.g. "Braids with Jane", "Cuts with Sam")
    rather than the system handling conflicts internally.
    """
    id = UUIDField(primary_key)
    user = FK(User)
    slug = SlugField(unique=True, max_length=40)
    label = CharField(200)             # "Book braids with Kawaida"
    industry_template = CharField(20)  # salon / real_estate / fitness / consultant / generic

    # What can be booked
    services = JSONField(default=list)
    # services = [
    #   {"name": "Box braids", "duration_minutes": 180, "price_kes": 3500},
    #   {"name": "Cornrows",   "duration_minutes": 120, "price_kes": 2000},
    # ]

    # When it's available
    working_hours = JSONField(default=dict)
    # working_hours = {
    #   "mon": [{"start": "09:00", "end": "18:00"}],
    #   "tue": [...], ..., "sun": [],
    # }
    timezone = CharField(40, default="Africa/Nairobi")
    advance_notice_minutes = IntegerField(default=120)  # can't book within 2h
    max_advance_days = IntegerField(default=30)         # can't book past 30 days out

    # Contact for confirmation
    owner_whatsapp = CharField(20, blank=True)
    owner_email = EmailField(blank=True)

    # Status
    is_active = BooleanField(default=True)
    created_at + updated_at


class Booking(models.Model):
    """A single confirmed-or-pending booking on a BookingLink."""
    id = UUIDField(primary_key)
    booking_link = FK(BookingLink)

    # Customer
    customer_name = CharField(120)
    customer_phone = CharField(20)
    customer_email = EmailField(blank=True)

    # What was booked
    service_name = CharField(200)
    duration_minutes = IntegerField()
    price_kes = DecimalField(10, 2)  # snapshot from BookingLink.services
    scheduled_at = DateTimeField(db_index=True)

    # Lifecycle
    class Status(TextChoices):
        PENDING   = "pending",   "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW   = "no_show",   "No-show"
    status = CharField(20, choices=Status.choices, default=Status.CONFIRMED)

    # Attribution chain — where did this booking come from?
    source_post   = FK(Post, null=True)        # Engage Agent reply included our link
    source_campaign = FK(Campaign, null=True)
    source_qr     = FK(QRCode, null=True)      # customer scanned a QR
    source_channel = CharField(40, blank=True) # "engage_agent", "qr", "direct"

    # Confirmation
    customer_confirmation_sent_at = DateTimeField(null=True)
    owner_confirmation_sent_at = DateTimeField(null=True)
    notes = TextField(blank=True)

    # Timestamps
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    confirmed_at = DateTimeField(null=True)
    completed_at = DateTimeField(null=True)
```

`scheduled_at` is the index that matters — slot-availability queries
hit it most. The `(booking_link, scheduled_at)` composite makes calendar
view fast for the owner.

---

## URLs

```python
# User-side (login required)
/bookings/                      — BookingLink list + recent bookings
/bookings/links/new/            — create new BookingLink
/bookings/links/<id>/           — edit BookingLink (services, hours)
/bookings/links/<id>/calendar/  — calendar view for this link
/bookings/<id>/                 — single Booking detail
/bookings/<id>/cancel/          — cancel
/bookings/<id>/complete/        — mark completed (triggers W9 review)

# Public — anyone with the link
/book/<slug>/                   — pick service + time + leave contact
/book/<slug>/confirm/           — POST submit, creates Booking
```

`/book/<slug>/` is the mobile-first conversion page. Single column,
big tap targets, asks the absolute minimum.

---

## Engage Agent intent detection

In `apps/agents/engage_v2/intent.py` (new):

```python
BOOKING_INTENT_PATTERNS = [
    r"\bbook\b", r"\breserve\b", r"\bappointment\b",
    r"\bschedule\b", r"\bopen\b.*\?",  # "are you open Saturday?"
    r"\bavailable\b", r"\btime\b.*\?",
    r"\bbook(?:ing)?\b", r"\bbeza\b",  # Swahili "make"
]

def detect_booking_intent(message: str) -> bool:
    """Returns True when a message expresses booking intent."""
```

When `detect_booking_intent(comment) and user.has_booking_link()`:

1. Engage Agent draft now includes the booking link automatically
2. Confidence tier shifts up — booking links are high-confidence
   responses (the link is the answer)
3. Reply ends with `\n\nTap to book: kova.link/book/{slug}`

---

## WhatsApp confirmation flow

Uses the existing `apps/whatsapp/` template send infrastructure.

Two templates needed:

* **`booking_confirmed_customer`** — to customer:
  > Karibu! Your {service} is confirmed for {date} at {time}.
  > Save this WhatsApp number for changes. Asante! — {business_name}

* **`booking_new_owner`** — to owner:
  > New booking: {customer_name} ({customer_phone})
  > {service} · {date} {time} · KES {price}
  > Source: {source_channel}

Both fire from `Booking.save()` post-save signal when `status` flips
to `confirmed`. Failures log to `AgentAction` but don't block the
booking — owners get a Daily Brief alert if WhatsApp is down.

---

## Revenue Dashboard rollup

`apps/analytics/revenue.py:get_revenue_summary` extends again to
include bookings (parallel to the WalkInEvent rollup just shipped):

```python
booking_totals = Booking.objects.filter(
    booking_link__user=user,
    status__in=["completed", "confirmed"],
    scheduled_at__gte=cutoff,
).aggregate(revenue=Sum("price_kes"), count=Count("id"))

totals["booking_revenue"] = booking_totals["revenue"] or 0
totals["booking_count"]   = booking_totals["count"] or 0
totals["total_revenue"]   = totals["total_revenue"] + totals["booking_revenue"]
```

Confirmed-but-not-completed bookings count as **projected** revenue;
completed bookings count as **realized**. The dashboard shows both.

---

## File-level work plan

| ID | File | What |
|----|------|------|
| W7.1 | `apps/bookings/__init__.py` | New app skeleton |
| W7.2 | `apps/bookings/apps.py` | AppConfig |
| W7.3 | `apps/bookings/models.py` | `BookingLink`, `Booking` |
| W7.4 | `apps/bookings/migrations/0001_initial.py` | Generated |
| W7.5 | `apps/bookings/views.py` | All views |
| W7.6 | `apps/bookings/urls.py` | URL routes |
| W7.7 | `apps/bookings/slots.py` | Slot-availability engine — given a BookingLink + date, return free slots |
| W7.8 | `apps/bookings/admin.py` | Django admin |
| W7.9 | `apps/bookings/signals.py` | Post-save → WhatsApp confirmation fire |
| W7.10 | `templates/bookings/list.html` | Owner BookingLink list |
| W7.11 | `templates/bookings/link_form.html` | Create / edit BookingLink |
| W7.12 | `templates/bookings/link_calendar.html` | Calendar view per link |
| W7.13 | `templates/bookings/detail.html` | Single Booking owner detail |
| W7.14 | `templates/bookings/public/book.html` | Public booking page |
| W7.15 | `templates/bookings/public/confirm.html` | "You're booked!" page |
| W7.16 | `apps/agents/engage_v2/intent.py` | Booking intent detection |
| W7.17 | `apps/agents/engage_v2/replier.py` | Embed booking link in replies |
| W7.18 | `apps/analytics/revenue.py` | Rollup booking revenue |
| W7.19 | `templates/layouts/app.html` | "Bookings" sub-link under Customers |
| W7.20 | `apps/whatsapp/templates.py` | Two new templates |
| W7.21 | `tests/test_bookings.py` | ~20 tests |
| W7.22 | `docs/DEVELOPMENT_ROADMAP.md` | Tick W7.1-22 |

W7.8 (Calendly OAuth provider) — punted to a Phase 3 backlog item.
v2 ships Kova-hosted bookings; Calendly users already have a flow.

---

## Acceptance test (manual)

Kawaida sets up `/book/kawaida` with two services (braids 180min /
cornrows 120min) and Tues-Sat 09:00-18:00.

She posts on IG: "Slots open Saturday! DM to book." A customer
comments "can I get braids saturday?"

Engage Agent v2 (already deployed) drafts a reply. Booking intent
detection (new) prepends `Tap to book: kova.link/book/kawaida` to the
draft. Owner approves. Reply sent.

Customer taps. Picks "Box braids" → Saturday 14:00. Enters phone.
Submits. Sees confirmation page.

Kawaida gets WhatsApp from Kova: "New booking: Mary +254712...
Box braids · Sat 14:00 · KES 3,500 · Source: engage_agent".
Mary gets WhatsApp: "Karibu! Your Box braids is confirmed for
Saturday at 14:00."

Saturday afternoon. Mary arrives, gets braids, pays. Kawaida opens
the booking detail, taps "Mark completed". Booking flips to completed.

Revenue Dashboard now shows:
- `total_revenue` includes the KES 3,500
- `booking_revenue` = 3,500
- Source breakdown shows `engage_agent` as the channel
- (Phase 3 W9 review request will fire 24h later)

---

## Done when

- [ ] `python manage.py check` clean
- [ ] All tests in `tests/test_bookings.py` pass
- [ ] Booking model migrations applied without conflict
- [ ] Slot engine correctly excludes already-booked times
- [ ] Slot engine respects working_hours + advance_notice + max_advance_days
- [ ] Engage Agent draft includes booking link when intent detected
- [ ] WhatsApp confirmation fires post-save (mock the WhatsApp call in tests)
- [ ] Bookings nav link visible under Customers section
- [ ] `get_revenue_summary` returns `booking_revenue` and `total_revenue` includes it
