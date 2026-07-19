"""Guards against SSRF: only ever fetch public http(s) hosts.

Used at the top of :func:`scrape_company` (blocks the initial URL) and on
every redirect hop inside the Tier-1 fetcher (blocks a public URL that
redirects somewhere internal). DNS resolution happens here rather than being
left to the HTTP client, so we validate the actual IP(s) a host resolves to —
not just the hostname string.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL is not a fetchable public http(s) host."""


def normalize_url(url: str) -> str:
    """Prepend https:// to a bare domain (e.g. ``acme.com``) if no scheme is given."""
    if not urlparse(url).scheme:
        return f"https://{url}"
    return url


def assert_public_http_url(url: str) -> None:
    """Raise :class:`UnsafeURLError` unless ``url`` is http(s) and every address
    its host resolves to is a public, routable IP.

    Blocking network call (DNS resolution) — run off the event loop.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host: {host}") from exc

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked(ip):
            raise UnsafeURLError(f"Host {host} resolves to a non-public address ({ip})")


def _is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Unwrap IPv4-mapped IPv6 addresses (::ffff:127.0.0.1) before checking —
    # the IPv6 flags don't recognise the embedded IPv4 loopback/private range.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
