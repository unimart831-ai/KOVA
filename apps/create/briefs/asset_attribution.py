"""Top asset attribution for revenue board (Wave 7)."""

from __future__ import annotations

from django.db.models import Count, Sum

PROFESSIONAL_ASSET_TYPES = frozenset({"portfolio", "case_study", "testimonial"})


def asset_type_label(asset_type: str) -> str:
    labels = {
        "product": "Product",
        "service": "Service",
        "digital": "Digital",
        "portfolio": "Portfolio",
        "case_study": "Case study",
        "testimonial": "Testimonial",
    }
    return labels.get(asset_type or "", "Offer")


def top_asset_this_week(user, since, *, business_model: str = "") -> dict:
    """
    Best-performing asset this week — M-Pesa, bookings, or showcase activity.
  Returns title, revenue, asset_type, type_label, source, signals (tie-breaker).
    """
    candidates: list[dict] = []
    candidates.extend(_mpesa_candidates(user, since))
    candidates.extend(_booking_candidates(user, since))

    if business_model == "professional":
        candidates.extend(_professional_showcase_candidates(user, since))

    if not candidates:
        return {}

    best = max(candidates, key=lambda row: (row["revenue"], row.get("signals", 0)))
    asset_type = best.get("asset_type", "product")
    return {
        "title": best["title"],
        "revenue": best["revenue"],
        "sales": best.get("sales", 0),
        "asset_type": asset_type,
        "type_label": asset_type_label(asset_type),
        "source": best.get("source", ""),
        "signals": best.get("signals", 0),
    }


def _mpesa_candidates(user, since) -> list[dict]:
    from apps.commerce.products.models import BusinessAsset, CommercePayment

    rows = (
        CommercePayment.objects.filter(
            user=user,
            status=CommercePayment.Status.COMPLETED,
            completed_at__gte=since,
            product__isnull=False,
        )
        .values("product_id")
        .annotate(revenue=Sum("amount"), sales=Count("id"))
        .order_by("-revenue")
    )
    out = []
    for row in rows:
        asset = BusinessAsset.objects.filter(product_id=row["product_id"], user=user).first()
        title = asset.title if asset else "Top product"
        out.append({
            "title": title,
            "revenue": float(row["revenue"] or 0),
            "sales": row["sales"] or 0,
            "asset_type": asset.asset_type if asset else "product",
            "source": "mpesa",
            "signals": row["sales"] or 0,
        })
    return out


def _booking_candidates(user, since) -> list[dict]:
    from apps.commerce.bookings.models import Booking
    from apps.commerce.products.models import BusinessAsset

    rows = (
        Booking.objects.filter(
            booking_link__user=user,
            status__in=(Booking.Status.CONFIRMED, Booking.Status.COMPLETED),
            created_at__gte=since,
        )
        .values("service_name")
        .annotate(revenue=Sum("price_kes"), sales=Count("id"))
        .order_by("-revenue")
    )
    out = []
    for row in rows:
        service = (row["service_name"] or "").strip()
        asset = (
            BusinessAsset.objects.filter(user=user, title__iexact=service).first()
            if service
            else None
        )
        asset_type = asset.asset_type if asset else "service"
        out.append({
            "title": asset.title if asset else (service or "Bookings"),
            "revenue": float(row["revenue"] or 0),
            "sales": row["sales"] or 0,
            "asset_type": asset_type,
            "source": "booking",
            "signals": row["sales"] or 0,
        })
    return out


def _professional_showcase_candidates(user, since) -> list[dict]:
    """Rank portfolio / case study assets by posts + leads when revenue is thin."""
    from apps.create.content.models import Post
    from apps.commerce.leads.models import Lead
    from apps.commerce.products.models import BusinessAsset

    assets = BusinessAsset.objects.filter(
        user=user,
        asset_type__in=PROFESSIONAL_ASSET_TYPES,
    )
    out = []
    for asset in assets:
        post_count = Post.objects.filter(
            user=user,
            created_at__gte=since,
            seed__product_id=asset.product_id,
        ).count() if asset.product_id else 0

        if not post_count and asset.product_id is None:
            post_count = Post.objects.filter(
                user=user,
                created_at__gte=since,
                seed__blueprint__asset_type=asset.asset_type,
            ).count()

        lead_count = 0
        if asset.asset_type in ("portfolio", "case_study"):
            lead_count = Lead.objects.filter(
                user=user,
                last_activity_at__gte=since,
                temperature=Lead.Temperature.HOT,
            ).count()

        signals = post_count * 2 + lead_count
        if signals <= 0:
            continue
        out.append({
            "title": asset.title,
            "revenue": 0.0,
            "sales": post_count,
            "asset_type": asset.asset_type,
            "source": "showcase",
            "signals": signals,
        })
    return out


