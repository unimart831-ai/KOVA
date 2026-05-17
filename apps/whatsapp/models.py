"""
WhatsApp data models.

Covers the full WhatsApp Cloud API lifecycle:
- Conversations (thread-based, 24-hour window aware)
- Messages (inbound + outbound, all types)
- Templates (Meta approval workflow)
- Broadcasts (segmented campaigns with drip support)
- Status Content Studio (Sprint 5C)
- Broadcast Sequences / Drip Campaigns (Sprint 5D)
- WhatsApp Analytics (Sprint 5D)
- WhatsApp Channels (Sprint 5E)
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ─── CONVERSATION ────────────────────────────────────────────────────────────

class WhatsAppConversation(models.Model):
    """
    A conversation thread with a WhatsApp contact.

    WhatsApp uses a 24-hour window model:
    - When a user messages you, a "service" window opens for 24 hours.
    - You can send free-form messages within this window.
    - After the window closes, you must use an approved template to re-initiate.

    The `window_expires_at` field tracks this so we know when to switch
    from free-form to template-only messaging.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        ESCALATED = "escalated", "Escalated"  # Routed to human

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        SWAHILI = "sw", "Swahili"
        SHENG = "sheng", "Sheng"
        UNKNOWN = "unknown", "Unknown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="whatsapp_conversations",
    )
    # Contact info (phone stored as hash for privacy in production)
    contact_wa_id = models.CharField(
        max_length=32, db_index=True,
        help_text="WhatsApp ID (usually the phone number without +)",
    )
    contact_phone = models.CharField(max_length=32, blank=True)
    contact_name = models.CharField(max_length=255, blank=True, help_text="Push name from WhatsApp")
    # State
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    language = models.CharField(max_length=10, choices=Language.choices, default=Language.UNKNOWN)
    ai_handling = models.BooleanField(default=True, help_text="Is AI currently handling this conversation?")
    # 24-hour window tracking
    window_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the 24-hour service window expires. After this, only templates allowed.",
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    # AI analysis
    sentiment_score = models.FloatField(
        null=True, blank=True,
        help_text="Running average sentiment (-1 negative to +1 positive)",
    )
    tags = models.JSONField(default=list, blank=True, help_text="Customer segments / tags")
    context = models.JSONField(
        default=dict, blank=True,
        help_text="Conversation context for AI (product interests, past questions, etc.)",
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        unique_together = ["social_account", "contact_wa_id"]
        indexes = [
            models.Index(fields=["social_account", "status", "-last_message_at"]),
        ]

    def __str__(self):
        name = self.contact_name or self.contact_wa_id
        return f"Conversation with {name}"

    @property
    def is_window_open(self):
        """Can we send free-form messages (within 24-hour window)?"""
        if not self.window_expires_at:
            return False
        return timezone.now() < self.window_expires_at

    def open_window(self):
        """Open/extend the 24-hour service window (called on inbound message)."""
        self.window_expires_at = timezone.now() + timezone.timedelta(hours=24)
        self.last_message_at = timezone.now()
        self.save(update_fields=["window_expires_at", "last_message_at"])


# ─── MESSAGE ─────────────────────────────────────────────────────────────────

class WhatsAppMessage(models.Model):
    """
    A single message in a WhatsApp conversation.

    Tracks both inbound (customer → business) and outbound (business → customer)
    messages, with full status tracking (sent → delivered → read → failed).
    """

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        DOCUMENT = "document", "Document"
        STICKER = "sticker", "Sticker"
        LOCATION = "location", "Location"
        CONTACTS = "contacts", "Contacts"
        INTERACTIVE = "interactive", "Interactive"
        TEMPLATE = "template", "Template"
        REACTION = "reaction", "Reaction"
        ORDER = "order", "Order"

    class MessageStatus(models.TextChoices):
        PENDING = "pending", "Pending"       # Queued locally
        SENT = "sent", "Sent"                # Accepted by WhatsApp
        DELIVERED = "delivered", "Delivered"  # Delivered to device
        READ = "read", "Read"                # User opened it
        FAILED = "failed", "Failed"          # Send failed

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        WhatsAppConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    # Content
    content = models.TextField(blank=True, help_text="Text content or caption")
    media_url = models.URLField(blank=True, help_text="Media URL (image, video, audio, document)")
    media_mime_type = models.CharField(max_length=100, blank=True)
    interactive_data = models.JSONField(
        default=dict, blank=True,
        help_text="Button clicks, list selections, flow responses",
    )
    # WhatsApp tracking
    wamid = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="WhatsApp message ID (wamid) for status tracking",
    )
    status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.PENDING,
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)
    error_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    # AI tracking
    is_ai_generated = models.BooleanField(default=False)
    confidence_score = models.FloatField(
        null=True, blank=True,
        help_text="AI confidence when auto-replied (0.0 to 1.0)",
    )
    # Template reference
    template = models.ForeignKey(
        "WhatsAppTemplate",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="messages",
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["wamid"]),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} {self.get_message_type_display()} ({self.status})"


