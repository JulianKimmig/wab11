"""
System-level state model for the WAB11.

Contains global system state including operating mode, temperatures,
error codes, and warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .base import OperatingState, SystemMode, Temperature


@dataclass
class SystemState:
    """
    Global system state - mirrors registers 30xxx and 40xxx.

    This is the top-level state container representing the overall
    system status of the WAB11 controller.

    Attributes:
        outdoor_temp_1: Primary outdoor temperature sensor [°C]
        outdoor_temp_2: Secondary outdoor temperature sensor [°C]
        error_code: Current error code (65535 = no error)
        warning_code: Current warning code (65535 = no warning)
        is_error_free: True if no errors active
        operating_state: Current operating state display
        system_mode: Current system operating mode
        power_request_watts: System power request [W]
        last_updated: Timestamp of last state update
    """

    # Input registers (read-only from device)
    outdoor_temp_1: Temperature = field(default_factory=Temperature.no_value)
    outdoor_temp_2: Temperature = field(default_factory=Temperature.no_value)
    error_code: int = 65535  # 65535 = no error
    warning_code: int = 65535  # 65535 = no warning
    is_error_free: bool = True
    operating_state: OperatingState = OperatingState.UNDEFINED

    # Holding registers (read/write)
    system_mode: SystemMode = SystemMode.AUTOMATIC
    power_request_watts: int = 0  # 0-30000 W

    # Metadata
    last_updated: Optional[datetime] = None

    @property
    def has_error(self) -> bool:
        """Check if any error is active."""
        return self.error_code != 65535

    @property
    def has_warning(self) -> bool:
        """Check if any warning is active."""
        return self.warning_code != 65535

    @property
    def outdoor_temp(self) -> float | None:
        """
        Get primary outdoor temperature in °C.

        Returns:
            Temperature in °C or None if sensor unavailable.
        """
        return self.outdoor_temp_1.celsius

    @property
    def is_heating(self) -> bool:
        """Check if system is currently in heating mode."""
        return self.operating_state == OperatingState.HEATING

    @property
    def is_cooling(self) -> bool:
        """Check if system is currently in cooling mode."""
        return self.operating_state in (
            OperatingState.COOLING,
            OperatingState.PASSIVE_COOLING,
        )

    @property
    def is_hot_water(self) -> bool:
        """Check if system is currently heating hot water."""
        return self.operating_state == OperatingState.HOT_WATER

    @property
    def is_defrosting(self) -> bool:
        """Check if system is currently defrosting."""
        return self.operating_state in (
            OperatingState.DEFROST,
            OperatingState.MANUAL_DEFROST,
        )

    @property
    def is_standby(self) -> bool:
        """Check if system is in standby."""
        return self.operating_state == OperatingState.STANDBY

    def __repr__(self) -> str:
        status = "OK" if self.is_error_free else f"ERROR({self.error_code})"
        return (
            f"SystemState(mode={self.system_mode.name}, "
            f"state={self.operating_state.name}, "
            f"outdoor={self.outdoor_temp}°C, "
            f"status={status})"
        )
