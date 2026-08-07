"""
Core loop smoke test — fast pre-deploy / CI checks.

Validates migrations applied, critical routes resolve, and strategic
modules import without error. Exit code non-zero on any FAIL.

Usage:
    python manage.py core_smoke
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.urls import NoReverseMatch, reverse

OK = "PASS"
WARN = "WARN"
FAIL = "FAIL"

CRITICAL_ROUTES = (
    ("brief:home", {}),
    ("products:snap", {}),
    ("content:studio", {}),
    ("bookings:list", {}),
    ("bookings:link_create", {}),
    ("accounts:settings", {}),
    ("api:asset-list", {}),
    ("api:product-list", {}),
    ("whatsapp:webhook", {}),
)


class Command(BaseCommand):
    help = "Smoke-test core loop: routes, models, blueprint pipeline"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._counts = {OK: 0, WARN: 0, FAIL: 0}

    def _result(self, status: str, label: str, detail: str = ""):
        self._counts[status] += 1
        style = {OK: self.style.SUCCESS, WARN: self.style.WARNING, FAIL: self.style.ERROR}[status]
        line = f"  [{style(status)}] {label}"
        if detail:
            line += f" — {detail}"
        self.stdout.write(line)

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Kova core loop smoke test"))

        self._check_django()
        self._check_routes()
        self._check_imports()
        self._check_blueprint_roundtrip()

        c = self._counts
        msg = f"{c[OK]} passed, {c[WARN]} warnings, {c[FAIL]} failed"
        if c[FAIL]:
            self.stdout.write(self.style.ERROR(f"SMOKE FAILED — {msg}"))
            raise CommandError("Core smoke test failed.")
        if c[WARN]:
            self.stdout.write(self.style.WARNING(f"SMOKE OK WITH WARNINGS — {msg}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"SMOKE OK — {msg}"))

    def _check_django(self):
        from django.core.management import call_command
        from io import StringIO

        self.stdout.write(self.style.MIGRATE_HEADING("1. Django checks"))
        out = StringIO()
        try:
            call_command("check", stdout=out, stderr=out)
            self._result(OK, "django check")
        except Exception as exc:
            self._result(FAIL, "django check", str(exc)[:120])

    def _check_routes(self):
        self.stdout.write(self.style.MIGRATE_HEADING("2. Critical routes"))
        for name, kwargs in CRITICAL_ROUTES:
            try:
                path = reverse(name, kwargs=kwargs)
                self._result(OK, name, path)
            except NoReverseMatch:
                self._result(FAIL, name, "NoReverseMatch")

    def _check_imports(self):
        self.stdout.write(self.style.MIGRATE_HEADING("3. Strategic modules"))
        modules = (
            "apps.create.content.blueprints",
            "apps.create.content.blueprint_pipeline",
            "apps.create.content.renderers",
            "apps.create.content.blueprint_retry",
            "apps.create.content.service_templates",
            "apps.create.content.professional_templates",
            "apps.create.content.professional_cta",
            "apps.create.briefs.revenue_summary",
            "apps.create.briefs.asset_attribution",
            "apps.core.accounts.product_voice",
            "apps.create.content.post_labels",
            "apps.commerce.leads.bridges",
            "apps.commerce.leads.professional_funnel",
            "apps.commerce.products.business_assets",
            "apps.commerce.products.professional_assets",
            "apps.create.media.brand_dna",
            "apps.create.media.asset_intelligence",
            "apps.create.media.router",
            "apps.create.media.orchestrator",
            "apps.commerce.bookings.service_setup",
            "apps.create.briefs.whatsapp_commands",
            "apps.create.content.approval",
        )
        for mod in modules:
            try:
                __import__(mod)
                self._result(OK, mod)
            except Exception as exc:
                self._result(FAIL, mod, str(exc)[:100])

    def _check_blueprint_roundtrip(self):
        self.stdout.write(self.style.MIGRATE_HEADING("4. Blueprint roundtrip"))
        from apps.create.content.blueprints import build_blueprint_from_asset, validate_blueprint
        from apps.create.content.blueprint_pipeline import blueprint_prompt_section
        from apps.commerce.products.models import BusinessAsset

        class _Stub:
            id = "00000000-0000-0000-0000-000000000001"
            asset_type = BusinessAsset.AssetType.PRODUCT
            title = "Smoke test item"
            description = "CI"
            metadata = {"price": "1000", "currency": "KES"}
            source = BusinessAsset.Source.MANUAL

        data = build_blueprint_from_asset(_Stub()).to_dict()
        ok, errors = validate_blueprint(data)
        if ok and blueprint_prompt_section(data):
            self._result(OK, "blueprint build + prompt section")
        else:
            self._result(FAIL, "blueprint roundtrip", "; ".join(errors) or "empty prompt")
