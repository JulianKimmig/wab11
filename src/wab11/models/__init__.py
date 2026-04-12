"""
WAB11 data models.

This module contains Pydantic models representing the state of
various components of the WAB11 heat pump controller.
"""

from __future__ import annotations

from .base import (
    HeatingCircuitMode,
    HeatingCircuitStatus,
    HeatPumpConfig,
    HotWaterStatus,
    OperatingState,
    SystemMode,
    Temperature,
)
from .energy import EnergyPeriod, EnergyStatistics
from .heat_pump import HeatPumpState
from .heating import HeatingCircuit, PartyPauseCode
from .hot_water import HotWaterState
from .inputs import InputFunction, InputsState
from .secondary_heat import SecondaryHeatSourceState
from .system import SystemState

__all__ = [
    # Base types and enums
    "Temperature",
    "SystemMode",
    "OperatingState",
    "HeatingCircuitMode",
    "HeatingCircuitStatus",
    "HotWaterStatus",
    "HeatPumpConfig",
    # State models
    "SystemState",
    "HeatingCircuit",
    "PartyPauseCode",
    "HotWaterState",
    "HeatPumpState",
    "SecondaryHeatSourceState",
    "InputsState",
    "InputFunction",
    "EnergyStatistics",
    "EnergyPeriod",
]
