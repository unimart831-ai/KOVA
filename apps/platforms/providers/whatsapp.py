"""
WhatsApp Cloud API Provider.

Unlike other social platforms, WhatsApp uses:
1. A permanent System User access token (not OAuth per-user)
2. Webhooks for inbound messages (not polling)
3. Template messages for outbound outside 24-hour window
4. Conversation-based pricing (not per-message)

This provider handles all outbound messaging via the Graph API.
Inbound messages are handled by the webhook endpoint (apps/whatsapp/webhook.py).

Cloud API Reference:
  https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""

import hashlib
import hmac
import logging
from typing import Optional

import httpx
from django.conf import settings

from apps.platforms.providers.base import (
    BaseProvider,
    OAuthResult,
    PlatformAuthError,
    PostMetrics,
    ProfileSnapshot,
    PublishResult,
)
from apps.platforms.providers.registry import register_provider

logger = logging.getLogger(__name__)

# ── Graph API versioning ─────────────────────────────────────────────────────
WA_API_VERSION = "v21.0"
WA_API_BASE = f"https://graph.facebook.com/{WA_API_VERSION}"
HTTP_TIMEOUT = 30.0


class WhatsAppProvider(BaseProvider):
    """
    WhatsApp Cloud API provider.

    Key differences from other providers:
    - No OAuth flow — WhatsApp uses a permanent access token from Meta Business Suite
    - publish_post() sends a template message (the only way to initiate contact)
    - send_message() sends a free-form message (within 24-hour window)
    - get_auth_url/handle_callback just store the permanent token
    """

    platform_name = "whatsapp"

    def __init__(self):
        self.access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        self.waba_id = getattr(settings, "WHATSAPP_WABA_ID", "")
        self.verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
        self.app_secret = getattr(settings, "WHATSAPP_APP_SECRET", "")
        self.client = httpx.Client(timeout=HTTP_TIMEOUT)

    # ── Auth (WhatsApp doesn't use OAuth — manual token setup) ───────────

    def get_auth_url(self, state: str, redirect_uri: str) -> str:
        """WhatsApp doesn't use OAuth. Returns empty — connection is manual."""
        return ""

    def handle_callback(self, code: str, redirect_uri: str, phone_number_id: str = "", waba_id: str = "") -> OAuthResult:
        """
        For WhatsApp, 'code' is the permanent access token entered manually.
        We verify it by calling the Graph API to get the phone number info.
        """
        token = code  # The user pastes their permanent token
        # Use per-connection IDs if provided, fall back to global settings
        pn_id = phone_number_id or self.phone_number_id
        wa_id = waba_id or self.waba_id
        if not pn_id:
            raise PlatformAuthError("Phone Number ID is required. Find it in Meta Business Suite → WhatsApp → API Setup.")
        try:
            resp = self.client.get(
                f"{WA_API_BASE}/{pn_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "display_phone_number,verified_name,quality_rating"},
            )
            resp.raise_for_status()
            data = resp.json()
            return OAuthResult(
                platform_user_id=pn_id,
                username=data.get("display_phone_number", ""),
                display_name=data.get("verified_name", "WhatsApp Business"),
                access_token=token,
                metadata={
                    "phone_number_id": pn_id,
                    "waba_id": wa_id,
                    "quality_rating": data.get("quality_rating", ""),
                    "display_phone_number": data.get("display_phone_number", ""),
                },
            )
        except httpx.HTTPStatusError as e:
            raise PlatformAuthError(f"WhatsApp token verification failed: {e}")

    def refresh_access_token(self, refresh_token: str) -> dict:
        """WhatsApp permanent tokens don't expire. No-op."""
        return {}

    def handle_embedded_signup(self, code: str, phone_number_id: str, waba_id: str) -> OAuthResult:
        """
        Handle WhatsApp Embedded Signup flow.

        1. Exchange authorization code for access token
        2. Auto-discover WABA + phone if session info wasn't captured
        3. Subscribe WABA to our app for webhooks
        4. Register phone number for Cloud API
        5. Fetch phone display info
        """
        app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")

        if not app_id or not app_secret:
            raise PlatformAuthError("Facebook App ID and Secret must be configured.")

        # Step 1: Exchange code for access token
        token_resp = self.client.get(
            f"{WA_API_BASE}/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "code": code,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        # Step 2: Auto-discover WABA and phone number if session info was empty
        # (WA_EMBEDDED_SIGNUP message doesn't always fire for existing WABAs)
        if not waba_id or not phone_number_id:
            logger.info("Session info incomplete — discovering WABA/phone from API")
            try:
                waba_id, phone_number_id = self._discover_waba_and_phone(
                    access_token, waba_id, phone_number_id
                )
            except Exception as e:
                logger.warning("WABA auto-discovery failed (non-fatal): %s", e)

        # Step 3: Subscribe WABA to our app (enables webhooks)
        if waba_id:
            try:
                sub_resp = self.client.post(
                    f"{WA_API_BASE}/{waba_id}/subscribed_apps",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                sub_resp.raise_for_status()
                logger.info("Subscribed WABA %s to app", waba_id)
            except httpx.HTTPStatusError as e:
                logger.warning("WABA subscription failed (non-fatal): %s", e)

        # Step 4: Register phone number for Cloud API
        if phone_number_id:
            try:
                reg_resp = self.client.post(
                    f"{WA_API_BASE}/{phone_number_id}/register",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"messaging_product": "whatsapp", "pin": "123456"},
                )
                reg_resp.raise_for_status()
                logger.info("Registered phone %s for Cloud API", phone_number_id)
            except httpx.HTTPStatusError:
                logger.warning("Phone registration skipped (may already be registered)")

        # Step 5: Fetch phone number details
        display_phone = ""
        verified_name = "WhatsApp Business"
        quality = ""

        if phone_number_id:
            try:
                info_resp = self.client.get(
                    f"{WA_API_BASE}/{phone_number_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"fields": "display_phone_number,verified_name,quality_rating"},
                )
                info_resp.raise_for_status()
                info = info_resp.json()
                display_phone = info.get("display_phone_number", "")
                verified_name = info.get("verified_name", "WhatsApp Business")
                quality = info.get("quality_rating", "")
            except httpx.HTTPStatusError:
                logger.warning("Could not fetch phone info for %s", phone_number_id)

        if not phone_number_id and not waba_id:
            raise PlatformAuthError(
                "Could not determine your WhatsApp Business Account. "
                "Please try the manual setup instead."
            )

        return OAuthResult(
            platform_user_id=phone_number_id or waba_id,
            username=display_phone,
            display_name=verified_name,
            access_token=access_token,
            metadata={
                "phone_number_id": phone_number_id,
                "waba_id": waba_id,
                "quality_rating": quality,
                "display_phone_number": display_phone,
                "signup_method": "embedded_signup",
            },
        )

    def _discover_waba_and_phone(
        self, access_token: str, waba_id: str, phone_number_id: str
    ) -> tuple[str, str]:
        """
        Discover WABA ID and phone number ID from the Graph API.

        When the WA_EMBEDDED_SIGNUP session event doesn't fire (common for
        existing WABAs), we query the API to find the shared assets.
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        # If we don't have the WABA ID, look it up via debug_token or shared WABAs
        if not waba_id:
            # Try debug_token first — it includes granular scopes with asset IDs
            try:
                app_id = getattr(settings, "FACEBOOK_APP_ID", "")
                debug_resp = self.client.get(
                    f"{WA_API_BASE}/debug_token",
                    params={"input_token": access_token},
                    headers={"Authorization": f"Bearer {app_id}|{getattr(settings, 'FACEBOOK_APP_SECRET', '')}"},
                )
                debug_resp.raise_for_status()
                debug_data = debug_resp.json().get("data", {})
                # Extract WABA ID from granular scopes
                for scope in debug_data.get("granular_scopes", []):
                    if scope.get("scope") == "whatsapp_business_management":
                        target_ids = scope.get("target_ids", [])
                        if target_ids:
                            waba_id = str(target_ids[0])
                            logger.info("Discovered WABA %s from debug_token", waba_id)
                            break
            except Exception as e:
                logger.warning("debug_token lookup failed: %s", e)

        # If we have WABA but no phone number, list phone numbers under the WABA
        if waba_id and not phone_number_id:
            try:
                phones_resp = self.client.get(
                    f"{WA_API_BASE}/{waba_id}/phone_numbers",
                    headers=headers,
                )
                phones_resp.raise_for_status()
                phones = phones_resp.json().get("data", [])
                if phones:
                    phone_number_id = str(phones[0]["id"])
                    logger.info("Discovered phone %s from WABA %s", phone_number_id, waba_id)
            except Exception as e:
                logger.warning("Phone number lookup failed: %s", e)

        return waba_id, phone_number_id

    # ── Profile audit (P4.2 — WhatsApp into Magic Fill) ──────────────────

    def audit_profile(self, access_token: str, **kwargs) -> ProfileSnapshot:
        """Fetch the WABA business profile so Magic Fill can pre-populate
        company name, website, email, vertical (industry), and address."""
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        if not token or not phone_id:
            return ProfileSnapshot(
                error="WhatsApp business profile audit requires a connected phone number.",
            )
        url = (
            f"https://graph.facebook.com/v18.0/{phone_id}/whatsapp_business_profile"
            "?fields=about,address,description,email,profile_picture_url,vertical,websites"
        )
        try:
            resp = self.client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code != 200:
                return ProfileSnapshot(error=f"WhatsApp API {resp.status_code}: {resp.text[:120]}")
            payload = resp.json().get("data", [{}])
            data = payload[0] if isinstance(payload, list) and payload else {}
        except Exception as e:  # pragma: no cover
            return ProfileSnapshot(error=f"WhatsApp profile fetch failed: {e}")

        websites = data.get("websites") or []
        website = websites[0] if websites else ""
        return ProfileSnapshot(
            bio=(data.get("about") or "").strip(),
            description=(data.get("description") or "").strip(),
            email=(data.get("email") or "").strip(),
            website=website,
            address=(data.get("address") or "").strip(),
            category=(data.get("vertical") or "").strip(),
            profile_picture_url=(data.get("profile_picture_url") or "").strip(),
        )

    # ── Messaging ────────────────────────────────────────────────────────

    def _get_token(self, access_token: str) -> str:
        """Use per-account token if available, otherwise global."""
        return access_token or self.access_token

    def _get_phone_id(self, access_token: str, **kwargs) -> str:
        """Get the phone number ID for API calls."""
        return kwargs.get("phone_number_id", self.phone_number_id)

    def send_text_message(self, access_token: str, to: str, body: str,
                          preview_url: bool = False, **kwargs) -> dict:
        """
        Send a plain text message.

        Args:
            access_token: WhatsApp access token
            to: Recipient's WhatsApp ID (phone number without +)
            body: Message text
            preview_url: Whether to show link preview
        Returns:
            dict with 'success', 'wamid', or 'error'
        """
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": body,
            },
        }
        return self._send_api_message(token, phone_id, payload)

    def send_image_message(self, access_token: str, to: str, image_url: str,
                           caption: str = "", **kwargs) -> dict:
        """Send an image message with optional caption."""
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        image_data = {"link": image_url}
        if caption:
            image_data["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": image_data,
        }
        return self._send_api_message(token, phone_id, payload)

    def send_template_message(self, access_token: str, to: str,
                              template_name: str, language_code: str = "en",
                              components: Optional[list] = None, **kwargs) -> dict:
        """
        Send a pre-approved template message.

        This is the ONLY way to message someone outside the 24-hour window.
        Templates must be approved by Meta before use.

        Args:
            access_token: WhatsApp access token
            to: Recipient's WhatsApp ID
            template_name: Name of the approved template
            language_code: Template language (e.g., 'en', 'sw')
            components: Template variable components [{type, parameters}]
        Returns:
            dict with 'success', 'wamid', or 'error'
        """
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        template_data = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template_data["components"] = components
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template_data,
        }
        return self._send_api_message(token, phone_id, payload)

    def send_interactive_buttons(self, access_token: str, to: str,
                                 body: str, buttons: list[dict],
                                 header: str = "", footer: str = "",
                                 **kwargs) -> dict:
        """
        Send an interactive message with reply buttons (max 3).

        Args:
            buttons: [{id: "btn_1", title: "Yes"}, {id: "btn_2", title: "No"}]
        """
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        interactive = {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in buttons[:3]
                ],
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return self._send_api_message(token, phone_id, payload)

    def send_interactive_list(self, access_token: str, to: str,
                              body: str, button_text: str,
                              sections: list[dict], header: str = "",
                              footer: str = "", **kwargs) -> dict:
        """
        Send an interactive list message.

        Args:
            button_text: Text on the "view options" button
            sections: [{title: "Section", rows: [{id, title, description}]}]
        """
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        interactive = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections[:10],
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return self._send_api_message(token, phone_id, payload)

    def mark_as_read(self, access_token: str, wamid: str, **kwargs) -> bool:
        """Mark an inbound message as read (shows blue checkmarks to sender)."""
        token = self._get_token(access_token)
        phone_id = self._get_phone_id(access_token, **kwargs)
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wamid,
        }
        try:
            resp = self.client.post(
                f"{WA_API_BASE}/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Failed to mark message as read: %s", e)
            return False

    # ── Template Management ──────────────────────────────────────────────

    def create_template(self, access_token: str, waba_id: str,
                        name: str, category: str, language: str,
                        components: list[dict], **kwargs) -> dict:
        """
        Submit a new template to Meta for approval.

        Args:
            waba_id: WhatsApp Business Account ID
            name: Template name (lowercase, underscores)
            category: marketing | utility | authentication
            language: Language code (e.g., 'en', 'sw')
            components: Template components [{type: HEADER|BODY|FOOTER|BUTTONS, ...}]
        Returns:
            dict with 'success', 'template_id', or 'error'
        """
        token = self._get_token(access_token)
        payload = {
            "name": name,
            "category": category.upper(),
            "language": language,
            "components": components,
        }
        try:
            resp = self.client.post(
                f"{WA_API_BASE}/{waba_id}/message_templates",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            data = resp.json()
            if resp.status_code == 200:
                return {
                    "success": True,
                    "template_id": data.get("id", ""),
                    "status": data.get("status", ""),
                }
            return {
                "success": False,
                "error": data.get("error", {}).get("message", str(data)),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_templates(self, access_token: str, waba_id: str, **kwargs) -> list[dict]:
        """Fetch all templates for this WhatsApp Business Account."""
        token = self._get_token(access_token)
        try:
            resp = self.client.get(
                f"{WA_API_BASE}/{waba_id}/message_templates",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 100},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.error("Failed to fetch WhatsApp templates: %s", e)
            return []

    # ── BaseProvider interface (required methods) ────────────────────────

    def publish_post(self, access_token: str, content: str,
                     media_urls: Optional[list[str]] = None,
                     **kwargs) -> PublishResult:
        """
        For WhatsApp, "publishing" means sending a template message to a list
        of recipients (broadcast). The kwargs should include:
        - template_name: str
        - recipients: list[str] (WhatsApp IDs)
        - language_code: str
        - components: list[dict] (template variables)
        """
        template_name = kwargs.get("template_name", "")
        recipients = kwargs.get("recipients", [])
        language_code = kwargs.get("language_code", "en")
        components = kwargs.get("components")

        if not template_name or not recipients:
            return PublishResult(
                success=False,
                error="template_name and recipients are required for WhatsApp publishing",
            )

        sent = 0
        failed = 0
        last_wamid = ""
        for recipient in recipients:
            result = self.send_template_message(
                access_token, recipient, template_name, language_code, components,
            )
            if result.get("success"):
                sent += 1
                last_wamid = result.get("wamid", "")
            else:
                failed += 1

        return PublishResult(
            success=sent > 0,
            platform_post_id=last_wamid,
            metadata={"sent": sent, "failed": failed, "total": len(recipients)},
        )

    def get_post_metrics(self, access_token: str,
                         platform_post_id: str) -> PostMetrics:
        """WhatsApp doesn't have per-post metrics in the same way. Returns empty."""
        return PostMetrics()

    def send_message(self, access_token: str, recipient_id: str,
                     message: str, **kwargs) -> dict:
        """Send a text message (BaseProvider interface)."""
        result = self.send_text_message(access_token, recipient_id, message, **kwargs)
        return result

    def get_messages(self, access_token: str, **kwargs) -> list[dict]:
        """WhatsApp messages come via webhook, not polling. Returns empty."""
        return []

    # ── Webhook Signature Verification ───────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify that a webhook payload was sent by Meta.

        Meta signs webhooks with HMAC-SHA256 using the app secret.
        The signature header format is: sha256=<hex_digest>
        """
        if not self.app_secret:
            logger.warning("WHATSAPP_APP_SECRET not set — skipping signature verification")
            return True  # Allow in dev, but log warning

        expected = hmac.new(
            self.app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        provided = signature.replace("sha256=", "") if signature else ""
        return hmac.compare_digest(expected, provided)

    # ── Internal ─────────────────────────────────────────────────────────

    def _send_api_message(self, token: str, phone_id: str, payload: dict) -> dict:
        """Send a message via the WhatsApp Cloud API."""
        try:
            resp = self.client.post(
                f"{WA_API_BASE}/{phone_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = resp.json()

            if resp.status_code == 200 and "messages" in data:
                wamid = data["messages"][0].get("id", "")
                logger.info("WhatsApp message sent: %s → %s", payload.get("to"), wamid)
                return {"success": True, "wamid": wamid}

            error_msg = data.get("error", {}).get("message", str(data))
            error_code = data.get("error", {}).get("code", 0)
            logger.error("WhatsApp send failed: %s (code=%s)", error_msg, error_code)
            return {"success": False, "error": error_msg, "error_code": error_code}

        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            logger.error("WhatsApp API error: %s", e)
            return {"success": False, "error": str(e)}


# ── Auto-register ────────────────────────────────────────────────────────────
register_provider(WhatsAppProvider())
