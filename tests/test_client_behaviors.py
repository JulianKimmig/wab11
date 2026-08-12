from __future__ import annotations

import asyncio
import logging

import pytest

from wab11 import (
    HeatPumpConfig,
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HotWaterConfig,
    OperatingState,
    RequestType,
    SafetyError,
    SystemMode,
    Temperature,
    ValidationError,
    WAB11Client,
)
from wab11.exceptions import ModbusResponseError
from wab11.models.heating import PartyPauseCode
from wab11.registers.definitions import ALL_REGISTERS
from wab11.registers.formats import FormatCodec
from wab11.security.validator import WriteValidator


class ExactRegisterConnection:
    def __init__(
        self,
        *,
        input_blocks: dict[tuple[int, int], list[int]] | None = None,
        holding_blocks: dict[tuple[int, int], list[int]] | None = None,
    ) -> None:
        self.input_blocks = input_blocks or {}
        self.holding_blocks = holding_blocks or {}
        self.writes: list[tuple[int, int]] = []
        self.is_connected = True

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        key = (address, count)
        if key not in self.input_blocks:
            raise AssertionError(f"Unexpected input register read: {key}")
        return list(self.input_blocks[key])

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        key = (address, count)
        if key not in self.holding_blocks:
            raise AssertionError(f"Unexpected holding register read: {key}")
        return list(self.holding_blocks[key])

    async def write_register(self, address: int, value: int) -> None:
        self.writes.append((address, value))


class ExplodingConnection:
    def __init__(self) -> None:
        self.is_connected = True

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        raise RuntimeError("boom")

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        raise RuntimeError("boom")

    async def write_register(self, address: int, value: int) -> None:
        raise AssertionError("Polling test must not write to the device")


class RecordingLimiter:
    def __init__(self) -> None:
        self.acquired: list[str] = []

    async def acquire(self, register_name: str) -> None:
        self.acquired.append(register_name)


@pytest.mark.asyncio
async def test_client_rejects_invalid_heating_circuit_count() -> None:
    with pytest.raises(ValidationError, match="n_heating_circuits must be 1-5"):
        WAB11Client("127.0.0.1", n_heating_circuits=0)


@pytest.mark.asyncio
async def test_client_auto_detects_heating_circuit_count(make_test_client) -> None:
    """Stop auto-detection only at the controller's absent-circuit response."""

    class AutoDetectConnection(ExactRegisterConnection):
        async def read_input_registers(self, address: int, count: int) -> list[int]:
            if address == 31301:
                raise ModbusResponseError(
                    function_code=132,
                    exception_code=10,
                    operation="reading input register 31301",
                )
            return await super().read_input_registers(address, count)

    connection = AutoDetectConnection(
        input_blocks={
            (31101, 5): [200, 201, 50, 300, 301],
            (31201, 5): [210, 211, 51, 310, 311],
        },
        holding_blocks={
            (41101, 12): [1, 1, 200, 190, 170, 0, 0, 0, 0, 0, 0, 0],
            (41201, 12): [1, 1, 210, 200, 180, 0, 0, 0, 0, 0, 0, 0],
        },
    )
    client = make_test_client(connection)

    await client._sync_heating_circuits()

    assert [circuit.circuit_id for circuit in client.heating_circuits] == [1, 2]


@pytest.mark.asyncio
async def test_client_auto_detection_propagates_other_modbus_errors(
    make_test_client,
) -> None:
    """Do not misclassify communication failures as the end of the circuit list."""

    class FailingDetectionConnection(ExactRegisterConnection):
        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise ModbusResponseError(
                function_code=132,
                exception_code=4,
                operation=f"reading input register {address}",
            )

    client = make_test_client(FailingDetectionConnection())

    with pytest.raises(ModbusResponseError) as error:
        await client._sync_heating_circuits()

    assert error.value.exception_code == 4


