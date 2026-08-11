"""
Base types, enums, and value classes for WAB11 models.

This module contains the fundamental types used throughout the library,
including temperature representation and all Modbus enumeration mappings.
"""

from __future__ import annotations

from enum import IntEnum


class Temperature:
    """
    Represents a temperature value with proper handling of special states.

    The WAB11 Modbus protocol uses specific values to indicate sensor states:
    - NO_SENSOR (-32768): No sensor connected or no request
    - SENSOR_FAULT (-32767): Sensor defect

    Normal temperature values are stored as raw integers where value/10 = °C.

    Examples:
        >>> temp = Temperature(215)
        >>> temp.celsius
        21.5
        >>> temp.is_valid
        True

        >>> no_sensor = Temperature(-32768)
        >>> no_sensor.celsius
        None
        >>> no_sensor.is_valid
        False
    """

    NO_SENSOR: int = -32768
    SENSOR_FAULT: int = -32767

    __slots__ = ("_raw",)

    def __init__(self, raw: int) -> None:
        """
        Initialize from raw Modbus register value.

        Args:
            raw: Raw 16-bit signed value from Modbus register
        """
        self._raw = raw

    @property
    def celsius(self) -> float | None:
        """
        Get temperature in degrees Celsius.

        Returns:
            Temperature in °C, or None if sensor unavailable/faulty.
        """
        if self._raw in (self.NO_SENSOR, self.SENSOR_FAULT):
            return None
        return self._raw / 10.0

    @property
    def raw(self) -> int:
        """Get the raw Modbus register value."""
        return self._raw

    @property
    def is_valid(self) -> bool:
        """Check if temperature reading is valid."""
        return self._raw not in (self.NO_SENSOR, self.SENSOR_FAULT)

    @property
    def is_sensor_fault(self) -> bool:
        """Check if sensor is reporting a fault."""
        return self._raw == self.SENSOR_FAULT

    @property
    def is_no_sensor(self) -> bool:
        """Check if no sensor is connected."""
        return self._raw == self.NO_SENSOR

    @classmethod
    def from_celsius(cls, value: float) -> Temperature:
        """
        Create Temperature from degrees Celsius.

        Args:
            value: Temperature in °C

        Returns:
            Temperature instance
        """
        return cls(int(round(value * 10)))

    @classmethod
    def no_value(cls) -> Temperature:
        """Create a Temperature representing no sensor/no value."""
        return cls(cls.NO_SENSOR)

    def __repr__(self) -> str:
        if self.is_valid:
            return f"Temperature({self.celsius}°C)"
        elif self.is_sensor_fault:
            return "Temperature(SENSOR_FAULT)"
        else:
            return "Temperature(NO_SENSOR)"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Temperature):
            return self._raw == other._raw
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._raw)


class SystemMode(IntEnum):
    """
    System operating mode (Systembetriebsart).

    Corresponds to register 40001.
    """

    AUTOMATIC = 0  # Only available when cooling is enabled
    HEATING = 1  # Heating mode
    COOLING = 2  # Cooling mode (only when cooling enabled)
    SUMMER = 3  # Summer mode (hot water + frost protection only)
    STANDBY = 4  # Standby (frost protection only)
    SECOND_HEAT = 5  # 2nd heat source only (heat pump locked)


class OperatingState(IntEnum):
    """
    Operating state display (Betriebsstatusanzeige).

    Corresponds to register 30006 and represents the current
    operational state shown on the WAB controller display.
    """

    UNDEFINED = 0
    RELAY_TEST = 1
    EMERGENCY_OFF = 2
    DIAGNOSTICS = 3
    MANUAL = 4
    MANUAL_HEATING = 5
    MANUAL_COOLING = 6
    MANUAL_DEFROST = 7
    DEFROST = 8
    SECOND_HEAT_SOURCE = 9
    EVU_LOCK = 10
    SG_TARIFF = 11
    SG_MAXIMUM = 12
    TARIFF_CHARGING = 13
    ELEVATED_OPERATION = 14
    IDLE_TIME = 15
    STANDBY = 16
    FLUSH = 17
    FROST_PROTECTION = 18
    HEATING = 19
    HOT_WATER = 20
    LEGIONELLA_PROTECTION = 21
    HEATING_COOLING_SWITCH = 22
    COOLING = 23
    PASSIVE_COOLING = 24
    SUMMER = 25
    POOL = 26
    VACATION = 27
    SCREED = 28
    LOCKED = 29
    AT_LOCK = 30
    SUMMER_LOCK = 31
    WINTER_LOCK = 32
    OPERATING_LIMIT = 33
    HK_LOCK = 34
    SETBACK = 35


