"""
Lead Bridge — auto-creates Leads from commerce payments, bookings, QR scans,
walk-ins, and social engagement with purchase intent.
Closes the flywheel: Social -> Commerce -> Leads -> Nurture -> Repeat.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

PURCHASE_INTENT_SIGNALS = frozenset({"pricing", "booking", "purchase", "buy", "order"})


def _engage_lead_metadata(interaction) -> dict:
    """Build lead metadata including booking link when intent is booking."""
    meta = {
        "engage_intent": interaction.ai_intent,
        "platform": interaction.platform or "",
        "author_username": interaction.author_username,
        "first_message": (interaction.content or "")[:200],
    }
    if interaction.ai_intent == "booking":
        try:
            from apps.commerce.bookings.models import BookingLink
            from apps.commerce.bookings.service_setup import booking_public_url

            link = BookingLink.objects.filter(
                user=interaction.user, is_active=True,
            ).first()
            if link:
                meta["booking_url"] = booking_public_url(link)
                meta["suggested_owner_action"] = "Reply with booking link or let WhatsApp bot handle BOOK"
        except Exception:
            pass
    return meta


def _whatsapp_lead_email(wa_id: str) -> str:
    return f"wa_{wa_id}@kova.page"


def find_lead_for_whatsapp_conversation(conversation):
    """Return an existing Lead linked to this WhatsApp thread, if any."""
    from apps.commerce.leads.models import Lead

    user = conversation.social_account.user
    wa_id = conversation.contact_wa_id
    email = _whatsapp_lead_email(wa_id)
    lead = Lead.objects.filter(user=user, email=email).first()
    if lead:
        return lead
    phone = (conversation.contact_phone or wa_id or "").strip()
    if phone:
        return Lead.objects.filter(user=user, phone=phone).first()
    meta_id = (conversation.context or {}).get("lead_id")
    if meta_id:
        return Lead.objects.filter(user=user, pk=meta_id).first()
    return None


def create_lead_from_whatsapp_conversation(conversation, *, enroll: bool = True):
    """Create or return a Lead from a WhatsApp conversation."""
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    existing = find_lead_for_whatsapp_conversation(conversation)
    if existing:
        return existing

    user = conversation.social_account.user
    wa_id = conversation.contact_wa_id
    contact_name = (conversation.contact_name or "").strip()
    phone = (conversation.contact_phone or wa_id or "").strip()
    email = _whatsapp_lead_email(wa_id)

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": contact_name,
            "phone": phone,
            "source_type": Lead.Source.SOCIAL_DM,
            "source_platform": "whatsapp",
            "temperature": Lead.Temperature.HOT,
            "metadata": {
                "wa_id": wa_id,
                "conversation_id": str(conversation.pk),
            },
        },
    )

    if not created:
        updates = []
        if contact_name and not lead.name:
            lead.name = contact_name
            updates.append("name")
        if phone and not lead.phone:
            lead.phone = phone
            updates.append("phone")
        if updates:
            updates.append("last_activity_at")
            lead.save(update_fields=updates)
    else:
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.SOCIAL_INTERACTION,
            description=f"WhatsApp conversation started with {contact_name or wa_id}",
            metadata={
                "conversation_id": str(conversation.pk),
                "wa_id": wa_id,
                "channel": "whatsapp",
            },
        )
        lead.compute_priority()
        lead.save(update_fields=["priority"])

        ctx = conversation.context or {}
        ctx["lead_id"] = str(lead.pk)
        conversation.context = ctx
        conversation.save(update_fields=["context", "updated_at"])

        if enroll:
            from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
            from apps.commerce.leads.tasks import enroll_lead_in_sequences

            if should_auto_enroll_leads(user):
                try:
                    enroll_lead_in_sequences(lead)
                except Exception:
                    logger.exception("Failed to enroll WhatsApp lead %s", lead.pk)

    return lead


def create_lead_from_commerce_payment(payment):
    """Create or update a Lead when a commerce payment completes."""
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    user = payment.user
    phone = payment.phone_number or ""

    email = f"buyer_{phone}@kova.page" if phone else f"payment_{payment.pk}@kova.page"

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    name = f"Buyer ({phone[-4:]})" if phone else "Unknown Buyer"

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": name,
            "phone": phone,
            "source_type": Lead.Source.COMMERCE_PURCHASE,
            "source_platform": "mpesa",
            "status": Lead.Status.CONVERTED,
            "temperature": Lead.Temperature.HOT,
            "metadata": {
                "first_product": payment.product.name if payment.product else "",
                "first_amount": str(payment.amount),
                "payment_source": payment.source,
            },
        },
    )

    if not created:
        updates = []
        if lead.status != Lead.Status.CONVERTED:
            lead.status = Lead.Status.CONVERTED
            lead.converted_at = timezone.now()
            updates.extend(["status", "converted_at"])
        if lead.temperature != Lead.Temperature.HOT:
            lead.temperature = Lead.Temperature.HOT
            updates.append("temperature")
        if phone and not lead.phone:
            lead.phone = phone
            updates.append("phone")
        if updates:
            updates.append("last_activity_at")
            lead.save(update_fields=updates)

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.COMMERCE_PURCHASE,
        description=(
            f"Purchased {payment.product.name} for KES {payment.amount}"
            if payment.product
            else f"M-Pesa payment of KES {payment.amount}"
        ),
        metadata={
            "payment_id": str(payment.pk),
            "product_id": str(payment.product_id) if payment.product_id else "",
            "product_name": payment.product.name if payment.product else "",
            "amount": str(payment.amount),
            "receipt": payment.receipt_number or "",
            "phone": phone,
        },
    )

    lead.compute_priority()
    lead.save(update_fields=["priority"])

    if created:
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        if should_auto_enroll_leads(user):
            try:
                enroll_lead_in_sequences(lead)
            except Exception:
                logger.exception("Failed to enroll commerce lead %s", lead.pk)

    return lead


def create_lead_from_booking(booking):
    """Create or update a Lead when a booking is confirmed or completed."""
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    user = booking.booking_link.user
    email = booking.customer_email or f"booking_{booking.customer_phone}@kova.page"

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": booking.customer_name,
            "phone": booking.customer_phone,
            "source_type": Lead.Source.BOOKING,
            "source_platform": booking.source_channel or "direct",
            "temperature": Lead.Temperature.HOT,
            "metadata": {
                "first_service": booking.service_name,
                "first_booking_price": str(booking.price_kes),
                "booking_source": booking.source_channel,
            },
        },
    )

    if not created:
        updates = []
        if booking.customer_name and not lead.name:
            lead.name = booking.customer_name
            updates.append("name")
        if booking.customer_phone and not lead.phone:
            lead.phone = booking.customer_phone
            updates.append("phone")
        if lead.temperature == Lead.Temperature.COLD:
            lead.temperature = Lead.Temperature.WARM
            updates.append("temperature")
        if updates:
            updates.append("last_activity_at")
            lead.save(update_fields=updates)

    is_completed = booking.status == "completed"
    activity_type = (
        LeadActivity.ActivityType.BOOKING_COMPLETED
        if is_completed
        else LeadActivity.ActivityType.BOOKING_MADE
    )
    LeadActivity.objects.create(
        lead=lead,
        activity_type=activity_type,
        description=f"{'Completed' if is_completed else 'Booked'} {booking.service_name} ({booking.scheduled_at:%b %d at %H:%M})",
        metadata={
            "booking_id": str(booking.pk),
            "service": booking.service_name,
            "price": str(booking.price_kes),
            "scheduled_at": booking.scheduled_at.isoformat() if booking.scheduled_at else "",
            "status": booking.status,
        },
    )

    if is_completed and lead.status != Lead.Status.CONVERTED:
        lead.status = Lead.Status.CONVERTED
        lead.converted_at = timezone.now()
        lead.temperature = Lead.Temperature.HOT
        lead.save(update_fields=["status", "converted_at", "temperature", "last_activity_at"])

    lead.compute_priority()
    lead.save(update_fields=["priority"])

    if created:
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        if should_auto_enroll_leads(user):
            try:
                enroll_lead_in_sequences(lead)
            except Exception:
                logger.exception("Failed to enroll booking lead %s", lead.pk)

    try:
        from apps.commerce.leads.professional_funnel import process_professional_consult_lead

        process_professional_consult_lead(lead, user, booking=booking)
    except Exception:
        logger.exception("Professional consult funnel failed for booking lead %s", lead.pk)

    return lead


def create_lead_from_qr_scan(*, user, phone: str, name: str = "", qr_code=None, scan=None):
    """Create or update a Lead when a customer submits phone on a QR landing page."""
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    customer_phone = (phone or "").strip()
    customer_name = (name or "").strip()
    if not customer_phone:
        return None

    phone_key = "".join(c for c in customer_phone if c.isdigit())[-12:] or customer_phone
    email = f"qr_{phone_key}@kova.page"

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": customer_name,
            "phone": customer_phone,
            "source_type": Lead.Source.QR_SCAN,
            "source_platform": "qr",
            "temperature": Lead.Temperature.WARM,
            "metadata": {
                "qr_id": str(qr_code.pk) if qr_code else "",
                "qr_label": getattr(qr_code, "label", "") if qr_code else "",
                "scan_id": str(scan.pk) if scan else "",
            },
        },
    )

    if not created:
        updates = []
        if customer_name and not lead.name:
            lead.name = customer_name
            updates.append("name")
        if customer_phone and not lead.phone:
            lead.phone = customer_phone
            updates.append("phone")
        if updates:
            updates.append("last_activity_at")
            lead.save(update_fields=updates)

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.QR_SCANNED,
        description=f"QR scan lead capture{f' — {qr_code.label}' if qr_code else ''}",
        metadata={
            "qr_id": str(qr_code.pk) if qr_code else "",
            "scan_id": str(scan.pk) if scan else "",
            "phone": customer_phone,
        },
    )

    if created:
        lead.compute_priority()
        lead.save(update_fields=["priority"])
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        if should_auto_enroll_leads(user):
            try:
                enroll_lead_in_sequences(lead)
            except Exception:
                logger.exception("Failed to enroll QR scan lead %s", lead.pk)

    return lead


def create_lead_from_walkin(walkin_event):
    """Create or update a Lead from a walk-in event (if customer info available)."""
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    user = walkin_event.user

    customer_phone = (walkin_event.customer_phone or "").strip()
    customer_name = (walkin_event.customer_name or "").strip()

    if not customer_phone:
        return None

    # Normalize phone for stable lead key
    phone_key = "".join(c for c in customer_phone if c.isdigit())[-12:] or customer_phone
    email = f"walkin_{phone_key}@kova.page"

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": customer_name,
            "phone": customer_phone,
            "source_type": Lead.Source.WALK_IN,
            "source_platform": walkin_event.attribution_source,
            "temperature": Lead.Temperature.WARM,
            "metadata": {
                "attribution": walkin_event.attribution_source,
                "revenue": str(walkin_event.revenue or 0),
                "walkin_id": str(walkin_event.pk),
            },
        },
    )

    if not created:
        updates = []
        if customer_name and not lead.name:
            lead.name = customer_name
            updates.append("name")
        if customer_phone and not lead.phone:
            lead.phone = customer_phone
            updates.append("phone")
        if updates:
            updates.append("last_activity_at")
            lead.save(update_fields=updates)

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.WALK_IN,
        description=f"Walk-in visit (attributed: {walkin_event.get_attribution_source_display()})",
        metadata={
            "walkin_id": str(walkin_event.pk),
            "attribution": walkin_event.attribution_source,
            "revenue": str(walkin_event.revenue or 0),
        },
    )

    if created:
        lead.compute_priority()
        lead.save(update_fields=["priority"])
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        if should_auto_enroll_leads(user):
            try:
                enroll_lead_in_sequences(lead)
            except Exception:
                logger.exception("Failed to enroll walk-in lead %s", lead.pk)

    return lead


def create_lead_from_engage_intent(interaction):
    """
    Create a Lead when a social interaction shows purchase intent
    (pricing inquiry, booking request, etc.).
    """
    from apps.core.billing.enforcement import check_leads_limit
    from apps.commerce.leads.models import Lead, LeadActivity

    if not interaction.ai_intent or interaction.ai_intent not in PURCHASE_INTENT_SIGNALS:
        return None

    user = interaction.user
    author = interaction.author_username or interaction.author_name
    platform = interaction.platform or ""

    # Build a placeholder email from platform + username
    email = f"{platform}_{author}@kova.page" if author else f"engage_{interaction.pk}@kova.page"
    email = email.lower().replace(" ", "_")[:254]

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return None

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "name": interaction.author_name or author,
            "source_type": Lead.Source.SOCIAL_DM if interaction.interaction_type == "dm" else Lead.Source.SOCIAL_COMMENT,
            "source_platform": platform,
            "source_post": interaction.post,
            "temperature": (
                Lead.Temperature.HOT
                if interaction.ai_intent == "booking"
                else Lead.Temperature.WARM
            ),
            "metadata": _engage_lead_metadata(interaction),
        },
    )

    if not created:
        meta = dict(lead.metadata or {})
        meta.update(_engage_lead_metadata(interaction))
        lead.metadata = meta
        if interaction.ai_intent == "booking" and lead.temperature != Lead.Temperature.HOT:
            lead.temperature = Lead.Temperature.HOT
            lead.save(update_fields=["metadata", "temperature", "last_activity_at"])
        elif lead.temperature == Lead.Temperature.COLD:
            lead.temperature = Lead.Temperature.WARM
            lead.save(update_fields=["metadata", "temperature", "last_activity_at"])
        else:
            lead.save(update_fields=["metadata", "last_activity_at"])

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.SOCIAL_INTERACTION,
        description=f"{platform.title()} {interaction.get_interaction_type_display()}: {interaction.ai_intent} intent — \"{(interaction.content or '')[:80]}\"",
        metadata={
            "interaction_id": str(interaction.pk),
            "platform": platform,
            "intent": interaction.ai_intent,
            "interaction_type": interaction.interaction_type,
            "content_preview": (interaction.content or "")[:200],
        },
    )

    if created:
        lead.compute_priority()
        lead.save(update_fields=["priority"])

    _maybe_enroll_engage_lead(lead, user, interaction, created=created)

    if interaction.ai_intent == "booking":
        try:
            from apps.commerce.leads.professional_funnel import process_professional_consult_lead

            process_professional_consult_lead(lead, user, interaction=interaction)
        except Exception:
            logger.exception("Professional consult funnel failed for lead %s", lead.pk)

    return lead


def _maybe_enroll_engage_lead(lead, user, interaction, *, created: bool):
    """Auto-enroll engage leads; booking intent always re-checks nurture sequences."""
    from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
    from apps.commerce.leads.tasks import enroll_lead_in_sequences

    if not should_auto_enroll_leads(user):
        return
    if interaction.ai_intent == "booking" or created:
        try:
            enroll_lead_in_sequences(lead)
        except Exception:
            logger.exception("Failed to enroll engage-intent lead %s", lead.pk)
