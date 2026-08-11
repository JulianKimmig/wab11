"""
WAB11 Modbus register definitions and format handling.

This module contains the complete catalog of Modbus registers
for the WAB11 controller and utilities for encoding/decoding values.
"""

from __future__ import annotations

from .definitions import (
    ALL_REGISTERS,
    ENERGY_REGISTERS,
    HEAT_PUMP_REGISTERS,
    HEATING_CIRCUIT_REGISTERS,
    HOT_WATER_REGISTERS,
    INPUTS_REGISTERS,
    SECONDARY_HEAT_REGISTERS,
    SYSTEM_REGISTERS,
    DataFormat,
    RegisterDef,
    RegisterType,
    generate_heating_circuit_registers,
)
from .formats import FormatCodec

__all__ = [
    # Register definitions
    "RegisterDef",
    "RegisterType",
    "DataFormat",
    "ALL_REGISTERS",
    "SYSTEM_REGISTERS",
    "HEATING_CIRCUIT_REGISTERS",
    "HOT_WATER_REGISTERS",
    "HEAT_PUMP_REGISTERS",
    "SECONDARY_HEAT_REGISTERS",
    "INPUTS_REGISTERS",
    "ENERGY_REGISTERS",
    "generate_heating_circuit_registers",
    # Format handling
    "FormatCodec",
]
