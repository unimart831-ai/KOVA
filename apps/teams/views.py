import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from apps.billing.models import get_plan_limits

from .models import Team, TeamInvitation, TeamMember

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
    limits = get_plan_limits(user.profile.plan)
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
        messages.error(request, "Upgrade to Pro or Agency to use team features.")
        return redirect("billing:pricing")

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

    limits = get_plan_limits(team.owner.profile.plan)
    max_members = limits.get("max_team_members", 0)
    current_count = members.count()

    return render(request, "teams/detail.html", {
        "team": team,
        "member": member,
        "members": members,
        "pending_invitations": pending_invitations,
        "max_members": max_members,
        "current_count": current_count,
        "can_invite": member.can_manage_members and current_count < max_members,
    })


@login_required
def team_invite(request, slug):
    """Invite a user by email."""
    team = get_object_or_404(Team, slug=slug)
    member = _require_membership(request.user, team, min_role="admin")

    limits = get_plan_limits(team.owner.profile.plan)
    max_members = limits.get("max_team_members", 0)
    current_count = team.members.count()
    if current_count >= max_members:
        messages.error(request, f"Team is at capacity ({max_members} members). Upgrade the owner's plan for more.")
        return redirect("teams:detail", slug=slug)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        role = request.POST.get("role", TeamMember.Role.EDITOR)

        if not email:
            messages.error(request, "Email is required.")
            return redirect("teams:detail", slug=slug)

        if role not in [TeamMember.Role.ADMIN, TeamMember.Role.EDITOR, TeamMember.Role.VIEWER]:
            role = TeamMember.Role.EDITOR

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
            token=token,
            invited_by=request.user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
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
            )
        invitation.accepted = True
        invitation.save(update_fields=["accepted"])
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
