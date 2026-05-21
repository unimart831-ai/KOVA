"""
WhatsApp Celery Tasks — AI Auto-Reply Engine.

This is the brain of WhatsApp Intelligence. When a customer messages,
the webhook saves the message and fires handle_incoming_message() which:

1. Detects the customer's language (English, Swahili, Sheng)
2. Loads conversation history for context
3. Loads the brand's voice, offerings, and restrictions
4. Generates an AI reply using the Engage Agent's LLM
5. Routes based on confidence:
   - High (>0.8): Send automatically
   - Medium (0.5-0.8): Save draft, flag for review
   - Low (<0.5): Escalate to human, don't auto-reply
6. Sends the reply via the WhatsApp Cloud API
"""

import json
import logging

from celery import shared_task
from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json

logger = logging.getLogger(__name__)


# ─── Confidence thresholds ───────────────────────────────────────────────────
HIGH_CONFIDENCE = 0.8   # Auto-send immediately
MEDIUM_CONFIDENCE = 0.5  # Draft + flag for human review
# Below MEDIUM_CONFIDENCE = escalate to human


@shared_task(name="whatsapp.handle_incoming_message", bind=True, max_retries=2)
def handle_incoming_message(self, message_id: str):
    """
    Process an incoming WhatsApp message and generate an AI reply.

    Called async by the webhook after saving the inbound message.
    This is the core AI auto-reply pipeline.
    """
    from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage
    from apps.platforms.providers.registry import get_provider

    try:
        message = WhatsAppMessage.objects.select_related(
            "conversation", "conversation__social_account",
            "conversation__social_account__user",
        ).get(id=message_id)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("WhatsApp message %s not found", message_id)
        return

    conversation = message.conversation
    social_account = conversation.social_account
    user = social_account.user

    # Commerce bot — handle product browsing, bookings, payments before AI
    try:
        from apps.whatsapp.commerce import handle_commerce_message
        if handle_commerce_message(conversation, message, social_account):
            return
    except Exception as e:
        logger.warning("Commerce bot error (falling through to AI): %s", e)

    # Skip if AI handling is disabled for this conversation
    if not conversation.ai_handling:
        logger.info("AI handling disabled for conversation %s", conversation.id)
        return

    # Skip reactions and status messages — no reply needed
    if message.message_type in ("reaction",):
        return

    # Load brand context
    profile = getattr(user, "profile", None)
    if not profile:
        logger.warning("No profile for user %s — skipping AI reply", user.email)
        return

    # Get conversation history (last 20 messages for context)
    recent_messages = WhatsAppMessage.objects.filter(
        conversation=conversation,
    ).order_by("-created_at")[:20]
    recent_messages = list(reversed(recent_messages))

    # Detect language from the incoming message
    detected_language = _detect_language(message.content)
    if conversation.language == WhatsAppConversation.Language.UNKNOWN and detected_language:
        conversation.language = detected_language
        conversation.save(update_fields=["language", "updated_at"])

    # Build the AI prompt
    system_prompt = _build_system_prompt(profile, conversation)
    user_prompt = _build_conversation_prompt(recent_messages, message, conversation)

    # Generate AI reply
    model = get_model_for_task("engage")
    response = generate(
        prompt=user_prompt,
        system=system_prompt,
        model=model,
        temperature=0.7,
        max_tokens=1024,
        json_mode=True,
    )

    if not response.content:
        logger.warning("Empty LLM response for WhatsApp message %s", message_id)
        return

    # Parse the AI response
    parsed = parse_llm_json(response.content)
    if not parsed:
        logger.warning("Failed to parse LLM JSON for WhatsApp message %s", message_id)
        return

    reply_text = parsed.get("reply", "").strip()
    confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.5))))
    reasoning = parsed.get("reasoning", "")
    suggested_action = parsed.get("action", "reply")  # reply | escalate | no_reply

    if not reply_text or suggested_action == "no_reply":
        logger.info("AI chose not to reply to message %s (action=%s)", message_id, suggested_action)
        return

    # Route based on confidence
    if suggested_action == "escalate" or confidence < MEDIUM_CONFIDENCE:
        # LOW confidence: escalate to human
        _escalate_conversation(conversation, message, reply_text, confidence, reasoning)
        return

    # Create the outbound message record
    outbound = WhatsAppMessage.objects.create(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        message_type=WhatsAppMessage.MessageType.TEXT,
        content=reply_text,
        is_ai_generated=True,
        confidence_score=confidence,
        status=WhatsAppMessage.MessageStatus.PENDING,
    )

    if confidence >= HIGH_CONFIDENCE:
        # HIGH confidence: auto-send immediately
        provider = get_provider("whatsapp")
        if not provider:
            logger.error("WhatsApp provider not available")
            return

        result = provider.send_text_message(
            access_token=social_account.access_token,
            to=conversation.contact_wa_id,
            body=reply_text,
        )

        if result.get("success"):
            outbound.wamid = result.get("wamid", "")
            outbound.status = WhatsAppMessage.MessageStatus.SENT
            outbound.save(update_fields=["wamid", "status"])
            # Update conversation
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at", "updated_at"])
            logger.info(
                "WhatsApp AI auto-reply sent (confidence=%.2f) to %s",
                confidence, conversation.contact_wa_id,
            )
        else:
            outbound.status = WhatsAppMessage.MessageStatus.FAILED
            outbound.error_message = result.get("error", "Unknown error")
            outbound.save(update_fields=["status", "error_message"])
            logger.error("WhatsApp AI reply send failed: %s", result.get("error"))
    else:
        # MEDIUM confidence: save as draft for human review
        logger.info(
            "WhatsApp AI draft saved (confidence=%.2f) for review — conversation %s",
            confidence, conversation.id,
        )


