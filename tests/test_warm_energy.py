"""Opt-in read-only electrical block capture; display validation remains manual."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from wab11.connection import ConnectionConfig, WAB11Connection
from wab11.exceptions import ModbusResponseError


@pytest.mark.warm
def test_live_electrical_energy_block(warm_device_settings, record_property) -> None:
    """Capture UTC and raw blocks without embedding a device address in test output."""

    async def capture() -> None:
        """Read legacy and optional blocks, accepting only optional exception code 2."""
        config = ConnectionConfig(
            host=warm_device_settings["host"],
            port=warm_device_settings["port"],
            unit_id=warm_device_settings["unit_id"],
            timeout=warm_device_settings["timeout"],
        )
        async with WAB11Connection(config) as connection:
            record_property("captured_at_utc", datetime.now(timezone.utc).isoformat())
            record_property(
                "legacy_raw", await connection.read_input_registers(36101, 4)
            )
            try:
                raw = await connection.read_input_registers(36701, 4)
            except ModbusResponseError as error:
                if error.exception_code != 2:
                    raise
                record_property(
                    "electrical_unavailable_exception", error.exception_code
                )
            else:
                assert len(raw) == 4
                assert all(type(value) is int and 0 <= value <= 65535 for value in raw)
                record_property("electrical_raw", raw)

    asyncio.run(capture())
