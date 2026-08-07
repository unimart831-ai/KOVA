"""Pilot readiness smoke test.

Certifies the launch-critical path for a pilot business end to end:
config → provider wiring → connected account → publish readiness →
engagement readiness → compliance endpoints. Run this BEFORE a pilot
onboarding so breakage shows up in a terminal, not in front of a customer.

Usage:
    python manage.py pilot_smoke                      # dry checks, all IG/FB accounts
    python manage.py pilot_smoke --user owner@biz.com # focus one pilot user
    python manage.py pilot_smoke --user owner@biz.com --live     # hit Meta read-only (validate token, fetch comments)
    python manage.py pilot_smoke --user owner@biz.com --publish  # publish + delete a real FB test post (destructive opt-in)

Exit code is non-zero if any check FAILs, so it is CI/pre-deploy usable.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.urls import NoReverseMatch, reverse

from apps.core.platforms.models import SocialAccount
from apps.core.platforms.providers import get_provider
from apps.core.platforms.providers.base import BaseProvider

User = get_user_model()

OK = "PASS"
WARN = "WARN"
FAIL = "FAIL"


class Command(BaseCommand):
    help = "Smoke-test the pilot path: config, providers, account, publish, engagement, compliance."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Email of the pilot user to check")
        parser.add_argument(
            "--live", action="store_true",
            help="Hit Meta APIs read-only (validate token + fetch recent comments)",
        )
        parser.add_argument(
            "--publish", action="store_true",
            help="Publish and immediately delete a real Facebook test post (destructive opt-in)",
        )

    # ── result helpers ────────────────────────────────────────────────────
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._counts = {OK: 0, WARN: 0, FAIL: 0}

    def _result(self, status: str, label: str, detail: str = ""):
        self._counts[status] += 1
        style = {
            OK: self.style.SUCCESS,
            WARN: self.style.WARNING,
            FAIL: self.style.ERROR,
        }[status]
        line = f"  [{style(status)}] {label}"
        if detail:
            line += f" — {detail}"
        self.stdout.write(line)

    def _section(self, title: str):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(title))

    # ── handle ────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        self.stdout.write(self.style.MIGRATE_HEADING("Kova pilot readiness smoke test"))

        self._check_config()
        self._check_providers()
        accounts = self._check_accounts(opts.get("user"))

        if opts.get("live") or opts.get("publish"):
            self._check_live(accounts, publish=opts.get("publish", False))
        else:
            self.stdout.write("")
            self.stdout.write(
                "  (Run with --live to validate tokens + engagement against Meta; "
                "--publish to test a real post.)"
            )

        self._check_compliance()
        self._summary()

    # ── 1. config ─────────────────────────────────────────────────────────
    def _check_config(self):
        self._section("1. Configuration")

        if getattr(settings, "FACEBOOK_APP_ID", ""):
            self._result(OK, "FACEBOOK_APP_ID set")
        else:
            self._result(FAIL, "FACEBOOK_APP_ID missing", "IG/FB OAuth cannot work")

        if getattr(settings, "FACEBOOK_APP_SECRET", ""):
            self._result(OK, "FACEBOOK_APP_SECRET set")
        else:
            self._result(FAIL, "FACEBOOK_APP_SECRET missing", "IG/FB OAuth cannot work")

        if getattr(settings, "FB_LOGIN_CONFIG_ID", ""):
            self._result(OK, "FB_LOGIN_CONFIG_ID set", "using Facebook Login for Business")
        else:
            self._result(WARN, "FB_LOGIN_CONFIG_ID empty", "falling back to classic scope login (OK)")

        fernet = getattr(settings, "FERNET_KEYS", [])
        secret = getattr(settings, "SECRET_KEY", "")
        if fernet and fernet[0] and fernet[0] != secret:
            self._result(OK, "FIELD_ENCRYPTION_KEY set", "dedicated key (separate from SECRET_KEY)")
        elif fernet and fernet[0] == secret:
            self._result(WARN, "FIELD_ENCRYPTION_KEY falling back to SECRET_KEY",
                         "set a dedicated key before production")
        else:
            self._result(FAIL, "No Fernet key", "token encryption broken")

        wa_fields = {
            "WHATSAPP_PHONE_NUMBER_ID": getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", ""),
            "WHATSAPP_ACCESS_TOKEN": getattr(settings, "WHATSAPP_ACCESS_TOKEN", ""),
            "WHATSAPP_WABA_ID": getattr(settings, "WHATSAPP_WABA_ID", ""),
            "WHATSAPP_VERIFY_TOKEN": getattr(settings, "WHATSAPP_VERIFY_TOKEN", ""),
        }
        missing_wa = [k for k, v in wa_fields.items() if not v]
        if not missing_wa:
            self._result(OK, "WhatsApp config complete")
        else:
            self._result(WARN, "WhatsApp config incomplete", f"missing: {', '.join(missing_wa)}")

    # ── 2. providers ──────────────────────────────────────────────────────
    def _check_providers(self):
        self._section("2. Provider wiring")

        for name in ("facebook", "instagram", "whatsapp"):
            provider = get_provider(name)
            if provider is None:
                self._result(FAIL, f"{name} provider not registered")
                continue

            publishes = type(provider).publish_post is not BaseProvider.publish_post
            self._result(
                OK if publishes else FAIL,
                f"{name} provider registered",
                "publish_post implemented" if publishes else "publish_post is a stub",
            )

            if name in ("facebook", "instagram"):
                reads = type(provider).get_comments is not BaseProvider.get_comments
                replies = type(provider).reply_to_comment is not BaseProvider.reply_to_comment
                self._result(
                    OK if (reads and replies) else WARN,
                    f"{name} engagement",
                    "read + reply implemented" if (reads and replies) else "engagement partial",
                )

    # ── 3. accounts ───────────────────────────────────────────────────────
    def _check_accounts(self, user_email):
        self._section("3. Connected accounts (IG/FB)")

        qs = SocialAccount.objects.filter(
            is_active=True, platform__in=("facebook", "instagram"),
        ).select_related("user")

        if user_email:
            try:
                user = User.objects.get(email__iexact=user_email)
            except User.DoesNotExist:
                self._result(FAIL, "User not found", user_email)
                return []
            qs = qs.filter(user=user)

        accounts = list(qs)
        if not accounts:
            self._result(
                WARN, "No connected IG/FB accounts",
                f"add as app tester + connect for {user_email}" if user_email
                else "connect a pilot account to fully certify",
            )
            return []

        for acct in accounts:
            label = f"{acct.platform} @{acct.username} (user={acct.user.email})"
            if not acct.access_token:
                self._result(FAIL, label, "no access token")
                continue
            if acct.is_token_expired:
                self._result(FAIL, label, "token expired — reconnect")
                continue

            pages = (acct.metadata or {}).get("pages", [])
            if not pages:
                self._result(FAIL, label, "no pages in metadata")
            elif not pages[0].get("access_token"):
                self._result(FAIL, label, "no page access token")
            else:
                detail = "token valid, page token present"
                if acct.last_error:
                    detail += f" (last_error: {acct.last_error[:60]})"
                self._result(OK, label, detail)

        return accounts

    # ── 4/5. live token + engagement ──────────────────────────────────────
    def _check_live(self, accounts, *, publish: bool):
        self._section("4. Live token + engagement (read-only)")

        if not accounts:
            self._result(WARN, "Skipped live checks", "no connected account to test")
            return

        for acct in accounts:
            provider = get_provider(acct.platform)
            if provider is None:
                continue
            pages = (acct.metadata or {}).get("pages", [])
            token = pages[0].get("access_token") if pages else acct.access_token
            label = f"{acct.platform} @{acct.username}"

            try:
                valid = provider.validate_token(token)
                self._result(
                    OK if valid else FAIL, f"{label} token live-check",
                    "Meta accepted the token" if valid else "Meta rejected the token",
                )
            except Exception as exc:
                self._result(FAIL, f"{label} token live-check", f"error: {str(exc)[:80]}")
                continue

            # Engagement read: fetch own posts → comments on the first one
            try:
                posts = provider.get_own_posts(token, count=1) if hasattr(provider, "get_own_posts") else []
                if posts:
                    pid = posts[0].get("id")
                    comments = provider.get_comments(token, pid)
                    self._result(OK, f"{label} engagement read",
                                 f"latest post has {len(comments)} comment(s)")
                else:
                    self._result(WARN, f"{label} engagement read",
                                 "no recent posts to read comments from")
            except Exception as exc:
                self._result(WARN, f"{label} engagement read", f"error: {str(exc)[:80]}")

            if publish and acct.platform == "facebook":
                self._publish_test(provider, token, label)

    def _publish_test(self, provider, token, label):
        self._section("5. Live publish test (destructive)")
        msg = "Kova pilot smoke test — please ignore. (auto-deleted)"
        try:
            result = provider.publish_post(access_token=token, content=msg)
            if getattr(result, "success", False):
                pid = result.platform_post_id
                self._result(OK, f"{label} publish", f"posted id={pid} url={result.url}")
                try:
                    deleted = provider.delete_post(token, pid)
                    self._result(
                        OK if deleted else WARN, f"{label} cleanup",
                        "test post deleted" if deleted else "could not auto-delete — remove manually",
                    )
                except Exception as exc:
                    self._result(WARN, f"{label} cleanup", f"delete failed: {str(exc)[:60]} — remove manually")
            else:
                self._result(FAIL, f"{label} publish", getattr(result, "error", "unknown error")[:100])
        except Exception as exc:
            self._result(FAIL, f"{label} publish", f"error: {str(exc)[:100]}")

    # ── 6. compliance endpoints ───────────────────────────────────────────
    def _check_compliance(self):
        self._section("6. Compliance endpoints (App Review requirement)")

        for name, kwargs in (
            ("privacy", {}),
            ("facebook_data_deletion", {}),
            ("platforms:facebook_data_deletion_callback", {}),
        ):
            try:
                path = reverse(name, kwargs=kwargs)
                self._result(OK, f"{name} resolves", path)
            except NoReverseMatch:
                self._result(FAIL, f"{name} missing", "App Review will reject without it")

    # ── summary ───────────────────────────────────────────────────────────
    def _summary(self):
        self.stdout.write("")
        c = self._counts
        msg = f"{c[OK]} passed, {c[WARN]} warnings, {c[FAIL]} failed"
        if c[FAIL]:
            self.stdout.write(self.style.ERROR(f"NOT READY — {msg}"))
            raise CommandError("Pilot smoke test failed. Fix FAILs before onboarding.")
        if c[WARN]:
            self.stdout.write(self.style.WARNING(f"READY WITH WARNINGS — {msg}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"READY — {msg}"))