@pytest.mark.asyncio
async def test_client_requires_first_heating_circuit_during_auto_detection(
    make_test_client,
) -> None:
    """Propagate an absent-circuit response when circuit one is unavailable."""

    class NoFirstCircuitConnection(ExactRegisterConnection):
        async def read_input_registers(self, address: int, count: int) -> list[int]:
            raise ModbusResponseError(
                function_code=132,
                exception_code=10,
                operation=f"reading input register {address}",
            )

    client = make_test_client(NoFirstCircuitConnection())

    with pytest.raises(ModbusResponseError) as error:
        await client._sync_heating_circuits()

    assert error.value.exception_code == 10


@pytest.mark.asyncio
async def test_client_connection_context_and_basic_properties(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    fake_system_connection.is_connected = False
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    assert client.host == "127.0.0.1"
    assert client.is_connected is False
    assert client.inputs is client._inputs
    assert client.energy is client._energy
    assert client.audit_log is client._audit
    assert client.last_sync is None
    assert "disconnected" in repr(client)

    await client.connect()
    assert client.is_connected is True

    await client.sync()
    assert client.last_sync is not None
    assert client.last_sync == client.system.last_updated
    assert "connected" in repr(client)

    await client.disconnect()
    assert client.is_connected is False

    async with client as managed:
        assert managed is client
        assert managed.is_connected is True

    assert client.is_connected is False


@pytest.mark.asyncio
async def test_client_change_callbacks_and_cache_updates(
    caplog: pytest.LogCaptureFixture,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(fake_system_connection, n_heating_circuits=1)
    events = []

    def collect(event) -> None:
        events.append(event)

    def broken(_event) -> None:
        raise RuntimeError("broken callback")

    client.on_change(collect)
    client.on_change(broken)
    client._state_cache["sensor"] = Temperature.from_celsius(10.0)

    with caplog.at_level(logging.ERROR, logger="wab11.client"):
        client._update_cached_state("sensor", Temperature.from_celsius(10.0))
        client._update_cached_state("sensor", Temperature.from_celsius(11.0))
        client._update_cached_state("flag", True)
        client._emit_change("flag", True, True)

    assert [event.register for event in events] == ["sensor", "flag"]
    assert [event.source for event in events] == ["device", "device"]
    assert events[0].old_value == Temperature.from_celsius(10.0)
    assert events[0].new_value == Temperature.from_celsius(11.0)
    assert events[1].old_value is None
    assert events[1].new_value is True
    assert "Change callback error: broken callback" in caplog.text
    assert client.remove_change_callback(broken) is True
    assert client.remove_change_callback(broken) is False


@pytest.mark.asyncio
async def test_client_reads_known_registers_and_rejects_unknown(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    assert (await client.read_register("outdoor_temp_1")).celsius == 4.5
    assert await client.read_register("system_mode") == SystemMode.HEATING

    with pytest.raises(ValidationError, match="Unknown register: missing_register"):
        await client.read_register("missing_register")


@pytest.mark.asyncio
async def test_client_high_level_write_methods_update_state_and_audit(
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(fake_system_connection, n_heating_circuits=2)
    limiter = RecordingLimiter()
    client._rate_limiter = limiter
    local_events = []
    client.on_change(local_events.append)

    expected_writes = [
        ("system_mode", SystemMode.COOLING),
        ("hk1_mode", HeatingCircuitMode.COMFORT),
        ("hk1_setpoint_comfort", 21.5),
        ("hk1_setpoint_normal", 20.0),
        ("hk1_setpoint_setback", 17.0),
        ("hk1_party_pause", PartyPauseCode.AUTOMATIC),
        ("hk1_party_pause", PartyPauseCode.party_hours(3.0)),
        ("hk1_party_pause", PartyPauseCode.pause_hours(2.0)),
        ("ww_normal", 50.0),
        ("ww_setback", 43.0),
        ("ww_push_minutes", 15),
        ("ww_push_minutes", 0),
        ("power_request", 9500),
    ]

    await client.set_system_mode(SystemMode.COOLING, confirmed=True)
    await client.set_heating_circuit_mode(1, HeatingCircuitMode.COMFORT)
    await client.set_heating_circuit_setpoint(1, "comfort", 21.5)
    await client.set_heating_circuit_setpoint(1, "normal", 20.0)
    await client.set_heating_circuit_setpoint(1, "setback", 17.0)
    await client.set_heating_party_pause(1, "auto")
    await client.set_heating_party_pause(1, "party", 3.0)
    await client.set_heating_party_pause(1, "pause", 2.0)
    await client.set_hot_water_setpoint("normal", 50.0)
    await client.set_hot_water_setpoint("setback", 43.0)
    await client.trigger_hot_water_push(15)
    await client.cancel_hot_water_push()
    await client.write_register("power_request", 9500)

    assert fake_system_connection.writes == [
        (
            ALL_REGISTERS[name].address,
            FormatCodec.encode(ALL_REGISTERS[name].fmt, value),
        )
        for name, value in expected_writes
    ]
    assert limiter.acquired == [name for name, _ in expected_writes]
    assert [event.source for event in local_events] == ["local"] * len(expected_writes)
    assert [event.register for event in local_events] == [
        name for name, _ in expected_writes
    ]
    assert client.system.system_mode == SystemMode.COOLING
    assert client.heating_circuits[0].mode == HeatingCircuitMode.COMFORT
    assert client.heating_circuits[0].setpoint_comfort.celsius == 21.5
    assert client.heating_circuits[0].setpoint_normal.celsius == 20.0
    assert client.heating_circuits[0].setpoint_setback.celsius == 17.0
    assert client.heating_circuits[0].party_pause == PartyPauseCode.pause_hours(2.0)
    assert client.hot_water.setpoint_normal.celsius == 50.0
    assert client.hot_water.setpoint_setback.celsius == 43.0
    assert client.hot_water.push_minutes == 0
    assert client._state_cache["power_request"] == 9500
    assert len(client.audit_log.get_writes()) == len(expected_writes)


@pytest.mark.asyncio
async def test_client_high_level_methods_validate_arguments(
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(fake_system_connection, n_heating_circuits=2)

    with pytest.raises(ValidationError, match="Circuit must be 1-2"):
        await client.set_heating_circuit_mode(3, HeatingCircuitMode.AUTOMATIC)

    with pytest.raises(
        ValidationError, match="Level must be 'comfort', 'normal', or 'setback'"
    ):
        await client.set_heating_circuit_setpoint(1, "boost", 21.0)

    with pytest.raises(
        ValidationError, match="Mode must be 'party', 'pause', or 'auto'"
    ):
        await client.set_heating_party_pause(1, "boost")

    with pytest.raises(ValidationError, match="Level must be 'normal' or 'setback'"):
        await client.set_hot_water_setpoint("comfort", 50.0)

    with pytest.raises(
        ValidationError, match="Push minutes must be 0 \\(off\\) or 5-240"
    ):
        await client.trigger_hot_water_push(4)


@pytest.mark.asyncio
async def test_client_failed_write_is_audited(
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(fake_system_connection, n_heating_circuits=1)
    client._validator = WriteValidator(require_confirmation=True)
    client._state_cache["system_mode"] = SystemMode.AUTOMATIC

    with pytest.raises(SafetyError, match="requires explicit confirmation"):
        await client.set_system_mode(SystemMode.HEATING)

    failures = client.audit_log.get_failures()
    assert len(failures) == 1
    assert failures[0].register == "system_mode"
    assert failures[0].old_value == SystemMode.AUTOMATIC
    assert failures[0].new_value == SystemMode.HEATING
    assert "requires explicit confirmation" in failures[0].error
    assert fake_system_connection.writes == []


@pytest.mark.asyncio
async def test_client_sync_preserves_previous_values_for_unknown_enums(
    make_test_client,
) -> None:
    connection = ExactRegisterConnection(
        input_blocks={
            (30001, 6): [45, 42, 65535, 65535, 1, 999],
            (31101, 5): [215, 208, 40, 320, 318],
            (32101, 2): [500, 487],
            (33101, 11): [999, 1, 47, 332, 287, 25, 61, 315, 284, 310, 308],
            (34101, 7): [0, 1200, 80, 0, 0, 0, 0],
            (35101, 8): [0, 1, 1, 0, 0, 1, 0, 0],
        },
        holding_blocks={
            (40001, 2): [999, 8000],
            (
                41101,
                12,
            ): [
                HeatingCircuitConfig.PUMP_CIRCUIT.value,
                999,
                999,
                25,
                225,
                205,
                175,
                12,
                18,
                350,
                280,
                180,
            ],
            (42101, 5): [999, 0, 500, 430, 20],
            (43101, 10): [999, 0, 0, 70, 65, 75, 80, 18, 12, 9],
            (44101, 6): [0, 5, 6, 65416, 65486, 65506],
        },
    )
    client = make_test_client(connection, n_heating_circuits=1)
    hk = client.heating_circuits[0]

    client.system.operating_state = OperatingState.COOLING
    client.system.system_mode = SystemMode.SUMMER
    hk.request_type = RequestType.CONSTANT
    hk.mode = HeatingCircuitMode.NORMAL
    client.hot_water.config = HotWaterConfig.PUMP
    client.heat_pump.operating_state = OperatingState.HEATING
    client.heat_pump.config = HeatPumpConfig.HEATING_ONLY

    await client.sync()

    assert client.system.operating_state == OperatingState.COOLING
    assert client.system.system_mode == SystemMode.SUMMER
    assert hk.config == HeatingCircuitConfig.PUMP_CIRCUIT
    assert hk.request_type == RequestType.CONSTANT
    assert hk.mode == HeatingCircuitMode.NORMAL
    assert hk.room_humidity == 40
    assert client.hot_water.config == HotWaterConfig.PUMP
    assert client.heat_pump.operating_state == OperatingState.HEATING
    assert client.heat_pump.config == HeatPumpConfig.HEATING_ONLY
    assert client.heat_pump.power_request_percent == 47


@pytest.mark.asyncio
async def test_client_sync_treats_unknown_heating_config_as_not_configured(
    make_test_client,
) -> None:
    connection = ExactRegisterConnection(
        input_blocks={(31101, 5): [215, 208, 40, 320, 318]},
        holding_blocks={
            (41101, 12): [
                999,
                1,
                HeatingCircuitMode.COMFORT.value,
                25,
                225,
                205,
                175,
                12,
                18,
                350,
                280,
                180,
            ]
        },
    )
    client = make_test_client(connection, n_heating_circuits=1)
    hk = client.heating_circuits[0]
    hk.room_temp = Temperature.from_celsius(19.0)

    await client._sync_heating_circuit(1, hk)

    assert hk.config == HeatingCircuitConfig.NOT_CONFIGURED
    assert hk.room_temp.celsius == 19.0


@pytest.mark.asyncio
async def test_client_polling_lifecycle_updates_state_and_disconnects_cleanly(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    await client.start_polling(interval=0.001, energy_interval=0.0)
    first_task = client._polling_task
    await client.start_polling(interval=0.001, energy_interval=0.0)

    await asyncio.sleep(0.02)

    assert client._polling_task is first_task
    assert client.is_polling is True
    assert "polling" in repr(client)
    assert client.last_sync is not None
    assert client.energy.total.year == 1240.0

    await client.disconnect()
    await client.stop_polling()

    assert client.is_connected is False
    assert client.is_polling is False
    assert "polling" not in repr(client)


@pytest.mark.asyncio
async def test_client_polling_logs_sync_errors(
    caplog: pytest.LogCaptureFixture,
    make_test_client,
) -> None:
    client = make_test_client(ExplodingConnection(), n_heating_circuits=1)

    with caplog.at_level(logging.ERROR, logger="wab11.client"):
        await client.start_polling(interval=0.001, energy_interval=0.0)
        await asyncio.sleep(0.01)
        await client.stop_polling()

    assert "Polling error: boom" in caplog.text
