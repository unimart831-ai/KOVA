"""
WhatsApp Commerce Bot — Conversational commerce state machine.

Handles product browsing, booking flows, and M-Pesa payments
within WhatsApp conversations. Plugs into the existing auto-reply
pipeline via handle_commerce_message().

State is stored in conversation.context["commerce"] and transitions
are driven by keyword triggers + interactive reply callbacks.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

NAIROBI_TZ = ZoneInfo("Africa/Nairobi")

# Keywords that activate the commerce bot (lowercased for matching)
BROWSE_TRIGGERS = {"menu", "products", "catalog", "catalogue", "prices", "what do you sell", "shop", "bei"}
BOOKING_TRIGGERS = {"book", "appointment", "schedule", "booking", "reserve"}
PAYMENT_TRIGGERS = {"pay", "buy", "order", "nunua", "lipa"}

COMMERCE_STATES = {
    "idle", "browsing", "product_detail", "cart_review",
    "booking_select", "booking_time", "booking_confirm",
    "payment_pending",
}

CART_TRIGGERS = {"cart", "my cart", "checkout", "view cart", "basket"}


def handle_commerce_message(conversation, message, social_account):
    """
    Returns True if the commerce bot handled the message, False to fall
    through to AI auto-reply.

    Called from handle_incoming_message BEFORE the LLM pipeline.
    """
    from apps.core.platforms.providers.registry import get_provider

    if not conversation.is_window_open:
        return False

    provider = get_provider("whatsapp")
    if not provider:
        logger.error("WhatsApp provider not available for commerce bot")
        return False

    ctx = _get_commerce_ctx(conversation)
    state = ctx.get("state", "idle")
    text = (message.content or "").strip()
    text_lower = text.lower()
    interactive = message.interactive_data or {}

    # Interactive replies always route to commerce if we have an active state
    is_interactive = interactive.get("type") in ("button_reply", "list_reply")
    reply_id = interactive.get("id", "")

    user = social_account.user

    # Ensure a lead exists for commerce interactions
    _ensure_lead(user, conversation)

    handled = False

    if state == "idle":
        if _matches_any(text_lower, CART_TRIGGERS):
            return _show_cart(
                conversation, social_account, provider,
                social_account.access_token, conversation.contact_wa_id,
                ctx, user,
            )
        handled = _handle_idle(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "browsing":
        handled = _handle_browsing(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "product_detail":
        handled = _handle_product_detail(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "cart_review":
        handled = _handle_cart_review(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "booking_select":
        handled = _handle_booking_select(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "booking_time":
        handled = _handle_booking_time(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "booking_confirm":
        handled = _handle_booking_confirm(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )
    elif state == "payment_pending":
        handled = _handle_payment_pending(
            conversation, message, social_account, provider,
            text_lower, is_interactive, reply_id, ctx, user,
        )

    return handled


# ═════════════════════════════════════════════════════════════════════════════
# STATE HANDLERS
# ═════════════════════════════════════════════════════════════════════════════


def _handle_idle(conversation, message, social_account, provider,
                 text_lower, is_interactive, reply_id, ctx, user):
    """Detect trigger keywords and transition to the appropriate state."""
    token = social_account.access_token
    to = conversation.contact_wa_id

    if _matches_any(text_lower, BROWSE_TRIGGERS):
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    if _matches_any(text_lower, BOOKING_TRIGGERS):
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    if _matches_any(text_lower, PAYMENT_TRIGGERS):
        _send_text(provider, token, to,
                   "What would you like to pay for? You can browse our *products* or *book* a service first.")
        return True

    return False


def _handle_browsing(conversation, message, social_account, provider,
                     text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if text_lower in ("back", "cancel", "exit"):
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "No problem! How else can I help you?")
        return True

    if _matches_any(text_lower, BROWSE_TRIGGERS):
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    if is_interactive and reply_id.startswith("cat_"):
        category_id = reply_id[4:]
        return _show_category_products(
            conversation, social_account, provider, token, to, ctx, user, category_id,
        )

    if is_interactive and reply_id.startswith("prod_"):
        product_id = reply_id[5:]
        return _show_product_detail(
            conversation, social_account, provider, token, to, ctx, user, product_id,
        )

    # Fallback: re-show categories
    return _show_categories(conversation, social_account, provider, token, to, ctx, user)


def _handle_product_detail(conversation, message, social_account, provider,
                           text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if text_lower in ("back", "cancel", "exit"):
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    if is_interactive and reply_id == "buy_now":
        product_id = ctx.get("current_product_id")
        if product_id:
            return _initiate_product_payment(
                conversation, social_account, provider, token, to, ctx, user, product_id,
            )

    if is_interactive and reply_id == "add_cart":
        product_id = ctx.get("current_product_id")
        if product_id:
            return _add_to_cart(conversation, social_account, provider, token, to, ctx, user, product_id)

    if is_interactive and reply_id == "view_cart":
        return _show_cart(conversation, social_account, provider, token, to, ctx, user)

    if is_interactive and reply_id == "ask_question":
        _set_state(conversation, ctx, "idle")
        return False  # Let AI auto-reply handle the question

    if is_interactive and reply_id == "browse_more":
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    return False


def _handle_booking_select(conversation, message, social_account, provider,
                           text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if text_lower in ("back", "cancel", "exit"):
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "Booking cancelled. How else can I help?")
        return True

    if is_interactive and reply_id.startswith("svc_"):
        service_index = reply_id[4:]
        return _select_booking_service(
            conversation, social_account, provider, token, to, ctx, user, service_index,
        )

    if _matches_any(text_lower, BOOKING_TRIGGERS):
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    return False


def _handle_booking_time(conversation, message, social_account, provider,
                         text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if text_lower in ("back", "cancel", "exit"):
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    if is_interactive and reply_id.startswith("slot_"):
        slot_str = reply_id[5:]
        return _select_time_slot(
            conversation, social_account, provider, token, to, ctx, user, slot_str,
        )

    # User typed a date — try to parse it
    parsed_date = _parse_date_input(text_lower)
    if parsed_date:
        return _show_time_slots(
            conversation, social_account, provider, token, to, ctx, user, parsed_date,
        )

    _send_text(provider, token, to,
               "Please type a date (e.g. *tomorrow*, *Monday*, or *2026-05-25*).")
    return True


def _handle_booking_confirm(conversation, message, social_account, provider,
                            text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if is_interactive and reply_id == "confirm_booking":
        return _confirm_booking(
            conversation, social_account, provider, token, to, ctx, user,
        )

    if is_interactive and reply_id == "cancel_booking":
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "Booking cancelled. Let me know if you need anything else!")
        return True

    if text_lower in ("back", "cancel", "exit", "no"):
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "Booking cancelled. Let me know if you need anything else!")
        return True

    if text_lower in ("yes", "confirm"):
        return _confirm_booking(
            conversation, social_account, provider, token, to, ctx, user,
        )

    return False


def _handle_payment_pending(conversation, message, social_account, provider,
                            text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if text_lower in ("cancel", "exit"):
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "Payment cancelled. Let me know if you need anything else!")
        return True

    # User providing phone number for M-Pesa
    phone = _extract_phone(text_lower)
    if phone:
        return _trigger_stk_push(
            conversation, social_account, provider, token, to, ctx, user, phone,
        )

    _send_text(provider, token, to,
               "Please send your M-Pesa phone number (e.g. 0712345678) to complete payment.")
    return True


# ═════════════════════════════════════════════════════════════════════════════
# PRODUCT BROWSING
# ═════════════════════════════════════════════════════════════════════════════


def _show_categories(conversation, social_account, provider, token, to, ctx, user):
    from apps.commerce.products.models import Product, ProductCategory

    categories = ProductCategory.objects.filter(
        user=user, is_active=True,
    ).order_by("position", "name")

    # Also count uncategorized products
    uncategorized_count = Product.objects.promotable(user).filter(category__isnull=True).count()

    if not categories.exists() and uncategorized_count == 0:
        _send_text(provider, token, to,
                   "We don't have any products listed right now. Please check back later!")
        _reset_state(conversation, ctx)
        return True

    rows = []
    for cat in categories[:9]:
        product_count = Product.objects.promotable(user).filter(category=cat).count()
        if product_count == 0:
            continue
        rows.append({
            "id": f"cat_{cat.pk}",
            "title": cat.name[:24],
            "description": f"{product_count} item{'s' if product_count != 1 else ''}",
        })

    if uncategorized_count > 0 and len(rows) < 10:
        rows.append({
            "id": "cat_uncategorized",
            "title": "Other Products",
            "description": f"{uncategorized_count} item{'s' if uncategorized_count != 1 else ''}",
        })

    if not rows:
        _send_text(provider, token, to,
                   "We don't have any products available right now. Please check back later!")
        _reset_state(conversation, ctx)
        return True

    sections = [{"title": "Categories", "rows": rows}]
    provider.send_interactive_list(
        access_token=token, to=to,
        body="Welcome! Browse our catalog below 👇",
        button_text="View Categories",
        sections=sections,
        header="Our Products",
        footer="Reply 'exit' to go back",
    )

    _set_state(conversation, ctx, "browsing")
    _log_action(user, "commerce_browse_categories", "Customer browsing product categories")
    return True


def _show_category_products(conversation, social_account, provider, token, to,
                            ctx, user, category_id):
    from apps.commerce.products.models import Product, ProductCategory

    if category_id == "uncategorized":
        products = Product.objects.promotable(user).filter(category__isnull=True)[:10]
        cat_name = "Other Products"
    else:
        try:
            category = ProductCategory.objects.get(pk=category_id, user=user)
            cat_name = category.name
        except ProductCategory.DoesNotExist:
            _send_text(provider, token, to, "Category not found. Let me show you our catalog.")
            return _show_categories(conversation, social_account, provider, token, to, ctx, user)
        products = Product.objects.promotable(user).filter(category=category)[:10]

    if not products:
        _send_text(provider, token, to, f"No products available in {cat_name} right now.")
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    rows = []
    for p in products:
        rows.append({
            "id": f"prod_{p.pk}",
            "title": p.name[:24],
            "description": p.display_price or "Price on request",
        })

    sections = [{"title": cat_name[:24], "rows": rows}]
    provider.send_interactive_list(
        access_token=token, to=to,
        body=f"Here are our products in *{cat_name}*:",
        button_text="View Products",
        sections=sections,
        footer="Reply 'back' to see categories",
    )
    return True


def _show_product_detail(conversation, social_account, provider, token, to,
                         ctx, user, product_id):
    from apps.commerce.products.models import Product

    try:
        product = Product.objects.get(pk=product_id, user=user, is_active=True)
    except Product.DoesNotExist:
        _send_text(provider, token, to, "Product not found. Let me show you our catalog.")
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    # Send product image if available
    image_url = None
    if product.image:
        try:
            image_url = product.image.url
            if image_url and not image_url.startswith("http"):
                from django.conf import settings as django_settings
                base = getattr(django_settings, "SITE_URL", "").rstrip("/")
                if base:
                    image_url = f"{base}{image_url}"
        except Exception:
            image_url = None

    # Build product description
    lines = [f"*{product.name}*"]
    if product.description:
        desc = product.description[:300]
        lines.append(desc)
    if product.display_price:
        lines.append(f"\n💰 *Price:* {product.display_price}")
    stock_labels = {
        "in_stock": "✅ In Stock",
        "low_stock": "⚠️ Limited Stock",
        "made_to_order": "🔨 Made to Order",
        "unlimited": "✅ Available",
        "out_of_stock": "❌ Out of Stock",
    }
    lines.append(f"📦 {stock_labels.get(product.stock_status, product.stock_status)}")
    if (
        product.stock_status == "low_stock"
        and product.quantity is not None
        and product.quantity > 0
    ):
        lines.append(f"🔥 Only {product.quantity} left — order soon!")

    body = "\n".join(lines)

    if image_url:
        provider.send_image_message(
            access_token=token, to=to,
            image_url=image_url, caption=body,
        )
    else:
        _send_text(provider, token, to, body)

    # Send action buttons — no Buy Now on out-of-stock items
    buttons = []
    if product.stock_status != "out_of_stock":
        buttons.append({"id": "buy_now", "title": "Buy Now 💳"})
        buttons.append({"id": "add_cart", "title": "Add to Cart 🛒"})
    buttons.append({"id": "ask_question", "title": "Ask a Question"})
    buttons.append({"id": "browse_more", "title": "Browse More"})

    provider.send_interactive_buttons(
        access_token=token, to=to,
        body="What would you like to do?",
        buttons=buttons[:3],
    )
    if len(buttons) > 3:
        provider.send_interactive_buttons(
            access_token=token, to=to,
            body="More options:",
            buttons=buttons[3:6][:3],
        )

    ctx["current_product_id"] = str(product.pk)
    _set_state(conversation, ctx, "product_detail")
    _log_action(user, "commerce_view_product", f"Customer viewing product: {product.name}",
                input_data={"product_id": str(product.pk), "product_name": product.name})
    return True


# ═════════════════════════════════════════════════════════════════════════════
# BOOKING FLOW
# ═════════════════════════════════════════════════════════════════════════════


def _show_booking_services(conversation, social_account, provider, token, to, ctx, user):
    from apps.commerce.bookings.models import BookingLink

    booking_link = BookingLink.objects.filter(user=user, is_active=True).first()
    if not booking_link:
        _send_text(provider, token, to,
                   "We don't have online booking set up yet. Please contact us directly!")
        _reset_state(conversation, ctx)
        return True

    services = booking_link.services or []
    if not services:
        _send_text(provider, token, to,
                   "No booking services available right now. Please check back later!")
        _reset_state(conversation, ctx)
        return True

    rows = []
    for i, svc in enumerate(services[:10]):
        name = svc.get("name", f"Service {i + 1}")
        duration = svc.get("duration_minutes", 0)
        price = svc.get("price_kes", 0)
        desc_parts = []
        if duration:
            desc_parts.append(f"{duration} min")
        if price:
            desc_parts.append(f"KES {price:,.0f}")
        rows.append({
            "id": f"svc_{i}",
            "title": name[:24],
            "description": " · ".join(desc_parts) if desc_parts else "Contact for pricing",
        })

    sections = [{"title": "Our Services", "rows": rows}]
    provider.send_interactive_list(
        access_token=token, to=to,
        body="Choose a service to book 📅",
        button_text="View Services",
        sections=sections,
        header="Book an Appointment",
        footer="Reply 'exit' to cancel",
    )

    ctx["booking_link_id"] = str(booking_link.pk)
    _set_state(conversation, ctx, "booking_select")
    _log_action(user, "commerce_view_services", "Customer browsing booking services")
    return True


def _select_booking_service(conversation, social_account, provider, token, to,
                            ctx, user, service_index_str):
    from apps.commerce.bookings.models import BookingLink

    booking_link_id = ctx.get("booking_link_id")
    if not booking_link_id:
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    try:
        booking_link = BookingLink.objects.get(pk=booking_link_id, user=user)
    except BookingLink.DoesNotExist:
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    try:
        idx = int(service_index_str)
        service = booking_link.services[idx]
    except (ValueError, IndexError):
        _send_text(provider, token, to, "Service not found. Please select from the list.")
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    ctx["selected_service"] = service
    ctx["selected_service_index"] = idx
    _set_state(conversation, ctx, "booking_time")

    name = service.get("name", "Service")
    duration = service.get("duration_minutes", 0)
    price = service.get("price_kes", 0)

    lines = [
        f"Great choice! You selected *{name}*.",
    ]
    if duration:
        lines.append(f"⏱ Duration: {duration} minutes")
    if price:
        lines.append(f"💰 Price: KES {price:,.0f}")
    lines.append("\nWhen would you like to come in?")
    lines.append("Please type a date (e.g. *tomorrow*, *Monday*, or *2026-05-25*).")

    _send_text(provider, token, to, "\n".join(lines))
    return True


def _show_time_slots(conversation, social_account, provider, token, to,
                     ctx, user, target_date):
    from apps.commerce.bookings.models import Booking, BookingLink

    booking_link_id = ctx.get("booking_link_id")
    if not booking_link_id:
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    try:
        booking_link = BookingLink.objects.get(pk=booking_link_id, user=user)
    except BookingLink.DoesNotExist:
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    service = ctx.get("selected_service", {})
    duration = service.get("duration_minutes", 60)

    # Get working hours for the target day
    day_name = target_date.strftime("%a").lower()[:3]
    working_hours = booking_link.working_hours or booking_link.default_working_hours()
    day_hours = working_hours.get(day_name, [])

    if not day_hours:
        _send_text(provider, token, to,
                   f"Sorry, we're closed on {target_date.strftime('%A, %b %d')}. "
                   "Please pick another date.")
        return True

    # Generate time slots
    existing_bookings = Booking.objects.filter(
        booking_link=booking_link,
        scheduled_at__date=target_date,
        status__in=["pending", "confirmed"],
    ).values_list("scheduled_at", flat=True)
    booked_times = {b.astimezone(NAIROBI_TZ).strftime("%H:%M") for b in existing_bookings}

    now = timezone.now().astimezone(NAIROBI_TZ)
    slots = []
    for window in day_hours:
        start_h, start_m = map(int, window["start"].split(":"))
        end_h, end_m = map(int, window["end"].split(":"))
        current = datetime(
            target_date.year, target_date.month, target_date.day,
            start_h, start_m, tzinfo=NAIROBI_TZ,
        )
        end_time = datetime(
            target_date.year, target_date.month, target_date.day,
            end_h, end_m, tzinfo=NAIROBI_TZ,
        )
        while current + timedelta(minutes=duration) <= end_time:
            time_str = current.strftime("%H:%M")
            if time_str not in booked_times and current > now:
                slots.append(time_str)
            current += timedelta(minutes=30)

    if not slots:
        _send_text(provider, token, to,
                   f"No available slots on {target_date.strftime('%A, %b %d')}. "
                   "Please try another date.")
        return True

    # Show up to 3 slots as buttons (WhatsApp max)
    display_slots = slots[:3]
    date_str = target_date.isoformat()

    buttons = [
        {"id": f"slot_{date_str}T{s}", "title": s}
        for s in display_slots
    ]

    ctx["booking_date"] = date_str
    _save_commerce_ctx(conversation, ctx)

    body = f"Available slots on *{target_date.strftime('%A, %b %d')}*:"
    if len(slots) > 3:
        body += f"\n(Showing first 3 of {len(slots)} slots)"

    provider.send_interactive_buttons(
        access_token=token, to=to,
        body=body,
        buttons=buttons,
        footer="Reply 'back' to change date",
    )
    return True


def _select_time_slot(conversation, social_account, provider, token, to,
                      ctx, user, slot_str):
    """slot_str is like '2026-05-25T10:00'"""
    try:
        dt = datetime.fromisoformat(slot_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=NAIROBI_TZ)
    except ValueError:
        _send_text(provider, token, to, "Invalid time slot. Please try again.")
        return True

    service = ctx.get("selected_service", {})
    name = service.get("name", "Service")
    duration = service.get("duration_minutes", 0)
    price = service.get("price_kes", 0)

    ctx["booking_datetime"] = dt.isoformat()
    _set_state(conversation, ctx, "booking_confirm")

    lines = [
        "📋 *Booking Summary*",
        f"Service: {name}",
        f"Date: {dt.strftime('%A, %b %d, %Y')}",
        f"Time: {dt.strftime('%I:%M %p')}",
    ]
    if duration:
        lines.append(f"Duration: {duration} min")
    if price:
        lines.append(f"Price: KES {price:,.0f}")
    lines.append(f"\nCustomer: {conversation.contact_name or conversation.contact_wa_id}")

    _send_text(provider, token, to, "\n".join(lines))

    provider.send_interactive_buttons(
        access_token=token, to=to,
        body="Confirm your booking?",
        buttons=[
            {"id": "confirm_booking", "title": "✅ Confirm"},
            {"id": "cancel_booking", "title": "❌ Cancel"},
        ],
    )
    return True


def _confirm_booking(conversation, social_account, provider, token, to, ctx, user):
    from apps.commerce.bookings.models import Booking, BookingLink

    booking_link_id = ctx.get("booking_link_id")
    service = ctx.get("selected_service", {})
    datetime_str = ctx.get("booking_datetime")

    if not booking_link_id or not datetime_str:
        _send_text(provider, token, to, "Something went wrong. Let's start over.")
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    try:
        booking_link = BookingLink.objects.get(pk=booking_link_id)
    except BookingLink.DoesNotExist:
        _send_text(provider, token, to, "Booking service not found. Please try again.")
        _reset_state(conversation, ctx)
        return True

    try:
        scheduled_dt = datetime.fromisoformat(datetime_str)
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=NAIROBI_TZ)
    except ValueError:
        _send_text(provider, token, to, "Invalid booking time. Let's try again.")
        return _show_booking_services(conversation, social_account, provider, token, to, ctx, user)

    name = service.get("name", "Service")
    duration = service.get("duration_minutes", 60)
    price = Decimal(str(service.get("price_kes", 0)))

    booking = Booking.objects.create(
        booking_link=booking_link,
        customer_name=conversation.contact_name or conversation.contact_wa_id,
        customer_phone=conversation.contact_phone or conversation.contact_wa_id,
        service_name=name,
        duration_minutes=duration,
        price_kes=price,
        scheduled_at=scheduled_dt,
        status=Booking.Status.CONFIRMED,
        source_channel="engage_agent",
        notes=f"Booked via WhatsApp commerce bot. Conversation: {conversation.pk}",
    )

    lines = [
        "✅ *Booking Confirmed!*",
        f"Service: {name}",
        f"Date: {scheduled_dt.strftime('%A, %b %d, %Y')}",
        f"Time: {scheduled_dt.strftime('%I:%M %p')}",
        f"Ref: {str(booking.pk)[:8].upper()}",
    ]

    if price > 0:
        lines.append(f"\nTotal: KES {price:,.0f}")
        lines.append("Would you like to pay now via M-Pesa?")

    _send_text(provider, token, to, "\n".join(lines))

    _log_action(user, "commerce_booking_confirmed", f"Booking confirmed: {name}",
                input_data={
                    "booking_id": str(booking.pk),
                    "service": name,
                    "scheduled_at": scheduled_dt.isoformat(),
                })

    try:
        from apps.commerce.leads.bridges import create_lead_from_booking

        create_lead_from_booking(booking)
    except Exception as exc:
        logger.warning("Lead bridge from WA booking failed: %s", exc)

    if price > 0:
        ctx["payment_amount"] = str(price)
        ctx["payment_description"] = f"Booking: {name}"
        ctx["booking_id"] = str(booking.pk)
        _set_state(conversation, ctx, "payment_pending")

        provider.send_interactive_buttons(
            access_token=token, to=to,
            body=f"Pay KES {price:,.0f} via M-Pesa?",
            buttons=[
                {"id": "pay_mpesa", "title": "Pay Now 💳"},
                {"id": "pay_later", "title": "Pay Later"},
            ],
        )
    else:
        _reset_state(conversation, ctx)

    return True


# ═════════════════════════════════════════════════════════════════════════════
# PAYMENT FLOW (M-Pesa)
# ═════════════════════════════════════════════════════════════════════════════


def _initiate_product_payment(conversation, social_account, provider, token, to,
                              ctx, user, product_id):
    from apps.commerce.products.models import Product

    try:
        product = Product.objects.get(pk=product_id, user=user, is_active=True)
    except Product.DoesNotExist:
        _send_text(provider, token, to, "Product not found. Let me show you our catalog.")
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    if product.stock_status == "out_of_stock":
        _send_text(provider, token, to,
                   f"Sorry, *{product.name}* is currently out of stock. "
                   "We'll let you know when it's back!")
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    price = product.price
    if not price:
        _send_text(provider, token, to,
                   f"Please contact us for pricing on *{product.name}*. "
                   "A team member will get back to you shortly!")
        _set_state(conversation, ctx, "idle")
        return False  # Fall through to AI for pricing questions

    ctx["payment_amount"] = str(price)
    ctx["payment_description"] = f"Product: {product.name}"
    ctx["payment_product_id"] = str(product.pk)
    _set_state(conversation, ctx, "payment_pending")

    # Check if we already know the customer's phone
    phone = conversation.contact_phone or conversation.contact_wa_id
    if phone and _is_valid_mpesa_phone(phone):
        _send_text(provider, token, to,
                   f"💳 *Payment for {product.name}*\n"
                   f"Amount: KES {price:,.0f}\n\n"
                   f"We'll send an M-Pesa prompt to *{phone}*.\n"
                   "Enter your M-Pesa PIN on your phone to complete payment.")
        return _trigger_stk_push(
            conversation, social_account, provider, token, to, ctx, user, phone,
        )

    _send_text(provider, token, to,
               f"💳 *Payment for {product.name}*\n"
               f"Amount: KES {price:,.0f}\n\n"
               "Please send your M-Pesa phone number (e.g. *0712345678*) to pay.")
    return True


def _trigger_stk_push(conversation, social_account, provider, token, to,
                      ctx, user, phone):
    from apps.core.billing.mpesa import format_phone_number, initiate_stk_push

    amount = ctx.get("payment_amount")
    description = ctx.get("payment_description", "Kova Purchase")

    if not amount:
        _send_text(provider, token, to, "Payment error. Please try again.")
        _reset_state(conversation, ctx)
        return True

    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        _send_text(provider, token, to,
                   "Invalid phone number. Please use format: *07XXXXXXXX* or *254XXXXXXXXX*")
        return True

    try:
        result = initiate_stk_push(
            phone_number=formatted_phone,
            amount=int(Decimal(amount)),
            account_reference=f"Kova-{str(conversation.pk)[:6]}",
            transaction_desc=description[:13],
        )

        checkout_id = result.get("CheckoutRequestID", "")
        ctx["mpesa_checkout_id"] = checkout_id
        _save_commerce_ctx(conversation, ctx)

        _send_text(provider, token, to,
                   "📱 *M-Pesa payment request sent!*\n\n"
                   "Check your phone and enter your M-Pesa PIN to complete payment.\n"
                   "You'll receive a confirmation once payment is processed.")

        _log_action(user, "commerce_stk_push_sent", f"STK Push initiated: KES {amount}",
                    input_data={
                        "amount": amount,
                        "phone": formatted_phone,
                        "checkout_id": checkout_id,
                        "description": description,
                    })

        _reset_state(conversation, ctx)
        return True

    except (ConnectionError, ValueError) as e:
        logger.error("STK Push failed for conversation %s: %s", conversation.pk, e)
        _send_text(provider, token, to,
                   "😔 M-Pesa is temporarily unavailable. Please try again in a moment, "
                   "or contact us directly.")
        _reset_state(conversation, ctx)
        return True


# ═════════════════════════════════════════════════════════════════════════════
# CART (multi-item checkout)
# ═════════════════════════════════════════════════════════════════════════════


def _cart_items(ctx) -> list[dict]:
    items = ctx.get("cart_items")
    return list(items) if isinstance(items, list) else []


def _save_cart(ctx, items: list[dict]) -> None:
    ctx["cart_items"] = items


def _add_to_cart(conversation, social_account, provider, token, to, ctx, user, product_id):
    from apps.commerce.products.models import Product

    try:
        product = Product.objects.get(pk=product_id, user=user, is_active=True)
    except Product.DoesNotExist:
        _send_text(provider, token, to, "Product not found.")
        return True

    if product.stock_status == "out_of_stock" or not product.price:
        _send_text(provider, token, to, f"*{product.name}* isn't available to add right now.")
        return True

    items = _cart_items(ctx)
    for row in items:
        if row.get("product_id") == str(product.pk):
            row["qty"] = int(row.get("qty") or 1) + 1
            break
    else:
        items.append({
            "product_id": str(product.pk),
            "name": product.name[:80],
            "price": str(product.price),
            "qty": 1,
        })
    _save_cart(ctx, items)
    _set_state(conversation, ctx, "cart_review")
    _send_text(
        provider, token, to,
        f"Added *{product.name}* to cart ({len(items)} item type{'s' if len(items) != 1 else ''}).\n"
        "Reply *checkout* to pay · *cart* to review.",
    )
    return True


def _show_cart(conversation, social_account, provider, token, to, ctx, user):
    items = _cart_items(ctx)
    if not items:
        _send_text(provider, token, to, "Your cart is empty. Reply *shop* to browse products.")
        _set_state(conversation, ctx, "idle")
        return True

    lines = ["🛒 *Your cart*"]
    total = Decimal("0")
    for row in items:
        qty = int(row.get("qty") or 1)
        price = Decimal(row.get("price") or "0")
        sub = price * qty
        total += sub
        lines.append(f"• {row.get('name', 'Item')} ×{qty} — KES {sub:,.0f}")

    lines.append(f"\n*Total: KES {total:,.0f}*")
    _send_text(provider, token, to, "\n".join(lines))

    provider.send_interactive_buttons(
        access_token=token, to=to,
        body="Ready to checkout?",
        buttons=[
            {"id": "checkout_cart", "title": "Checkout 💳"},
            {"id": "browse_more", "title": "Add More"},
            {"id": "clear_cart", "title": "Clear Cart"},
        ],
    )
    _set_state(conversation, ctx, "cart_review")
    return True


def _handle_cart_review(conversation, message, social_account, provider,
                        text_lower, is_interactive, reply_id, ctx, user):
    token = social_account.access_token
    to = conversation.contact_wa_id

    if is_interactive and reply_id == "clear_cart":
        _save_cart(ctx, [])
        _reset_state(conversation, ctx)
        _send_text(provider, token, to, "Cart cleared.")
        return True

    if is_interactive and reply_id == "browse_more":
        return _show_categories(conversation, social_account, provider, token, to, ctx, user)

    if is_interactive and reply_id == "checkout_cart" or text_lower in {"checkout", "pay"}:
        items = _cart_items(ctx)
        if not items:
            return _show_cart(conversation, social_account, provider, token, to, ctx, user)
        total = Decimal("0")
        names = []
        for row in items:
            qty = int(row.get("qty") or 1)
            price = Decimal(row.get("price") or "0")
            total += price * qty
            names.append(f"{row.get('name', 'Item')} ×{qty}")
        ctx["payment_amount"] = str(total)
        ctx["payment_description"] = "Cart: " + ", ".join(names)[:200]
        ctx["payment_cart"] = items
        _set_state(conversation, ctx, "payment_pending")
        _send_text(
            provider, token, to,
            f"💳 *Checkout*\nTotal: KES {total:,.0f}\n\nSend your M-Pesa number to pay.",
        )
        return True

    if _matches_any(text_lower, CART_TRIGGERS):
        return _show_cart(conversation, social_account, provider, token, to, ctx, user)

    return False


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════


def _get_commerce_ctx(conversation):
    context = conversation.context or {}
    return context.get("commerce", {})


def _save_commerce_ctx(conversation, ctx):
    context = conversation.context or {}
    context["commerce"] = ctx
    conversation.context = context
    conversation.save(update_fields=["context", "updated_at"])


def _set_state(conversation, ctx, state):
    ctx["state"] = state
    _save_commerce_ctx(conversation, ctx)


def _reset_state(conversation, ctx):
    kept_keys = {}
    if ctx.get("mpesa_checkout_id"):
        kept_keys["mpesa_checkout_id"] = ctx["mpesa_checkout_id"]
    ctx.clear()
    ctx["state"] = "idle"
    ctx.update(kept_keys)
    _save_commerce_ctx(conversation, ctx)


def _send_text(provider, token, to, body):
    result = provider.send_text_message(access_token=token, to=to, body=body)
    if not result.get("success"):
        logger.warning("Commerce bot send failed: %s", result.get("error"))
    return result


def _matches_any(text, triggers):
    for trigger in triggers:
        if trigger in text:
            return True
    return False


def _ensure_lead(user, conversation):
    from apps.commerce.leads.models import Lead, LeadActivity

    wa_id = conversation.contact_wa_id
    lead, created = Lead.objects.get_or_create(
        user=user,
        email=f"wa_{wa_id}@kova.page",
        defaults={
            "name": conversation.contact_name or "",
            "phone": wa_id,
            "source_type": Lead.Source.SOCIAL_DM,
            "source_platform": "whatsapp",
            "metadata": {
                "wa_id": wa_id,
                "conversation_id": str(conversation.pk),
            },
        },
    )
    if not created:
        # Update temperature — commerce intent signals warmth
        if lead.temperature == Lead.Temperature.COLD:
            lead.temperature = Lead.Temperature.WARM
            lead.save(update_fields=["temperature", "last_activity_at"])

    return lead


def _log_action(user, action_type, description, input_data=None):
    try:
        from apps.create.agents.models import AgentAction
        AgentAction.objects.create(
            user=user,
            agent_type="engage",
            action_type=action_type,
            description=description,
            status=AgentAction.ActionStatus.COMPLETED,
            input_data=input_data or {},
        )
    except Exception as e:
        logger.warning("Failed to log commerce action: %s", e)


def _parse_date_input(text):
    """Parse natural date input from the user."""
    now = timezone.now().astimezone(NAIROBI_TZ)
    today = now.date()

    text = text.strip().lower()

    if text in ("today", "leo"):
        return today
    if text in ("tomorrow", "kesho"):
        return today + timedelta(days=1)

    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
        "jumatatu": 0, "jumanne": 1, "jumatano": 2, "alhamisi": 3,
        "ijumaa": 4, "jumamosi": 5, "jumapili": 6,
    }
    if text in day_map:
        target_weekday = day_map[text]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    # Try ISO format (YYYY-MM-DD)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def _extract_phone(text):
    """Extract a Kenyan phone number from text."""
    import re
    text = text.replace(" ", "").replace("-", "")
    match = re.search(r"(?:254|\+254|0)(7\d{8}|1\d{8})", text)
    if match:
        return "254" + match.group(1)
    if re.match(r"^2547\d{8}$", text) or re.match(r"^2541\d{8}$", text):
        return text
    return None


def _is_valid_mpesa_phone(phone):
    """Check if a phone string looks like a valid Kenyan M-Pesa number."""
    import re
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    return bool(re.match(r"^254[71]\d{8}$", clean))
