from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from apps.notifications.models import Notification, NotificationPreference


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
    notifications = Notification.objects.filter(user=request.user).select_related("related_post")[:10]
    Notification.mark_all_read(request.user)
    return render(request, "notifications/_dropdown.html", {
        "notifications": notifications,
    })


@login_required
def mark_all_read(request):
    """HTMX endpoint: mark all notifications as read."""
    Notification.mark_all_read(request.user)
    return HttpResponse("")


@login_required
def notification_preferences(request):
    """Notification preferences page — toggle which notifications to receive."""
    prefs = NotificationPreference.for_user(request.user)

    if request.method == "POST":
        prefs.post_published = request.POST.get("post_published") == "on"
        prefs.publish_failed = request.POST.get("publish_failed") == "on"
        prefs.posts_generated = request.POST.get("posts_generated") == "on"
        prefs.agent_action = request.POST.get("agent_action") == "on"
        prefs.save()

        if request.headers.get("HX-Request"):
            return render(request, "notifications/_prefs_saved.html")
        return render(request, "notifications/preferences.html", {
            "prefs": prefs,
            "saved": True,
        })

    return render(request, "notifications/preferences.html", {"prefs": prefs})