class HeatingCircuitMode(IntEnum):
    """
    Heating circuit operating mode (Heizkreis Betriebsart).

    Corresponds to registers 41x03 for each heating circuit.
    """

    AUTOMATIC = 0  # Follow time program
    COMFORT = 1  # Comfort setpoint
    NORMAL = 2  # Normal setpoint
    SETBACK = 3  # Setback/reduced setpoint
    STANDBY = 4  # Standby mode


class HeatingCircuitStatus(IntEnum):
    """
    Heating circuit status (FormatStatusHeizkreis).

    Indicates the current operational status of a heating circuit.
    """

    OFF = 0  # Standby
    HEATING = 1  # Heating active
    COOLING = 2  # Cooling active
    HEATING_BLOCKED = 3  # Heating blocked
    COOLING_BLOCKED = 4  # Cooling blocked


class HeatingCircuitConfig(IntEnum):
    """
    Heating circuit configuration type (FormatKonfigHeizkreis).

    Set during commissioning, read-only via Modbus.
    """

    NOT_CONFIGURED = 0
    PUMP_CIRCUIT = 1
    MIXER_CIRCUIT = 2
    SETPOINT_PUMP_M1 = 3


class HotWaterStatus(IntEnum):
    """
    Hot water status (FormatStatusWarmwasser).

    Indicates the current state of hot water operation.
    """

    OFF = 0  # Standby
    NO_REQUEST = 1  # No heating request
    PRIORITY_CHARGING = 2  # Priority charging active
    PARALLEL_CHARGING = 3  # Parallel charging active
    REQUEST_BLOCKED = 4  # Request active but blocked


class HotWaterConfig(IntEnum):
    """
    Hot water configuration (FormatKonfigWarmwasser).

    Set during commissioning.
    """

    DISABLED = 0  # Hot water not configured
    DIVERTER_VALVE = 1  # Using diverter valve
    PUMP = 8  # Using dedicated pump


class HeatPumpConfig(IntEnum):
    """
    Heat pump configuration (FormatKonfigWärmepumpe).

    Indicates whether heating and/or cooling is available.
    """

    NOT_CONFIGURED = 0
    HEATING_ONLY = 1
    HEATING_AND_COOLING = 2


class HeatPumpRelease(IntEnum):
    """
    Heat pump release status (FormatFreigabeStatusWP).

    Indicates which modes are currently allowed.
    """

    NONE = 0  # Neither heating nor cooling allowed
    HEATING_ONLY = 1  # Only heating allowed
    COOLING_ONLY = 2  # Only cooling allowed
    HEATING_AND_COOLING = 3  # Both allowed


class RequestType(IntEnum):
    """
    Heating request type (Anforderungstyp).

    Determines how the heating circuit calculates its setpoint.
    """

    OFF = 0
    WEATHER_COMPENSATED = 1  # Based on outdoor temperature curve
    CONSTANT = 3  # Fixed temperature


def decode_signed_16(value: int) -> int:
    """
    Decode an unsigned 16-bit value to signed.

    Args:
        value: Unsigned 16-bit value (0-65535)

    Returns:
        Signed 16-bit value (-32768 to 32767)
    """
    if value >= 0x8000:
        return value - 0x10000
    return value


def encode_signed_16(value: int) -> int:
    """
    Encode a signed value to unsigned 16-bit.

    Args:
        value: Signed value

    Returns:
        Unsigned 16-bit value
    """
    if value < 0:
        return value + 0x10000
    return value
