"""REACH lead automation — walk-in bridge, nurture triggers, scoring."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.leads.bridges import create_lead_from_walkin
from apps.leads.defaults import WELCOME_SEQUENCE_NAME, ensure_default_nurture_sequences
from apps.leads.models import Lead, LeadEnrollment, NurtureSequence, NurtureStep
from apps.leads.tasks import enroll_lead_in_sequences, enroll_stale_lead_in_winback
from apps.qr_attribution.models import WalkInEvent


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="reachowner",
        email="reach@kova.ai",
        password="ReachPass123!",
        full_name="Reach Owner",
    )
    UserProfile.objects.filter(user=u).update(plan="growth", company_name="Reach Biz")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


class TestWalkInBridge:
    def test_walkin_with_phone_creates_lead(self, owner):
        WalkInEvent.objects.create(
            user=owner,
            attribution_source=WalkInEvent.AttributionSource.INSTAGRAM,
            customer_phone="254712345678",
            customer_name="Jane Doe",
        )
        lead = Lead.objects.get(user=owner, phone="254712345678")
        assert lead.source_type == Lead.Source.WALK_IN
        assert lead.name == "Jane Doe"

    def test_bridge_direct_call(self, owner):
        walkin = WalkInEvent(
            user=owner,
            attribution_source=WalkInEvent.AttributionSource.WHATSAPP,
            customer_phone="254700000099",
        )
        lead = create_lead_from_walkin(walkin)
        assert lead is not None
        assert lead.phone == "254700000099"

    def test_walkin_without_phone_skips_lead(self, owner):
        walkin = WalkInEvent.objects.create(
            user=owner,
            attribution_source=WalkInEvent.AttributionSource.FLYER,
        )
        assert create_lead_from_walkin(walkin) is None
        assert Lead.objects.filter(user=owner).count() == 0

    def test_post_save_signal_creates_lead(self, owner):
        WalkInEvent.objects.create(
            user=owner,
            customer_phone="0711999888",
            customer_name="Signal Test",
        )
        assert Lead.objects.filter(user=owner, source_type=Lead.Source.WALK_IN).exists()


class TestNurtureTriggerParsing:
    def test_from_walk_in_trigger_matches(self, owner):
        ensure_default_nurture_sequences(owner)
        walkin_seq = NurtureSequence.objects.create(
            user=owner,
            name="Walk-in only",
            trigger=NurtureSequence.Trigger.FROM_WALK_IN,
            is_active=True,
        )
        NurtureStep.objects.create(sequence=walkin_seq, order=0, delay_hours=0)

        walkin_lead = Lead.objects.create(
            user=owner,
            email="walkin_test@kova.page",
            phone="254700000001",
            source_type=Lead.Source.WALK_IN,
        )
        form_lead = Lead.objects.create(
            user=owner,
            email="form_test@example.com",
            source_type=Lead.Source.FORM_SUBMISSION,
        )

        enroll_lead_in_sequences(walkin_lead)
        enroll_lead_in_sequences(form_lead)

        assert LeadEnrollment.objects.filter(lead=walkin_lead, sequence=walkin_seq).exists()
        assert not LeadEnrollment.objects.filter(lead=form_lead, sequence=walkin_seq).exists()

    def test_stale_winback_only_via_task(self, owner):
        winback = NurtureSequence.objects.create(
            user=owner,
            name="Stale test",
            trigger=NurtureSequence.Trigger.STALE_WINBACK,
            is_active=True,
        )
        NurtureStep.objects.create(sequence=winback, order=0, delay_hours=0)

        lead = Lead.objects.create(
            user=owner,
            email="stale@example.com",
            source_type=Lead.Source.MANUAL,
        )
        enroll_lead_in_sequences(lead)
        assert not LeadEnrollment.objects.filter(lead=lead, sequence=winback).exists()

        assert enroll_stale_lead_in_winback(lead)
        assert LeadEnrollment.objects.filter(lead=lead, sequence=winback).exists()

    def test_default_welcome_sequence_created(self, owner):
        ensure_default_nurture_sequences(owner)
        welcome = NurtureSequence.objects.get(user=owner, name=WELCOME_SEQUENCE_NAME)
        assert welcome.trigger == NurtureSequence.Trigger.ALL_NEW
        assert welcome.steps.count() == 2
        assert NurtureStep.ActionType.SEND_WHATSAPP in [
            s.action_type for s in welcome.steps.all()
        ]


class TestCompositeScoringInTask:
    def test_score_all_leads_writes_composite_score(self, owner):
        lead = Lead.objects.create(
            user=owner,
            email="score@example.com",
            phone="254711122233",
            source_type=Lead.Source.FORM_SUBMISSION,
        )
        lead.activities.create(
            activity_type="form_submitted",
            description="Test",
        )
        from apps.leads.tasks import score_all_leads

        score_all_leads()
        lead.refresh_from_db()
        assert "composite_score" in (lead.metadata or {})
        assert lead.metadata["composite_score"] >= 0


class TestStaleReengage:
    def test_stale_lead_gets_priority_bump(self, owner):
        lead = Lead.objects.create(
            user=owner,
            email="old@example.com",
            priority=Lead.Priority.LOW,
            last_activity_at=timezone.now() - timedelta(days=10),
        )
        from apps.leads.tasks import reengage_stale_leads

        reengage_stale_leads()
        lead.refresh_from_db()
        assert lead.priority == Lead.Priority.MEDIUM
