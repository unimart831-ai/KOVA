"""
M-Pesa Daraja API client for Kova Agent.

Handles:
    - OAuth access token generation
    - STK Push (Lipa Na M-Pesa Online) initiation
    - STK Push status query
    - Callback processing

Daraja API docs: https://developer.safaricom.co.ke/
"""

import base64
import logging
from datetime import datetime, timezone as dt_tz

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── API URLs ────────────────────────────────────────────────────────────────
SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


def _get_base_url():
    """Return sandbox or production base URL based on settings."""
    if getattr(settings, "MPESA_ENVIRONMENT", "sandbox") == "production":
        return PRODUCTION_BASE
    return SANDBOX_BASE


# ─── Authentication ──────────────────────────────────────────────────────────

def get_access_token():
    """
    Generate an OAuth access token from Daraja API.

    Uses Consumer Key + Consumer Secret (Basic Auth) to get a Bearer token.
    Token is valid for 1 hour (3599 seconds).
    """
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    if not consumer_key or not consumer_secret:
        raise ValueError("MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET must be set")

    url = f"{_get_base_url()}/oauth/v1/generate?grant_type=client_credentials"

    response = requests.get(
        url,
        auth=(consumer_key, consumer_secret),
        timeout=30,
    )

    if response.status_code != 200:
        logger.error("M-Pesa auth failed: %s %s", response.status_code, response.text)
        raise ConnectionError(f"M-Pesa auth failed: {response.status_code}")

    data = response.json()
    return data["access_token"]


# ─── Password Generation ────────────────────────────────────────────────────

def _generate_password(timestamp):
    """
    Generate the API password.

    Password = Base64(BusinessShortCode + Passkey + Timestamp)
    Timestamp format: YYYYMMDDHHmmss
    """
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


def _get_timestamp():
    """Get current timestamp in M-Pesa format: YYYYMMDDHHmmss (Nairobi time)."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Africa/Nairobi"))
    return now.strftime("%Y%m%d%H%M%S")


# ─── STK Push (Lipa Na M-Pesa Online) ───────────────────────────────────────

def initiate_stk_push(phone_number, amount, account_reference, transaction_desc="Kova Agent"):
    """
    Send an STK Push (payment prompt) to the customer's phone.

    Args:
        phone_number: Customer phone in 254XXXXXXXXX format
        amount: Amount in KES (integer)
        account_reference: Short reference shown on M-Pesa (max 12 chars)
        transaction_desc: Description shown on M-Pesa statement

    Returns:
        dict with MerchantRequestID, CheckoutRequestID, ResponseCode, etc.

    Raises:
        ConnectionError: If M-Pesa API call fails
        ValueError: If credentials are not configured
    """
    timestamp = _get_timestamp()
    password = _generate_password(timestamp)
    access_token = get_access_token()

    url = f"{_get_base_url()}/mpesa/stkpush/v1/processrequest"

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference[:12],
        "TransactionDesc": transaction_desc[:13],
    }

    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    data = response.json()

    if response.status_code != 200 or data.get("ResponseCode") != "0":
        error_msg = data.get("errorMessage") or data.get("ResponseDescription", "Unknown error")
        logger.error("STK Push failed: %s", error_msg)
        raise ConnectionError(f"STK Push failed: {error_msg}")

    logger.info(
        "STK Push initiated: CheckoutRequestID=%s Phone=%s Amount=%s",
        data.get("CheckoutRequestID"),
        phone_number[-4:],  # Log only last 4 digits
        amount,
    )
    return data


def query_stk_push(checkout_request_id):
    """
    Query the status of an STK Push transaction.

    Returns:
        dict with ResultCode (0=success), ResultDesc, etc.
    """
    timestamp = _get_timestamp()
    password = _generate_password(timestamp)
    access_token = get_access_token()

    url = f"{_get_base_url()}/mpesa/stkpushquery/v1/query"

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    return response.json()


# ─── Phone Number Formatting ────────────────────────────────────────────────

def format_phone_number(phone):
    """
    Normalize a Kenyan phone number to 254XXXXXXXXX format.

    Accepts: 0712345678, +254712345678, 254712345678, 712345678
    Returns: 254712345678 (string)
    Raises: ValueError if invalid format
    """
    phone = str(phone).strip().replace(" ", "").replace("-", "")

    # Remove leading +
    if phone.startswith("+"):
        phone = phone[1:]

    # Convert 07xx to 2547xx
    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]

    # Convert 7xx to 2547xx
    if phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone

    # Validate
    if not phone.startswith("254") or len(phone) != 12 or not phone.isdigit():
        raise ValueError(f"Invalid Kenyan phone number: {phone}")

    return phone


# ─── Callback Processing ────────────────────────────────────────────────────

def parse_stk_callback(callback_data):
    """
    Parse the STK Push callback from M-Pesa.

    Args:
        callback_data: The JSON body from M-Pesa callback POST

    Returns:
        dict with keys:
            - success (bool)
            - checkout_request_id (str)
            - merchant_request_id (str)
            - result_code (int)
            - result_desc (str)
            - amount (Decimal, if success)
            - receipt_number (str, if success)
            - transaction_date (datetime, if success)
            - phone_number (str, if success)
    """
    stk = callback_data.get("Body", {}).get("stkCallback", {})

    result = {
        "success": stk.get("ResultCode") == 0,
        "checkout_request_id": stk.get("CheckoutRequestID", ""),
        "merchant_request_id": stk.get("MerchantRequestID", ""),
        "result_code": stk.get("ResultCode"),
        "result_desc": stk.get("ResultDesc", ""),
    }

    # Extract metadata on success
    if result["success"] and stk.get("CallbackMetadata"):
        items = stk["CallbackMetadata"].get("Item", [])
        meta = {item["Name"]: item.get("Value") for item in items}

        result["amount"] = meta.get("Amount")
        result["receipt_number"] = meta.get("MpesaReceiptNumber", "")
        result["phone_number"] = str(meta.get("PhoneNumber", ""))

        # Parse transaction date (format: YYYYMMDDHHmmss as integer)
        txn_date = meta.get("TransactionDate")
        if txn_date:
            try:
                from zoneinfo import ZoneInfo
                result["transaction_date"] = datetime.strptime(
                    str(txn_date), "%Y%m%d%H%M%S"
                ).replace(tzinfo=ZoneInfo("Africa/Nairobi"))
            except (ValueError, TypeError):
                result["transaction_date"] = timezone.now()

    return result