def asset_type_breakdown(user, since) -> list[dict]:
    """
    Revenue + activity grouped by BusinessAsset type for analytics charts.
    Merges M-Pesa, bookings, and showcase signal counts.
    """
    buckets: dict[str, dict] = {}

    def _bucket(asset_type: str) -> dict:
        key = asset_type or "product"
        if key not in buckets:
            buckets[key] = {
                "asset_type": key,
                "type_label": asset_type_label(key),
                "revenue": 0.0,
                "sales": 0,
                "activity": 0,
            }
        return buckets[key]

    for row in _mpesa_candidates(user, since):
        b = _bucket(row["asset_type"])
        b["revenue"] += row["revenue"]
        b["sales"] += row.get("sales", 0)

    for row in _booking_candidates(user, since):
        b = _bucket(row["asset_type"])
        b["revenue"] += row["revenue"]
        b["sales"] += row.get("sales", 0)

    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "business_model", "") == "professional":
        for row in _professional_showcase_candidates(user, since):
            b = _bucket(row["asset_type"])
            b["activity"] += row.get("signals", 0)
            b["sales"] += row.get("sales", 0)

    rows = list(buckets.values())
    rows.sort(key=lambda r: (-r["revenue"], -r["activity"], r["type_label"]))
    return rows


def attribution_confidence_score(user, since) -> dict:
    """
    Wave 7 attribution confidence — 0–100 score with factors and one improvement tip.
    """
    from apps.create.content.models import Post
    from apps.commerce.leads.models import Lead
    from apps.commerce.products.models import CommercePayment

    score = 0
    factors: list[str] = []
    tips: list[str] = []

    breakdown = asset_type_breakdown(user, since)
    total_rev = sum(r["revenue"] for r in breakdown)

    payments = CommercePayment.objects.filter(
        user=user,
        status=CommercePayment.Status.COMPLETED,
        completed_at__gte=since,
    )
    total_payments = payments.count()
    linked_payments = payments.filter(product__isnull=False).count()
    if total_payments:
        pct = linked_payments / total_payments * 100
        if pct >= 80:
            score += 25
            factors.append(f"{pct:.0f}% of M-Pesa sales linked to offers")
        elif pct >= 50:
            score += 15
            factors.append(f"{pct:.0f}% of sales attributed to offers")
            tips.append("Link every sale to an offer in Commerce for clearer post attribution.")
        else:
            score += 8
            tips.append("Snap products with prices so M-Pesa payments tie back to posts.")
    else:
        tips.append("Share shop links or QR codes to start proving which posts drive sales.")

    published = Post.objects.filter(
        user=user,
        status=Post.Status.PUBLISHED,
        published_at__gte=since,
    )
    pub_count = published.count()
    if pub_count:
        with_product = published.filter(product__isnull=False).count()
        post_pct = with_product / pub_count * 100
        if post_pct >= 50:
            score += 20
            factors.append(f"{post_pct:.0f}% of published posts promote a specific offer")
        elif post_pct >= 25:
            score += 12
            factors.append(f"{post_pct:.0f}% of posts tied to offers")
            tips.append("Attach an offer when approving posts so revenue traces to content.")
        else:
            score += 5
            tips.append("Promote specific offers from Studio — not generic posts.")

    leads = Lead.objects.filter(user=user, first_seen_at__gte=since)
    lead_count = leads.count()
    if lead_count:
        with_source = leads.exclude(source_type=Lead.Source.MANUAL).exclude(source_type=Lead.Source.IMPORT).count()
        src_pct = with_source / lead_count * 100
        if src_pct >= 60:
            score += 15
            factors.append(f"{src_pct:.0f}% of leads have a known source")
        else:
            score += 8
            tips.append("Use Kova Links and QR codes so every lead shows where it came from.")

    profile = getattr(user, "profile", None)
    bm = getattr(profile, "business_model", "") if profile else ""
    if bm == "professional" and any(r.get("activity") for r in breakdown):
        score += 10
        factors.append("Portfolio and case-study activity tracked")

    if total_rev > 0:
        score += 20
        factors.append("Revenue recorded in this period")
    elif breakdown:
        score += 10
        factors.append("Asset-level activity tracked")

    if not factors:
        factors.append("Connect platforms and publish to build attribution confidence")

    score = min(100, max(0, score))
    if score >= 75:
        label = "Strong"
    elif score >= 50:
        label = "Growing"
    else:
        label = "Building"

    return {
        "score": score,
        "label": label,
        "factors": factors[:4],
        "tip": tips[0] if tips else "",
    }
