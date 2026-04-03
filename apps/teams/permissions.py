"""Team permission helpers for cross-app use."""

from .models import TeamMember


def get_teammate_ids(user):
    """Return user IDs of all teammates (including self).

    If the user has no teams, returns just their own ID.
    Used by content views to show team-shared posts.
    """
    team_ids = set(
        TeamMember.objects.filter(user=user).values_list("team_id", flat=True)
    )
    if not team_ids:
        return {user.id}
    return set(
        TeamMember.objects.filter(team_id__in=team_ids).values_list("user_id", flat=True)
    )


def can_approve_post(user, post):
    """Check if user can approve/reject a post.

    - Users can always approve their own posts
    - Team admins/owners can approve teammate posts
    """
    if post.user_id == user.id:
        return True

    # Check shared team membership with approver role
    user_teams = set(
        TeamMember.objects.filter(
            user=user, role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN]
        ).values_list("team_id", flat=True)
    )
    if not user_teams:
        return False

    post_owner_teams = set(
        TeamMember.objects.filter(user_id=post.user_id).values_list("team_id", flat=True)
    )
    return bool(user_teams & post_owner_teams)


def can_edit_post(user, post):
    """Check if user can edit a post.

    - Users can edit their own posts
    - Team admins/owners can edit teammate posts
    - Team editors can edit their own posts (already covered by first check)
    """
    return can_approve_post(user, post)
