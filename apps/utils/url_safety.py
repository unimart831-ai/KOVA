"""
SSRF (Server-Side Request Forgery) protection for user-supplied URLs.

Resolves hostnames and rejects requests targeting private/reserved IP ranges
so that internal services (cloud metadata, localhost, RFC-1918 networks) are
never reachable through user-facing endpoints like URL inference.
"""

import ipaddress
import socket
import urllib.parse
from typing import Optional


class SSRFBlockedError(Exception):
    """Raised when a URL resolves to a blocked (private/reserved) IP."""

    def __init__(self, message: str = "This URL is not allowed."):
        super().__init__(message)
        self.message = message


def validate_url_for_ssrf(url: str) -> Optional[str]:
    """Validate that *url* does not target a private or reserved IP.

    Returns ``None`` on success, or a human-readable error string if the URL
    should be blocked.

    Steps:
      1. Parse & enforce http(s) scheme.
      2. Resolve the hostname via ``socket.getaddrinfo``.
      3. Check every resolved address against private/reserved ranges.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Only http and https URLs are supported."

    hostname = parsed.hostname
    if not hostname:
        return "Could not determine the hostname from this URL."

    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return "Could not resolve that hostname."

    if not addr_infos:
        return "Could not resolve that hostname."

    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return f"Unexpected address format: {ip_str}"

        if _is_blocked_ip(ip):
            return "This URL points to an internal or reserved network address."

    return None


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if *ip* falls within a private, loopback, link-local, or
    otherwise reserved range that should never be fetched server-side."""
    if ip.is_private:
        return True
    if ip.is_loopback:
        return True
    if ip.is_link_local:
        return True
    if ip.is_reserved:
        return True
    if ip.is_multicast:
        return True
    if ip.is_unspecified:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        # 100.64.0.0/10 — Carrier-Grade NAT (RFC 6598), not caught by is_private
        # in older Python versions.
        if ip in ipaddress.IPv4Network("100.64.0.0/10"):
            return True

    return False
