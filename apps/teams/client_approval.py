"""Agency client campaign approval workflow."""

from __future__ import annotations


def request_client_approval(campaign, *, requested_by) -> None:
    """Mark campaign pending client sign-off (Agency brands)."""
    meta = dict(campaign.proposal_meta or {})
    meta["client_approval"] = {
        "status": "pending",
        "requested_by": str(getattr(requested_by, "pk", "")),
    }
    campaign.proposal_meta = meta
    campaign.save(update_fields=["proposal_meta", "updated_at"])


def client_approve_campaign(campaign, user) -> bool:
    """Client approves campaign for publishing."""
    from apps.teams.permissions import get_client_membership

    membership = get_client_membership(user)
    if not membership:
        return False
    meta = dict(campaign.proposal_meta or {})
    ca = meta.get("client_approval") or {}
    ca["status"] = "approved"
    ca["approved_by"] = str(user.pk)
    meta["client_approval"] = ca
    campaign.proposal_meta = meta
    campaign.save(update_fields=["proposal_meta", "updated_at"])
    return True
