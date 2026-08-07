"""Shared DRF permission classes."""

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsStaffOrDebug(BasePermission):
    """Allow OpenAPI schema access in DEBUG; require staff in production."""

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
