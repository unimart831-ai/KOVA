"""WhatsApp conversation → lead bridge tests."""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.commerce.leads.bridges import create_lead_from_whatsapp_conversation, find_lead_for_whatsapp_conversation
from apps.commerce.leads.models import Lead
from apps.core.platforms.models import SocialAccount
from apps.messaging.whatsapp.models import WhatsAppConversation


@pytest.mark.django_db
class TestWhatsAppLeadBridge:
    @pytest.fixture
    def conversation(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])
        account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa99",
            username="shop",
            access_token="tok",
            is_active=True,
        )
        return WhatsAppConversation.objects.create(
            social_account=account,
            contact_wa_id="254799887766",
            contact_name="Jane Buyer",
            contact_phone="254799887766",
        )

    def test_create_lead_from_conversation(self, conversation, user):
        lead = create_lead_from_whatsapp_conversation(conversation)
        assert lead is not None
        assert lead.user == user
        assert lead.phone == "254799887766"
        assert lead.source_platform == "whatsapp"
        assert find_lead_for_whatsapp_conversation(conversation) == lead

    def test_save_as_lead_view(self, client, user, conversation):
        client.force_login(user)
        url = reverse("whatsapp:save_as_lead", kwargs={"pk": conversation.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert Lead.objects.filter(user=user, phone="254799887766").exists()

    def test_lead_enroll_nurture(self, client, user, conversation):
        lead = create_lead_from_whatsapp_conversation(conversation, enroll=False)
        client.force_login(user)
        url = reverse("leads:enroll_nurture", kwargs={"lead_id": lead.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert lead.enrollments.exists()
