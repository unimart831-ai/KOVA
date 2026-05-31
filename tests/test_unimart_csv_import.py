"""Tests for file-based UNIMART / marketplace CSV import."""

import io

import pytest

from apps.partners.marketplace_csv_import import (
    import_sellers_csv,
    parse_campus_codes,
    provision_vendor_self_serve,
    row_to_seller_payload,
    validate_usk_format,
)
from apps.partners.models import MarketplacePartner, MarketplaceSellerAccount, Partner


@pytest.fixture
def unimart_mp(user, db):
    partner = Partner.objects.create(user=user, referral_code="KOVA-UNIMART-01")
    return MarketplacePartner.objects.create(
        name="UNIMART Africa",
        slug="unimart-test-csv",
        partner=partner,
        api_key_hash="abc123csv",
        api_key_prefix="kmp_csv1",
        seller_identity_field=MarketplacePartner.SellerIdentity.EXTERNAL_ID,
        auto_activate_sellers=True,
        seller_default_plan="growth",
        settings={"vendor_join_pending_usks": ["USK-PENDING-01"]},
    )


class TestCsvParsing:
    def test_parse_campus_codes_json(self):
        assert parse_campus_codes('["USIU", "KU"]') == ["USIU", "KU"]

    def test_parse_campus_codes_comma(self):
        assert parse_campus_codes("USIU, KU") == ["USIU", "KU"]

    def test_row_to_seller_payload(self):
        payload = row_to_seller_payload({
            "external_seller_id": "USK-00123",
            "full_name": "Jane Kamau",
            "email": "jane@usiu.ac.ke",
            "business_name": "Jane Electronics",
            "campus_codes": "USIU,KU",
        })
        assert payload["external_seller_id"] == "USK-00123"
        assert payload["seller_metadata"]["campus_codes"] == ["USIU", "KU"]

    def test_validate_usk_format(self):
        assert validate_usk_format("USK-00123") is True
        assert validate_usk_format("invalid") is False


@pytest.mark.django_db
class TestSellerCsvImport:
    def test_import_provisions_sellers(self, unimart_mp):
        csv_data = io.StringIO(
            "external_seller_id,full_name,email,business_name,business_url,campus_codes\n"
            "USK-00123,Jane Kamau,jane@usiu.ac.ke,Jane Electronics,https://example.com/store,USIU\n"
            "USK-00456,Brian Ochieng,,Campus Snacks,,KU\n"
        )
        summary = import_sellers_csv(unimart_mp, csv_data)
        assert summary.provisioned == 2
        assert summary.failed == 0
        assert MarketplaceSellerAccount.objects.filter(marketplace=unimart_mp).count() == 2

    def test_import_idempotent(self, unimart_mp):
        csv_data = io.StringIO(
            "external_seller_id,full_name,business_name\n"
            "USK-00999,Test Seller,Test Shop\n"
        )
        import_sellers_csv(unimart_mp, csv_data)
        summary = import_sellers_csv(unimart_mp, io.StringIO(
            "external_seller_id,full_name,business_name\n"
            "USK-00999,Test Seller,Test Shop\n"
        ))
        assert summary.already_exists == 1
        assert summary.provisioned == 0

    def test_pending_only_rows(self, unimart_mp):
        csv_data = io.StringIO(
            "external_seller_id,full_name,business_name,pending_only\n"
            "USK-INVITE-99,Jane,Shop,true\n"
        )
        summary = import_sellers_csv(unimart_mp, csv_data)
        assert summary.pending_added == 1
        assert summary.provisioned == 0
        unimart_mp.refresh_from_db()
        assert "USK-INVITE-99" in unimart_mp.settings["vendor_join_pending_usks"]


@pytest.mark.django_db
class TestVendorSelfServe:
    def test_pending_usk_provisions(self, unimart_mp):
        response, status = provision_vendor_self_serve(
            unimart_mp,
            external_seller_id="USK-PENDING-01",
            full_name="Pending Seller",
            email="pending@usiu.ac.ke",
            business_name="Pending Shop",
        )
        assert status == 201
        assert response["status"] == "provisioned"
        unimart_mp.refresh_from_db()
        assert "USK-PENDING-01" not in unimart_mp.settings.get("vendor_join_pending_usks", [])

    def test_open_join_requires_approval(self, unimart_mp):
        response, status = provision_vendor_self_serve(
            unimart_mp,
            external_seller_id="USK-NEW-777",
            full_name="New Seller",
            email="new@usiu.ac.ke",
            business_name="New Shop",
        )
        assert response.get("approval_required") is True
        seller = MarketplaceSellerAccount.objects.get(
            marketplace=unimart_mp, external_seller_id="USK-NEW-777",
        )
        assert seller.status == MarketplaceSellerAccount.Status.INVITED
