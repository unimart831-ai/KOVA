"""Nurture sequence UI — removed from V1 (models kept)."""
from __future__ import annotations

import pytest
from django.urls import NoReverseMatch, reverse


@pytest.mark.django_db
class TestNurtureWhatsAppUI:
    def test_nurture_routes_removed_in_v1(self):
        for name in (
            "leads:nurture_list",
            "leads:nurture_create",
            "leads:nurture_detail",
            "leads:nurture_toggle",
            "leads:enroll_nurture",
        ):
            with pytest.raises(NoReverseMatch):
                reverse(name)
