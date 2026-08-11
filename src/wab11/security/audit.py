"""
Audit logging for WAB11 operations.

Maintains an audit trail of all read and write operations
for debugging, monitoring, and compliance.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """
    Single audit log entry.

    Attributes:
        timestamp: When the operation occurred
        operation: Type of operation ("read" or "write")
        register: Register name involved
        old_value: Previous value (for writes)
        new_value: New value (for writes) or read value
        success: Whether the operation succeeded
        error: Error message if operation failed
        source: Origin of operation ("api", "polling", "sync")
    """

    timestamp: datetime
    operation: str  # "read" or "write"
    register: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    success: bool
    error: Optional[str] = None
    source: str = "api"

    def __repr__(self) -> str:
        status = "OK" if self.success else f"FAILED({self.error})"
        if self.operation == "write":
            return (
                f"AuditEntry({self.timestamp.isoformat()}, "
                f"WRITE {self.register}: {self.old_value} -> {self.new_value}, "
                f"{status})"
            )
        else:
            return (
                f"AuditEntry({self.timestamp.isoformat()}, "
                f"READ {self.register}: {self.new_value}, "
                f"{status})"
            )


@dataclass
class AuditLog:
    """
    Maintains an audit trail of all operations.

    Features:
    - In-memory ring buffer for recent entries
    - Structured logging integration
    - Query methods for recent operations
    - Export capability for external storage

    Usage:
        audit = AuditLog(max_entries=10000)
        audit.log_write("system_mode", old_value=0, new_value=1, success=True)

        for entry in audit.get_recent(100):
            print(entry)
    """

    max_entries: int = 10000
    _entries: deque = field(default_factory=deque, repr=False)
    _logger: logging.Logger = field(default_factory=lambda: logger, repr=False)

    def __post_init__(self) -> None:
        """Initialize the deque with max length."""
        self._entries = deque(maxlen=self.max_entries)

    def log_write(
        self,
        register: str,
        old_value: Any,
        new_value: Any,
        success: bool,
        error: Optional[str] = None,
        source: str = "api",
    ) -> AuditEntry:
        """
        Log a write operation.

        Args:
            register: Register name that was written
            old_value: Value before the write
            new_value: Value after the write (or attempted value)
            success: Whether the write succeeded
            error: Error message if write failed
            source: Origin of the write operation

        Returns:
            The created audit entry
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            operation="write",
            register=register,
            old_value=old_value,
            new_value=new_value,
            success=success,
            error=error,
            source=source,
        )
        self._entries.append(entry)

        # Log to standard logger
        if success:
            self._logger.info(
                f"WRITE {register}: {old_value} -> {new_value} [source={source}]"
            )
        else:
            self._logger.warning(
                f"WRITE FAILED {register}: {old_value} -> {new_value} "
                f"[source={source}, error={error}]"
            )

        return entry

    def log_read(
        self,
        register: str,
        value: Any,
        success: bool,
        error: Optional[str] = None,
        source: str = "polling",
    ) -> AuditEntry:
        """
        Log a read operation.

        Read operations are logged at debug level to avoid log spam.

        Args:
            register: Register name that was read
            value: Value that was read (or None if failed)
            success: Whether the read succeeded
            error: Error message if read failed
            source: Origin of the read operation

        Returns:
            The created audit entry
        """
        entry = AuditEntry(
            timestamp=datetime.now(),
            operation="read",
            register=register,
            old_value=None,
            new_value=value,
            success=success,
            error=error,
            source=source,
        )
        self._entries.append(entry)

        # Only log failures to standard logger
        if not success:
            self._logger.debug(f"READ FAILED {register}: {error}")

        return entry

    def get_recent(self, count: int = 100) -> list[AuditEntry]:
        """
        Get the most recent audit entries.

        Args:
            count: Maximum number of entries to return

        Returns:
            List of recent entries (newest last)
        """
        entries = list(self._entries)
        return entries[-count:] if len(entries) > count else entries

    def get_writes(
        self,
        register: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[AuditEntry]:
        """
        Get write entries, optionally filtered.

        Args:
            register: Filter by register name (None for all)
            since: Filter to entries after this time

        Returns:
            List of matching write entries
        """
        entries = [e for e in self._entries if e.operation == "write"]

        if register:
            entries = [e for e in entries if e.register == register]

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries

    def get_failures(
        self,
        since: Optional[datetime] = None,
    ) -> list[AuditEntry]:
        """
        Get all failed operations.

        Args:
            since: Filter to entries after this time

        Returns:
            List of failed entries
        """
        entries = [e for e in self._entries if not e.success]

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries

    def get_by_register(self, register: str) -> list[AuditEntry]:
        """
        Get all entries for a specific register.

        Args:
            register: Register name

        Returns:
            List of entries for that register
        """
        return [e for e in self._entries if e.register == register]

    def clear(self) -> None:
        """Clear all audit entries."""
        self._entries.clear()

    def __len__(self) -> int:
        """Get number of entries in the log."""
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        """Iterate over all entries."""
        return iter(self._entries)

    def export(self) -> list[dict]:
        """
        Export all entries as dictionaries.

        Useful for external storage or serialization.

        Returns:
            List of entry dictionaries
        """
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "operation": e.operation,
                "register": e.register,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "success": e.success,
                "error": e.error,
                "source": e.source,
            }
            for e in self._entries
        ]
