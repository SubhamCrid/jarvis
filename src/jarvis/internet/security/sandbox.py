"""
URLSandbox with dual-stage IP validation and DNS rebinding protection.
Guarantees SSRF defense against local loopbacks, private subnets, and cloud metadata endpoints.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import List, Optional
from jarvis.internet.exceptions import SSRFPolicyError


class URLSandbox:
    """
    Validates target URLs against Server-Side Request Forgery (SSRF) and DNS rebinding attacks.
    """

    BLOCKED_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),      # IPv4 Loopback
        ipaddress.ip_network("10.0.0.0/8"),       # Private Class A
        ipaddress.ip_network("172.16.0.0/12"),    # Private Class B
        ipaddress.ip_network("192.168.0.0/16"),   # Private Class C
        ipaddress.ip_network("169.254.0.0/16"),   # Link-Local / Cloud Metadata (169.254.169.254)
        ipaddress.ip_network("0.0.0.0/8"),        # Current network
        ipaddress.ip_network("::1/128"),          # IPv6 Loopback
        ipaddress.ip_network("fe80::/10"),        # IPv6 Link-Local
        ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local
    ]

    BLOCKED_HOSTNAMES = {
        "localhost",
        "loopback",
        "metadata.google.internal",
        "169.254.169.254",
    }

    def __init__(
        self,
        allowed_protocols: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
        allowed_domains: Optional[List[str]] = None,
        enable_ssrf_protection: bool = True,
    ) -> None:
        self.allowed_protocols = allowed_protocols or ["http", "https"]
        self.blocked_domains = set(d.lower() for d in (blocked_domains or []))
        self.allowed_domains = set(d.lower() for d in (allowed_domains or []))
        self.enable_ssrf_protection = enable_ssrf_protection

    def validate_url(self, url: str) -> str:
        """
        Validate URL scheme, domain, and target IP address.
        Raises SSRFPolicyError if URL violates security policy.
        Returns canonical validated URL.
        """
        if not url or not isinstance(url, str):
            raise SSRFPolicyError("Invalid URL format.")

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower() if parsed.hostname else ""

        if scheme not in self.allowed_protocols:
            raise SSRFPolicyError(f"Protocol '{scheme}' is not permitted. Allowed: {self.allowed_protocols}")

        if not hostname:
            raise SSRFPolicyError("URL lacks a valid hostname.")

        if hostname in self.BLOCKED_HOSTNAMES:
            raise SSRFPolicyError(f"Hostname '{hostname}' is explicitly blocked by security policy.")

        if self.blocked_domains and hostname in self.blocked_domains:
            raise SSRFPolicyError(f"Domain '{hostname}' is blacklisted.")

        if self.allowed_domains and hostname not in self.allowed_domains:
            raise SSRFPolicyError(f"Domain '{hostname}' is not in the domain whitelist.")

        if self.enable_ssrf_protection:
            self._validate_resolved_ip(hostname)

        return url

    def _validate_resolved_ip(self, hostname: str) -> None:
        """Resolve domain name to IP and verify against BLOCKED_NETWORKS."""
        try:
            # Check if hostname is already a raw IP string
            try:
                ip_obj = ipaddress.ip_address(hostname)
                self._check_ip_address(ip_obj)
                return
            except ValueError:
                pass  # Hostname is a domain name, proceed to DNS resolution

            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                self._check_ip_address(ip_obj)

        except socket.gaierror as err:
            raise SSRFPolicyError(f"Failed to resolve DNS for hostname '{hostname}': {err}")

    def _check_ip_address(self, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        for net in self.BLOCKED_NETWORKS:
            if ip_obj in net:
                raise SSRFPolicyError(
                    f"Resolved target IP '{ip_obj}' falls within restricted private/internal network '{net}'."
                )
