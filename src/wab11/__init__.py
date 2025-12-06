"""
WAB11 - Python library for Weishaupt WAB11 heat pump control via Modbus TCP.

This library provides a digital twin interface for the WAB11 heat pump
controller, enabling monitoring and control via Modbus TCP protocol.

Quick Start (Async):
    from wab11 import WAB11Client, SystemMode

    async with WAB11Client("192.168.1.100") as wab:
        await wab.sync()
        print(f"Outdoor: {wab.system.outdoor_temp}°C")
        print(f"Mode: {wab.system.system_mode.name}")

        # Change settings (requires confirmation for safety)
        await wab.set_system_mode(SystemMode.HEATING, confirmed=True)
        await wab.set_heating_circuit_setpoint(1, "comfort", 21.5)

Quick Start (Sync):
    from wab11 import WAB11SyncClient, SystemMode

    with WAB11SyncClient("192.168.1.100") as wab:
        wab.sync()
        print(f"Mode: {wab.system.system_mode.name}")

Features:
    - Digital twin pattern: synchronized local state
    - Type-safe models for all WAB11 components
    - Validated, rate-limited write operations
    - Event system for state changes
    - Comprehensive audit logging
    - Both async and sync interfaces

Security:
    - All writes validated against documented limits
    - Critical operations require explicit confirmation
    - Rate limiting prevents excessive writes
    - Full audit trail of all operations

Warning:
    The Modbus TCP interface is unencrypted. Only use on isolated
    network segments as recommended by Weishaupt documentation.
"""

from __future__ import annotations

from ._version import __version__, __version_info__

# Main client classes
from .client import StateChangeEvent, WAB11Client
from .sync_client import WAB11SyncClient

# Connection
from .connection import ConnectionConfig

# Models and enums
from .models.base import (
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HeatingCircuitStatus,
    HeatPumpConfig,
    HeatPumpRelease,
    HotWaterConfig,
    HotWaterStatus,
    OperatingState,
    RequestType,
    SystemMode,
    Temperature,
)
from .models.energy import EnergyPeriod, EnergyStatistics
from .models.heat_pump import HeatPumpState
from .models.heating import HeatingCircuit, PartyPauseCode
from .models.hot_water import HotWaterState
from .models.inputs import InputFunction, InputsState, SGReadyState
from .models.secondary_heat import SecondaryHeatSourceState
from .models.system import SystemState

# Exceptions
from .exceptions import (
    ConnectionError,
    DeviceError,
    DeviceWarning,
    RateLimitError,
    ReadOnlyError,
    RegisterError,
    SafetyError,
    TimeoutError,
    UnknownRegisterError,
    ValidationError,
    WAB11Error,
)

__all__ = [
    # Version
    "__version__",
    "__version_info__",
    # Clients
    "WAB11Client",
    "WAB11SyncClient",
    "StateChangeEvent",
    "ConnectionConfig",
    # Base types and enums
    "Temperature",
    "SystemMode",
    "OperatingState",
    "HeatingCircuitMode",
    "HeatingCircuitStatus",
    "HeatingCircuitConfig",
    "HotWaterStatus",
    "HotWaterConfig",
    "HeatPumpConfig",
    "HeatPumpRelease",
    "RequestType",
    "SGReadyState",
    "InputFunction",
    # State models
    "SystemState",
    "HeatingCircuit",
    "PartyPauseCode",
    "HotWaterState",
    "HeatPumpState",
    "SecondaryHeatSourceState",
    "InputsState",
    "EnergyStatistics",
    "EnergyPeriod",
    # Exceptions
    "WAB11Error",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "SafetyError",
    "RateLimitError",
    "RegisterError",
    "ReadOnlyError",
    "UnknownRegisterError",
    "DeviceError",
    "DeviceWarning",
]