def _escalate_conversation(conversation, trigger_message, draft_reply, confidence, reasoning):
    """Escalate a conversation to human handling."""
    conversation.ai_handling = False
    conversation.status = conversation.Status.ESCALATED
    context = conversation.context or {}
    context["escalation"] = {
        "reason": reasoning,
        "confidence": confidence,
        "trigger_message": trigger_message.content[:500],
        "draft_reply": draft_reply[:500],
        "escalated_at": timezone.now().isoformat(),
    }
    conversation.context = context
    conversation.save(update_fields=["ai_handling", "status", "context", "updated_at"])
    logger.info("Conversation %s escalated to human (confidence=%.2f)", conversation.id, confidence)

    # Create a notification for the user
    try:
        from apps.notifications.models import Notification
        Notification.objects.create(
            user=conversation.social_account.user,
            title="WhatsApp: Conversation needs attention",
            message=f"{conversation.contact_name or 'A customer'} needs a human reply. AI confidence was too low.",
            notification_type="whatsapp_escalation",
            link=f"/whatsapp/conversation/{conversation.id}/",
        )
    except Exception as e:
        logger.warning("Failed to create escalation notification: %s", e)


# ─── Language Detection ──────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """
    Simple language detection for Kenya's main WhatsApp languages.

    Uses keyword heuristics — not perfect, but fast and works for routing.
    The AI model handles actual language matching in its reply.
    """
    if not text:
        return ""

    text_lower = text.lower()

    # Common Sheng words/phrases (Nairobi urban slang — mix of Swahili + English + more)
    sheng_markers = [
        "sasa", "niaje", "poa", "maze", "manze", "aje", "buda", "dem",
        "mathree", "mbuzi", "cheki", "dishi", "fiti", "iko", "sawa sawa",
        "wasee", "nini", "rada", "chapaa", "doh", "gashui", "mharo",
    ]
    # Common Swahili words
    swahili_markers = [
        "habari", "jambo", "karibu", "asante", "tafadhali", "ndio", "hapana",
        "nzuri", "sana", "rafiki", "biashara", "bei", "duka", "wateja",
        "naomba", "ninaweza", "unataka", "tunafanya", "haraka", "pole",
        "shukrani", "hujambo", "salama",
    ]

    sheng_count = sum(1 for w in sheng_markers if w in text_lower)
    swahili_count = sum(1 for w in swahili_markers if w in text_lower)

    if sheng_count >= 2:
        return "sheng"
    if swahili_count >= 2:
        return "sw"
    if sheng_count == 1 or swahili_count == 1:
        # Mixed — check if mostly English
        words = text_lower.split()
        if len(words) > 3:
            return "en"  # Default to English for mixed messages
        return "sw" if swahili_count else "sheng"

    return "en"  # Default


# ─── Prompt Building ─────────────────────────────────────────────────────────

def _build_system_prompt(profile, conversation):
    """Build the system prompt with brand context and conversation rules."""
    brand_name = profile.company_name or profile.user.get_full_name() or "the business"
    language_instruction = _get_language_instruction(conversation.language)

    parts = [
        f"You are the AI customer engagement assistant for {brand_name} on WhatsApp.",
        f"You respond to customer messages in the brand's voice.",
        "",
        "## BRAND CONTEXT",
        f"Business: {brand_name}",
    ]
    if profile.industry:
        parts.append(f"Industry: {profile.get_industry_display()}")
    if profile.brand_voice:
        parts.append(f"Brand voice: {profile.brand_voice}")
    if profile.tone_attributes:
        parts.append(f"Tone: {', '.join(profile.tone_attributes)}")
    if profile.target_audience:
        parts.append(f"Target audience: {profile.target_audience}")
    if profile.key_offerings:
        offerings = profile.key_offerings
        if isinstance(offerings, list):
            offerings = ", ".join(offerings)
        parts.append(f"Products/Services: {offerings}")
    if profile.brand_restrictions:
        parts.append(f"\n## RESTRICTIONS\n{profile.brand_restrictions}")

    parts.extend([
        "",
        "## CONVERSATION RULES",
        language_instruction,
        "- Keep replies concise — WhatsApp is a chat, not an email. 1-3 short paragraphs max.",
        "- Use emojis naturally (not excessively) — they're expected on WhatsApp.",
        "- If asked about pricing, provide it if you know it. If unsure, say you'll confirm.",
        "- If the customer is angry or complaining, be empathetic first, solve second.",
        "- If you genuinely don't know the answer, say so honestly and offer to connect them with the team.",
        "- NEVER make up product details, prices, or availability that you don't know.",
        "- For orders/purchases, guide them but don't confirm transactions you can't fulfill.",
        "",
        "## RESPONSE FORMAT",
        "Respond in JSON with these fields:",
        '  "reply": "Your WhatsApp reply text"',
        '  "confidence": 0.0-1.0 (how confident are you this reply is correct and helpful?)',
        '  "reasoning": "Brief internal note on why you chose this reply"',
        '  "action": "reply" | "escalate" | "no_reply"',
        "",
        "Set action to 'escalate' if:",
        "- Customer is very angry/upset and needs human touch",
        "- Question requires access to systems you don't have (order status, account changes)",
        "- Customer explicitly asks for a human",
        "- Topic is sensitive (refunds, legal, personal data requests)",
        "",
        "Set action to 'no_reply' if:",
        "- Message is just a reaction emoji",
        "- Message is a 'thanks' or 'ok' that doesn't need a response",
    ])

    # Add conversation context if available
    context = conversation.context or {}
    if context.get("product_interests"):
        parts.append(f"\nCustomer's product interests: {context['product_interests']}")
    if conversation.tags:
        parts.append(f"Customer tags: {', '.join(conversation.tags)}")

    return "\n".join(parts)


def _build_conversation_prompt(recent_messages, current_message, conversation):
    """Build the user prompt with conversation history."""
    parts = ["## CONVERSATION HISTORY"]

    for msg in recent_messages[:-1]:  # All except the current message
        direction = "Customer" if msg.direction == "inbound" else "Business"
        ai_tag = " [AI]" if msg.is_ai_generated else ""
        parts.append(f"{direction}{ai_tag}: {msg.content[:500]}")

    parts.extend([
        "",
        "## NEW MESSAGE (respond to this)",
        f"Customer: {current_message.content}",
    ])

    if current_message.interactive_data:
        parts.append(f"[Interactive data: {json.dumps(current_message.interactive_data)[:200]}]")

    if current_message.message_type != "text":
        parts.append(f"[Message type: {current_message.get_message_type_display()}]")

    return "\n".join(parts)


def _get_language_instruction(language: str) -> str:
    """Get language-specific instructions for the AI."""
    instructions = {
        "en": "- Respond in English.",
        "sw": "- Respond in Swahili. Use proper Kiswahili — the customer prefers Swahili.",
        "sheng": "- Respond in Sheng (Nairobi urban slang — mix of Swahili, English, and street language). Keep it natural and relatable.",
        "unknown": "- Detect the customer's language from their message and respond in the SAME language. If mixed, match their style.",
    }
    return instructions.get(language, instructions["unknown"])


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5C — STATUS CONTENT STUDIO TASKS
# ═════════════════════════════════════════════════════════════════════════════

@shared_task(name="whatsapp.generate_status_content", bind=True, max_retries=2)
def generate_status_content(self, user_id: int, prompt: str, category: str):
    """
    AI-generate a Status content item optimized for WhatsApp Status.

    Creates short, punchy content with Kenyan tone, generates the
    share URL, and schedules it at an optimal time.
    """
    from apps.accounts.models import User
    from apps.whatsapp.models import StatusContent

    try:
        user = User.objects.select_related("profile").get(id=user_id)
    except User.DoesNotExist:
        logger.warning("User %s not found for status generation", user_id)
        return

    profile = getattr(user, "profile", None)
    brand_name = profile.company_name if profile else "the business"

    system = f"""You are a WhatsApp Status content creator for {brand_name}.
