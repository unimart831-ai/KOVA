"""
Resilient HTTP client for external API calls.

Provides retry with exponential backoff + jitter for transient failures.
Used by: platform providers, M-Pesa, email services, media uploads.

Retries on:
  - HTTP 429 (Rate Limited)
  - HTTP 500, 502, 503, 504 (Server Errors)
  - Connection errors, timeouts

Does NOT retry:
  - HTTP 401, 403 (auth failures — these are permanent)
  - HTTP 400, 404 (client errors — retrying won't help)
"""

import logging
import random
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Status codes that indicate transient failures (safe to retry)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Status codes that indicate permanent auth failures (do NOT retry)
PERMANENT_ERROR_CODES = {401, 403}

# Default configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 30.0  # seconds
DEFAULT_TIMEOUT = 30  # seconds


class TransientAPIError(Exception):
    """Raised when an API returns a retryable error after all retries exhausted."""

    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PermanentAPIError(Exception):
    """Raised when an API returns a non-retryable error (401, 403)."""

    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def is_transient_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a transient (retryable) error."""
    return status_code in RETRYABLE_STATUS_CODES


def is_permanent_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a permanent (non-retryable) error."""
    return status_code in PERMANENT_ERROR_CODES


def _calculate_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Exponential backoff with full jitter."""
    exp_delay = base_delay * (2 ** attempt)
    capped = min(exp_delay, max_delay)
    return random.uniform(0, capped)


def resilient_request(
    method: str,
    url: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    timeout: int = DEFAULT_TIMEOUT,
    service_name: str = "external",
    raise_for_status: bool = True,
    # httpx request kwargs
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    json: Optional[dict] = None,
    files: Optional[dict] = None,
    auth: Optional[tuple] = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    """
    Make an HTTP request with automatic retry on transient failures.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        url: The URL to request
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay cap in seconds
        timeout: Request timeout in seconds
        service_name: Name for logging (e.g., "twitter", "mpesa")
        raise_for_status: If True, raise on non-2xx after retries
        **kwargs: Passed through to httpx (headers, params, json, data, files, auth)

    Returns:
        httpx.Response on success

    Raises:
        PermanentAPIError: On 401/403 (no retry attempted)
        TransientAPIError: On retryable errors after all retries exhausted
        httpx.TimeoutException: On timeout after all retries exhausted
    """
    last_exception = None
    request_kwargs = {"timeout": timeout, "follow_redirects": follow_redirects}
    if headers:
        request_kwargs["headers"] = headers
    if params:
        request_kwargs["params"] = params
    if data:
        request_kwargs["data"] = data
    if json:
        request_kwargs["json"] = json
    if files:
        request_kwargs["files"] = files
    if auth:
        request_kwargs["auth"] = auth

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client() as client:
                response = client.request(method, url, **request_kwargs)

            # Permanent errors — fail immediately, don't retry
            if is_permanent_error(response.status_code):
                body = response.text[:500]
                logger.warning(
                    "[%s] Permanent error %d on %s %s: %s",
                    service_name, response.status_code, method, url, body,
                )
                raise PermanentAPIError(
                    f"{service_name} returned {response.status_code}",
                    status_code=response.status_code,
                    response_body=body,
                )

            # Transient errors — retry with backoff
            if is_transient_error(response.status_code):
                # Check for Retry-After header (rate limiting)
                retry_after = response.headers.get("Retry-After")
                if retry_after and attempt < max_retries:
                    try:
                        delay = min(float(retry_after), max_delay)
                    except (ValueError, TypeError):
                        delay = _calculate_delay(attempt, base_delay, max_delay)
                else:
                    delay = _calculate_delay(attempt, base_delay, max_delay)

                if attempt < max_retries:
                    logger.info(
                        "[%s] Transient %d on %s %s — retry %d/%d in %.1fs",
                        service_name, response.status_code, method, url,
                        attempt + 1, max_retries, delay,
                    )
                    time.sleep(delay)
                    continue
                else:
                    # All retries exhausted
                    body = response.text[:500]
                    logger.error(
                        "[%s] All %d retries exhausted for %s %s (last status: %d)",
                        service_name, max_retries, method, url, response.status_code,
                    )
                    raise TransientAPIError(
                        f"{service_name} returned {response.status_code} after {max_retries} retries",
                        status_code=response.status_code,
                        response_body=body,
                    )

            # Success or other client error
            if raise_for_status:
                response.raise_for_status()

            return response

        except PermanentAPIError:
            raise  # Don't retry permanent errors

        except TransientAPIError:
            raise  # Already exhausted retries

        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            last_exception = exc
            if attempt < max_retries:
                delay = _calculate_delay(attempt, base_delay, max_delay)
                logger.info(
                    "[%s] Connection error on %s %s — retry %d/%d in %.1fs: %s",
                    service_name, method, url, attempt + 1, max_retries, delay, exc,
                )
                time.sleep(delay)
                continue
            else:
                logger.error(
                    "[%s] All %d retries exhausted for %s %s: %s",
                    service_name, max_retries, method, url, exc,
                )
                raise

        except httpx.HTTPStatusError:
            # Non-retryable HTTP error (4xx except 401/403/429)
            raise

        except Exception as exc:
            # Unexpected error — don't retry
            logger.error("[%s] Unexpected error on %s %s: %s", service_name, method, url, exc)
            raise

    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise TransientAPIError(f"{service_name}: request failed after {max_retries} retries")


# ─── Convenience wrappers ────────────────────────────────────────────────────

def resilient_get(url, *, service_name="external", **kwargs) -> httpx.Response:
    """GET with retry."""
    return resilient_request("GET", url, service_name=service_name, **kwargs)


def resilient_post(url, *, service_name="external", **kwargs) -> httpx.Response:
    """POST with retry."""
    return resilient_request("POST", url, service_name=service_name, **kwargs)
