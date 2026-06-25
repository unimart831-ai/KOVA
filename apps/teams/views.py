import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.billing.models import get_user_plan_limits
from apps.billing.plan_limit_ui import plan_limit_redirect

from .models import Brand, Team, TeamActivity, TeamInvitation, TeamMember

User = get_user_model()


def _get_team_member(user, team):
    """Return the TeamMember for this user/team, or None."""
    return TeamMember.objects.filter(team=team, user=user).select_related("team").first()


def _require_membership(user, team, min_role=None):
    """Get membership or raise 404. Optionally enforce minimum role."""
    member = _get_team_member(user, team)
    if not member:
        raise Http404
    if min_role:
        role_order = ["viewer", "editor", "admin", "owner"]
        if role_order.index(member.role) < role_order.index(min_role):
            raise Http404
    return member


def _can_use_teams(user):
    """Check if user's plan includes team features."""
    limits = get_user_plan_limits(user)
    return limits.get("max_team_members", 0) > 0


@login_required
def team_list(request):
    """List teams the user belongs to, or prompt to create one."""
    memberships = (
        TeamMember.objects.filter(user=request.user)
        .select_related("team", "team__owner")
    )
    has_team_access = _can_use_teams(request.user)
    return render(request, "teams/list.html", {
        "memberships": memberships,
        "has_team_access": has_team_access,
    })


@login_required
def team_create(request):
    """Create a new team."""
    if not _can_use_teams(request.user):
        return plan_limit_redirect(
            request,
            "Upgrade to Pro or Agency to use team features.",
            "teams:list",
        )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Team name is required.")
            return render(request, "teams/create.html")

        # Generate unique slug
        base_slug = slugify(name)[:240]
        slug = base_slug
        counter = 1
        while Team.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        team = Team.objects.create(name=name, slug=slug, owner=request.user)
        TeamMember.objects.create(
            team=team, user=request.user, role=TeamMember.Role.OWNER,
        )
        TeamActivity.log(team, request.user, TeamActivity.EventType.MEMBER_JOINED, f"{request.user.email} created the team")
        messages.success(request, f'Team "{name}" created successfully.')
        return redirect("teams:detail", slug=team.slug)

    return render(request, "teams/create.html")


@login_required
def team_detail(request, slug):
    """Team management page — members, invitations, settings."""
    team = get_object_or_404(Team, slug=slug)
    member = _require_membership(request.user, team)
    members = team.members.select_related("user").all()
    pending_invitations = team.invitations.filter(accepted=False, expires_at__gt=timezone.now())

    limits = get_user_plan_limits(team.owner)
    max_members = limits.get("max_team_members", 0)
    current_count = members.count()
    brands = team.brands.all()
    recent_activities = team.activities.select_related("actor").order_by("-created_at")[:20]

    return render(request, "teams/detail.html", {
        "team": team,
        "member": member,
        "members": members,
        "pending_invitations": pending_invitations,
        "max_members": max_members,
        "current_count": current_count,
        "can_invite": member.can_manage_members and current_count < max_members,
        "brands": brands,
        "recent_activities": recent_activities,
    })


