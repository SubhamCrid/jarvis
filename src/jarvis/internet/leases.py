"""
ResourceLeaseManager for deterministic resource ownership & leak prevention.
Manages leases for browser pages, contexts, downloads, and authenticated sessions.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ResourceLease(BaseModel):
    """Lease container tracking resource ownership and TTL."""

    lease_id: str = Field(default_factory=lambda: f"lease-{uuid.uuid4().hex[:8]}")
    resource_type: str  # "browser_context", "download_handle", "session_credential"
    acquired_at: float = Field(default_factory=time.time)
    ttl_sec: float = 30.0
    expired: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_valid(self) -> bool:
        if self.expired:
            return False
        return (time.time() - self.acquired_at) < self.ttl_sec


class ResourceLeaseManager:
    """Thread-safe lease manager providing acquire, renew, release, and expire semantics."""

    def __init__(self) -> None:
        self._leases: Dict[str, ResourceLease] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, resource_type: str, ttl_sec: float = 30.0, metadata: Optional[Dict[str, Any]] = None) -> ResourceLease:
        """Acquire a new resource lease."""
        async with self._lock:
            lease = ResourceLease(
                resource_type=resource_type,
                ttl_sec=ttl_sec,
                metadata=metadata or {},
            )
            self._leases[lease.lease_id] = lease
            return lease

    async def renew(self, lease_id: str, additional_ttl_sec: float = 30.0) -> bool:
        """Renew an existing resource lease."""
        async with self._lock:
            if lease_id in self._leases:
                lease = self._leases[lease_id]
                if lease.is_valid():
                    lease.ttl_sec += additional_ttl_sec
                    return True
            return False

    async def release(self, lease_id: str) -> bool:
        """Release and destroy a resource lease."""
        async with self._lock:
            if lease_id in self._leases:
                self._leases[lease_id].expired = True
                del self._leases[lease_id]
                return True
            return False

    async def cleanup_expired(self) -> int:
        """Purge all expired leases and return count of cleaned leases."""
        async with self._lock:
            expired_ids = [lid for lid, lease in self._leases.items() if not lease.is_valid()]
            for lid in expired_ids:
                del self._leases[lid]
            return len(expired_ids)