Generate content optimized for WhatsApp Status (similar to Instagram Stories).

RULES:
- Keep text SHORT — 200 characters max is ideal for Status.
- Be punchy, direct, and engaging. Think billboard copy.
- Use emojis naturally — they grab attention in Status feeds.
- Kenyan context and tone when relevant.
- Include a call-to-action (reply to this status, DM us, visit our link).
- Category: {category}
"""

    if profile:
        if profile.brand_voice:
            system += f"\nBrand voice: {profile.brand_voice}"
        if profile.key_offerings:
            offerings = profile.key_offerings
            if isinstance(offerings, list):
                offerings = ", ".join(offerings)
            system += f"\nProducts/Services: {offerings}"
        if profile.target_audience:
            system += f"\nTarget audience: {profile.target_audience}"

    system += """

RESPOND IN JSON:
{
  "text": "The main Status text (short, punchy)",
  "caption": "Optional extended caption for media posts",
  "reasoning": "Why this content works for Status format"
}"""

    response = generate(
        prompt=f"Create a WhatsApp Status post about: {prompt}",
        system=system,
        model=get_model_for_task("create"),
        temperature=0.8,
        json_mode=True,
    )

    parsed = parse_llm_json(response.content) if response.content else None
    if not parsed:
        logger.warning("Failed to parse status content for user %s", user_id)
        return

    # Schedule at next optimal Kenya time slot
    # Peak times: 6-8am commute, 12-1pm lunch, 6-9pm evening scroll
    now = timezone.now()
    hour = now.hour
    if hour < 6:
        scheduled = now.replace(hour=7, minute=0, second=0, microsecond=0)
    elif hour < 12:
        scheduled = now.replace(hour=12, minute=30, second=0, microsecond=0)
    elif hour < 18:
        scheduled = now.replace(hour=19, minute=0, second=0, microsecond=0)
    else:
        # Schedule for next morning
        from datetime import timedelta
        scheduled = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)

    status_obj = StatusContent.objects.create(
        user=user,
        text=parsed.get("text", "")[:700],
        caption=parsed.get("caption", ""),
        category=category,
        state=StatusContent.StatusState.READY,
        scheduled_for=scheduled,
        ai_generated=True,
        ai_reasoning=parsed.get("reasoning", ""),
        model_used=response.model or "",
        tokens_used=response.total_tokens or 0,
    )
    status_obj.generate_share_url()
    status_obj.save(update_fields=["share_url"])

    logger.info("Status content generated for user %s — scheduled for %s", user_id, scheduled)


@shared_task(name="whatsapp.repurpose_post_to_status", bind=True, max_retries=2)
def repurpose_post_to_status(self, user_id: int, post_id: str):
    """
    Repurpose a post from another platform into WhatsApp Status format.

    Takes LinkedIn/IG/TikTok post → AI-adapt for Status format
    (short, visual, punchy, Kenyan tone).
    """
    from apps.accounts.models import User
    from apps.content.models import Post
    from apps.whatsapp.models import StatusContent

    try:
        user = User.objects.select_related("profile").get(id=user_id)
        post = Post.objects.get(id=post_id, user=user)
    except (User.DoesNotExist, Post.DoesNotExist):
        logger.warning("User %s or post %s not found for repurpose", user_id, post_id)
        return

    profile = getattr(user, "profile", None)
    brand_name = profile.company_name if profile else "the business"

    platform = "social media"
    if post.social_account:
        platform = post.social_account.platform

    system = f"""You are adapting a {platform} post into WhatsApp Status format for {brand_name}.

