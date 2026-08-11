"""
Synchronous wrapper for WAB11Client.

Provides a blocking interface for environments that don't use asyncio,
such as simple scripts or interactive use.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from .client import StateChangeEvent, WAB11Client
from .models.base import HeatingCircuitMode, SystemMode
from .models.energy import EnergyStatistics
from .models.heat_pump import HeatPumpState
from .models.heating import HeatingCircuit
from .models.hot_water import HotWaterState
from .models.inputs import InputsState
from .models.secondary_heat import SecondaryHeatSourceState
from .models.system import SystemState
from .security.audit import AuditLog


class WAB11SyncClient:
    """
    Synchronous wrapper for WAB11Client.

    Useful for simple scripts, REPL usage, or integration with
    synchronous frameworks.

    Note: This wrapper creates its own event loop and runs async
    operations synchronously. For better performance in async
    applications, use WAB11Client directly.

    Usage:
        with WAB11SyncClient("192.168.1.100") as wab:
            wab.sync()
            print(f"Outdoor temp: {wab.system.outdoor_temp}°C")
            wab.set_system_mode(SystemMode.HEATING, confirmed=True)
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        *,
        require_write_confirmation: bool = True,
        enable_rate_limiting: bool = True,
        timeout: float = 3.0,
        n_heating_circuits: int = 5,
    ) -> None:
        """
        Initialize synchronous client.

        Args:
            host: IP address of the WAB11 controller
            port: Modbus TCP port (default: 502)
            unit_id: Modbus unit/slave ID (default: 1)
            require_write_confirmation: Require explicit confirmation for critical writes
            enable_rate_limiting: Enable write rate limiting
            timeout: Connection timeout in seconds
            n_heating_circuits: Number of heating circuits (default: 5)
        """
        self._host = host
        self._port = port
        self._unit_id = unit_id
        self._require_write_confirmation = require_write_confirmation
        self._enable_rate_limiting = enable_rate_limiting
        self._timeout = timeout
        self._n_heating_circuits = n_heating_circuits

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[WAB11Client] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create the event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro):
        """Run a coroutine synchronously."""
        return self._get_loop().run_until_complete(coro)

    def connect(self) -> None:
        """
        Connect to the WAB11 controller.

        This must be called before using other methods, or use
        the context manager interface.
        """
        self._client = WAB11Client(
            self._host,
            self._port,
            self._unit_id,
            require_write_confirmation=self._require_write_confirmation,
            enable_rate_limiting=self._enable_rate_limiting,
            timeout=self._timeout,
            n_heating_circuits=self._n_heating_circuits,
        )
        self._run(self._client.connect())

    def disconnect(self) -> None:
        """Disconnect from the WAB11 controller."""
        if self._client:
            self._run(self._client.disconnect())
            self._client = None

    def __enter__(self) -> "WAB11SyncClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    def _ensure_connected(self) -> WAB11Client:
        """Ensure client is connected and return it."""
        if self._client is None:
            raise RuntimeError(
                "Client not connected. Call connect() first or use context manager."
            )
        return self._client

    # =========================================================================
    # State Properties
    # =========================================================================

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._client is not None and self._client.is_connected

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._host

    @property
    def system(self) -> SystemState:
        """Get system state."""
        return self._ensure_connected().system

    @property
    def heating_circuits(self) -> list[HeatingCircuit]:
        """Get heating circuits."""
        return self._ensure_connected().heating_circuits

    @property
    def hot_water(self) -> HotWaterState:
        """Get hot water state."""
        return self._ensure_connected().hot_water

    @property
    def heat_pump(self) -> HeatPumpState:
        """Get heat pump state."""
        return self._ensure_connected().heat_pump

    @property
    def secondary_heat(self) -> SecondaryHeatSourceState:
        """Get secondary heat source state."""
        return self._ensure_connected().secondary_heat

    @property
    def inputs(self) -> InputsState:
        """Get inputs state."""
        return self._ensure_connected().inputs

    @property
    def energy(self) -> EnergyStatistics:
        """Get energy statistics."""
        return self._ensure_connected().energy

    @property
    def audit_log(self) -> AuditLog:
        """Get audit log."""
        return self._ensure_connected().audit_log

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def sync(self) -> None:
        """Perform full state synchronization."""
        self._run(self._ensure_connected().sync())

    def sync_energy(self) -> None:
        """Sync energy statistics."""
        self._run(self._ensure_connected().sync_energy())

    # =========================================================================
    # Change Events
    # =========================================================================

    def on_change(self, callback: Callable[[StateChangeEvent], None]) -> None:
        """Register a callback for state changes."""
        self._ensure_connected().on_change(callback)

    # =========================================================================
    # Control Methods
    # =========================================================================

    def set_system_mode(self, mode: SystemMode, confirmed: bool = False) -> None:
        """
        Set system operating mode.

        Args:
            mode: Target system mode
            confirmed: Confirm critical operation
        """
        self._run(self._ensure_connected().set_system_mode(mode, confirmed))

    def set_heating_circuit_mode(self, circuit: int, mode: HeatingCircuitMode) -> None:
        """
        Set heating circuit mode.

        Args:
            circuit: Circuit number (1-5)
            mode: Target mode
        """
        self._run(self._ensure_connected().set_heating_circuit_mode(circuit, mode))

    def set_heating_circuit_setpoint(
        self,
        circuit: int,
        level: str,
        temperature: float,
    ) -> None:
        """
        Set heating circuit temperature setpoint.

        Args:
            circuit: Circuit number (1-5)
            level: "comfort", "normal", or "setback"
            temperature: Temperature in °C
        """
        self._run(
            self._ensure_connected().set_heating_circuit_setpoint(
                circuit, level, temperature
            )
        )

    def set_heating_party_pause(
        self,
        circuit: int,
        mode: str,
        hours: float = 2.0,
    ) -> None:
        """
        Set heating circuit party/pause mode.

        Args:
            circuit: Circuit number (1-5)
            mode: "party", "pause", or "auto"
            hours: Duration in hours (0.5-12)
        """
        self._run(
            self._ensure_connected().set_heating_party_pause(circuit, mode, hours)
        )

    def set_hot_water_setpoint(self, level: str, temperature: float) -> None:
        """
        Set hot water temperature setpoint.

        Args:
            level: "normal" or "setback"
            temperature: Temperature in °C
        """
        self._run(self._ensure_connected().set_hot_water_setpoint(level, temperature))

    def trigger_hot_water_push(self, minutes: int = 30) -> None:
        """
        Trigger hot water push/boost.

        Args:
            minutes: Duration (0=off, 5-240)
        """
        self._run(self._ensure_connected().trigger_hot_water_push(minutes))

    def cancel_hot_water_push(self) -> None:
        """Cancel active hot water push."""
        self._run(self._ensure_connected().cancel_hot_water_push())

    # =========================================================================
    # Generic Register Access
    # =========================================================================

    def read_register(self, register_name: str) -> Any:
        """
        Read a register by name.

        Args:
            register_name: Name of the register

        Returns:
            Decoded value
        """
        return self._run(self._ensure_connected().read_register(register_name))

    def write_register(
        self,
        register_name: str,
        value: Any,
        confirmed: bool = False,
    ) -> None:
        """
        Write a register by name.

        Args:
            register_name: Name of the register
            value: Value to write
            confirmed: Confirm critical operations
        """
        self._run(
            self._ensure_connected().write_register(register_name, value, confirmed)
        )

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"WAB11SyncClient({self._host}, {status})"
