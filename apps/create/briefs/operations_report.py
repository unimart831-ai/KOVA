"""Unified task / operations report for the Daily Brief."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone as tz

# Human labels + category for agent action types
ACTION_META = {
    "snap.vision": ("products", "Snap to Sell", "Analyzed product photos and launched content"),
    "snap.vision_batch": ("products", "Batch Snap", "Identified and listed batch products"),
    "snap.carousel": ("products", "Product carousel", "Built swipeable carousel posts"),
    "snap.reel": ("products", "Motion reel", "Composed motion reel from product photos"),
    "receipt_to_restock": ("inventory", "Receipt to Restock", "Extracted receipt items and updated stock"),
    "generate_daily_brief": ("strategist", "Daily brief", "Compiled your morning briefing"),
    "discover_trends": ("research", "Trend research", "Scanned trending topics in your niche"),
    "generate_from_seed": ("content", "Content generation", "Drafted platform posts from a seed"),
    "process_voice_brief": ("content", "Voice brief", "Turned voice memo into a campaign"),
    "engage.reply": ("engage", "Engagement reply", "Replied to a comment or message"),
    "engage.auto_reply": ("engage", "Auto-reply", "Sent an autonomous engagement reply"),
}


def _category_defs():
    return {
        "products": {
            "label": "Products & Snap",
            "description": "Snap to Sell, batch listings, carousels, and reels",
            "url_name": "products:list",
        },
        "inventory": {
            "label": "Inventory & Restock",
            "description": "Receipt scans, stock updates, and catalog changes",
            "url_name": "products:restock",
        },
        "content": {
            "label": "Content Studio",
            "description": "Seeds, drafts, voice briefs, and publishing",
            "url_name": "content:studio",
        },
        "engage": {
            "label": "Engagement",
            "description": "Comments, messages, and inbox activity",
            "url_name": "whatsapp:inbox",
        },
        "reviews": {
            "label": "Reviews",
            "description": "Review requests and testimonial content",
            "url_name": "leads:list",
        },
        "leads": {
            "label": "Leads & Bookings",
            "description": "New leads, walk-ins, and completed bookings",
            "url_name": "leads:list",
        },
        "research": {
            "label": "Research & Intel",
            "description": "Trends, competitors, and market scans",
            "url_name": "agents:activity_log",
        },
        "strategist": {
            "label": "Strategy",
            "description": "Briefings and strategic planning",
            "url_name": "brief:home",
        },
    }


def _empty_category(cat_id, cat_def):
    return {
        "id": cat_id,
        "label": cat_def["label"],
        "description": cat_def["description"],
        "url_name": cat_def["url_name"],
        "count": 0,
        "items": [],
    }


def build_operations_report(user, hours=24):
    """
    Aggregate completed tasks across products, content, engage, and more.
    Powers the Daily Brief operations report panel.
    """
    from apps.create.agents.models import AgentAction

    cutoff = tz.now() - timedelta(hours=hours)
    cats = _category_defs()
    categories = {k: _empty_category(k, v) for k, v in cats.items()}
    recent_tasks = []

    actions = AgentAction.objects.filter(
        user=user,
        created_at__gte=cutoff,
    ).order_by("-created_at")

    completed_actions = actions.filter(status=AgentAction.ActionStatus.COMPLETED)

    # ── Agent actions by type ──
    action_counts = dict(
        completed_actions.values("action_type")
        .annotate(n=Count("id"))
        .values_list("action_type", "n")
    )

    for action_type, count in action_counts.items():
        cat_id, label, detail = ACTION_META.get(
            action_type,
            (None, action_type.replace("_", " ").replace(".", " ").title(), ""),
        )
        if not cat_id or cat_id not in categories:
            # Map by agent_type prefix when action_type unknown
            sample = completed_actions.filter(action_type=action_type).first()
            if sample:
                agent_map = {
                    "create": "content",
                    "engage": "engage",
                    "research": "research",
                    "analyst": "research",
                    "adapt": "content",
                    "strategist": "strategist",
                }
                cat_id = agent_map.get(sample.agent_type, "content")
            else:
                cat_id = "content"
            label = action_type.replace("_", " ").replace(".", " ").title()
            detail = sample.description[:80] if sample and sample.description else ""

        categories[cat_id]["items"].append({
            "label": label,
            "count": count,
            "detail": detail,
        })
        categories[cat_id]["count"] += count

    # ── Products: snap-created listings ──
    try:
        from apps.commerce.products.models import Product

        snap_products = Product.objects.filter(
            user=user,
            source=Product.Source.SNAP,
            created_at__gte=cutoff,
        ).count()
        if snap_products:
            categories["products"]["items"].append({
                "label": "New snap listings",
                "count": snap_products,
                "detail": "Products added via Snap to Sell or Batch Snap",
            })
            categories["products"]["count"] += snap_products
    except Exception:
        pass

    # ── Inventory: restock scans ──
    try:
        from apps.commerce.products.models import RestockScan

        scans = RestockScan.objects.filter(user=user, created_at__gte=cutoff)
        completed_scans = scans.filter(status=RestockScan.Status.COMPLETED)
        failed_scans = scans.filter(status=RestockScan.Status.FAILED)
        items_updated = completed_scans.aggregate(
            total=Sum("products_updated"),
        )["total"] or 0

        if scans.exists():
            categories["inventory"]["items"].append({
                "label": "Receipt scans",
                "count": scans.count(),
                "detail": f"{completed_scans.count()} completed"
                + (f", {items_updated} products restocked" if items_updated else ""),
            })
            categories["inventory"]["count"] += scans.count()

        if failed_scans.exists():
            categories["inventory"]["items"].append({
                "label": "Failed receipt scans",
                "count": failed_scans.count(),
                "detail": "Needs retry or clearer photo",
            })
    except Exception:
        pass

    # ── Inventory: stock updates ──
    try:
        from apps.commerce.products.models import StockUpdate

        stock_changes = StockUpdate.objects.filter(
            product__user=user,
            created_at__gte=cutoff,
        ).count()
        if stock_changes:
            categories["inventory"]["items"].append({
                "label": "Stock level changes",
                "count": stock_changes,
                "detail": "Manual updates, sales, and restock events",
            })
            categories["inventory"]["count"] += stock_changes
    except Exception:
        pass

    # ── Content: seeds & posts ──
    try:
        from apps.create.content.models import ContentSeed, Post

        seeds = ContentSeed.objects.filter(user=user, created_at__gte=cutoff).count()
        if seeds:
            categories["content"]["items"].append({
                "label": "Content seeds created",
                "count": seeds,
                "detail": "New campaign ideas queued for Create Agent",
            })
            categories["content"]["count"] += seeds

        drafts = Post.objects.filter(
            user=user,
            created_at__gte=cutoff,
            status__in=["draft", "pending_approval"],
        ).count()
        if drafts:
            categories["content"]["items"].append({
                "label": "Posts drafted",
                "count": drafts,
                "detail": "Awaiting your review in Studio or Queue",
            })
            categories["content"]["count"] += drafts

        published = Post.objects.filter(
            user=user,
            published_at__gte=cutoff,
            status="published",
        ).count()
        if published:
            categories["content"]["items"].append({
                "label": "Posts published",
                "count": published,
                "detail": "Live on connected platforms",
            })
            categories["content"]["count"] += published

        reels = Post.objects.filter(
            user=user,
            created_at__gte=cutoff,
            post_format="reel",
        ).count()
        if reels:
            categories["content"]["items"].append({
                "label": "Motion reels",
                "count": reels,
                "detail": "Reel-format posts created or composed",
            })
            categories["content"]["count"] += reels
    except Exception:
        pass

    # ── Voice briefs ──
    try:
        from apps.create.content.models import VoiceBrief

        voice_done = VoiceBrief.objects.filter(
            user=user,
            completed_at__gte=cutoff,
            status=VoiceBrief.Status.COMPLETED,
        ).count()
        if voice_done:
            categories["content"]["items"].append({
                "label": "Voice briefs processed",
                "count": voice_done,
                "detail": "Voice memos turned into campaigns",
            })
            categories["content"]["count"] += voice_done
    except Exception:
        pass

    # ── Engage / reviews / leads from action summary ──
    try:
        from apps.create.briefs.tasks import _build_action_summary

        action_summary = _build_action_summary(user)
        engage = action_summary.get("engage", {})
        if engage.get("auto_sent"):
            categories["engage"]["items"].append({
                "label": "Auto-replies sent",
                "count": engage["auto_sent"],
                "detail": "Comments handled without needing you",
            })
            categories["engage"]["count"] += engage["auto_sent"]
        if engage.get("escalated"):
            categories["engage"]["items"].append({
                "label": "Escalated to you",
                "count": engage["escalated"],
                "detail": "Flagged for owner review",
            })
            categories["engage"]["count"] += engage["escalated"]

        reviews = action_summary.get("reviews", {})
        review_total = (
            reviews.get("scheduled", 0)
            + reviews.get("sent", 0)
            + reviews.get("positive_seeds", 0)
        )
        if review_total:
            categories["reviews"]["items"].append({
                "label": "Review outreach",
                "count": review_total,
                "detail": "Requests sent and testimonial seeds created",
            })
            categories["reviews"]["count"] += review_total

        if action_summary.get("walk_ins"):
            categories["leads"]["items"].append({
                "label": "Walk-ins recorded",
                "count": action_summary["walk_ins"],
                "detail": "In-store visits attributed",
            })
            categories["leads"]["count"] += action_summary["walk_ins"]

        if action_summary.get("bookings_completed"):
            categories["leads"]["items"].append({
                "label": "Bookings completed",
                "count": action_summary["bookings_completed"],
                "detail": "Appointments marked done",
            })
            categories["leads"]["count"] += action_summary["bookings_completed"]
    except Exception:
        pass

    # ── New leads ──
    try:
        from apps.commerce.leads.models import Lead

        new_leads = Lead.objects.filter(
            user=user,
            first_seen_at__gte=cutoff,
        ).count()
        if new_leads:
            categories["leads"]["items"].append({
                "label": "New leads captured",
                "count": new_leads,
                "detail": "Fresh pipeline opportunities",
            })
            categories["leads"]["count"] += new_leads
    except Exception:
        pass

    # ── Recent task timeline (from agent actions) ──
    for action in actions[:20]:
        cat_id, label, _ = ACTION_META.get(
            action.action_type,
            (action.agent_type, action.action_type.replace(".", " ").title(), ""),
        )
        recent_tasks.append({
            "id": str(action.pk),
            "label": label if label else action.description[:60],
            "description": action.description[:120],
            "category": cat_id or action.agent_type,
            "category_label": (
                categories[cat_id]["label"]
                if cat_id in categories
                else action.agent_type.replace("_", " ").title()
            ),
            "status": action.status,
            "agent_type": action.agent_type,
            "time": action.created_at.isoformat(),
            "time_display": action.created_at.strftime("%H:%M"),
        })

    # Drop empty categories, sort by count
    category_list = [
        c for c in categories.values()
        if c["count"] > 0 or c["items"]
    ]
    category_list.sort(key=lambda c: c["count"], reverse=True)

    total_tasks = sum(c["count"] for c in category_list)

    return {
        "window_hours": hours,
        "total_tasks": total_tasks,
        "categories": category_list,
        "recent_tasks": recent_tasks[:15],
        "has_activity": total_tasks > 0 or bool(recent_tasks),
    }


def enrich_overnight_work(user, base=None):
    """Extend overnight_work dict with product/inventory task counts."""
    from apps.create.agents.models import AgentAction

    base = dict(base or {})
    cutoff = tz.now() - timedelta(hours=12)

    actions = AgentAction.objects.filter(
        user=user,
        created_at__gte=cutoff,
        status=AgentAction.ActionStatus.COMPLETED,
    )

    def _count(action_type):
        return actions.filter(action_type=action_type).count()

    base["snap_launches"] = _count("snap.vision")
    base["batch_snaps"] = _count("snap.vision_batch")
    base["carousels_built"] = _count("snap.carousel")
    base["reels_composed"] = _count("snap.reel")
    base["receipt_scans"] = _count("receipt_to_restock")

    try:
        from apps.commerce.products.models import RestockScan

        base["products_restocked"] = (
            RestockScan.objects.filter(
                user=user,
                completed_at__gte=cutoff,
                status=RestockScan.Status.COMPLETED,
            ).aggregate(total=Sum("products_updated"))["total"]
            or 0
        )
    except Exception:
        base["products_restocked"] = 0

    try:
        from apps.create.content.models import VoiceBrief

        base["voice_briefs"] = VoiceBrief.objects.filter(
            user=user,
            completed_at__gte=cutoff,
            status=VoiceBrief.Status.COMPLETED,
        ).count()
    except Exception:
        base["voice_briefs"] = 0

    return base


def build_platform_operations_report(hours=24):
    """
    Platform-wide task aggregation for the admin Operations dashboard.
    Mirrors build_operations_report() but aggregates across all users.
    """
    from apps.create.agents.models import AgentAction
    from apps.create.content.models import ContentSeed, Post, VoiceBrief
    from apps.commerce.leads.models import Lead
    from apps.commerce.products.models import Product, RestockScan, StockUpdate

    cutoff = tz.now() - timedelta(hours=hours)
    cats = _category_defs()
    categories = {k: _empty_category(k, v) for k, v in cats.items()}

    completed = AgentAction.objects.filter(
        created_at__gte=cutoff,
        status=AgentAction.ActionStatus.COMPLETED,
    )

    action_counts = dict(
        completed.values("action_type")
        .annotate(n=Count("id"))
        .values_list("action_type", "n")
    )

    for action_type, count in action_counts.items():
        cat_id, label, detail = ACTION_META.get(
            action_type,
            (None, action_type.replace("_", " ").replace(".", " ").title(), ""),
        )
        if not cat_id or cat_id not in categories:
            sample = completed.filter(action_type=action_type).first()
            agent_map = {
                "create": "content",
                "engage": "engage",
                "research": "research",
                "analyst": "research",
                "adapt": "content",
                "strategist": "strategist",
            }
            cat_id = agent_map.get(sample.agent_type, "content") if sample else "content"
            label = action_type.replace("_", " ").replace(".", " ").title()
            detail = sample.description[:80] if sample and sample.description else ""

        categories[cat_id]["items"].append({
            "label": label,
            "count": count,
            "detail": detail,
        })
        categories[cat_id]["count"] += count

    snap_products = Product.objects.filter(
        source=Product.Source.SNAP,
        created_at__gte=cutoff,
    ).count()
    if snap_products:
        categories["products"]["items"].append({
            "label": "New snap listings",
            "count": snap_products,
            "detail": "Products added via Snap to Sell or Batch Snap",
        })
        categories["products"]["count"] += snap_products

    scans = RestockScan.objects.filter(created_at__gte=cutoff)
    completed_scans = scans.filter(status=RestockScan.Status.COMPLETED)
    failed_scans = scans.filter(status=RestockScan.Status.FAILED)
    items_updated = completed_scans.aggregate(total=Sum("products_updated"))["total"] or 0

    if scans.exists():
        categories["inventory"]["items"].append({
            "label": "Receipt scans",
            "count": scans.count(),
            "detail": f"{completed_scans.count()} completed"
            + (f", {items_updated} products restocked" if items_updated else ""),
        })
        categories["inventory"]["count"] += scans.count()

    if failed_scans.exists():
        categories["inventory"]["items"].append({
            "label": "Failed receipt scans",
            "count": failed_scans.count(),
            "detail": "Needs retry or clearer photo",
        })

    stock_changes = StockUpdate.objects.filter(created_at__gte=cutoff).count()
    if stock_changes:
        categories["inventory"]["items"].append({
            "label": "Stock level changes",
            "count": stock_changes,
            "detail": "Manual updates, sales, and restock events",
        })
        categories["inventory"]["count"] += stock_changes

    seeds = ContentSeed.objects.filter(created_at__gte=cutoff).count()
    if seeds:
        categories["content"]["items"].append({
            "label": "Content seeds created",
            "count": seeds,
            "detail": "New campaign ideas queued for Create Agent",
        })
        categories["content"]["count"] += seeds

    catalog_samples = ContentSeed.objects.filter(
        created_at__gte=cutoff,
        notes__startswith="Catalog sample:",
    ).count()
    if catalog_samples:
        categories["content"]["items"].append({
            "label": "Catalog sample seeds",
            "count": catalog_samples,
            "detail": "Rotating product promotion into content",
        })
        categories["content"]["count"] += catalog_samples

    published = Post.objects.filter(
        published_at__gte=cutoff,
        status="published",
    ).count()
    if published:
        categories["content"]["items"].append({
            "label": "Posts published",
            "count": published,
            "detail": "Live on connected platforms",
        })
        categories["content"]["count"] += published

    reels = Post.objects.filter(created_at__gte=cutoff, post_format="reel").count()
    if reels:
        categories["content"]["items"].append({
            "label": "Motion reels",
            "count": reels,
            "detail": "Reel-format posts created or composed",
        })
        categories["content"]["count"] += reels

    voice_done = VoiceBrief.objects.filter(
        completed_at__gte=cutoff,
        status=VoiceBrief.Status.COMPLETED,
    ).count()
    if voice_done:
        categories["content"]["items"].append({
            "label": "Voice briefs processed",
            "count": voice_done,
            "detail": "Voice memos turned into campaigns",
        })
        categories["content"]["count"] += voice_done

    new_leads = Lead.objects.filter(first_seen_at__gte=cutoff).count()
    if new_leads:
        categories["leads"]["items"].append({
            "label": "New leads captured",
            "count": new_leads,
            "detail": "Fresh pipeline opportunities",
        })
        categories["leads"]["count"] += new_leads

    recent_tasks = []
    for action in AgentAction.objects.select_related("user").filter(
        created_at__gte=cutoff,
    ).order_by("-created_at")[:25]:
        cat_id, label, _ = ACTION_META.get(
            action.action_type,
            (action.agent_type, action.action_type.replace(".", " ").title(), ""),
        )
        recent_tasks.append({
            "id": str(action.pk),
            "label": label if label else action.description[:60],
            "description": action.description[:120],
            "category": cat_id or action.agent_type,
            "category_label": (
                categories[cat_id]["label"]
                if cat_id in categories
                else action.agent_type.replace("_", " ").title()
            ),
            "status": action.status,
            "user_email": action.user.email if action.user_id else "",
            "time_display": action.created_at.strftime("%H:%M"),
            "created_at": action.created_at,
        })

    category_list = [c for c in categories.values() if c["count"] > 0 or c["items"]]
    category_list.sort(key=lambda c: c["count"], reverse=True)
    total_tasks = sum(c["count"] for c in category_list)

    active_users = AgentAction.objects.filter(
        created_at__gte=cutoff,
    ).values("user").distinct().count()

    return {
        "window_hours": hours,
        "total_tasks": total_tasks,
        "active_users": active_users,
        "categories": category_list,
        "recent_tasks": recent_tasks[:20],
        "has_activity": total_tasks > 0 or bool(recent_tasks),
    }
