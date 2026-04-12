"""
Heat pump state model for the WAB11.

Contains the core heat pump operational data including temperatures,
power levels, and pump configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import HeatPumpConfig, OperatingState, Temperature


@dataclass
class HeatPumpState:
    """
    Heat pump / Pump M1 state model.

    Input registers: 33xxx
    Holding registers: 43xxx

    Attributes:
        config: Heat pump configuration (heating only vs heating+cooling)
        operating_state: Current operating state
        is_error_free: True if no errors active
        power_request_percent: Current power request [0-100%]
        flow_temp_b4: Flow temperature at sensor B4 [°C]
        return_temp: Return temperature [°C]
        evaporator_temp: Evaporator temperature [°C]
        suction_gas_temp: Suction gas temperature [°C]
        separator_temp_b2: Hydraulic separator temperature B2 [°C]
        regenerative_flow_b21: Regenerative flow temperature B2.1 [°C]
        buffer_temp_b11: Buffer tank temperature B11 [°C]
        sum_flow_b7: Sum flow temperature B7 [°C]
        quiet_mode: Quiet mode setting (0=off)
        pump_start_mode: Pump start mode configuration
        pump_power_heating: Pump power in heating mode [20-100%]
        pump_power_cooling: Pump power in cooling mode [20-100%]
        pump_power_hot_water: Pump power in hot water mode [20-100%]
        pump_power_defrost: Pump power during defrost [%]
        flow_rate_heating: Volume flow rate heating [m³/h]
        flow_rate_cooling: Volume flow rate cooling [m³/h]
        flow_rate_hot_water: Volume flow rate hot water [m³/h]
    """

    # Configuration
    config: HeatPumpConfig = HeatPumpConfig.NOT_CONFIGURED

    # Input registers (read-only)
    operating_state: OperatingState = OperatingState.UNDEFINED
    is_error_free: bool = True
    power_request_percent: int = 0  # 0-100%

    # Temperature sensors
    flow_temp_b4: Temperature = field(default_factory=Temperature.no_value)
    return_temp: Temperature = field(default_factory=Temperature.no_value)
    evaporator_temp: Temperature = field(default_factory=Temperature.no_value)
    suction_gas_temp: Temperature = field(default_factory=Temperature.no_value)
    separator_temp_b2: Temperature = field(default_factory=Temperature.no_value)
    regenerative_flow_b21: Temperature = field(default_factory=Temperature.no_value)
    buffer_temp_b11: Temperature = field(default_factory=Temperature.no_value)
    sum_flow_b7: Temperature = field(default_factory=Temperature.no_value)

    # Holding registers (read/write)
    quiet_mode: int = 0  # 0=off
    pump_start_mode: int = 0
    pump_power_heating: int = 100  # 20-100%
    pump_power_cooling: int = 100  # 20-100%
    pump_power_hot_water: int = 100  # 20-100%
    pump_power_defrost: int = 100  # %
    flow_rate_heating: int = 0  # m³/h (scaled)
    flow_rate_cooling: int = 0  # m³/h (scaled)
    flow_rate_hot_water: int = 0  # m³/h (scaled)

    @property
    def is_configured(self) -> bool:
        """Check if heat pump is configured."""
        return self.config != HeatPumpConfig.NOT_CONFIGURED

    @property
    def supports_cooling(self) -> bool:
        """Check if heat pump supports cooling."""
        return self.config == HeatPumpConfig.HEATING_AND_COOLING

    @property
    def is_running(self) -> bool:
        """Check if heat pump compressor is running."""
        return self.power_request_percent > 0

    @property
    def is_heating(self) -> bool:
        """Check if heat pump is in heating mode."""
        return self.operating_state == OperatingState.HEATING

    @property
    def is_cooling(self) -> bool:
        """Check if heat pump is in cooling mode."""
        return self.operating_state in (
            OperatingState.COOLING,
            OperatingState.PASSIVE_COOLING,
        )

    @property
    def is_defrosting(self) -> bool:
        """Check if heat pump is defrosting."""
        return self.operating_state in (
            OperatingState.DEFROST,
            OperatingState.MANUAL_DEFROST,
        )

    @property
    def is_hot_water(self) -> bool:
        """Check if heat pump is heating hot water."""
        return self.operating_state == OperatingState.HOT_WATER

    @property
    def spread(self) -> float | None:
        """
        Calculate temperature spread (flow - return).

        Returns:
            Temperature spread in K, or None if data unavailable.
        """
        flow = self.flow_temp_b4.celsius
        ret = self.return_temp.celsius
        if flow is None or ret is None:
            return None
        return flow - ret

    @property
    def is_quiet_mode(self) -> bool:
        """Check if quiet mode is enabled."""
        return self.quiet_mode > 0

    def __repr__(self) -> str:
        if not self.is_configured:
            return "HeatPumpState(NOT_CONFIGURED)"
        return (
            f"HeatPumpState(state={self.operating_state.name}, "
            f"power={self.power_request_percent}%, "
            f"flow={self.flow_temp_b4.celsius}°C, "
            f"return={self.return_temp.celsius}°C)"
        )
