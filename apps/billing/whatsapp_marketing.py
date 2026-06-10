"""WhatsApp marketing conversation caps — Plan v2.

Counts outbound *marketing* template sends per calendar month. Utility templates
(e.g. booking confirmations) and authentication templates do NOT count toward the cap.
"""

from __future__ import annotations

from django.utils import timezone

from apps.billing.models import get_user_plan_limits

# Template categories that bill as marketing conversations on Meta.
MARKETING_TEMPLATE_CATEGORIES = frozenset({"marketing"})


def _month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def count_marketing_conversations_this_month(user) -> int:
    """Distinct conversations contacted via marketing templates this month."""
    from apps.whatsapp.models import WhatsAppMessage

    return (
        WhatsAppMessage.objects.filter(
            conversation__social_account__user=user,
            direction=WhatsAppMessage.Direction.OUTBOUND,
            message_type=WhatsAppMessage.MessageType.TEMPLATE,
            template__category__in=MARKETING_TEMPLATE_CATEGORIES,
            created_at__gte=_month_start(),
            status__in=[
                WhatsAppMessage.MessageStatus.SENT,
                WhatsAppMessage.MessageStatus.DELIVERED,
                WhatsAppMessage.MessageStatus.READ,
            ],
        )
        .values("conversation_id")
        .distinct()
        .count()
    )


def get_whatsapp_marketing_usage(user) -> dict:
    limits = get_user_plan_limits(user)
    max_convos = int(limits.get("whatsapp_marketing_conversations_per_month", 0))
    used = count_marketing_conversations_this_month(user)
    at_limit = max_convos <= 0 or used >= max_convos
    return {
        "used": used,
        "max": max_convos,
        "remaining": max(0, max_convos - used) if max_convos > 0 else 0,
        "at_limit": at_limit,
        "plan_label": limits.get("label", "Starter"),
    }


def is_marketing_template(template) -> bool:
    if template is None:
        return True
    category = (getattr(template, "category", "") or "marketing").lower()
    return category in MARKETING_TEMPLATE_CATEGORIES


def check_whatsapp_marketing_limit(
    user,
    *,
    additional_conversations: int = 1,
    template=None,
) -> tuple[bool, str]:
    """Return (allowed, message). Skips check for non-marketing utility/auth templates."""
    if not is_marketing_template(template):
        return True, ""

    usage = get_whatsapp_marketing_usage(user)
    max_convos = usage["max"]
    if max_convos <= 0:
        return False, (
            f"WhatsApp marketing is not included on your {usage['plan_label']} plan. "
            "Upgrade to Kazi or Biashara for marketing broadcasts."
        )

    projected = usage["used"] + max(0, additional_conversations)
    if projected > max_convos:
        return False, (
            f"You've reached your WhatsApp marketing limit "
            f"({max_convos} conversations/month on {usage['plan_label']}). "
            "Upgrade for more marketing sends."
        )
    return True, ""