# ─── TEMPLATE ────────────────────────────────────────────────────────────────

class WhatsAppTemplate(models.Model):
    """
    A WhatsApp message template.

    Templates must be approved by Meta before they can be used to message
    customers outside the 24-hour window. This model tracks the full lifecycle:
    draft → submitted → approved/rejected → active use.

    The AI Create Agent can draft templates, and we validate them against
    Meta's policies before submission to reduce rejection rates.
    """

    class Category(models.TextChoices):
        MARKETING = "marketing", "Marketing"
        UTILITY = "utility", "Utility"
        AUTHENTICATION = "authentication", "Authentication"

    class TemplateStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAUSED = "paused", "Paused"  # Meta paused due to quality issues

    class HeaderType(models.TextChoices):
        NONE = "none", "None"
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        DOCUMENT = "document", "Document"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="whatsapp_templates",
    )
    # Meta requirements
    name = models.CharField(
        max_length=512,
        help_text="Template name (lowercase, underscores only — Meta requirement)",
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    language = models.CharField(max_length=10, default="en")
    # Structure
    header_type = models.CharField(max_length=20, choices=HeaderType.choices, default=HeaderType.NONE)
    header_text = models.CharField(max_length=60, blank=True, help_text="Header text (if header_type=text)")
    header_media_url = models.URLField(blank=True, help_text="Header media URL (if image/video/document)")
    body_text = models.TextField(help_text="Template body with {{1}}, {{2}} variable slots")
    footer_text = models.CharField(max_length=60, blank=True)
    buttons = models.JSONField(
        default=list, blank=True,
        help_text="Quick reply or CTA buttons [{type, text, url/phone_number}]",
    )
    # Meta tracking
    meta_template_id = models.CharField(max_length=255, blank=True, help_text="Template ID from Meta")
    status = models.CharField(
        max_length=20, choices=TemplateStatus.choices, default=TemplateStatus.DRAFT,
    )
    rejection_reason = models.TextField(blank=True)
    # Performance
    performance_data = models.JSONField(
        default=dict, blank=True,
        help_text="Tracked: open_rate, reply_rate, block_rate, send_count",
    )
    # AI
    created_by_ai = models.BooleanField(default=False)
    ai_prompt_used = models.TextField(blank=True, help_text="The natural language prompt that generated this template")
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["social_account", "name", "language"]
        indexes = [
            models.Index(fields=["social_account", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


# ─── BROADCAST ───────────────────────────────────────────────────────────────

class WhatsAppBroadcast(models.Model):
    """
    A broadcast campaign — send a template message to a segment of contacts.

    Supports smart segmentation, per-contact timing (via Adapt Agent),
    and drip sequences (multi-day campaigns).
    """

    class BroadcastStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        COMPLETED = "completed", "Completed"
        PAUSED = "paused", "Paused"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="whatsapp_broadcasts",
    )
    name = models.CharField(max_length=255)
    template = models.ForeignKey(
        WhatsAppTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="broadcasts",
    )
    # Targeting
    segment = models.JSONField(
        default=dict, blank=True,
        help_text="Targeting criteria: {tags: [], languages: [], last_active_days: N}",
    )
    recipient_phones = models.JSONField(
        default=list, blank=True,
        help_text="Resolved list of contact wa_ids to send to",
    )
    template_variables = models.JSONField(
        default=dict, blank=True,
        help_text="Variable mappings: {1: 'field_name', 2: 'field_name'}",
    )
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    per_contact_timing = models.BooleanField(
        default=False,
        help_text="Let Adapt Agent optimize send time per recipient",
    )
    # Status & metrics
    status = models.CharField(
        max_length=20, choices=BroadcastStatus.choices, default=BroadcastStatus.DRAFT,
    )
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    replied_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


# ─── STATUS CONTENT (Sprint 5C) ─────────────────────────────────────────────

class StatusContent(models.Model):
    """
    A piece of content ready for WhatsApp Status sharing.

    WhatsApp Status doesn't have a direct posting API (yet), so we prepare
    content and give the user a one-tap deep link to share. The AI generates
    Status-optimized content (short, visual, punchy, Kenyan tone) and the
    smart scheduler suggests optimal posting times.
    """

    class ContentCategory(models.TextChoices):
        NEW_PRODUCT = "new_product", "New Product"
        OFFER = "offer", "Offer / Discount"
        TESTIMONIAL = "testimonial", "Testimonial"
        BTS = "bts", "Behind the Scenes"
        POLL = "poll", "Poll / Question"
        MEME = "meme", "Meme / Humor"
        QUOTE = "quote", "Motivational Quote"
        TIP = "tip", "Tip / How-To"
        ANNOUNCEMENT = "announcement", "Announcement"
        REPURPOSED = "repurposed", "Repurposed Content"

    class StatusState(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready to Share"
        SHARED = "shared", "Shared"
        EXPIRED = "expired", "Expired"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="status_contents",
    )
    # Content
    text = models.TextField(help_text="Status text (short, punchy — 200 chars ideal)")
    caption = models.TextField(blank=True, help_text="Extended caption if sharing media")
    media_url = models.URLField(blank=True, help_text="Image/video URL for visual Status")
    media_type = models.CharField(
        max_length=10, blank=True,
        choices=[("image", "Image"), ("video", "Video")],
    )
    # Classification
    category = models.CharField(max_length=20, choices=ContentCategory.choices)
    state = models.CharField(max_length=10, choices=StatusState.choices, default=StatusState.DRAFT)
    # Scheduling
    scheduled_for = models.DateTimeField(
        null=True, blank=True,
        help_text="Suggested share time (based on contact activity patterns)",
    )
    shared_at = models.DateTimeField(null=True, blank=True)
    # Source tracking (for repurposed content)
    source_post = models.ForeignKey(
        "content.Post",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="status_repurposes",
        help_text="Original post if this Status was repurposed from another platform",
    )
    source_platform = models.CharField(max_length=20, blank=True, help_text="Platform the content came from")
    # AI metadata
    ai_generated = models.BooleanField(default=False)
    ai_reasoning = models.TextField(blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    # Deep link
    share_url = models.URLField(blank=True, help_text="WhatsApp deep link for one-tap sharing")
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_for", "-created_at"]
        indexes = [
            models.Index(fields=["user", "state", "-scheduled_for"]),
        ]

    def __str__(self):
        return f"Status: {self.text[:50]}… ({self.get_state_display()})"

    @property
    def is_shareable(self):
        return self.state in (self.StatusState.DRAFT, self.StatusState.READY)

    def generate_share_url(self):
        """Build a WhatsApp pre-fill link for sharing content.

        WhatsApp has no Status posting API for businesses — the owner must
        post Status manually. This URL opens the WhatsApp app with the text
        pre-filled so the owner can paste it into their Status in one tap.
        The `api.whatsapp.com/send` form works on both mobile and desktop;
        `wa.me/?text=` opens a new chat instead (wrong behaviour).
        """
        from urllib.parse import quote
        text = self.text
        if self.media_url:
            text = f"{self.text}\n{self.media_url}"
        self.share_url = f"https://api.whatsapp.com/send?text={quote(text)}"
        return self.share_url


class StatusTemplate(models.Model):
    """
    Reusable Status content templates for common business scenarios.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=StatusContent.ContentCategory.choices)
    text_template = models.TextField(
        help_text="Template with {product}, {price}, {name} etc. placeholders",
    )
    caption_template = models.TextField(blank=True)
    media_prompt = models.TextField(blank=True, help_text="AI image generation prompt if visual")
    example_text = models.TextField(blank=True, help_text="Filled-in example for preview")
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-usage_count", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


# ─── BROADCAST SEQUENCES (Sprint 5D) ────────────────────────────────────────

class BroadcastSequence(models.Model):
    """
    A multi-step drip sequence — automated multi-day broadcast campaigns.

    Each step sends a template at a specified delay after the trigger
    (onboarding, re-engagement, cart abandonment, etc.).
    """

    class SequenceType(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        RE_ENGAGEMENT = "re_engagement", "Re-engagement"
        CART_ABANDONMENT = "cart_abandonment", "Cart Abandonment"
        POST_PURCHASE = "post_purchase", "Post Purchase"
        CUSTOM = "custom", "Custom"

    class SequenceStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="broadcast_sequences",
    )
    name = models.CharField(max_length=255)
    sequence_type = models.CharField(max_length=20, choices=SequenceType.choices)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=SequenceStatus.choices, default=SequenceStatus.DRAFT)
    # Targeting
    segment = models.JSONField(
        default=dict, blank=True,
        help_text="Targeting criteria: {tags: [], languages: [], last_active_days: N}",
    )
    # Metrics
    enrolled_count = models.PositiveIntegerField(default=0)
    completed_count = models.PositiveIntegerField(default=0)
    dropped_count = models.PositiveIntegerField(default=0)
    # AI
    ai_generated = models.BooleanField(default=False)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_sequence_type_display()})"

    @property
    def total_steps(self):
        return self.steps.count()


class BroadcastSequenceStep(models.Model):
    """A single step in a drip sequence."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        BroadcastSequence,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveIntegerField(help_text="Step number (1, 2, 3...)")
    template = models.ForeignKey(
        WhatsAppTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sequence_steps",
    )
    delay_hours = models.PositiveIntegerField(
        help_text="Hours to wait after previous step (or enrollment for step 1)",
    )
    template_variables = models.JSONField(
        default=dict, blank=True,
        help_text="Variable mappings for this step",
    )
    # Metrics
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    replied_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "order"]
        unique_together = ["sequence", "order"]

    def __str__(self):
        return f"Step {self.order} of {self.sequence.name}"


class SequenceEnrollment(models.Model):
    """Tracks a contact's progress through a broadcast sequence."""

    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"
        PAUSED = "paused", "Paused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        BroadcastSequence,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    conversation = models.ForeignKey(
        WhatsAppConversation,
        on_delete=models.CASCADE,
        related_name="sequence_enrollments",
    )
    current_step = models.PositiveIntegerField(default=0, help_text="Last completed step number")
    status = models.CharField(
        max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE,
    )
    next_send_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-enrolled_at"]
        unique_together = ["sequence", "conversation"]

    def __str__(self):
        return f"{self.conversation} in {self.sequence.name} (step {self.current_step})"


# ─── WHATSAPP ANALYTICS (Sprint 5D) ─────────────────────────────────────────

class WhatsAppAnalytics(models.Model):
    """
    Daily analytics snapshot for a WhatsApp Business account.

    Aggregated daily so we can track trends: conversation volume,
    response times, AI performance, sentiment shifts, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="whatsapp_analytics",
    )
    date = models.DateField()
    # Volume
    conversations_total = models.PositiveIntegerField(default=0)
    conversations_new = models.PositiveIntegerField(default=0)
    conversations_escalated = models.PositiveIntegerField(default=0)
    messages_inbound = models.PositiveIntegerField(default=0)
    messages_outbound = models.PositiveIntegerField(default=0)
    # AI performance
    ai_replies = models.PositiveIntegerField(default=0)
    ai_auto_sent = models.PositiveIntegerField(default=0, help_text="High confidence, sent automatically")
    ai_drafts_approved = models.PositiveIntegerField(default=0, help_text="Medium confidence, user approved")
    ai_drafts_rejected = models.PositiveIntegerField(default=0)
    # Response metrics
    avg_response_time_seconds = models.FloatField(
        null=True, blank=True,
        help_text="Average time from inbound message to first reply",
    )
    avg_ai_confidence = models.FloatField(null=True, blank=True)
    # Sentiment
    avg_sentiment = models.FloatField(null=True, blank=True, help_text="-1 to +1")
    sentiment_positive_pct = models.FloatField(default=0)
    sentiment_negative_pct = models.FloatField(default=0)
    # Delivery
    messages_delivered = models.PositiveIntegerField(default=0)
    messages_read = models.PositiveIntegerField(default=0)
    messages_failed = models.PositiveIntegerField(default=0)
    # Revenue attribution (manual or webhook-tracked)
    conversions = models.PositiveIntegerField(default=0)
    revenue_attributed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Status content
    statuses_shared = models.PositiveIntegerField(default=0)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ["social_account", "date"]
        indexes = [
            models.Index(fields=["social_account", "-date"]),
        ]

    def __str__(self):
        return f"WA Analytics {self.social_account} — {self.date}"

    @property
    def delivery_rate(self):
        total = self.messages_outbound
        if not total:
            return 0
        return round(self.messages_delivered / total * 100, 1)

    @property
    def read_rate(self):
        total = self.messages_delivered
        if not total:
            return 0
        return round(self.messages_read / total * 100, 1)


class WeeklyDigest(models.Model):
    """
    AI-generated weekly WhatsApp performance digest.

    "Top-performing Status was the chapati meme (847 views).
     Response time improved 34%."
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wa_weekly_digests",
    )
    week_start = models.DateField()
    week_end = models.DateField()
    # Content
    summary = models.TextField(help_text="AI-generated natural language summary")
    highlights = models.JSONField(
        default=list, blank=True,
        help_text="Key metrics [{title, value, change_pct, insight}]",
    )
    recommendations = models.JSONField(
        default=list, blank=True,
        help_text="AI-generated action items for next week",
    )
    # Raw data
    analytics_data = models.JSONField(default=dict, blank=True, help_text="Aggregated metrics for the week")
    model_used = models.CharField(max_length=100, blank=True)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = ["user", "week_start"]

    def __str__(self):
        return f"WA Digest {self.user} — {self.week_start} to {self.week_end}"


# ─── WHATSAPP CHANNELS (Sprint 5E) ──────────────────────────────────────────

class WhatsAppChannel(models.Model):
    """
    A WhatsApp Channel managed by Kova.

    WhatsApp Channels are broadcast-only (like newsletters). Kova can
    curate content from any platform and cross-post to the Channel.
    """

    class ChannelStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        DISCONNECTED = "disconnected", "Disconnected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="whatsapp_channels",
    )
    channel_id = models.CharField(max_length=255, blank=True, help_text="WhatsApp Channel ID from Meta")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Status
    status = models.CharField(max_length=20, choices=ChannelStatus.choices, default=ChannelStatus.ACTIVE)
    # Growth metrics
    follower_count = models.PositiveIntegerField(default=0)
    follower_count_updated_at = models.DateTimeField(null=True, blank=True)
    # Settings
    auto_curate = models.BooleanField(
        default=False,
        help_text="Let AI automatically select and post content to this Channel",
    )
    curate_from_platforms = models.JSONField(
        default=list, blank=True,
        help_text="Platforms to pull content from: ['linkedin', 'instagram', ...]",
    )
    max_posts_per_day = models.PositiveIntegerField(default=3)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Channel: {self.name} ({self.get_status_display()})"


class ChannelPost(models.Model):
    """A post published to a WhatsApp Channel."""

    class PostStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        WhatsAppChannel,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    # Content
    text = models.TextField()
    media_url = models.URLField(blank=True)
    media_type = models.CharField(
        max_length=10, blank=True,
        choices=[("image", "Image"), ("video", "Video"), ("document", "Document")],
    )
    # Source tracking
    source_post = models.ForeignKey(
        "content.Post",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="channel_reposts",
        help_text="Original post if cross-posted from another platform",
    )
    source_platform = models.CharField(max_length=20, blank=True)
    ai_adapted = models.BooleanField(default=False, help_text="Was the content AI-adapted for Channel format?")
    # Scheduling
    status = models.CharField(max_length=20, choices=PostStatus.choices, default=PostStatus.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # Engagement (from Channel analytics)
    reach = models.PositiveIntegerField(default=0)
    reactions = models.PositiveIntegerField(default=0)
    # Meta tracking
    meta_post_id = models.CharField(max_length=255, blank=True, help_text="Channel post ID from Meta")
    # AI
    ai_reasoning = models.TextField(blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "status", "-scheduled_at"]),
        ]

    def __str__(self):
        return f"Channel post: {self.text[:50]}… ({self.get_status_display()})"
