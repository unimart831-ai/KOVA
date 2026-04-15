"""
WhatsApp data models.

Covers the full WhatsApp Cloud API lifecycle:
- Conversations (thread-based, 24-hour window aware)
- Messages (inbound + outbound, all types)
- Templates (Meta approval workflow)
- Broadcasts (segmented campaigns with drip support)
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
