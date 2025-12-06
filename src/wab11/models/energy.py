"""
Energy statistics models for the WAB11.

Contains energy consumption data for heating, cooling, and hot water
operations, mirroring the statistics shown in the controller's menu.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnergyPeriod:
    """
    Energy consumption for a specific time period.

    All values are in kWh.

    Attributes:
        today: Energy consumed today
        yesterday: Energy consumed yesterday
        month: Energy consumed this calendar month
        year: Energy consumed this calendar year
    """

    today: float = 0.0
    yesterday: float = 0.0
    month: float = 0.0
    year: float = 0.0

    @property
    def total_recent(self) -> float:
        """Get sum of today and yesterday."""
        return self.today + self.yesterday


@dataclass
class EnergyStatistics:
    """
    Complete energy statistics from the WAB11.

    Input registers: 36xxx

    These values correspond to the statistics shown in the
    controller's Info → Statistik menu.

    Attributes:
        total: Total energy (heating + hot water + cooling)
        heating: Energy used for space heating
        hot_water: Energy used for domestic hot water
        cooling: Energy used for cooling
    """

    total: EnergyPeriod = field(default_factory=EnergyPeriod)
    heating: EnergyPeriod = field(default_factory=EnergyPeriod)
    hot_water: EnergyPeriod = field(default_factory=EnergyPeriod)
    cooling: EnergyPeriod = field(default_factory=EnergyPeriod)

    @property
    def today_total(self) -> float:
        """Get total energy consumed today in kWh."""
        return self.total.today

    @property
    def yesterday_total(self) -> float:
        """Get total energy consumed yesterday in kWh."""
        return self.total.yesterday

    @property
    def month_total(self) -> float:
        """Get total energy consumed this month in kWh."""
        return self.total.month

    @property
    def year_total(self) -> float:
        """Get total energy consumed this year in kWh."""
        return self.total.year

    @property
    def heating_percentage_today(self) -> float | None:
        """
        Get percentage of today's energy used for heating.

        Returns:
            Percentage (0-100) or None if no data.
        """
        if self.total.today == 0:
            return None
        return (self.heating.today / self.total.today) * 100

    @property
    def hot_water_percentage_today(self) -> float | None:
        """
        Get percentage of today's energy used for hot water.

        Returns:
            Percentage (0-100) or None if no data.
        """
        if self.total.today == 0:
            return None
        return (self.hot_water.today / self.total.today) * 100

    def __repr__(self) -> str:
        return (
            f"EnergyStatistics("
            f"today={self.total.today:.1f}kWh, "
            f"month={self.total.month:.1f}kWh, "
            f"year={self.total.year:.1f}kWh)"
        )

