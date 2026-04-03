from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from apps.notifications.models import Notification


@login_required
def notification_list(request):
    """Full notifications page."""
    notifications = Notification.objects.filter(user=request.user).select_related("related_post")[:50]
    Notification.mark_all_read(request.user)
    return render(request, "notifications/list.html", {
        "notifications": notifications,
        "page_title": "Notifications",
    })


@login_required
def notification_bell(request):
    """HTMX partial: notification bell badge with unread count."""
    count = Notification.unread_count(request.user)
    return render(request, "notifications/_bell.html", {"unread_count": count})


@login_required
def notification_dropdown(request):
    """HTMX partial: dropdown with recent notifications."""
    notifications = Notification.objects.filter(user=request.user)[:10]
    Notification.mark_all_read(request.user)
    return render(request, "notifications/_dropdown.html", {
        "notifications": notifications,
    })


@login_required
def mark_all_read(request):
    """HTMX endpoint: mark all notifications as read."""
    Notification.mark_all_read(request.user)
    return HttpResponse("")
