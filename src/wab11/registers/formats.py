"""
Format encoding and decoding for WAB11 Modbus registers.

Handles conversion between raw 16-bit Modbus values and
Python types based on the data format specification.
"""

from __future__ import annotations

from typing import Any

from ..models.base import (
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HeatingCircuitStatus,
    HeatPumpConfig,
    HotWaterConfig,
    HotWaterStatus,
    OperatingState,
    RequestType,
    SystemMode,
    Temperature,
)
from .definitions import DataFormat


class FormatCodec:
    """
    Encode and decode register values between raw Modbus and Python types.

    This class handles the conversion based on the DataFormat specification
    for each register, ensuring correct interpretation of temperatures,
    enums, booleans, and other value types.
    """

    @staticmethod
    def decode(fmt: DataFormat, raw: int) -> Any:
        """
        Decode a raw register value to the appropriate Python type.

        Args:
            fmt: The data format specification
            raw: Raw 16-bit register value (0-65535)

        Returns:
            Decoded Python value (Temperature, enum, int, bool, etc.)
        """
        match fmt:
            case DataFormat.TEMPERATURE:
                return Temperature(FormatCodec._to_signed(raw))

            case DataFormat.BOOL:
                return bool(raw)

            case DataFormat.SYSTEM_MODE:
                try:
                    return SystemMode(raw)
                except ValueError:
                    return raw

            case DataFormat.OPERATING_STATE:
                try:
                    return OperatingState(raw)
                except ValueError:
                    return raw

            case DataFormat.HEATING_MODE:
                try:
                    return HeatingCircuitMode(raw)
                except ValueError:
                    return raw

            case DataFormat.HEATING_STATUS:
                try:
                    return HeatingCircuitStatus(raw)
                except ValueError:
                    return raw

            case DataFormat.HEATING_CONFIG:
                try:
                    return HeatingCircuitConfig(raw)
                except ValueError:
                    return raw

            case DataFormat.HOT_WATER_STATUS:
                try:
                    return HotWaterStatus(raw)
                except ValueError:
                    return raw

            case DataFormat.HOT_WATER_CONFIG:
                try:
                    return HotWaterConfig(raw)
                except ValueError:
                    return raw

            case DataFormat.HEAT_PUMP_CONFIG:
                try:
                    return HeatPumpConfig(raw)
                except ValueError:
                    return raw

            case DataFormat.REQUEST_TYPE:
                try:
                    return RequestType(raw)
                except ValueError:
                    return raw

            case DataFormat.PERCENTAGE:
                # 0xFFFF typically means "no value"
                if raw == 0xFFFF:
                    return None
                return raw

            case DataFormat.SIGNED_16:
                return FormatCodec._to_signed(raw)

            case DataFormat.UNSIGNED_16:
                return raw

            case _:
                return raw

    @staticmethod
    def encode(fmt: DataFormat, value: Any) -> int:
        """
        Encode a Python value to a raw register value.

        Args:
            fmt: The data format specification
            value: Python value to encode

        Returns:
            Raw 16-bit register value (0-65535)

        Raises:
            TypeError: If the value type is incompatible with the format
            ValueError: If the value is out of range
        """
        match fmt:
            case DataFormat.TEMPERATURE:
                if isinstance(value, Temperature):
                    raw = value.raw
                elif isinstance(value, (int, float)):
                    raw = int(round(value * 10))
                else:
                    raise TypeError(
                        f"Cannot encode {type(value).__name__} as temperature"
                    )
                return FormatCodec._to_unsigned(raw)

            case DataFormat.BOOL:
                return 1 if value else 0

            case DataFormat.SYSTEM_MODE:
                if isinstance(value, SystemMode):
                    return value.value
                elif isinstance(value, int):
                    return value
                elif isinstance(value, str):
                    return SystemMode[value.upper()].value
                raise TypeError(f"Cannot encode {type(value).__name__} as SystemMode")

            case DataFormat.OPERATING_STATE:
                if isinstance(value, OperatingState):
                    return value.value
                return int(value)

            case DataFormat.HEATING_MODE:
                if isinstance(value, HeatingCircuitMode):
                    return value.value
                elif isinstance(value, int):
                    return value
                elif isinstance(value, str):
                    return HeatingCircuitMode[value.upper()].value
                raise TypeError(
                    f"Cannot encode {type(value).__name__} as HeatingCircuitMode"
                )

            case DataFormat.HEATING_STATUS:
                if isinstance(value, HeatingCircuitStatus):
                    return value.value
                return int(value)

            case DataFormat.HEATING_CONFIG:
                if isinstance(value, HeatingCircuitConfig):
                    return value.value
                return int(value)

            case DataFormat.HOT_WATER_STATUS:
                if isinstance(value, HotWaterStatus):
                    return value.value
                return int(value)

            case DataFormat.HOT_WATER_CONFIG:
                if isinstance(value, HotWaterConfig):
                    return value.value
                return int(value)

            case DataFormat.HEAT_PUMP_CONFIG:
                if isinstance(value, HeatPumpConfig):
                    return value.value
                return int(value)

            case DataFormat.REQUEST_TYPE:
                if isinstance(value, RequestType):
                    return value.value
                return int(value)

            case DataFormat.PERCENTAGE:
                if value is None:
                    return 0xFFFF
                return int(value)

            case DataFormat.SIGNED_16:
                return FormatCodec._to_unsigned(int(value))

            case DataFormat.UNSIGNED_16:
                return int(value)

            case _:
                return int(value)

    @staticmethod
    def _to_signed(value: int) -> int:
        """Convert unsigned 16-bit to signed."""
        if value >= 0x8000:
            return value - 0x10000
        return value

    @staticmethod
    def _to_unsigned(value: int) -> int:
        """Convert signed to unsigned 16-bit."""
        if value < 0:
            return value + 0x10000
        return value & 0xFFFF
