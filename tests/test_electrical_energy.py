"""Electrical register, model, and synchronization contracts without hardware."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

import pytest
from energy_helpers import EnergyConnection, modbus_error

from wab11.exceptions import ConnectionError, ReadOnlyError, TimeoutError
from wab11.models.energy import EnergyPeriod, EnergyStatistics
from wab11.registers.definitions import (
    ALL_REGISTERS,
    ENERGY_REGISTERS,
    DataFormat,
    RegisterType,
)

PERIODS = ("today", "yesterday", "month", "year")
BLOCKS = [(36101, 4), (36201, 4), (36301, 4), (36401, 4), (36701, 4)]


@pytest.fixture
def energy_device(fake_system_config):
    """Return a strict device with deliberately distinct legacy/electrical values."""
    device = EnergyConnection.from_config(fake_system_config)
    device.input_blocks[36101] = [0, 7, 26, 7997]
    device.input_blocks[36701] = [0, 2, 10, 1916]
    return device


def test_registry_preserves_legacy_and_adds_read_only_electrical() -> None:
    """Resolve all energy keys without address collisions or format changes."""
    categories = {
        "total": 36101,
        "heating": 36201,
        "hot_water": 36301,
        "cooling": 36401,
        "electrical": 36701,
    }
    assert len(ENERGY_REGISTERS) == 20
    for category, base in categories.items():
        for offset, period in enumerate(PERIODS):
            key = f"energy_{category}_{period}"
            register = ENERGY_REGISTERS[key]
            assert ALL_REGISTERS[key] is register
            assert register.name == key
            assert register.address == base + offset
            assert register.reg_type is RegisterType.INPUT
            assert register.fmt is DataFormat.UNSIGNED_16
            assert register.unit == "kWh"
            assert register.writable is False
    assert len({(r.reg_type, r.address) for r in ALL_REGISTERS.values()}) == len(
        ALL_REGISTERS
    )


def test_optional_model_preserves_positional_constructor_and_aliases() -> None:
    """Append optional data while retaining legacy fields, ratios and representation."""
    total = EnergyPeriod(10, 9, 100, 1000)
    heating, water, cooling = EnergyPeriod(7), EnergyPeriod(3), EnergyPeriod()
    stats = EnergyStatistics(total, heating, water, cooling)
    assert stats.electrical is None
    assert asdict(stats)["electrical"] is None
    assert (stats.total, stats.heating, stats.hot_water, stats.cooling) == (
        total,
        heating,
        water,
        cooling,
    )
    assert (
        stats.today_total,
        stats.yesterday_total,
        stats.month_total,
        stats.year_total,
    ) == (10, 9, 100, 1000)
    assert stats.heating_percentage_today == 70
    assert stats.hot_water_percentage_today == 30
    representation = repr(stats)
    electrical = EnergyPeriod(2, 1, 10, 300)
    stats.electrical = electrical
    assert repr(stats) == representation
    assert stats.total is total
    assert (
        EnergyStatistics(total, heating, water, cooling, electrical).electrical
        is electrical
    )
    assert EnergyStatistics().heating_percentage_today is None


@pytest.mark.asyncio
async def test_sync_reads_separate_blocks_in_order(energy_device, make_test_client):
    """Publish a complete electrical period using full input addresses and no writes."""
    client = make_test_client(energy_device)
    assert client.energy.electrical is None
    await client.sync_energy()
    assert energy_device.reads == BLOCKS
    assert energy_device.writes == []
    assert client.energy.total == EnergyPeriod(0, 7, 26, 7997)
    assert client.energy.electrical == EnergyPeriod(0, 2, 10, 1916)
    assert type(client.energy.electrical.yesterday) is float


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [[0, 0, 0, 0], [2, 65535, 0, 65535]])
async def test_zero_and_unsigned_max_are_valid(values, energy_device, make_test_client):
    """Accept every u16 boundary without sentinels or decimal scaling."""
    energy_device.input_blocks[36701] = values
    client = make_test_client(energy_device)
    await client.sync_energy()
    assert asdict(client.energy.electrical) == dict(zip(PERIODS, map(float, values)))


@pytest.mark.asyncio
async def test_unsupported_clears_previous_data_and_retries(
    energy_device,
    make_test_client,
    caplog,
):
    """Only optional exception 2 is quiet and recoverable on the next normal poll."""
    client = make_test_client(energy_device)
    await client.sync_energy()
    energy_device.responses[36701] = modbus_error(2)
    with caplog.at_level(logging.DEBUG):
        await client.sync_energy()
        await client.sync_energy()
    assert client.energy.electrical is None
    assert client.energy.total.year == 7997
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "36701" in caplog.text and "2" in caplog.text
    del energy_device.responses[36701]
    await client.sync_energy()
    assert client.energy.electrical == EnergyPeriod(0, 2, 10, 1916)
    assert energy_device.reads == BLOCKS * 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        modbus_error(4),
        modbus_error(10),
        TimeoutError("timeout"),
        ConnectionError("disconnected"),
    ],
)
async def test_failures_clear_availability_and_recover(
    error, energy_device, make_test_client
):
    """Propagate the exact typed failure and discard stale data before recovery."""
    client = make_test_client(energy_device)
    await client.sync_energy()
    previous = client.energy.electrical
    energy_device.responses[36701] = error
    with pytest.raises(type(error)) as raised:
        await client.sync_energy()
    assert raised.value is error
    assert client.energy.electrical is None
    assert previous == EnergyPeriod(0, 2, 10, 1916)
    del energy_device.responses[36701]
    await client.sync_energy()
    assert client.energy.electrical == previous
    assert client.energy.electrical is not previous


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        [],
        [1, 2, 3],
        [1, 2, 3, 4, 5],
        None,
        "1234",
        [1, 2, 3, -1],
        [1, 2, 3, 65536],
        [1, 2, 3, "4"],
        [1, 2, 3, 4.0],
        [1, 2, 3, True],
        [1, 2, 3, None],
        [1, 2, 3, float("nan")],
    ],
)
async def test_malformed_response_never_publishes_partial_period(
    response,
    energy_device,
    make_test_client,
):
    """Reject invalid length, type or range as a connection response failure."""
    client = make_test_client(energy_device)
    await client.sync_energy()
    previous = client.energy.electrical
    energy_device.responses[36701] = response
    with pytest.raises(ConnectionError, match="36701"):
        await client.sync_energy()
    assert client.energy.electrical is None
    assert previous == EnergyPeriod(0, 2, 10, 1916)


@pytest.mark.asyncio
@pytest.mark.parametrize("address", [36101, 36201, 36301, 36401])
async def test_mandatory_failure_clears_electrical(
    address, energy_device, make_test_client
):
    """Never suppress an exception 2 from a mandatory energy block."""
    client = make_test_client(energy_device)
    await client.sync_energy()
    error = modbus_error(2)
    energy_device.responses[address] = error
    energy_device.reads.clear()
    with pytest.raises(type(error)) as raised:
        await client.sync_energy()
    assert raised.value is error
    assert client.energy.electrical is None
    assert (36701, 4) not in energy_device.reads


@pytest.mark.asyncio
async def test_calendar_reset_replaces_complete_period(energy_device, make_test_client):
    """Accept decreases at calendar boundaries without mutating previously returned data."""
    client = make_test_client(energy_device)
    energy_device.input_blocks[36701] = [2, 1, 10, 1916]
    await client.sync_energy()
    previous = client.energy.electrical
    energy_device.input_blocks[36701] = [0, 2, 0, 0]
    await client.sync_energy()
    assert client.energy.electrical == EnergyPeriod(0, 2, 0, 0)
    assert previous == EnergyPeriod(2, 1, 10, 1916)


@pytest.mark.asyncio
@pytest.mark.parametrize("period,value", zip(PERIODS, [0, 2, 10, 65535]))
async def test_generic_access_stays_read_only(
    period, value, energy_device, make_test_client
):
    """Expose each register unscaled while rejecting writes through the public API."""
    energy_device.input_blocks[36701] = [0, 2, 10, 65535]
    client = make_test_client(energy_device)
    key = f"energy_electrical_{period}"
    assert await client.read_register(key) == value
    with pytest.raises(ReadOnlyError):
        await client.write_register(key, 3, confirmed=True)
    assert energy_device.writes == []
    address = 36701 + PERIODS.index(period)
    energy_device.responses[address] = modbus_error(2)
    with pytest.raises(type(energy_device.responses[address])):
        await client.read_register(key)


@pytest.mark.asyncio
async def test_cancelled_energy_sync_clears_availability(
    energy_device, make_test_client
):
    """A cancelled read must not leave an earlier electrical period available."""
    client = make_test_client(energy_device)
    await client.sync_energy()
    energy_device.responses[36701] = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await client.sync_energy()
    assert client.energy.electrical is None
