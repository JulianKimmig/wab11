"""
Secondary heat source state model for the WAB11.

Handles the second heat source (2. WEZ) and electric heaters (E1, E2).
These provide backup heating when the heat pump cannot meet demand
or when temperatures fall below the bivalence point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Temperature


@dataclass
class SecondaryHeatSourceState:
    """
    Second heat source (2. WEZ) and electric heaters (E1, E2) state.

    The second heat source is typically an external boiler (gas/oil)
    that provides heating when:
    - Outdoor temperature falls below bivalence temperature
    - Heat pump is locked or in fault
    - System mode is set to SECOND_HEAT

    Input registers: 34xxx
    Holding registers: 44xxx

    Attributes:
        status_wez2: Status of second heat source
        operating_hours_wez2: Total operating hours
        switching_cycles_wez2: Number of on/off cycles
        status_e1: Electric heater stage 1 active
        status_e2: Electric heater stage 2 active
        operating_hours_e1: Operating hours stage 1
        operating_hours_e2: Operating hours stage 2
        config_wez2: Configuration (255=off, 0=active)
        config_e1: Configuration (255=off, 5=active)
        config_e2: Configuration (255=off, 6=active)
        limit_temp: Temperature below which heat pump is locked
        bivalence_temp_heating: Parallel operation threshold for heating
        bivalence_temp_hot_water: Parallel operation threshold for hot water
    """

    # Input registers (read-only)
    status_wez2: int = 0
    operating_hours_wez2: int = 0
    switching_cycles_wez2: int = 0
    status_e1: bool = False
    status_e2: bool = False
    operating_hours_e1: int = 0
    operating_hours_e2: int = 0

    # Holding registers (read/write)
    config_wez2: int = 255  # 255=off, 0=active
    config_e1: int = 255  # 255=off, 5=active
    config_e2: int = 255  # 255=off, 6=active
    limit_temp: Temperature = field(default_factory=lambda: Temperature.from_celsius(-20.0))
    bivalence_temp_heating: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(-5.0)
    )
    bivalence_temp_hot_water: Temperature = field(
        default_factory=lambda: Temperature.from_celsius(-5.0)
    )

    @property
    def is_wez2_configured(self) -> bool:
        """Check if second heat source is configured."""
        return self.config_wez2 == 0

    @property
    def is_wez2_active(self) -> bool:
        """Check if second heat source is currently active."""
        return self.is_wez2_configured and self.status_wez2 > 0

    @property
    def is_e1_configured(self) -> bool:
        """Check if electric heater stage 1 is configured."""
        return self.config_e1 == 5

    @property
    def is_e2_configured(self) -> bool:
        """Check if electric heater stage 2 is configured."""
        return self.config_e2 == 6

    @property
    def is_e1_active(self) -> bool:
        """Check if electric heater stage 1 is currently on."""
        return self.is_e1_configured and self.status_e1

    @property
    def is_e2_active(self) -> bool:
        """Check if electric heater stage 2 is currently on."""
        return self.is_e2_configured and self.status_e2

    @property
    def any_backup_active(self) -> bool:
        """Check if any backup heating source is active."""
        return self.is_wez2_active or self.is_e1_active or self.is_e2_active

    @property
    def total_operating_hours(self) -> int:
        """Get total operating hours of all backup sources."""
        return self.operating_hours_wez2 + self.operating_hours_e1 + self.operating_hours_e2

    def should_activate_backup(self, outdoor_temp: float | None) -> bool:
        """
        Check if backup heating should activate based on outdoor temperature.

        Args:
            outdoor_temp: Current outdoor temperature in °C

        Returns:
            True if outdoor temp is below bivalence point
        """
        if outdoor_temp is None:
            return False
        bivalence = self.bivalence_temp_heating.celsius
        if bivalence is None:
            return False
        return outdoor_temp < bivalence

    def should_lock_heat_pump(self, outdoor_temp: float | None) -> bool:
        """
        Check if heat pump should be locked based on outdoor temperature.

        Args:
            outdoor_temp: Current outdoor temperature in °C

        Returns:
            True if outdoor temp is below limit temperature
        """
        if outdoor_temp is None:
            return False
        limit = self.limit_temp.celsius
        if limit is None:
            return False
        return outdoor_temp < limit

    def __repr__(self) -> str:
        active = []
        if self.is_wez2_active:
            active.append("WEZ2")
        if self.is_e1_active:
            active.append("E1")
        if self.is_e2_active:
            active.append("E2")
        active_str = ", ".join(active) if active else "none"
        return f"SecondaryHeatSourceState(active=[{active_str}])"

