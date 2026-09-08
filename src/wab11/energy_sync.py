"""Synchronize legacy energy periods and the empirical optional electrical block."""

from __future__ import annotations

import logging

from .connection import WAB11Connection
from .exceptions import ConnectionError, ModbusResponseError
from .models.energy import EnergyPeriod, EnergyStatistics

logger = logging.getLogger(__name__)


async def sync_energy_statistics(
    connection: WAB11Connection, energy: EnergyStatistics
) -> None:
    """Update energy state using full input addresses on the caller's energy schedule.

    Args:
        connection: Existing transport, including its normal retry policy.
        energy: Mutable state whose legacy period objects retain their identities.

    Returns:
        None. Electrical data is replaced only after a complete valid response.

    Raises:
        ConnectionError: A transport failure or malformed electrical response.
        ModbusResponseError: Any mandatory exception, or optional exception other
            than Illegal Data Address (2). Other legacy decoding errors propagate.
    """
    # Clear before any I/O so errors and cancellation cannot retain stale data.
    energy.electrical = None
    for address, period in (
        (36101, energy.total),
        (36201, energy.heating),
        (36301, energy.hot_water),
        (36401, energy.cooling),
    ):
        values = await connection.read_input_registers(address, 4)
        # Preserve the legacy per-field update behavior, including on failure.
        period.today = float(values[0])
        period.yesterday = float(values[1])
        period.month = float(values[2])
        period.year = float(values[3])

    try:
        values = await connection.read_input_registers(36701, 4)
    except ModbusResponseError as error:
        if error.exception_code != 2:
            raise
        logger.debug(
            "Optional electrical block 36701 unavailable (Modbus exception %s)",
            error.exception_code,
        )
        return

    if (
        not isinstance(values, (list, tuple))
        or len(values) != 4
        or any(type(value) is not int or not 0 <= value <= 65535 for value in values)
    ):
        raise ConnectionError(
            "Malformed electrical block 36701: expected four unsigned 16-bit integers"
        )
    energy.electrical = EnergyPeriod(*(float(value) for value in values))