RULES:
- WhatsApp Status = short, punchy. 200 chars ideal.
- Capture the ESSENCE of the original post, don't just truncate.
- Add emojis for visual impact.
- Include a CTA (reply, DM, link).
- Kenyan context when relevant.

RESPOND IN JSON:
{{
  "text": "Adapted Status text",
  "caption": "Optional media caption",
  "reasoning": "How you adapted the content"
}}"""

    response = generate(
        prompt=f"Adapt this {platform} post for WhatsApp Status:\n\n{post.content_text[:1000]}",
        system=system,
        model=get_model_for_task("adapt"),
        temperature=0.7,
        json_mode=True,
    )

    parsed = parse_llm_json(response.content) if response.content else None
    if not parsed:
        return

    status_obj = StatusContent.objects.create(
        user=user,
        text=parsed.get("text", "")[:700],
        caption=parsed.get("caption", ""),
        category="repurposed",
        state=StatusContent.StatusState.READY,
        source_post=post,
        source_platform=platform,
        ai_generated=True,
        ai_reasoning=parsed.get("reasoning", ""),
        model_used=response.model or "",
        tokens_used=response.total_tokens or 0,
    )
    status_obj.generate_share_url()
    status_obj.save(update_fields=["share_url"])

    logger.info("Post %s repurposed to Status for user %s", post_id, user_id)


@shared_task(name="whatsapp.generate_status_queue")
def generate_status_queue():
    """
    Periodic task — generate a week's worth of Status content for active users.

    Runs daily. Ensures each user has at least 2 statuses per day
    for the next 7 days, with a balanced category mix.
    """
    from apps.accounts.models import UserProfile
    from apps.whatsapp.models import StatusContent
    from datetime import timedelta

    active_profiles = UserProfile.objects.filter(
        plan__in=["pro", "agency"],
    ).select_related("user")

    now = timezone.now()
    week_ahead = now + timedelta(days=7)

    for profile in active_profiles:
        user = profile.user
        # Count existing upcoming statuses
        existing = StatusContent.objects.filter(
            user=user,
            state__in=["draft", "ready"],
            scheduled_for__gte=now,
            scheduled_for__lte=week_ahead,
        ).count()

        # Target: 2 per day × 7 days = 14
        needed = max(0, 14 - existing)
        if needed == 0:
            continue

        # Balanced category mix
        categories = ["tip", "quote", "bts", "offer", "new_product", "poll", "meme"]
        for i in range(min(needed, 5)):  # Generate max 5 per run to avoid LLM overload
            category = categories[i % len(categories)]
            brand_name = profile.company_name or "the business"
            generate_status_content.delay(
                user.id,
                f"Create a {category} Status post for {brand_name}",
                category,
            )

    logger.info("Status queue generation completed for %d users", active_profiles.count())


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5D — BROADCAST + ANALYTICS TASKS
# ═════════════════════════════════════════════════════════════════════════════

@shared_task(name="whatsapp.execute_broadcast", bind=True, max_retries=1)
def execute_broadcast(self, broadcast_id: str):
    """
    Execute a broadcast — send a template message to all recipients.

    Supports per-contact timing optimization if enabled.
    """
    from apps.whatsapp.models import WhatsAppBroadcast, WhatsAppMessage
    from apps.platforms.providers.registry import get_provider

    try:
        broadcast = WhatsAppBroadcast.objects.select_related(
            "social_account", "template",
        ).get(id=broadcast_id)
    except WhatsAppBroadcast.DoesNotExist:
        logger.warning("Broadcast %s not found", broadcast_id)
        return

    if broadcast.status not in ("scheduled", "sending"):
        logger.info("Broadcast %s has status %s — skipping", broadcast_id, broadcast.status)
        return

    broadcast.status = WhatsAppBroadcast.BroadcastStatus.SENDING
    broadcast.save(update_fields=["status", "updated_at"])

    provider = get_provider("whatsapp")
    if not provider:
        broadcast.status = WhatsAppBroadcast.BroadcastStatus.PAUSED
        broadcast.save(update_fields=["status", "updated_at"])
        logger.error("WhatsApp provider not available for broadcast %s", broadcast_id)
        return

    template = broadcast.template
    if not template:
        logger.error("Broadcast %s has no template", broadcast_id)
        return

    sent = 0
    failed = 0

    for phone in broadcast.recipient_phones:
        if broadcast.status == "paused":
            break

        try:
            result = provider.send_template_message(
                access_token=broadcast.social_account.access_token,
                to=phone,
                template_name=template.name,
                language=template.language,
                variables=broadcast.template_variables,
            )

            if result.get("success"):
                sent += 1
                # Create message record
                conversation = WhatsAppConversation.objects.filter(
                    social_account=broadcast.social_account,
                    contact_wa_id=phone,
                ).first()
                if conversation:
                    WhatsAppMessage.objects.create(
                        conversation=conversation,
                        direction=WhatsAppMessage.Direction.OUTBOUND,
                        message_type=WhatsAppMessage.MessageType.TEMPLATE,
                        content=template.body_text,
                        template=template,
                        wamid=result.get("wamid", ""),
                        status=WhatsAppMessage.MessageStatus.SENT,
                    )
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.warning("Broadcast send failed for %s: %s", phone, e)

    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.status = WhatsAppBroadcast.BroadcastStatus.COMPLETED
    broadcast.completed_at = timezone.now()
    broadcast.save(update_fields=[
        "sent_count", "failed_count", "status", "completed_at", "updated_at",
    ])

    logger.info("Broadcast %s completed: %d sent, %d failed", broadcast_id, sent, failed)


@shared_task(name="whatsapp.process_sequence_steps")
def process_sequence_steps():
    """
    Periodic task — process all active drip sequence enrollments.

    Checks which enrollments are due for their next step and sends
    the template message. Runs every 30 minutes.
    """
    from apps.whatsapp.models import (
        BroadcastSequence, BroadcastSequenceStep,
        SequenceEnrollment, WhatsAppMessage,
    )
    from apps.platforms.providers.registry import get_provider

    now = timezone.now()
    due_enrollments = SequenceEnrollment.objects.filter(
        status="active",
        next_send_at__lte=now,
        sequence__status="active",
    ).select_related("sequence", "conversation", "conversation__social_account")

    provider = get_provider("whatsapp")
    if not provider:
        logger.error("WhatsApp provider not available for sequence processing")
        return

    processed = 0
    for enrollment in due_enrollments[:100]:  # Batch limit
        next_order = enrollment.current_step + 1
        try:
            step = BroadcastSequenceStep.objects.get(
                sequence=enrollment.sequence,
                order=next_order,
            )
        except BroadcastSequenceStep.DoesNotExist:
            # Sequence completed
            enrollment.status = SequenceEnrollment.EnrollmentStatus.COMPLETED
            enrollment.completed_at = now
            enrollment.save(update_fields=["status", "completed_at"])
            enrollment.sequence.completed_count = (
                enrollment.sequence.enrollments.filter(status="completed").count()
            )
            enrollment.sequence.save(update_fields=["completed_count", "updated_at"])
            continue

        if not step.template:
            continue

        conversation = enrollment.conversation
        social_account = conversation.social_account

        try:
            result = provider.send_template_message(
                access_token=social_account.access_token,
                to=conversation.contact_wa_id,
                template_name=step.template.name,
                language=step.template.language,
                variables=step.template_variables,
            )

            if result.get("success"):
                step.sent_count += 1
                step.save(update_fields=["sent_count"])

                WhatsAppMessage.objects.create(
                    conversation=conversation,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    message_type=WhatsAppMessage.MessageType.TEMPLATE,
                    content=step.template.body_text,
                    template=step.template,
                    wamid=result.get("wamid", ""),
                    status=WhatsAppMessage.MessageStatus.SENT,
                )

                enrollment.current_step = next_order
                # Schedule next step
                next_step_exists = BroadcastSequenceStep.objects.filter(
                    sequence=enrollment.sequence,
                    order=next_order + 1,
                ).first()
                if next_step_exists:
                    from datetime import timedelta
                    enrollment.next_send_at = now + timedelta(hours=next_step_exists.delay_hours)
                else:
                    enrollment.next_send_at = None  # Will complete on next run
                enrollment.save(update_fields=["current_step", "next_send_at"])
                processed += 1
        except Exception as e:
            logger.warning("Sequence step send failed: %s", e)

    logger.info("Processed %d sequence steps", processed)


@shared_task(name="whatsapp.aggregate_daily_analytics")
def aggregate_daily_analytics():
    """
    Periodic task — aggregate daily WhatsApp analytics snapshots.

    Runs once daily. Counts messages, response times, AI performance,
    sentiment trends, and delivery metrics for each WhatsApp account.
    """
    from apps.whatsapp.models import (
        WhatsAppAnalytics, WhatsAppConversation, WhatsAppMessage, StatusContent,
    )
    from apps.platforms.models import SocialAccount
    from django.db.models import Avg, Count, Q
    from datetime import timedelta

    yesterday = (timezone.now() - timedelta(days=1)).date()
    day_start = timezone.make_aware(
        timezone.datetime.combine(yesterday, timezone.datetime.min.time())
    )
    day_end = day_start + timedelta(days=1)

    wa_accounts = SocialAccount.objects.filter(platform="whatsapp", is_active=True)

    for account in wa_accounts:
        messages = WhatsAppMessage.objects.filter(
            conversation__social_account=account,
            created_at__gte=day_start,
            created_at__lt=day_end,
        )

        inbound = messages.filter(direction="inbound")
        outbound = messages.filter(direction="outbound")
        ai_messages = outbound.filter(is_ai_generated=True)

        conversations = WhatsAppConversation.objects.filter(social_account=account)

        # Count statuses shared by this account's user
        statuses_shared = StatusContent.objects.filter(
            user=account.user,
            state="shared",
            shared_at__gte=day_start,
            shared_at__lt=day_end,
        ).count()

        analytics, _ = WhatsAppAnalytics.objects.update_or_create(
            social_account=account,
            date=yesterday,
            defaults={
                "conversations_total": conversations.count(),
                "conversations_new": conversations.filter(
                    created_at__gte=day_start, created_at__lt=day_end,
                ).count(),
                "conversations_escalated": conversations.filter(
                    status="escalated",
                ).count(),
                "messages_inbound": inbound.count(),
                "messages_outbound": outbound.count(),
                "ai_replies": ai_messages.count(),
                "ai_auto_sent": ai_messages.filter(
                    confidence_score__gte=0.8,
                    status="sent",
                ).count(),
                "ai_drafts_approved": ai_messages.filter(
                    confidence_score__lt=0.8,
                    confidence_score__gte=0.5,
                    status="sent",
                ).count(),
                "avg_ai_confidence": ai_messages.aggregate(
                    a=Avg("confidence_score"),
                )["a"],
                "messages_delivered": outbound.filter(status="delivered").count(),
                "messages_read": outbound.filter(status="read").count(),
                "messages_failed": outbound.filter(status="failed").count(),
                "avg_sentiment": conversations.aggregate(
                    a=Avg("sentiment_score"),
                )["a"],
                "statuses_shared": statuses_shared,
            },
        )

    logger.info("Daily WA analytics aggregated for %d accounts", wa_accounts.count())


@shared_task(name="whatsapp.generate_weekly_digest")
def generate_weekly_digest():
    """
    Periodic task — generate weekly WhatsApp performance digests.

    Runs once a week (Monday). Compiles the past 7 days of analytics
    and uses AI to generate natural language insights.
    """
    from apps.accounts.models import UserProfile
    from apps.whatsapp.models import WeeklyDigest, WhatsAppAnalytics
    from apps.platforms.models import SocialAccount
    from datetime import timedelta

    now = timezone.now()
    week_end = now.date()
    week_start = week_end - timedelta(days=7)

    active_profiles = UserProfile.objects.filter(
        plan__in=["pro", "agency"],
    ).select_related("user")

    for profile in active_profiles:
        user = profile.user
        wa_accounts = SocialAccount.objects.filter(
            user=user, platform="whatsapp", is_active=True,
        )
        if not wa_accounts.exists():
            continue

        # Aggregate week's data
        week_analytics = WhatsAppAnalytics.objects.filter(
            social_account__in=wa_accounts,
            date__gte=week_start,
            date__lt=week_end,
        )

        if not week_analytics.exists():
            continue

        totals = week_analytics.aggregate(
            total_inbound=Sum("messages_inbound"),
            total_outbound=Sum("messages_outbound"),
            total_ai=Sum("ai_replies"),
            total_escalated=Sum("conversations_escalated"),
            total_delivered=Sum("messages_delivered"),
            total_read=Sum("messages_read"),
            total_statuses=Sum("statuses_shared"),
            avg_sentiment=Avg("avg_sentiment"),
            avg_confidence=Avg("avg_ai_confidence"),
        )

        # Previous week for comparison
        prev_start = week_start - timedelta(days=7)
        prev_analytics = WhatsAppAnalytics.objects.filter(
            social_account__in=wa_accounts,
            date__gte=prev_start,
            date__lt=week_start,
        )
        prev_totals = prev_analytics.aggregate(
            total_inbound=Sum("messages_inbound"),
            total_outbound=Sum("messages_outbound"),
            total_ai=Sum("ai_replies"),
        )

        brand_name = profile.company_name or "your business"

        system = f"""You are a WhatsApp performance analyst for {brand_name}.
