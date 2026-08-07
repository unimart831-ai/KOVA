"""Business Memory — what Kova remembers about a customer across chats.

A returning customer should never feel like a stranger. This module recalls a
per-contact memory (interests, notes) so the WhatsApp AI Salesperson can greet
them with context — "last time you were looking for a Dell laptop" — and updates
that memory after each interaction. All functions are defensive: memory is a
nice-to-have, never a reason to drop a reply.
"""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_INTERESTS = 8


def recall_customer_memory(user, phone: str):
    """Return the CustomerMemory for this contact, or None."""
    if not phone:
        return None
    try:
        from apps.messaging.whatsapp.models import CustomerMemory

        return CustomerMemory.objects.filter(user=user, contact_phone=phone).first()
    except Exception:
        return None


def remember_customer_interaction(user, phone: str, *, name: str = "", message_text: str = ""):
    """Upsert memory for a contact from an inbound message. Returns the memory."""
    if not phone:
        return None
    try:
        from django.db import transaction

        from apps.messaging.whatsapp.models import CustomerMemory
    except Exception:
        return None

    interests = _detect_interests(user, message_text)
    try:
        with transaction.atomic():
            mem, _ = CustomerMemory.objects.get_or_create(
                user=user, contact_phone=phone, defaults={"contact_name": name or ""}
            )
            if name and not mem.contact_name:
                mem.contact_name = name
            if interests:
                existing = list(mem.interests or [])
                for item in interests:
                    if item in existing:
                        existing.remove(item)
                    existing.insert(0, item)
                mem.interests = existing[:MAX_INTERESTS]
            mem.interaction_count = (mem.interaction_count or 0) + 1
            mem.last_seen_at = timezone.now()
            mem.summary = _build_summary(mem)
            mem.save()
        return mem
    except Exception as exc:
        logger.warning("Customer memory update failed for %s: %s", phone, exc)
        return None


def memory_context_block(memory) -> str:
    """A prompt block reminding the assistant what it knows about a returning
    customer. Empty for first-time contacts so we don't fabricate familiarity."""
    if not memory or (memory.interaction_count or 0) <= 1:
        return ""
    bits = []
    if memory.interests:
        bits.append("previously interested in: " + ", ".join(memory.interests[:5]))
    if (memory.notes or "").strip():
        bits.append(memory.notes.strip()[:200])
    if not bits:
        return ""
    who = memory.contact_name or "This customer"
    return (
        "## RETURNING CUSTOMER MEMORY\n"
        f"{who} has chatted before ({memory.interaction_count} times). "
        + "; ".join(bits)
        + ".\nGreet them with this context naturally, like a salesperson who remembers them. "
        "Do not invent details beyond this memory and the catalog."
    )


def _detect_interests(user, message_text: str) -> list[str]:
    """Match product names mentioned in the message. Substring match keeps this
    conservative — we'd rather miss than misremember."""
    text = (message_text or "").lower()
    if not text:
        return []
    try:
        from apps.commerce.products.models import Product

        names = Product.objects.filter(user=user, is_active=True).values_list("name", flat=True)[:100]
    except Exception:
        return []
    hits = []
    for name in names:
        clean = (name or "").strip()
        if clean and clean.lower() in text:
            hits.append(clean)
    return hits


def _build_summary(mem) -> str:
    if mem.interests:
        return ("Interested in " + ", ".join(mem.interests[:3]))[:280]
    return mem.summary or ""
