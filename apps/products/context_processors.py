def product_nav(request):
    """Unread stock alert count for Products sub-nav."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    path = getattr(request, "path", "") or ""
    if "/products/" not in path:
        return {}
    from apps.products.models import StockAlert

    return {
        "unread_alerts": StockAlert.objects.filter(user=request.user, is_read=False).count(),
    }