Generate a concise, actionable weekly digest from these metrics.

RESPOND IN JSON:
{{
  "summary": "2-3 sentence natural language summary of the week",
  "highlights": [
    {{"title": "Metric name", "value": "23", "change_pct": 15, "insight": "Brief insight"}},
  ],
  "recommendations": [
    "Actionable recommendation for next week"
  ]
}}

Keep it conversational, Kenyan business-friendly tone. Be specific with numbers."""

        metrics_prompt = f"""This week's WhatsApp metrics for {brand_name}:
- Messages received: {totals['total_inbound'] or 0}
- Messages sent: {totals['total_outbound'] or 0}
- AI replies: {totals['total_ai'] or 0}
- Escalated conversations: {totals['total_escalated'] or 0}
- Delivered: {totals['total_delivered'] or 0}
- Read: {totals['total_read'] or 0}
- Status updates shared: {totals['total_statuses'] or 0}
- Avg sentiment: {totals['avg_sentiment'] or 'N/A'}
- Avg AI confidence: {totals['avg_confidence'] or 'N/A'}

Previous week comparison:
- Messages received: {prev_totals['total_inbound'] or 0}
- Messages sent: {prev_totals['total_outbound'] or 0}
- AI replies: {prev_totals['total_ai'] or 0}"""

        response = generate(
            prompt=metrics_prompt,
            system=system,
            model=get_model_for_task("analyst"),
            temperature=0.7,
            json_mode=True,
        )

        parsed = parse_llm_json(response.content) if response.content else None
        if not parsed:
            continue

        WeeklyDigest.objects.update_or_create(
            user=user,
            week_start=week_start,
            defaults={
                "week_end": week_end,
                "summary": parsed.get("summary", ""),
                "highlights": parsed.get("highlights", []),
                "recommendations": parsed.get("recommendations", []),
                "analytics_data": {k: str(v) for k, v in totals.items()},
                "model_used": response.model or "",
            },
        )

    logger.info("Weekly digests generated for %d users", active_profiles.count())


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5E — WHATSAPP CHANNELS TASKS
# ═════════════════════════════════════════════════════════════════════════════

@shared_task(name="whatsapp.cross_post_to_channel", bind=True, max_retries=2)
def cross_post_to_channel(self, channel_id: str, post_id: str):
    """
    Cross-post content from another platform to a WhatsApp Channel.

    Takes the original post, AI-adapts it for Channel format
    (shorter, more visual, direct), and creates a ChannelPost.
    """
    from apps.content.models import Post
    from apps.whatsapp.models import ChannelPost, WhatsAppChannel

    try:
        channel = WhatsAppChannel.objects.get(id=channel_id)
        post = Post.objects.get(id=post_id)
    except (WhatsAppChannel.DoesNotExist, Post.DoesNotExist):
        logger.warning("Channel %s or post %s not found", channel_id, post_id)
        return

    user = channel.social_account.user
    profile = getattr(user, "profile", None)
    brand_name = profile.company_name if profile else "the business"

    platform = "social media"
    if post.social_account:
        platform = post.social_account.platform

    system = f"""You are adapting a {platform} post for a WhatsApp Channel for {brand_name}.

