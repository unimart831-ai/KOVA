def product_nav(request):
    """Unread stock alert count for Products sub-nav."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    path = getattr(request, "path", "") or ""
    if "/products/" not in path:
        return {}
    from django.core.cache import cache
    from apps.products.models import StockAlert

    cache_key = f"product_nav:alerts:{request.user.pk}"
    count = cache.get(cache_key)
    if count is None:
        count = StockAlert.objects.filter(user=request.user, is_read=False).count()
        cache.set(cache_key, count, 60)
    return {"unread_alerts": count}
