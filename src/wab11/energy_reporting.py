"""Energy serialization and report formatting with explicit optional availability."""

from __future__ import annotations

from dataclasses import asdict

from .models.energy import EnergyStatistics

EnergyReport = dict[str, dict[str, float] | None]
PERIOD_NAMES = ("today", "yesterday", "month", "year")
CATEGORY_LABELS = (
    ("total", "Total"),
    ("heating", "Heating"),
    ("hot_water", "Hot Water"),
    ("cooling", "Cooling"),
    ("electrical", "Electrical"),
)


def serialize_energy(energy: EnergyStatistics) -> EnergyReport:
    """Return four-field period dictionaries, retaining None for unavailable input.

    Args:
        energy: Current model; serialization does not perform device I/O.

    Returns:
        A JSON-compatible snapshot with all legacy keys and additive electrical.
    """
    return asdict(energy)


def flatten_energy(energy: EnergyReport) -> dict[str, float | None]:
    """Return stable CSV columns for each period, using None for unavailable data.

    Args:
        energy: Serialized energy snapshot, including the electrical key.

    Returns:
        Twenty named columns; CSV writers encode missing values as empty cells.
    """
    return {
        f"energy_{category}_{period}": values[period] if values is not None else None
        for category, _ in CATEGORY_LABELS
        for values in (energy[category],)
        for period in PERIOD_NAMES
    }


def format_energy_rows(energy: EnergyReport) -> list[str]:
    """Return report rows preserving legacy layout and showing missing input explicitly.

    Args:
        energy: Serialized energy snapshot with optional electrical data.

    Returns:
        Five labelled rows. The electrical row uses integer-kWh source precision.
    """
    rows = []
    for category, label in CATEGORY_LABELS:
        values = energy[category]
        if values is None:
            rows.append(f"  {label:20} Unavailable")
        else:
            precision = 0 if category == "electrical" else 1
            columns = " ".join(
                f"{values[period]:>10.{precision}f}" for period in PERIOD_NAMES
            )
            rows.append(f"  {label:20} {columns} kWh")
    return rows
