"""Team permission helpers for cross-app use."""

from .models import TeamMember


def get_client_membership(user):
    """Return TeamMember row for client-role users."""
    if not user or not user.is_authenticated:
        return None
    return (
        TeamMember.objects.filter(user=user, role=TeamMember.Role.CLIENT)
        .select_related("brand", "team")
        .first()
    )


def get_client_brand_scope(user):
    """
    Return brand_id for client-role users, else None.
    Clients see only content tagged with their assigned brand.
    """
    membership = get_client_membership(user)
    if membership and membership.brand_id:
        return membership.brand_id
    return None


def get_scoped_post_queryset(user):
    """Base Post queryset respecting client brand scoping."""
    from apps.create.content.models import Post

    membership = get_client_membership(user)
    if membership and membership.brand_id:
        teammate_ids = TeamMember.objects.filter(team=membership.team_id).values_list(
            "user_id", flat=True,
        )
        return Post.objects.filter(user_id__in=teammate_ids, brand_id=membership.brand_id)
    return Post.objects.filter(user=user)


def filter_posts_by_brand_scope(qs, user):
    """Filter a Post queryset for client-role brand scoping."""
    brand_id = get_client_brand_scope(user)
    if brand_id:
        membership = get_client_membership(user)
        if membership:
            teammate_ids = TeamMember.objects.filter(team=membership.team_id).values_list(
                "user_id", flat=True,
            )
            return qs.filter(user_id__in=teammate_ids, brand_id=brand_id)
        return qs.filter(brand_id=brand_id)
    return qs


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
