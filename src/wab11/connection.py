"""
Modbus TCP connection management for WAB11.

Provides async connection handling with automatic chunking,
retry logic, and connection state monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from .exceptions import ConnectionError, ModbusResponseError, TimeoutError

logger = logging.getLogger(__name__)

# Try to import pymodbus
try:
    from pymodbus.client import AsyncModbusTcpClient
    from pymodbus.exceptions import ModbusException

    PYMODBUS_AVAILABLE = True
except ImportError:
    PYMODBUS_AVAILABLE = False
    AsyncModbusTcpClient = None  # type: ignore
    ModbusException = Exception  # type: ignore


def _check_pymodbus() -> None:
    """Raise ImportError if pymodbus is not available."""
    if not PYMODBUS_AVAILABLE:
        raise ImportError(
            "pymodbus is required for WAB11 communication.\n"
            "Install it with: pip install pymodbus>=3.5"
        )


@dataclass
class ConnectionConfig:
    """
    Configuration for WAB11 Modbus TCP connection.

    Attributes:
        host: IP address of the WAB11 controller
        port: Modbus TCP port (default: 502)
        unit_id: Modbus unit/slave ID (default: 1)
        timeout: Connection and read timeout in seconds
        max_registers_per_read: Maximum registers per read request (WAB11 limit: 5)
        reconnect_delay: Delay between reconnection attempts
        max_retries: Maximum number of retry attempts for operations
    """

    host: str
    port: int = 502
    unit_id: int = 1
    timeout: float = 3.0
    max_registers_per_read: int = 5  # WAB11 documented limit
    reconnect_delay: float = 5.0
    max_retries: int = 3


class WAB11Connection:
    """
    Manages the Modbus TCP connection to a WAB11 controller.

    Features:
    - Async context manager for safe connection handling
    - Automatic chunking of reads (max 5 registers per WAB11 spec)
    - Retry logic with configurable attempts
    - Thread-safe with asyncio locks
    - Connection state monitoring

    Usage:
        config = ConnectionConfig(host="192.168.1.100")
        async with WAB11Connection(config) as conn:
            temps = await conn.read_input_registers(30001, 2)
            await conn.write_register(40001, 1)
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """
        Initialize connection manager.

        Args:
            config: Connection configuration
        """
        _check_pymodbus()

        self._config = config
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._retry_count = 0

    @property
    def config(self) -> ConnectionConfig:
        """Get the connection configuration."""
        return self._config

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self._client is not None

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._config.host

    @property
    def port(self) -> int:
        """Get the port number."""
        return self._config.port

    async def connect(self) -> None:
        """
        Establish connection to WAB11.

        Raises:
            ConnectionError: If connection fails
        """
        async with self._lock:
            if self._connected:
                return

            self._client = AsyncModbusTcpClient(
                host=self._config.host,
                port=self._config.port,
                timeout=self._config.timeout,
            )
            # Set the slave/unit ID for all operations
            self._client.slave = self._config.unit_id  # type: ignore[attr-defined]

            try:
                connected = await self._client.connect()
                if not connected:
                    raise ConnectionError(
                        f"Failed to connect to WAB11 at "
                        f"{self._config.host}:{self._config.port}"
                    )

                self._connected = True
                self._retry_count = 0
                logger.info(
                    f"Connected to WAB11 at {self._config.host}:{self._config.port}"
                )

            except Exception as e:
                self._client = None
                if isinstance(e, ConnectionError):
                    raise
                raise ConnectionError(f"Connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Close connection gracefully."""
        async with self._lock:
            if self._client:
                self._client.close()
                self._client = None
            self._connected = False
            logger.info("Disconnected from WAB11")

    async def reconnect(self) -> None:
        """
        Attempt to reconnect after connection loss.

        Uses exponential backoff with configurable delay.
        """
        await self.disconnect()
        await asyncio.sleep(self._config.reconnect_delay)
        await self.connect()

    async def read_input_registers(
        self,
        address: int,
        count: int = 1,
    ) -> List[int]:
        """
        Read input registers with automatic chunking.

        The WAB11 limits reads to 5 consecutive registers, so this
        method automatically chunks larger requests.

        Args:
            address: Logical address (30001+) - used directly as WAB11 uses full addresses
            count: Number of registers to read

        Returns:
            List of raw register values

        Raises:
            ConnectionError: If read fails
            TimeoutError: If operation times out
        """
        if not self.is_connected:
            await self.connect()

        # WAB11 uses full logical addresses directly (not 0-based offset)
        results: List[int] = []

        # Chunk into max registers per request
        for chunk_start in range(0, count, self._config.max_registers_per_read):
            chunk_size = min(
                self._config.max_registers_per_read,
                count - chunk_start,
            )

            logger.debug(
                f"Reading input registers from {address + chunk_start} to {address + chunk_start + chunk_size}"
            )
            response = await self._read_input_with_retry(
                address + chunk_start,
                chunk_size,
            )
            results.extend(response)

        return results

    async def read_holding_registers(
        self,
        address: int,
        count: int = 1,
    ) -> List[int]:
        """
        Read holding registers with automatic chunking.

        Args:
            address: Logical address (40001+) - used directly as WAB11 uses full addresses
            count: Number of registers to read

        Returns:
            List of raw register values

        Raises:
            ConnectionError: If read fails
            TimeoutError: If operation times out
        """
        if not self.is_connected:
            await self.connect()

        # WAB11 uses full logical addresses directly (not 0-based offset)
        results: List[int] = []

        for chunk_start in range(0, count, self._config.max_registers_per_read):
            chunk_size = min(
                self._config.max_registers_per_read,
                count - chunk_start,
            )

            response = await self._read_holding_with_retry(
                address + chunk_start,
                chunk_size,
            )
            results.extend(response)

        return results

    async def write_register(
        self,
        address: int,
        value: int,
    ) -> None:
        """
        Write a single holding register.

        Args:
            address: Logical address (40001+) - used directly as WAB11 uses full addresses
            value: Raw 16-bit value to write

        Raises:
            ConnectionError: If write fails
            TimeoutError: If operation times out
        """
        if not self.is_connected:
            await self.connect()

        # WAB11 uses full logical addresses directly (not 0-based offset)
        await self._write_with_retry(address, value)

    async def _read_input_with_retry(
        self,
        address: int,
        count: int,
    ) -> List[int]:
        """Read input registers with retry logic."""
        assert self._client is not None

        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries):
            try:
                response = await self._client.read_input_registers(
                    address=address,
                    count=count,
                )

                if response.isError():
                    raise ModbusResponseError(
                        function_code=response.function_code,
                        exception_code=response.exception_code,
                        operation=f"reading input register {address}",
                    )

                return list(response.registers)

            except asyncio.TimeoutError as e:
                last_error = TimeoutError(f"Timeout reading input register {address}")
                logger.warning(f"Read timeout (attempt {attempt + 1}): {e}")

            except ModbusResponseError as e:
                last_error = e
                # Keep expected optional energy rejection quiet without changing
                # retries or suppressing the typed error for generic callers.
                level = (
                    logging.DEBUG
                    if (address, count, e.exception_code) == (36701, 4, 2)
                    else logging.WARNING
                )
                logger.log(level, "Modbus exception (attempt %s): %s", attempt + 1, e)

            except ModbusException as e:
                last_error = ConnectionError(f"Modbus error: {e}")
                logger.warning(f"Modbus error (attempt {attempt + 1}): {e}")

            except Exception as e:
                last_error = ConnectionError(f"Read failed: {e}")
                logger.warning(f"Read error (attempt {attempt + 1}): {e}")

            # Wait before retry
            if attempt < self._config.max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))

        raise last_error or ConnectionError("Read failed after retries")

    async def _read_holding_with_retry(
        self,
        address: int,
        count: int,
    ) -> List[int]:
        """Read holding registers with retry logic."""
        assert self._client is not None

        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries):
            try:
                response = await self._client.read_holding_registers(
                    address=address,
                    count=count,
                )

                if response.isError():
                    raise ModbusResponseError(
                        function_code=response.function_code,
                        exception_code=response.exception_code,
                        operation=f"reading holding register {address}",
                    )

                return list(response.registers)

            except asyncio.TimeoutError as e:
                last_error = TimeoutError(f"Timeout reading holding register {address}")
                logger.warning(f"Read timeout (attempt {attempt + 1}): {e}")

            except ModbusResponseError as e:
                last_error = e
                logger.warning("Modbus exception (attempt %s): %s", attempt + 1, e)

            except ModbusException as e:
                last_error = ConnectionError(f"Modbus error: {e}")
                logger.warning(f"Modbus error (attempt {attempt + 1}): {e}")

            except Exception as e:
                last_error = ConnectionError(f"Read failed: {e}")
                logger.warning(f"Read error (attempt {attempt + 1}): {e}")

            if attempt < self._config.max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))

        raise last_error or ConnectionError("Read failed after retries")

    async def _write_with_retry(
        self,
        address: int,
        value: int,
    ) -> None:
        """Write register with retry logic."""
        assert self._client is not None

        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries):
            try:
                async with self._lock:
                    response = await self._client.write_register(
                        address=address,
                        value=value,
                    )

                    if response.isError():
                        raise ConnectionError(
                            f"Modbus error writing register {address}: {response}"
                        )

                logger.debug(f"Wrote {value} to register {address}")
                return

            except asyncio.TimeoutError as e:
                last_error = TimeoutError(f"Timeout writing register {address}")
                logger.warning(f"Write timeout (attempt {attempt + 1}): {e}")

            except ModbusException as e:
                last_error = ConnectionError(f"Modbus error: {e}")
                logger.warning(f"Modbus error (attempt {attempt + 1}): {e}")

            except Exception as e:
                last_error = ConnectionError(f"Write failed: {e}")
                logger.warning(f"Write error (attempt {attempt + 1}): {e}")

            if attempt < self._config.max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))

        raise last_error or ConnectionError("Write failed after retries")

    async def __aenter__(self) -> "WAB11Connection":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"WAB11Connection({self._config.host}:{self._config.port}, {status})"
