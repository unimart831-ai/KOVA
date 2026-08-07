import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.accounts.soft_delete import SoftDeleteMixin


class Team(SoftDeleteMixin, models.Model):
    """A team workspace where multiple users collaborate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    """A brand within a team — each brand has its own voice, audience, and goals.

    Agency-plan teams can manage multiple brands (clients).
    Solo users get one implicit brand from their UserProfile.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="brands")
    name = models.CharField(max_length=255, help_text="Brand or client name")
    slug = models.SlugField(max_length=255)
    logo = models.ImageField(upload_to="brand_logos/", blank=True, null=True)
    brand_voice = models.TextField(
        blank=True,
        help_text="Describe this brand's tone and style.",
    )
    brand_voice_examples = models.JSONField(
        default=list, blank=True,
        help_text="Sample posts that represent this brand's voice.",
    )
    industry = models.CharField(max_length=30, blank=True)
    website_url = models.URLField(blank=True)
    target_audience = models.TextField(blank=True)
    content_pillars = models.JSONField(
        default=list, blank=True,
        help_text="Main topics/themes for this brand's content.",
    )
    goals = models.JSONField(
        default=list, blank=True,
        help_text='Social media goals for this brand.',
    )
    custom_domain = models.CharField(
        max_length=255, blank=True,
        help_text="Custom domain for commerce/Kova Link (display + CNAME setup).",
    )
    custom_domain_verified = models.BooleanField(
        default=False,
        help_text="True once DNS CNAME is verified (manual for v1).",
    )
    theme_primary_color = models.CharField(
        max_length=7, blank=True,
        help_text="Hex accent color for client-facing pages, e.g. #0066FF.",
    )
    logo_url = models.URLField(
        blank=True,
        help_text="Agency/client logo URL for reports and commerce pages.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("team", "slug")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.team.name})"


class TeamMember(models.Model):
    """A user's membership in a team with a specific role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"
        CLIENT = "client", "Client"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    brand = models.ForeignKey(
        "teams.Brand",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_members",
        help_text="For client role — limits dashboard to this brand's content.",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EDITOR)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("team", "user")]
        ordering = ["role", "joined_at"]

    def __str__(self):
        return f"{self.user.email} — {self.get_role_display()} @ {self.team.name}"

    @property
    def can_approve(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    @property
    def can_create_content(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.EDITOR)

    @property
    def can_manage_members(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)


class TeamInvitation(models.Model):
    """An email-based invitation to join a team."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=TeamMember.Role.choices,
        default=TeamMember.Role.EDITOR,
    )
    brand = models.ForeignKey(
        "teams.Brand",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        help_text="Required when inviting a client — scopes them to one brand.",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.email} → {self.team.name} ({self.get_role_display()})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.accepted and not self.is_expired


class TeamActivity(models.Model):
    """Lightweight activity log for team-level events."""

    class EventType(models.TextChoices):
        MEMBER_JOINED = "member_joined", "Member Joined"
        MEMBER_LEFT = "member_left", "Member Left"
        ROLE_CHANGED = "role_changed", "Role Changed"
        POST_CREATED = "post_created", "Post Created"
        POST_PUBLISHED = "post_published", "Post Published"
        POST_APPROVED = "post_approved", "Post Approved"
        BRAND_CREATED = "brand_created", "Brand Created"
        BRAND_UPDATED = "brand_updated", "Brand Updated"
        SEED_SUBMITTED = "seed_submitted", "Seed Submitted"
        INVITATION_SENT = "invitation_sent", "Invitation Sent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    description = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Team activities"

    def __str__(self):
        actor_name = self.actor.email if self.actor else "System"
        return f"{actor_name}: {self.description}"

    @classmethod
    def log(cls, team, actor, event_type, description, **metadata):
        """Convenience method to log an activity."""
        return cls.objects.create(
            team=team,
            actor=actor,
            event_type=event_type,
            description=description,
            metadata=metadata,
        )
