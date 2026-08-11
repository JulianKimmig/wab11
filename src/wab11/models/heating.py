"""
Heating circuit state models for the WAB11.

Supports up to 5 heating circuits (HK1-HK5), where HK1 is typically
the direct circuit on the controller and HK2-HK5 are via expansion modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .base import (
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HeatingCircuitStatus,
    RequestType,
    Temperature,
)


class PartyPauseCode:
    """
    Encodes/decodes Party/Pause duration values.

    The WAB11 uses a specific encoding for party/pause:
    - Values 1-24: Pause (12h down to 0.5h in 0.5h steps)
    - Value 25: Automatic (no party/pause active)
    - Values 26-48: Party (0.5h to 12h in 0.5h steps)

    Examples:
        >>> PartyPauseCode.pause_hours(2.0)  # 2 hour pause
        21
        >>> PartyPauseCode.party_hours(3.0)  # 3 hour party
        31
        >>> PartyPauseCode.decode(21)
        ('pause', 2.0)
    """

    AUTOMATIC = 25
    MIN_HOURS = 0.5
    MAX_HOURS = 12.0

    @classmethod
    def pause_hours(cls, hours: float) -> int:
        """
        Create pause code for given duration.

        Args:
            hours: Duration in hours (0.5-12.0)

        Returns:
            Encoded party/pause value

        Raises:
            ValueError: If hours out of range
        """
        if not cls.MIN_HOURS <= hours <= cls.MAX_HOURS:
            raise ValueError(f"Pause hours must be {cls.MIN_HOURS}-{cls.MAX_HOURS}")
        steps = int(hours / 0.5)
        return cls.AUTOMATIC - steps  # 24 = 0.5h, 1 = 12h

    @classmethod
    def party_hours(cls, hours: float) -> int:
        """
        Create party code for given duration.

        Args:
            hours: Duration in hours (0.5-12.0)

        Returns:
            Encoded party/pause value

        Raises:
            ValueError: If hours out of range
        """
        if not cls.MIN_HOURS <= hours <= cls.MAX_HOURS:
            raise ValueError(f"Party hours must be {cls.MIN_HOURS}-{cls.MAX_HOURS}")
        steps = int(hours / 0.5)
        return cls.AUTOMATIC + steps  # 26 = 0.5h, 48 = 12h

    @classmethod
    def decode(cls, value: int) -> tuple[str, float | None]:
        """
        Decode a party/pause value.

        Args:
            value: Encoded party/pause value

        Returns:
            Tuple of (mode, hours) where mode is 'party', 'pause', or 'automatic'
        """
        if value == cls.AUTOMATIC:
            return ("automatic", None)
        elif value < cls.AUTOMATIC:
            # Pause: 24 = 0.5h, 1 = 12h
            hours = (cls.AUTOMATIC - value) * 0.5
            return ("pause", hours)
        else:
            # Party: 26 = 0.5h, 48 = 12h
            hours = (value - cls.AUTOMATIC) * 0.5
            return ("party", hours)

    @classmethod
    def is_automatic(cls, value: int) -> bool:
        """Check if value represents automatic mode."""
        return value == cls.AUTOMATIC

    @classmethod
    def is_party(cls, value: int) -> bool:
        """Check if value represents party mode."""
        return value > cls.AUTOMATIC

    @classmethod
    def is_pause(cls, value: int) -> bool:
        """Check if value represents pause mode."""
        return 1 <= value < cls.AUTOMATIC


@dataclass
class HeatingCircuit:
    """
    State model for a single heating circuit (HK1-HK5).

    Each heating circuit can be configured as a pump circuit, mixer circuit,
    or setpoint circuit. The configuration is set during commissioning and
    is read-only via Modbus.

    Input registers: 31x01-31x05 (x = circuit number)
    Holding registers: 41x01-41x12

    Attributes:
        circuit_id: Circuit number (1-5)
        config: Circuit configuration type (read-only)
        status: Current operational status
        room_setpoint_effective: Currently active room setpoint [°C]
        room_temp: Measured room temperature [°C]
        room_humidity: Room humidity [%] (if sensor available)
        flow_setpoint: Calculated flow temperature setpoint [°C]
        flow_temp: Measured flow temperature [°C]
        request_type: How setpoint is calculated
        mode: Operating mode
        party_pause: Party/pause code
        setpoint_comfort: Comfort setpoint [°C]
        setpoint_normal: Normal setpoint [°C]
        setpoint_setback: Setback setpoint [°C]
        heating_curve_slope: Heating curve slope factor
        summer_winter_threshold: Temperature for summer/winter switch
    """

    # Identity
    circuit_id: int = 1

    # Configuration (read-only from commissioning)
    config: HeatingCircuitConfig = HeatingCircuitConfig.NOT_CONFIGURED
    status: HeatingCircuitStatus = HeatingCircuitStatus.OFF

    # Input registers (read-only)
    room_setpoint_effective: Temperature = field(default_factory=Temperature.no_value)
    room_temp: Temperature = field(default_factory=Temperature.no_value)
    room_humidity: Optional[int] = None  # 0-100%, None if no sensor
    flow_setpoint: Temperature = field(default_factory=Temperature.no_value)
    flow_temp: Temperature = field(default_factory=Temperature.no_value)

    # Holding registers (read/write)
    request_type: RequestType = RequestType.WEATHER_COMPENSATED
    mode: HeatingCircuitMode = HeatingCircuitMode.AUTOMATIC
    party_pause: int = PartyPauseCode.AUTOMATIC

    # Temperature setpoints
    setpoint_comfort: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(22.0)
    )
    setpoint_normal: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(20.0)
    )
    setpoint_setback: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(17.0)
    )

    # Heating curve parameters
    heating_curve_slope: int = 0
    summer_winter_threshold: int = 0

    # Constant temperature modes
    constant_temp_heating: Temperature = field(default_factory=Temperature.no_value)
    constant_temp_heating_setback: Temperature = field(
        default_factory=Temperature.no_value
    )
    constant_temp_cooling: Temperature = field(default_factory=Temperature.no_value)

    @property
    def is_configured(self) -> bool:
        """Check if this heating circuit is configured."""
        return self.config != HeatingCircuitConfig.NOT_CONFIGURED

    @property
    def is_heating(self) -> bool:
        """Check if circuit is currently heating."""
        return self.status == HeatingCircuitStatus.HEATING

    @property
    def is_cooling(self) -> bool:
        """Check if circuit is currently cooling."""
        return self.status == HeatingCircuitStatus.COOLING

    @property
    def is_mixer_circuit(self) -> bool:
        """Check if this is a mixer circuit."""
        return self.config == HeatingCircuitConfig.MIXER_CIRCUIT

    @property
    def is_pump_circuit(self) -> bool:
        """Check if this is a pump circuit."""
        return self.config == HeatingCircuitConfig.PUMP_CIRCUIT

    @property
    def party_pause_info(self) -> tuple[str, float | None]:
        """
        Get decoded party/pause information.

        Returns:
            Tuple of (mode, hours) where mode is 'party', 'pause', or 'automatic'
        """
        return PartyPauseCode.decode(self.party_pause)

    @property
    def is_party_active(self) -> bool:
        """Check if party mode is active."""
        return PartyPauseCode.is_party(self.party_pause)

    @property
    def is_pause_active(self) -> bool:
        """Check if pause mode is active."""
        return PartyPauseCode.is_pause(self.party_pause)

    @property
    def input_register_base(self) -> int:
        """Get base address for input registers."""
        return 31000 + (self.circuit_id * 100)

    @property
    def holding_register_base(self) -> int:
        """Get base address for holding registers."""
        return 41000 + (self.circuit_id * 100)

    def __repr__(self) -> str:
        if not self.is_configured:
            return f"HeatingCircuit(id={self.circuit_id}, NOT_CONFIGURED)"
        return (
            f"HeatingCircuit(id={self.circuit_id}, "
            f"mode={self.mode.name}, "
            f"room={self.room_temp.celsius}°C, "
            f"setpoint={self.room_setpoint_effective.celsius}°C)"
        )
