from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.api.permissions import IsStaffOrDebug

_SCHEMA_PERM = [IsStaffOrDebug]
# Schema/docs are not API consumers — skip plan throttling (also avoids init crash).
_SCHEMA_THROTTLE: list = []

urlpatterns = [
    path(
        "",
        SpectacularAPIView.as_view(permission_classes=_SCHEMA_PERM, throttle_classes=_SCHEMA_THROTTLE),
        name="schema",
    ),
    path(
        "swagger/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            permission_classes=_SCHEMA_PERM,
            throttle_classes=_SCHEMA_THROTTLE,
        ),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(
            url_name="schema",
            permission_classes=_SCHEMA_PERM,
            throttle_classes=_SCHEMA_THROTTLE,
        ),
        name="redoc",
    ),
]
