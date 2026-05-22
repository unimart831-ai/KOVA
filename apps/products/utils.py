"""
Product & Service Intelligence Utilities — Offering-Aware AI.

The intelligence layer that makes every Kova agent aware of what the business sells:
  - Physical products: stock-aware (urgency for low stock, skip OOS)
  - Services: always available, promote freely, highlight booking/scheduling
  - Digital products: unlimited supply, no stock constraints
  - Create Agent: writes about offerings with the right framing
  - Engage Agent: answers questions with real catalog data
  - Strategist: plans content around offerings, stock (products only), and demand
  - Research Agent: discovers trends relevant to what the business offers
  - Daily Brief: offering pulse, stock-content mismatches (products only), demand signals

This is NOT inventory management. This is inventory AWARENESS for the AI.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q, Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Core Product Context (injected into all agent prompts) ──────────────────

def get_product_context(user) -> str:
    """
    Build a formatted catalog summary for injection into agent prompts.
    Handles physical products (stock-aware), services, and digital products differently.
    Returns empty string if user has no offerings.
    Cached for 5 minutes to avoid repeated DB queries per agent call.
    """
    cache_key = f"product_context:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.products.models import Product

    products = Product.objects.filter(user=user, is_active=True).select_related("category").order_by(
        "-is_featured", "stock_status", "name"
    )[:50]

    if not products:
        cache.set(cache_key, "", 300)
        return ""

    # Separate by offering type
    services = []
    digital = []
    in_stock = []
    low_stock = []
    out_of_stock = []
    featured = []

    for p in products:
        line = f"• {p.name}"
        if p.display_price:
            line += f" — {p.display_price}"
        if p.product_url:
            line += f" → {p.product_url}"
        if p.is_featured:
            line += " [FEATURED]"
        if p.tags:
            line += f" {{{', '.join(p.tags)}}}"
        if p.category:
            line += f" ({p.category.name})"

        if p.offering_type == Product.OfferingType.SERVICE:
            services.append(line)
        elif p.offering_type == Product.OfferingType.DIGITAL:
            digital.append(line)
        elif p.stock_status == Product.StockStatus.OUT_OF_STOCK:
            out_of_stock.append(line)
        elif p.stock_status == Product.StockStatus.LOW_STOCK:
            if p.quantity is not None:
                line += f" [{p.quantity} units]"
            low_stock.append(line)
        else:
            if p.quantity is not None:
                line += f" [{p.quantity} units]"
            in_stock.append(line)

        if p.is_featured:
            featured.append(p.name)

    # Determine header based on what the business sells
    has_products = bool(in_stock or low_stock or out_of_stock)
    has_services = bool(services)
    has_digital = bool(digital)

    if has_services and not has_products:
        header = "## SERVICE CATALOG — OFFERING-AWARE INTELLIGENCE"
    elif has_products and not has_services:
        header = "## PRODUCT CATALOG — STOCK-AWARE INTELLIGENCE"
    else:
        header = "## CATALOG — OFFERING-AWARE INTELLIGENCE"

    parts = [header]
    parts.append("The business offers these products/services. Content must be offering-aware.\n")

    if services:
        parts.append("**🔧 SERVICES (always available — promote freely):**")
        parts.extend(services)
        parts.append("→ Services are always available. Focus on value, results, and booking/scheduling.")
        parts.append("→ Use language like 'book now', 'get started', 'schedule a call', 'let us help'.")
        parts.append("")

    if digital:
        parts.append("**💻 DIGITAL PRODUCTS (unlimited supply — promote freely):**")
        parts.extend(digital)
        parts.append("→ No stock constraints. Focus on value, instant access, and results.")
        parts.append("")

    if in_stock:
        parts.append("**✅ PRODUCTS IN STOCK (promote these):**")
        parts.extend(in_stock)
        parts.append("")

    if low_stock:
        parts.append("**⚠️ LOW STOCK (create urgency/scarcity content):**")
        parts.extend(low_stock)
        parts.append("→ Use scarcity language: 'Only X left', 'Almost gone', 'Grab yours before they sell out'")
        parts.append("")

    if out_of_stock:
        parts.append("**🔴 OUT OF STOCK — DO NOT PROMOTE:**")
        parts.extend(out_of_stock)
        parts.append("→ If asked about these, suggest in-stock alternatives. NEVER confirm availability.")
        parts.append("")

    if featured:
        parts.append(f"**⭐ FEATURED (push harder in content):** {', '.join(featured)}")
        parts.append("→ These items should get 2-3x more content mentions than non-featured items.")
        parts.append("")

    # Demand signals — what the audience is asking about
    demand = _get_demand_signals(user)
    if demand:
        parts.append("**📈 DEMAND SIGNALS (what your audience is asking about):**")
        for signal in demand[:5]:
            parts.append(f"  • \"{signal['keyword']}\" — mentioned {signal['count']}x in comments/DMs this week")
        parts.append("→ Create content that addresses these topics. Your audience is already interested.")
        parts.append("")

    parts.append("CONTENT RULES:")
    parts.append("1. NEVER create content promoting out-of-stock physical products.")
    parts.append("2. For LOW STOCK physical products: urgency language ('limited stock', 'almost gone').")
    parts.append("3. For SERVICES: promote freely. Use booking/scheduling language, not stock language.")
    parts.append("4. For FEATURED items: prioritize in content. Mention naturally, not forced.")
    parts.append("5. Reference REAL prices and names from the catalog — don't invent them.")
    parts.append("6. If a seed mentions a specific offering, match the right tone for its type.")
    parts.append(
        "7. ROTATING CATALOG: Uploaded products should not sit unused — when an idea "
        "is general, naturally feature a real in-stock offering ~1 in 3 times. Prefer "
        "featured items and offerings not mentioned recently."
    )

    result = "\n".join(parts)
    cache.set(cache_key, result, 300)
    return result


# ─── Catalog sampling (rotate products into content) ─────────────────────────

CATALOG_SAMPLE_DAILY_RATE = 30  # ~30% of users get a sample seed each daily run


def user_should_receive_catalog_sample(user, run_date=None) -> bool:
    """Deterministic daily lottery — not every user every day."""
    import hashlib

    run_date = run_date or timezone.now().date()
    key = f"{user.pk}:{run_date.isoformat()}:catalog_sample"
    bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
    return bucket < CATALOG_SAMPLE_DAILY_RATE


def resolve_product_by_name(user, name: str):
    """Match a catalog product by exact or close name."""
    from apps.products.models import Product

    name = (name or "").strip()
    if not name:
        return None

    exact = Product.objects.promotable(user).filter(is_active=True, name__iexact=name).first()
    if exact:
        return exact

    name_lower = name.lower()
    for product in Product.objects.promotable(user).filter(is_active=True):
        pn = product.name.lower()
        if name_lower in pn or pn in name_lower:
            return product
    return None


def sample_products_for_content(user, count=1, min_days_since_promotion=3):
    """
    Weighted random sample of promotable products not recently featured.
    Favors featured, never-promoted, and low-stock items.
    """
    import random

    from apps.content.models import ContentSeed, Post
    from apps.products.models import Product

    promotable = list(
        Product.objects.promotable(user).filter(is_active=True).order_by("name")
    )
    if not promotable:
        return []

    cutoff = timezone.now() - timedelta(days=min_days_since_promotion)
    pool = []

    for product in promotable:
        recently_used = (
            ContentSeed.objects.filter(
                user=user, product=product, created_at__gte=cutoff,
            ).exists()
            or Post.objects.filter(
                user=user, product=product, created_at__gte=cutoff,
            ).exists()
        )
        if recently_used:
            continue

        weight = 1.0
        if product.is_featured:
            weight += 2.0
        post_count = Post.objects.filter(user=user, product=product).count()
        if post_count == 0:
            weight += 2.5
        elif post_count < 3:
            weight += 1.0
        if product.stock_status == Product.StockStatus.LOW_STOCK:
            weight += 1.5

        pool.append((product, weight))

    if not pool:
        return []

    selected = []
    count = min(count, len(pool))
    work = list(pool)

    for _ in range(count):
        total = sum(w for _, w in work)
        pick = random.uniform(0, total)
        upto = 0.0
        for idx, (product, weight) in enumerate(work):
            upto += weight
            if pick <= upto:
                selected.append(product)
                work.pop(idx)
                break

    return selected


def get_catalog_sampling_hint() -> str:
    """Prompt snippet for Create Agent when seed has no linked product."""
    return (
        "\n### CATALOG ROTATION\n"
        "This seed is not tied to one product. When it fits naturally, weave in "
        "**one real offering** from the catalog (prefer featured or under-used items). "
        "Skip product mentions when the topic is purely educational.\n"
    )


def maybe_attach_sampled_product_to_autonomous_seed(seed) -> bool:
    """
    Attach a sampled catalog product to autonomous seeds that lack one.
    Used as a safety net for Strategist / Autopilot paths.
    """
    import random

    if seed.product_id:
        return False

    notes = seed.notes or ""
    if notes.startswith(("Auto-promoted:", "Catalog sample:")):
        return False

    autonomous = notes.startswith(("[Strategist Agent]", "[Autopilot]"))
    if not autonomous:
        return False

    if random.random() > 0.45:
        return False

    sampled = sample_products_for_content(seed.user, count=1)
    if not sampled:
        return False

    seed.product = sampled[0]
    seed.save(update_fields=["product"])
    return True


def enrich_idea_with_product(idea: str, product) -> str:
    """Ensure the seed idea names the product when one is linked."""
    if not product or not idea:
        return idea
    if product.name.lower() in idea.lower():
        return idea
    return f"Feature {product.name}. {idea}"


# ─── Demand Signals (what the audience is asking about) ──────────────────────

def _get_demand_signals(user) -> list:
    """
    Analyze recent comments/DMs for product-related keywords.
    Returns list of {keyword, count} showing what the audience is asking about.
    """
    from apps.engage.models import Interaction
    from apps.products.models import Product

    week_ago = timezone.now() - timedelta(days=7)
    product_names = list(
        Product.objects.filter(user=user, is_active=True)
        .values_list("name", flat=True)
    )

    if not product_names:
        return []

    interactions = Interaction.objects.filter(
        user=user, created_at__gte=week_ago,
    ).values_list("content", flat=True)

    if not interactions:
        return []

    # Count product name mentions in interactions
    mentions = defaultdict(int)
    for content in interactions:
        content_lower = (content or "").lower()
        for name in product_names:
            if name.lower() in content_lower:
                mentions[name] += 1

    # Also detect generic demand keywords (products + services)
    demand_keywords = ["price", "how much", "cost", "available", "stock", "order",
                       "buy", "purchase", "delivery", "shipping", "bei", "deliver",
                       "book", "schedule", "appointment", "consult", "quote",
                       "estimate", "project", "hire", "service", "package"]
    generic_demand = 0
    for content in interactions:
        content_lower = (content or "").lower()
        for kw in demand_keywords:
            if kw in content_lower:
                generic_demand += 1
                break

    signals = [{"keyword": name, "count": count} for name, count in mentions.items() if count > 0]
    signals.sort(key=lambda x: x["count"], reverse=True)

    if generic_demand > 0:
        signals.append({"keyword": "purchase intent (price/buy/order questions)", "count": generic_demand})

    return signals


# ─── Product-Engagement Correlation ──────────────────────────────────────────

def get_product_performance(user, days=30) -> dict:
    """
    Correlate products with post performance — which products drive the most engagement.
    Scans published posts for product name mentions and links to their metrics.

    Returns dict with product_rankings and insights.
    Cached for 30 minutes.
    """
    cache_key = f"product_performance:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.content.models import Post
    from apps.analytics.models import PostMetric
    from apps.products.models import Product

    products = Product.objects.filter(user=user, is_active=True)
    if not products.exists():
        cache.set(cache_key, {}, 1800)
        return {}

    product_names = {p.name: p for p in products}
    cutoff = timezone.now() - timedelta(days=days)

    posts = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__gte=cutoff,
        )
        .select_related("metrics")
    )

    product_stats = defaultdict(lambda: {
        "posts": 0, "total_engagement_rate": 0, "total_saves": 0,
        "total_shares": 0, "total_clicks": 0,
    })

    for post in posts:
        text_lower = (post.content_text or "").lower()
        for name, product in product_names.items():
            if name.lower() in text_lower:
                stats = product_stats[name]
                stats["posts"] += 1
                try:
                    m = post.metrics
                    stats["total_engagement_rate"] += m.engagement_rate or 0
                    stats["total_saves"] += m.saves or 0
                    stats["total_shares"] += m.shares or 0
                    stats["total_clicks"] += m.clicks or 0
                except PostMetric.DoesNotExist:
                    pass

    if not product_stats:
        cache.set(cache_key, {}, 1800)
        return {}

    # Calculate averages and rank
    rankings = []
    for name, stats in product_stats.items():
        if stats["posts"] > 0:
            avg_engagement = round(stats["total_engagement_rate"] / stats["posts"], 2)
            product = product_names[name]
            rankings.append({
                "name": name,
                "posts": stats["posts"],
                "avg_engagement_rate": avg_engagement,
                "total_saves": stats["total_saves"],
                "total_shares": stats["total_shares"],
                "total_clicks": stats["total_clicks"],
                "stock_status": product.stock_status,
                "is_featured": product.is_featured,
            })

    rankings.sort(key=lambda x: x["avg_engagement_rate"], reverse=True)

    # Products never mentioned in content
    never_promoted = [
        name for name in product_names
        if name not in product_stats and product_names[name].stock_status != Product.StockStatus.OUT_OF_STOCK
    ]

    result = {
        "rankings": rankings,
        "top_product": rankings[0]["name"] if rankings else None,
        "never_promoted": never_promoted,
        "total_product_posts": sum(s["posts"] for s in product_stats.values()),
    }

    cache.set(cache_key, result, 1800)
    return result


# ─── Stock-Content Mismatch Detection ────────────────────────────────────────

def detect_stock_content_mismatches(user) -> list:
    """
    Find content that's scheduled/approved but promotes an out-of-stock PHYSICAL product.
    Services and digital products are excluded — they don't have stock.
    Returns list of {post_id, post_preview, product_name, stock_status, severity}.
    """
    from apps.content.models import Post
    from apps.products.models import Product

    oos_products = Product.objects.filter(
        user=user, is_active=True,
        stock_status=Product.StockStatus.OUT_OF_STOCK,
        offering_type=Product.OfferingType.PRODUCT,  # Only physical products
    ).values_list("name", flat=True)

    if not oos_products:
        return []

    upcoming_posts = Post.objects.filter(
        user=user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.APPROVED, Post.Status.SCHEDULED],
    )

    mismatches = []
    for post in upcoming_posts:
        text_lower = (post.content_text or "").lower()
        for name in oos_products:
            if name.lower() in text_lower:
                mismatches.append({
                    "post_id": str(post.pk),
                    "post_preview": post.content_text[:100],
                    "product_name": name,
                    "stock_status": "out_of_stock",
                    "severity": "critical",
                    "action": f"Pause or edit — {name} is out of stock",
                })

    # Low-stock items with heavy scheduled content (>2 upcoming posts) — physical only
    low_stock_products = Product.objects.filter(
        user=user, is_active=True,
        stock_status=Product.StockStatus.LOW_STOCK,
        offering_type=Product.OfferingType.PRODUCT,
    ).values_list("name", flat=True)

    for name in low_stock_products:
        count = 0
        for post in upcoming_posts:
            if name.lower() in (post.content_text or "").lower():
                count += 1
        if count > 2:
            mismatches.append({
                "post_id": None,
                "post_preview": f"{count} upcoming posts mention {name}",
                "product_name": name,
                "stock_status": "low_stock",
                "severity": "warning",
                "action": f"Consider reducing — {name} is low stock with {count} scheduled posts",
            })

    return mismatches


# ─── Strategist Product Intelligence ─────────────────────────────────────────

def get_product_strategy_context(user) -> str:
    """
    Build a product intelligence briefing for the Strategist Agent.
    Includes stock awareness + demand signals + performance data + mismatches.
    More detailed than the basic get_product_context() used by Create Agent.

    Returns formatted string or empty string if no products.
    """
    cache_key = f"product_strategy:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.products.models import Product

    products = Product.objects.filter(user=user, is_active=True)
    if not products.exists():
        cache.set(cache_key, "", 300)
        return ""

    # Count by offering type
    service_count = products.filter(offering_type=Product.OfferingType.SERVICE).count()
    digital_count = products.filter(offering_type=Product.OfferingType.DIGITAL).count()
    physical_products = products.filter(offering_type=Product.OfferingType.PRODUCT)

    parts = ["\n=== OFFERING INTELLIGENCE (Strategy-Aware) ==="]

    # Offering type overview
    type_parts = []
    if physical_products.exists():
        type_parts.append(f"{physical_products.count()} physical products")
    if service_count:
        type_parts.append(f"{service_count} services")
    if digital_count:
        type_parts.append(f"{digital_count} digital products")
    parts.append(f"Catalog: {', '.join(type_parts)}")

    # Services — always available, no stock concerns
    service_names = list(
        products.filter(offering_type=Product.OfferingType.SERVICE)
        .values_list("name", flat=True)[:10]
    )
    if service_names:
        parts.append(f"\nServices (always available — promote freely): {', '.join(service_names)}")
        parts.append("→ Focus on expertise, results, testimonials, and booking. No stock language.")

    # Digital products — unlimited supply
    digital_names = list(
        products.filter(offering_type=Product.OfferingType.DIGITAL)
        .values_list("name", flat=True)[:10]
    )
    if digital_names:
        parts.append(f"\nDigital products (unlimited — promote freely): {', '.join(digital_names)}")

    # Stock overview — physical products only
    if physical_products.exists():
        stock_counts = {
            "in_stock": physical_products.filter(stock_status=Product.StockStatus.IN_STOCK).count(),
            "low_stock": physical_products.filter(stock_status=Product.StockStatus.LOW_STOCK).count(),
            "out_of_stock": physical_products.filter(stock_status=Product.StockStatus.OUT_OF_STOCK).count(),
            "made_to_order": physical_products.filter(stock_status=Product.StockStatus.MADE_TO_ORDER).count(),
            "unlimited": physical_products.filter(stock_status=Product.StockStatus.UNLIMITED).count(),
        }
        parts.append(
            f"\nPhysical product stock: {stock_counts['in_stock']} in stock, "
            f"{stock_counts['low_stock']} low stock, "
            f"{stock_counts['out_of_stock']} out of stock, "
            f"{stock_counts['made_to_order'] + stock_counts['unlimited']} unlimited/made-to-order"
        )

    # Featured products
    featured = list(products.filter(is_featured=True).values_list("name", flat=True)[:5])
    if featured:
        parts.append(f"Featured offerings (prioritize in content): {', '.join(featured)}")

    # Low stock items — physical products only
    low_stock = list(
        physical_products.filter(stock_status=Product.StockStatus.LOW_STOCK)
        .values_list("name", "quantity")[:10]
    )
    if low_stock:
        parts.append("Low stock products (create scarcity/urgency content):")
        for name, qty in low_stock:
            parts.append(f"  • {name}: {qty or 'few'} remaining")

    # Out of stock — physical products only, NEVER promote
    oos = list(
        physical_products.filter(stock_status=Product.StockStatus.OUT_OF_STOCK)
        .values_list("name", flat=True)[:10]
    )
    if oos:
        parts.append(f"OUT OF STOCK (DO NOT suggest content for): {', '.join(oos)}")

    # Stock-content mismatches
    mismatches = detect_stock_content_mismatches(user)
    if mismatches:
        parts.append("\n⚠️ STOCK-CONTENT MISMATCHES (needs immediate attention):")
        for m in mismatches[:5]:
            parts.append(f"  • [{m['severity'].upper()}] {m['action']}")

    # Product performance
    perf = get_product_performance(user)
    if perf.get("rankings"):
        parts.append("\nProduct engagement rankings (last 30 days):")
        for r in perf["rankings"][:5]:
            parts.append(
                f"  • {r['name']}: {r['avg_engagement_rate']}% avg engagement, "
                f"{r['posts']} posts, {r['total_saves']} saves, {r['total_clicks']} clicks"
            )

    if perf.get("never_promoted"):
        parts.append(
            f"\nProducts NEVER mentioned in content (opportunity): {', '.join(perf['never_promoted'][:5])}"
        )

    # Demand signals
    demand = _get_demand_signals(user)
    if demand:
        parts.append("\nAudience demand signals (from comments/DMs this week):")
        for d in demand[:5]:
            parts.append(f"  • \"{d['keyword']}\" — {d['count']} mentions")

    parts.append("")
    parts.append("STRATEGIST INSTRUCTIONS:")
    parts.append("- Plan content around IN-STOCK products, SERVICES, and FEATURED offerings.")
    parts.append("- For SERVICES: promote freely. Highlight expertise, results, client wins, booking.")
    parts.append("- For LOW STOCK physical products: create urgency seeds ('limited stock' angles).")
    parts.append("- NEVER suggest seeds for OUT OF STOCK physical products.")
    parts.append("- If an offering is never promoted but available, suggest content for it.")
    parts.append("- If demand signals show audience interest, plan content to match.")
    parts.append("- Flag stock-content mismatches as alerts (physical products only).\n")

    result = "\n".join(parts)
    cache.set(cache_key, result, 300)
    return result


# ─── Research Agent Product Context ──────────────────────────────────────────

def get_product_research_context(user) -> str:
    """
    Lightweight product context for the Research Agent — what the business sells
    so trend discovery is relevant to actual products.
    """
    from apps.products.models import Product

    products = Product.objects.filter(user=user, is_active=True)
    if not products.exists():
        return ""

    names = list(products.values_list("name", flat=True)[:20])
    categories = list(
        products.exclude(category=None)
        .values_list("category__name", flat=True)
        .distinct()[:10]
    )
    featured = list(products.filter(is_featured=True).values_list("name", flat=True)[:5])

    parts = ["\n=== PRODUCT CONTEXT (discover trends relevant to these) ==="]
    parts.append(f"Products/services: {', '.join(names)}")
    if categories:
        parts.append(f"Categories: {', '.join(categories)}")
    if featured:
        parts.append(f"Featured (extra attention): {', '.join(featured)}")
    parts.append("Find trends that connect to these products. Product-relevant trends are 3x more valuable.\n")

    return "\n".join(parts)


# ─── Daily Brief Product Intelligence ────────────────────────────────────────

def get_product_brief_data(user) -> dict:
    """
    Comprehensive product intelligence for the Daily Brief.
    Includes stock status, demand signals, content mismatches, and performance data.
    """
    from apps.products.models import Product, StockAlert

    products = Product.objects.filter(user=user, is_active=True)
    if not products.exists():
        return {}

    physical = products.filter(offering_type=Product.OfferingType.PRODUCT)
    in_stock_count = physical.filter(stock_status=Product.StockStatus.IN_STOCK).count()
    low_stock = list(
        physical.filter(stock_status=Product.StockStatus.LOW_STOCK)
        .values_list("name", "quantity")[:5]
    )
    out_of_stock = list(
        physical.filter(stock_status=Product.StockStatus.OUT_OF_STOCK)
        .values_list("name", flat=True)[:5]
    )
    services = list(
        products.filter(offering_type=Product.OfferingType.SERVICE)
        .values_list("name", flat=True)[:10]
    )
    featured = list(
        products.filter(is_featured=True)
        .values_list("name", flat=True)[:5]
    )
    unread_alerts = list(
        StockAlert.objects.filter(user=user, is_read=False)
        .values_list("message", flat=True)[:5]
    )

    # Stock-content mismatches
    mismatches = detect_stock_content_mismatches(user)

    # Product performance rankings
    perf = get_product_performance(user)

    # Demand signals
    demand = _get_demand_signals(user)

    # Recent stock changes (last 24h)
    from apps.products.models import StockUpdate
    recent_changes = list(
        StockUpdate.objects.filter(
            product__user=user,
            created_at__gte=timezone.now() - timedelta(hours=24),
        )
        .select_related("product")
        .values("product__name", "previous_status", "new_status", "new_quantity")[:5]
    )

    return {
        "total_products": products.count(),
        "services": services,
        "in_stock": in_stock_count,
        "low_stock_items": [{"name": name, "quantity": qty} for name, qty in low_stock],
        "out_of_stock_items": out_of_stock,
        "featured_items": featured,
        "unread_alerts": unread_alerts,
        "stock_content_mismatches": [
            {"product": m["product_name"], "severity": m["severity"], "action": m["action"]}
            for m in mismatches[:5]
        ],
        "product_performance": {
            "top_product": perf.get("top_product"),
            "never_promoted": perf.get("never_promoted", [])[:3],
            "rankings": [
                {"name": r["name"], "avg_engagement": r["avg_engagement_rate"], "posts": r["posts"]}
                for r in perf.get("rankings", [])[:3]
            ],
        },
        "demand_signals": [
            {"keyword": d["keyword"], "mentions": d["count"]}
            for d in demand[:3]
        ],
        "recent_stock_changes": recent_changes,
    }


# ─── Auto-Pause OOS Posts ────────────────────────────────────────────────────

def pause_oos_scheduled_posts(user, product_name: str) -> int:
    """
    When a physical product goes out of stock, find and pause any scheduled posts
    that mention it. Returns count of paused posts.
    Only meaningful for physical products — callers should guard on offering_type.
    """
    from apps.content.models import Post

    upcoming = Post.objects.filter(
        user=user,
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
    )

    paused = 0
    for post in upcoming:
        if product_name.lower() in (post.content_text or "").lower():
            post.status = Post.Status.PENDING_APPROVAL
            post.ai_reasoning = (
                f"{post.ai_reasoning or ''}\n\n"
                f"⚠️ AUTO-PAUSED: {product_name} went out of stock. "
                f"Review and edit before re-approving."
            ).strip()
            post.save(update_fields=["status", "ai_reasoning"])
            paused += 1
            logger.info("Auto-paused post %s — %s is OOS", post.pk, product_name)

    return paused


# ─── Auto-Generate Restock Seeds ─────────────────────────────────────────────

def generate_restock_seed(user, product_name: str, product=None) -> bool:
    """
    When a physical product is restocked, auto-create a 'Back in stock!' content seed.
    Returns True if seed was created.
    Only meaningful for physical products — callers should guard on offering_type.
    """
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount
    from apps.products.models import Product

    # Don't create if there's already a recent seed about this product
    recent = ContentSeed.objects.filter(
        user=user,
        idea__icontains=product_name,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).exists()

    if recent:
        return False

    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )

    if not platforms:
        return False

    # Look up the product to link via FK
    if product is None:
        product = Product.objects.filter(user=user, name=product_name, is_active=True).first()

    seed = ContentSeed.objects.create(
        user=user,
        product=product,
        idea=(
            f"🔥 BACK IN STOCK: {product_name} is available again! "
            f"Create an exciting 'back in stock' announcement. "
            f"Build urgency — it sold out before, it could sell out again. "
            f"Encourage immediate action."
        ),
        notes=f"Auto-generated: {product_name} was restocked.",
        target_platforms=platforms[:3],
    )
    from apps.content.tasks import generate_from_seed
    from apps.utils import fire_task

    fire_task(generate_from_seed, str(seed.id))
    logger.info("Auto-created restock seed for %s (user: %s)", product_name, user.email)
    return True


# ─── Cache Management ────────────────────────────────────────────────────────

def invalidate_product_cache(user):
    """Call this after any product update to clear all product-related caches."""
    cache.delete(f"product_context:{user.pk}")
    cache.delete(f"product_strategy:{user.pk}")
    cache.delete(f"product_performance:{user.pk}")
