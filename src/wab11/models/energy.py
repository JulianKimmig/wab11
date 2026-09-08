"""
Energy statistics models for the WAB11.

Legacy groups have evidence indicating thermal output; electrical input is a
separate, empirically observed optional group. Controller-display validation
remains necessary; see .docs/contracts/energy-statistics.md for evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnergyPeriod:
    """
    Reported energy for overlapping calendar periods.

    All values are in kWh. Register resolution is integer kWh; float storage
    does not imply fractional precision. Do not sum all four periods.

    Attributes:
        today: Energy reported today
        yesterday: Energy reported yesterday
        month: Energy reported this calendar month
        year: Energy reported this calendar year
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

    Existing groups retain their legacy meanings, with evidence indicating
    thermal output. Electrical input uses empirical registers 36701-36704;
    labels, measurement boundary and firmware compatibility need validation.

    Attributes:
        total: Total energy (heating + hot water + cooling)
        heating: Legacy space-heating energy
        hot_water: Legacy domestic-hot-water energy
        cooling: Legacy cooling energy
        electrical: Separate electrical input, or None before a successful
            energy sync, when unsupported, or after the latest energy sync
            fails. A complete zero-valued period is available data. Consumers
            remain responsible for freshness after polling stops.
    """

    total: EnergyPeriod = field(default_factory=EnergyPeriod)
    heating: EnergyPeriod = field(default_factory=EnergyPeriod)
    hot_water: EnergyPeriod = field(default_factory=EnergyPeriod)
    cooling: EnergyPeriod = field(default_factory=EnergyPeriod)
    electrical: EnergyPeriod | None = None

    @property
    def today_total(self) -> float:
        """Return today's legacy total energy in kWh."""
        return self.total.today

    @property
    def yesterday_total(self) -> float:
        """Return yesterday's legacy total energy in kWh."""
        return self.total.yesterday

    @property
    def month_total(self) -> float:
        """Return this month's legacy total energy in kWh."""
        return self.total.month

    @property
    def year_total(self) -> float:
        """Return this year's legacy total energy in kWh."""
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