WhatsApp Channels are like newsletters — followers see updates in their Updates tab.
- Keep it concise but complete (unlike Status, Channel posts can be longer).
- Use emojis for visual structure.
- No need for a CTA unless the post has one.
- Make it scannable — use line breaks.

RESPOND IN JSON:
{{
  "text": "Adapted Channel post text",
  "reasoning": "How you adapted it"
}}"""

    response = generate(
        prompt=f"Adapt this {platform} post for a WhatsApp Channel:\n\n{post.content_text[:1500]}",
        system=system,
        model=get_model_for_task("adapt"),
        temperature=0.7,
        json_mode=True,
    )

    parsed = parse_llm_json(response.content) if response.content else None
    if not parsed:
        return

    ChannelPost.objects.create(
        channel=channel,
        text=parsed.get("text", post.content_text[:500]),
        source_post=post,
        source_platform=platform,
        ai_adapted=True,
        status=ChannelPost.PostStatus.DRAFT,
        ai_reasoning=parsed.get("reasoning", ""),
        model_used=response.model or "",
    )

    logger.info("Post %s cross-posted to channel %s", post_id, channel_id)


@shared_task(name="whatsapp.curate_channel_content")
def curate_channel_content():
    """
    Periodic task — AI-curate content for channels with auto_curate enabled.

    Selects the best recent content from the user's connected platforms
    and queues it for the channel. Runs every 6 hours.
    """
    from apps.content.models import Post
    from apps.whatsapp.models import ChannelPost, WhatsAppChannel
    from datetime import timedelta

    channels = WhatsAppChannel.objects.filter(
        auto_curate=True,
        status="active",
    ).select_related("social_account", "social_account__user")

    now = timezone.now()

    for channel in channels:
        # Check daily post limit
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_posts = ChannelPost.objects.filter(
            channel=channel,
            created_at__gte=today_start,
        ).count()

        if today_posts >= channel.max_posts_per_day:
            continue

        user = channel.social_account.user

        # Find recent published posts not yet cross-posted
        recent_posts = Post.objects.filter(
            user=user,
            status="published",
            published_at__gte=now - timedelta(days=3),
        ).exclude(
            channel_reposts__channel=channel,
        ).order_by("-predicted_engagement_score", "-published_at")

        # Filter by curate_from_platforms if specified
        if channel.curate_from_platforms:
            recent_posts = recent_posts.filter(
                social_account__platform__in=channel.curate_from_platforms,
            )

        post = recent_posts.first()
        if post:
            cross_post_to_channel.delay(str(channel.pk), str(post.pk))

    logger.info("Channel curation completed for %d channels", channels.count())
