"""Exercise electrical statistics across polling, transport, sync and report APIs."""

from __future__ import annotations

import asyncio
import csv
import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from energy_helpers import EnergyConnection, modbus_error

from wab11 import WAB11Client, WAB11SyncClient
from wab11.connection import ConnectionConfig, WAB11Connection
from wab11.exceptions import ModbusResponseError
from wab11.models.energy import EnergyPeriod


@pytest.fixture
def device(fake_system_config):
    """Return a strict fixture device whose electrical block is expected in JSON."""
    return EnergyConnection.from_config(fake_system_config)


@pytest.fixture
def sync_client(device, monkeypatch):
    """Yield the real synchronous and asynchronous clients over an external-device fake."""
    monkeypatch.setattr("wab11.client.WAB11Connection", lambda config: device)
    with WAB11SyncClient("127.0.0.1", n_heating_circuits=5) as client:
        yield client


@pytest.fixture
def report():
    """Load the report entrypoint without running its network CLI."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "report.py"
    spec = importlib.util.spec_from_file_location("electrical_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_client_exposes_optional_values_and_errors(sync_client, device):
    """Keep the same model and exception contract through the blocking adapter."""
    assert sync_client.energy.electrical is None
    sync_client.sync_energy()
    assert sync_client.energy.electrical == EnergyPeriod(0, 2, 10, 1916)
    device.responses[36701] = modbus_error(2)
    sync_client.sync_energy()
    assert sync_client.energy.electrical is None
    device.responses[36701] = modbus_error(10)
    with pytest.raises(ModbusResponseError):
        sync_client.sync_energy()
    assert sync_client.energy.electrical is None
    del device.responses[36701]
    sync_client.sync_energy()
    assert sync_client.energy.electrical.yesterday == 2.0


@pytest.mark.asyncio
async def test_normal_sync_never_reads_energy(device, make_test_client):
    """Keep optional and legacy energy polling separate from normal synchronization."""
    client = make_test_client(device, n_heating_circuits=5)
    await client.sync()
    assert not [address for address, _ in device.reads if 36000 <= address < 37000]
    assert client.energy.electrical is None


@pytest.mark.asyncio
async def test_background_polling_uses_existing_energy_schedule(
    device, make_test_client
):
    """Poll electrical data on the initial energy cycle and not every state cycle."""
    client = make_test_client(device, n_heating_circuits=5)
    await client.start_polling(interval=0.001)
    try:

        async def observe_cycles():
            """Wait for several actual external-device reads within a bounded timeout."""
            while device.reads.count((30001, 6)) < 3:
                await asyncio.sleep(0.001)

        await asyncio.wait_for(observe_cycles(), timeout=2)
        assert device.reads.count((36701, 4)) == 1
        assert client.energy.electrical == EnergyPeriod(0, 2, 10, 1916)
    finally:
        await client.stop_polling()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address,count,code,quiet",
    [
        (36701, 4, 2, True),
        (36701, 4, 4, False),
        (36701, 4, 10, False),
        (36101, 4, 2, False),
        (36701, 1, 2, False),
    ],
)
async def test_transport_logging_preserves_typed_errors(
    address, count, code, quiet, caplog
):
    """Only unavailable optional-block warnings become debug; transport still raises."""
    response = SimpleNamespace(
        isError=lambda: True, function_code=132, exception_code=code
    )
    network = SimpleNamespace(read_input_registers=AsyncMock(return_value=response))
    connection = WAB11Connection(ConnectionConfig(host="127.0.0.1", max_retries=1))
    connection._client = network
    connection._connected = True
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ModbusResponseError) as raised:
            await connection.read_input_registers(address, count)
    assert raised.value.exception_code == code
    network.read_input_registers.assert_awaited_once_with(address=address, count=count)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert bool(warnings) is not quiet


@pytest.mark.asyncio
async def test_real_transport_optional_failure_is_quiet_and_keeps_legacy(caplog):
    """Exercise high-level availability through the real transport's Modbus response path."""
    success = SimpleNamespace(isError=lambda: False, registers=[0, 7, 26, 7997])
    unsupported = SimpleNamespace(
        isError=lambda: True, function_code=132, exception_code=2
    )
    network = SimpleNamespace(
        read_input_registers=AsyncMock(side_effect=[success] * 4 + [unsupported])
    )
    client = WAB11Client("127.0.0.1")
    client._connection.config.max_retries = 1
    client._connection._client = network
    client._connection._connected = True
    with caplog.at_level(logging.DEBUG):
        await client.sync_energy()
    assert client.energy.total == EnergyPeriod(0, 7, 26, 7997)
    assert client.energy.electrical is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize("supported", [True, False])
def test_reports_serialize_present_and_unavailable_energy(
    supported,
    sync_client,
    device,
    report,
    tmp_path,
):
    """Keep JSON, CSV and human-readable reports distinct and explicit about missing data."""
    if not supported:
        device.responses[36701] = modbus_error(2)
    data = report.collect_sensor_data(sync_client)
    expected = {"today": 0.0, "yesterday": 2.0, "month": 10.0, "year": 1916.0}
    assert json.loads(json.dumps(data))["energy"] == {
        "total": {"today": 12.0, "yesterday": 11.0, "month": 210.0, "year": 1240.0},
        "heating": {"today": 9.0, "yesterday": 8.0, "month": 150.0, "year": 900.0},
        "hot_water": {"today": 3.0, "yesterday": 3.0, "month": 60.0, "year": 280.0},
        "cooling": {"today": 0.0, "yesterday": 0.0, "month": 0.0, "year": 0.0},
        "electrical": expected if supported else None,
    }
    flat = report.flatten_data_for_csv(data)
    for period, value in expected.items():
        assert flat[f"energy_electrical_{period}"] == (value if supported else None)
    text = report.generate_text_report(data)
    electrical_line = next(line for line in text.splitlines() if "Electrical" in line)
    assert ("Unavailable" in electrical_line) is not supported
    if supported:
        assert "1916" in electrical_line and "kWh" in electrical_line
    target = tmp_path / "energy.csv"
    assert report.write_csv(data, str(target)) is False
    assert report.write_csv(data, str(target)) is True
    with target.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert rows[0]["energy_electrical_today"] == ("0.0" if supported else "")
    assert None not in rows[0]


def test_csv_old_schema_fails_without_corrupting_existing_file(
    sync_client, report, tmp_path
):
    """Require a new CSV when additive columns would no longer match its header."""
    data = report.collect_sensor_data(sync_client)
    target = tmp_path / "legacy.csv"
    previous = "timestamp,energy_total_today\nold,12.0\n"
    target.write_text(previous)
    with pytest.raises(ValueError, match="(?i)CSV.*schema"):
        report.write_csv(data, str(target))
    assert target.read_text() == previous


@pytest.mark.asyncio
async def test_transport_keeps_function_code_four_and_raw_boundaries():
    """Decode real transport input responses without offsetting, scaling or writes."""
    success = SimpleNamespace(isError=lambda: False, registers=[0, 2, 65535, 1916])
    network = SimpleNamespace(
        read_input_registers=AsyncMock(return_value=success), write_register=Mock()
    )
    client = WAB11Client("127.0.0.1")
    client._connection._client = network
    client._connection._connected = True
    await client.sync_energy()
    assert client.energy.electrical == EnergyPeriod(0, 2, 65535, 1916)
    assert [
        (call.kwargs["address"], call.kwargs["count"])
        for call in network.read_input_registers.await_args_list
    ] == [(36101, 4), (36201, 4), (36301, 4), (36401, 4), (36701, 4)]
    network.write_register.assert_not_called()