@login_required
def team_invite(request, slug):
    """Invite a user by email."""
    team = get_object_or_404(Team, slug=slug)
    member = _require_membership(request.user, team, min_role="admin")

    limits = get_user_plan_limits(team.owner)
    max_members = limits.get("max_team_members", 0)
    current_count = team.members.count()
    if current_count >= max_members:
        return plan_limit_redirect(
            request,
            f"Team is at capacity ({max_members} members). Upgrade the owner's plan for more.",
            "teams:detail",
            slug=slug,
        )

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", TeamMember.Role.EDITOR)

        if not email:
            messages.error(request, "Email is required.")
            return redirect("teams:detail", slug=slug)

        if role not in [
            TeamMember.Role.ADMIN,
            TeamMember.Role.EDITOR,
            TeamMember.Role.VIEWER,
            TeamMember.Role.CLIENT,
        ]:
            role = TeamMember.Role.EDITOR

        brand = None
        if role == TeamMember.Role.CLIENT:
            brand_id = request.POST.get("brand_id")
            if brand_id:
                brand = team.brands.filter(pk=brand_id).first()
            if not brand:
                messages.error(request, "Select a brand for client invitations.")
                return redirect("teams:detail", slug=slug)

        # Check if already a member
        if TeamMember.objects.filter(team=team, user__email=email).exists():
            messages.warning(request, f"{email} is already a team member.")
            return redirect("teams:detail", slug=slug)

        # Check for existing pending invite
        existing = TeamInvitation.objects.filter(
            team=team, email=email, accepted=False, expires_at__gt=timezone.now()
        ).first()
        if existing:
            messages.warning(request, f"A pending invitation already exists for {email}.")
            return redirect("teams:detail", slug=slug)

        token = secrets.token_urlsafe(48)
        TeamInvitation.objects.create(
            team=team,
            email=email,
            role=role,
            brand=brand,
            token=token,
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        TeamActivity.log(team, request.user, TeamActivity.EventType.INVITATION_SENT, f"Invited {email} as {role}", email=email, role=role)

        # Send invitation email
        from apps.emails.tasks import send_team_invitation_email
        from apps.utils import fire_task

        invite_url = request.build_absolute_uri(
            reverse("teams:invitation_accept", kwargs={"token": token})
        )
        fire_task(
            send_team_invitation_email,
            email,
            request.user.get_full_name() or request.user.email,
            team.name,
            invite_url,
        )

        messages.success(request, f"Invitation sent to {email}.")
        return redirect("teams:detail", slug=slug)

    return redirect("teams:detail", slug=slug)


@login_required
def invitation_accept(request, token):
    """Accept a team invitation."""
    invitation = get_object_or_404(TeamInvitation, token=token)

    if invitation.accepted:
        messages.info(request, "This invitation has already been accepted.")
        return redirect("teams:list")

    if invitation.is_expired:
        messages.error(request, "This invitation has expired. Ask the team admin to send a new one.")
        return redirect("teams:list")

    if invitation.email.lower() != request.user.email.lower():
        messages.error(request, "This invitation was sent to a different email address.")
        return redirect("teams:list")

    if request.method == "POST":
        # Accept
        if not TeamMember.objects.filter(team=invitation.team, user=request.user).exists():
            TeamMember.objects.create(
                team=invitation.team,
                user=request.user,
                role=invitation.role,
                invited_by=invitation.invited_by,
                brand=getattr(invitation, "brand", None) or invitation.brand,
            )
        invitation.accepted = True
        invitation.save(update_fields=["accepted"])
        TeamActivity.log(invitation.team, request.user, TeamActivity.EventType.MEMBER_JOINED, f"{request.user.email} joined as {invitation.get_role_display()}")
        messages.success(request, f'You joined "{invitation.team.name}" as {invitation.get_role_display()}.')
        return redirect("teams:detail", slug=invitation.team.slug)

    return render(request, "teams/invitation_accept.html", {
        "invitation": invitation,
    })


@login_required
def member_update_role(request, slug, member_id):
    """Change a team member's role. Owners and admins only."""
    team = get_object_or_404(Team, slug=slug)
    actor = _require_membership(request.user, team, min_role="admin")
    target = get_object_or_404(TeamMember, id=member_id, team=team)

    if target.role == TeamMember.Role.OWNER:
        messages.error(request, "Cannot change the owner's role.")
        return redirect("teams:detail", slug=slug)

    if actor.role != TeamMember.Role.OWNER and target.role == TeamMember.Role.ADMIN:
        messages.error(request, "Only the owner can change admin roles.")
        return redirect("teams:detail", slug=slug)

    if request.method == "POST":
        new_role = request.POST.get("role")
        if new_role in [TeamMember.Role.ADMIN, TeamMember.Role.EDITOR, TeamMember.Role.VIEWER]:
            target.role = new_role
            target.save(update_fields=["role"])
            TeamActivity.log(team, request.user, TeamActivity.EventType.ROLE_CHANGED, f"Changed {target.user.email} to {target.get_role_display()}", target_email=target.user.email, new_role=new_role)
            messages.success(request, f"Updated {target.user.email} to {target.get_role_display()}.")

    return redirect("teams:detail", slug=slug)


@login_required
def member_remove(request, slug, member_id):
    """Remove a member from the team."""
    team = get_object_or_404(Team, slug=slug)
    actor = _require_membership(request.user, team, min_role="admin")
    target = get_object_or_404(TeamMember, id=member_id, team=team)

    if target.role == TeamMember.Role.OWNER:
        messages.error(request, "Cannot remove the team owner.")
        return redirect("teams:detail", slug=slug)

    if target.user == request.user:
        messages.error(request, "Use 'Leave Team' instead of removing yourself.")
        return redirect("teams:detail", slug=slug)

    if request.method == "POST":
        email = target.user.email
        TeamActivity.log(team, request.user, TeamActivity.EventType.MEMBER_LEFT, f"Removed {email} from the team", email=email)
        target.delete()
        messages.success(request, f"Removed {email} from the team.")

    return redirect("teams:detail", slug=slug)


@login_required
def team_leave(request, slug):
    """Leave a team (non-owners only)."""
    team = get_object_or_404(Team, slug=slug)
    member = _require_membership(request.user, team)

    if member.role == TeamMember.Role.OWNER:
        messages.error(request, "Owners cannot leave their team. Transfer ownership first or delete the team.")
        return redirect("teams:detail", slug=slug)

    if request.method == "POST":
        TeamActivity.log(team, request.user, TeamActivity.EventType.MEMBER_LEFT, f"{request.user.email} left the team")
        member.delete()
        messages.success(request, f'You left "{team.name}".')
        return redirect("teams:list")

    return redirect("teams:detail", slug=slug)


@login_required
def invitation_cancel(request, slug, invitation_id):
    """Cancel a pending invitation."""
    team = get_object_or_404(Team, slug=slug)
    _require_membership(request.user, team, min_role="admin")
    invitation = get_object_or_404(TeamInvitation, id=invitation_id, team=team, accepted=False)

    if request.method == "POST":
        invitation.delete()
        messages.success(request, "Invitation cancelled.")

    return redirect("teams:detail", slug=slug)


# ─── Brand Management ────────────────────────────────────────────────────────


@login_required
def brand_create(request, slug):
    """Create a new brand within a team."""
    team = get_object_or_404(Team, slug=slug)
    _require_membership(request.user, team, min_role="admin")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Brand name is required.")
            return redirect("teams:detail", slug=slug)

        brand_slug = slugify(name)[:240]
        base_slug = brand_slug
        counter = 1
        while Brand.objects.filter(team=team, slug=brand_slug).exists():
            brand_slug = f"{base_slug}-{counter}"
            counter += 1

        Brand.objects.create(
            team=team,
            name=name,
            slug=brand_slug,
            brand_voice=request.POST.get("brand_voice", "").strip(),
            industry=request.POST.get("industry", "").strip(),
            website_url=request.POST.get("website_url", "").strip(),
            target_audience=request.POST.get("target_audience", "").strip(),
        )
        TeamActivity.log(team, request.user, TeamActivity.EventType.BRAND_CREATED, f'Created brand "{name}"', brand_name=name)
        messages.success(request, f'Brand "{name}" created.')
        return redirect("teams:detail", slug=slug)

    return redirect("teams:detail", slug=slug)


@login_required
def brand_edit(request, slug, brand_id):
    """Edit an existing brand."""
    team = get_object_or_404(Team, slug=slug)
    _require_membership(request.user, team, min_role="admin")
    brand = get_object_or_404(Brand, id=brand_id, team=team)

    if request.method == "POST":
        brand.name = request.POST.get("name", brand.name).strip()
        brand.brand_voice = request.POST.get("brand_voice", "").strip()
        brand.industry = request.POST.get("industry", "").strip()
        brand.website_url = request.POST.get("website_url", "").strip()
        brand.target_audience = request.POST.get("target_audience", "").strip()

        pillars_raw = request.POST.get("content_pillars", "").strip()
        if pillars_raw:
            brand.content_pillars = [p.strip() for p in pillars_raw.split(",") if p.strip()]
        else:
            brand.content_pillars = []

        goals_raw = request.POST.get("goals", "").strip()
        if goals_raw:
            brand.goals = [g.strip() for g in goals_raw.split(",") if g.strip()]
        else:
            brand.goals = []

        brand.custom_domain = request.POST.get("custom_domain", "").strip().lower()
        brand.theme_primary_color = request.POST.get("theme_primary_color", "").strip()
        brand.logo_url = request.POST.get("logo_url", "").strip()

        brand.save()
        TeamActivity.log(team, request.user, TeamActivity.EventType.BRAND_UPDATED, f'Updated brand "{brand.name}"', brand_id=str(brand.id))
        messages.success(request, f'Brand "{brand.name}" updated.')
        return redirect("teams:brand_detail", slug=slug, brand_id=brand.id)

    return render(request, "teams/brand_edit.html", {
        "team": team,
        "brand": brand,
    })


@login_required
def brand_detail(request, slug, brand_id):
    """View brand details + recent content."""
    team = get_object_or_404(Team, slug=slug)
    _require_membership(request.user, team)
    brand = get_object_or_404(Brand, id=brand_id, team=team)

    recent_posts = brand.posts.select_related("social_account", "user").order_by("-created_at")[:20]
    recent_seeds = brand.content_seeds.order_by("-created_at")[:10]

    return render(request, "teams/brand_detail.html", {
        "team": team,
        "brand": brand,
        "recent_posts": recent_posts,
        "recent_seeds": recent_seeds,
    })


@login_required
def brand_toggle(request, slug, brand_id):
    """Activate/deactivate a brand."""
    team = get_object_or_404(Team, slug=slug)
    _require_membership(request.user, team, min_role="admin")
    brand = get_object_or_404(Brand, id=brand_id, team=team)

    if request.method == "POST":
        brand.is_active = not brand.is_active
        brand.save(update_fields=["is_active"])
        state = "activated" if brand.is_active else "deactivated"
        messages.success(request, f'Brand "{brand.name}" {state}.')

    return redirect("teams:detail", slug=slug)


@login_required
def switch_agency_brand(request):
    """Agency client switcher — store active brand in session."""
    if request.method != "POST":
        return redirect("brief:home")

    from apps.teams.branding import _user_can_access_brand, get_agency_brands_for_user

    brand_id = request.POST.get("brand_id", "").strip()
    agency_brands = {str(b.pk): b for b in get_agency_brands_for_user(request.user)}

    if brand_id in agency_brands and _user_can_access_brand(request.user, agency_brands[brand_id]):
        request.session["agency_active_brand_id"] = brand_id
        messages.success(request, f"Switched to {agency_brands[brand_id].name}.")
    else:
        messages.error(request, "Could not switch to that client.")

    return redirect(request.META.get("HTTP_REFERER") or reverse("brief:home"))
