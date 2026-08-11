"""
Hot water (Warmwasser) state model for the WAB11.

Handles domestic hot water temperature control, including normal
and setback temperatures, and hot water push/boost functionality.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import HotWaterConfig, HotWaterStatus, Temperature


@dataclass
class HotWaterState:
    """
    Hot water (Warmwasser) state model.

    Input registers: 32xxx
    Holding registers: 42xxx

    Attributes:
        config: Hot water configuration type
        status: Current operational status
        setpoint_effective: Currently active setpoint [°C]
        temperature: Measured hot water temperature [°C]
        push_minutes: Hot water push duration (0=off, 5-240 min)
        setpoint_normal: Normal operation setpoint [°C]
        setpoint_setback: Setback/reduced setpoint [°C]
        sg_ready_boost: SG-Ready temperature boost [K]
    """

    # Configuration (read-only)
    config: HotWaterConfig = HotWaterConfig.DISABLED
    status: HotWaterStatus = HotWaterStatus.OFF

    # Input registers (read-only)
    setpoint_effective: Temperature = field(default_factory=Temperature.no_value)
    temperature: Temperature = field(default_factory=Temperature.no_value)

    # Holding registers (read/write)
    push_minutes: int = 0  # 0=off, 5-240 minutes
    setpoint_normal: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(50.0)
    )
    setpoint_setback: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(40.0)
    )
    sg_ready_boost: Temperature = field(default_factory=Temperature.no_value)  # 0-30K

    @property
    def is_configured(self) -> bool:
        """Check if hot water is configured."""
        return self.config != HotWaterConfig.DISABLED

    @property
    def is_push_active(self) -> bool:
        """Check if hot water push/boost is active."""
        return self.push_minutes > 0

    @property
    def is_charging(self) -> bool:
        """Check if hot water is currently being heated."""
        return self.status in (
            HotWaterStatus.PRIORITY_CHARGING,
            HotWaterStatus.PARALLEL_CHARGING,
        )

    @property
    def is_priority_charging(self) -> bool:
        """Check if hot water has priority over heating."""
        return self.status == HotWaterStatus.PRIORITY_CHARGING

    @property
    def current_temp(self) -> float | None:
        """Get current hot water temperature in °C."""
        return self.temperature.celsius

    @property
    def target_temp(self) -> float | None:
        """Get current target temperature in °C."""
        return self.setpoint_effective.celsius

    @property
    def temp_difference(self) -> float | None:
        """
        Get difference between target and current temperature.

        Returns:
            Positive value means more heating needed, None if data unavailable.
        """
        current = self.current_temp
        target = self.target_temp
        if current is None or target is None:
            return None
        return target - current

    def __repr__(self) -> str:
        if not self.is_configured:
            return "HotWaterState(NOT_CONFIGURED)"
        push_info = f", push={self.push_minutes}min" if self.is_push_active else ""
        return (
            f"HotWaterState(temp={self.current_temp}°C, "
            f"target={self.target_temp}°C, "
            f"status={self.status.name}{push_info})"
        )
