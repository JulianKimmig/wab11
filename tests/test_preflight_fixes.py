from __future__ import annotations

import asyncio

import pytest

import wab11.client as client_module
from wab11 import (
    HeatPumpConfig,
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HotWaterConfig,
    OperatingState,
    RequestType,
    SystemMode,
    ValidationError,
    WAB11Client,
)


def raw16(value: int) -> int:
    """Encode a signed 16-bit value as an unsigned Modbus register."""
    return value if value >= 0 else value + 0x10000


class FakeConnection:
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


def make_sync_connection(
    *,
    system_inputs: list[int],
    system_holdings: list[int],
    hk_inputs: list[int],
    hk_holdings: list[int],
    hot_water_inputs: list[int],
    hot_water_holdings: list[int],
    heat_pump_inputs: list[int],
    heat_pump_holdings: list[int],
    secondary_inputs: list[int],
    secondary_holdings: list[int],
    input_statuses: list[int] | None = None,
) -> FakeConnection:
    return FakeConnection(
        input_blocks={
            (30001, 6): system_inputs,
            (31101, 5): hk_inputs,
            (32101, 2): hot_water_inputs,
            (33101, 11): heat_pump_inputs,
            (34101, 7): secondary_inputs,
            (35101, 8): input_statuses or [0] * 8,
        },
        holding_blocks={
            (40001, 2): system_holdings,
            (41101, 12): hk_holdings,
            (42101, 5): hot_water_holdings,
            (43101, 10): heat_pump_holdings,
            (44101, 6): secondary_holdings,
        },
    )


def make_client(
    *,
    n_heating_circuits: int | None = None,
    connection: FakeConnection | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> WAB11Client:
    connection = connection or FakeConnection()
    if monkeypatch is not None:
        monkeypatch.setattr(client_module, "WAB11Connection", lambda config: connection)

    client_kwargs = {
        "require_write_confirmation": False,
        "enable_rate_limiting": False,
    }
    if n_heating_circuits is not None:
        client_kwargs["n_heating_circuits"] = n_heating_circuits

    client = WAB11Client("127.0.0.1", **client_kwargs)
    client._connection = connection
    return client


def test_client_defaults_to_auto_detecting_heating_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(monkeypatch=monkeypatch)

    assert client.heating_circuits == []


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("set_heating_circuit_mode", (3, HeatingCircuitMode.AUTOMATIC)),
        ("set_heating_circuit_setpoint", (3, "comfort", 21.0)),
        ("set_heating_party_pause", (3, "auto")),
    ],
)
def test_heating_circuit_methods_use_configured_circuit_count(
    method_name: str,
    args: tuple[object, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(
        n_heating_circuits=2,
        connection=FakeConnection(),
        monkeypatch=monkeypatch,
    )

    with pytest.raises(ValidationError, match="Circuit must be 1-2"):
        asyncio.run(getattr(client, method_name)(*args))


def test_sync_decodes_signed_temperatures_from_raw_modbus_registers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = make_sync_connection(
        system_inputs=[raw16(-10), raw16(-20), 65535, 65535, 1, OperatingState.HEATING],
        system_holdings=[SystemMode.HEATING, 1234],
        hk_inputs=[raw16(-30), raw16(-40), 55, raw16(-50), raw16(-60)],
        hk_holdings=[
            HeatingCircuitConfig.PUMP_CIRCUIT,
            RequestType.WEATHER_COMPENSATED,
            HeatingCircuitMode.AUTOMATIC,
            25,
            raw16(-70),
            raw16(-80),
            raw16(-90),
            7,
            15,
            raw16(-100),
            raw16(-110),
            raw16(-120),
        ],
        hot_water_inputs=[raw16(-130), raw16(-140)],
        hot_water_holdings=[
            HotWaterConfig.PUMP,
            0,
            raw16(-150),
            raw16(-160),
            raw16(-170),
        ],
        heat_pump_inputs=[
            OperatingState.HEATING,
            1,
            50,
            raw16(-180),
            raw16(-190),
            raw16(-200),
            raw16(-210),
            raw16(-220),
            raw16(-230),
            raw16(-240),
            raw16(-250),
        ],
        heat_pump_holdings=[
            HeatPumpConfig.HEATING_ONLY,
            0,
            0,
            50,
            50,
            50,
            50,
            10,
            10,
            10,
        ],
        secondary_inputs=[0, 0, 0, 0, 0, 0, 0],
        secondary_holdings=[0, 5, 6, raw16(-260), raw16(-270), raw16(-280)],
    )
    client = make_client(
        n_heating_circuits=1,
        connection=connection,
        monkeypatch=monkeypatch,
    )

    asyncio.run(client.sync())

    temperatures = {
        "cache.outdoor_temp_1": client._state_cache["outdoor_temp_1"],
        "cache.outdoor_temp_2": client._state_cache["outdoor_temp_2"],
        "system.outdoor_temp_1": client.system.outdoor_temp_1,
        "system.outdoor_temp_2": client.system.outdoor_temp_2,
        "hk.room_setpoint_effective": client.heating_circuits[
            0
        ].room_setpoint_effective,
        "hk.room_temp": client.heating_circuits[0].room_temp,
        "hk.flow_setpoint": client.heating_circuits[0].flow_setpoint,
        "hk.flow_temp": client.heating_circuits[0].flow_temp,
        "hk.setpoint_comfort": client.heating_circuits[0].setpoint_comfort,
        "hk.setpoint_normal": client.heating_circuits[0].setpoint_normal,
        "hk.setpoint_setback": client.heating_circuits[0].setpoint_setback,
        "hk.constant_temp_heating": client.heating_circuits[0].constant_temp_heating,
        "hk.constant_temp_heating_setback": client.heating_circuits[
            0
        ].constant_temp_heating_setback,
        "hk.constant_temp_cooling": client.heating_circuits[0].constant_temp_cooling,
        "hot_water.setpoint_effective": client.hot_water.setpoint_effective,
        "hot_water.temperature": client.hot_water.temperature,
        "hot_water.setpoint_normal": client.hot_water.setpoint_normal,
        "hot_water.setpoint_setback": client.hot_water.setpoint_setback,
        "hot_water.sg_ready_boost": client.hot_water.sg_ready_boost,
        "heat_pump.flow_temp_b4": client.heat_pump.flow_temp_b4,
        "heat_pump.return_temp": client.heat_pump.return_temp,
        "heat_pump.evaporator_temp": client.heat_pump.evaporator_temp,
        "heat_pump.suction_gas_temp": client.heat_pump.suction_gas_temp,
        "heat_pump.separator_temp_b2": client.heat_pump.separator_temp_b2,
        "heat_pump.regenerative_flow_b21": client.heat_pump.regenerative_flow_b21,
        "heat_pump.buffer_temp_b11": client.heat_pump.buffer_temp_b11,
        "heat_pump.sum_flow_b7": client.heat_pump.sum_flow_b7,
        "secondary.limit_temp": client.secondary_heat.limit_temp,
        "secondary.bivalence_temp_heating": client.secondary_heat.bivalence_temp_heating,
        "secondary.bivalence_temp_hot_water": client.secondary_heat.bivalence_temp_hot_water,
    }
    expected_raws = {
        "cache.outdoor_temp_1": -10,
        "cache.outdoor_temp_2": -20,
        "system.outdoor_temp_1": -10,
        "system.outdoor_temp_2": -20,
        "hk.room_setpoint_effective": -30,
        "hk.room_temp": -40,
        "hk.flow_setpoint": -50,
        "hk.flow_temp": -60,
        "hk.setpoint_comfort": -70,
        "hk.setpoint_normal": -80,
        "hk.setpoint_setback": -90,
        "hk.constant_temp_heating": -100,
        "hk.constant_temp_heating_setback": -110,
        "hk.constant_temp_cooling": -120,
        "hot_water.setpoint_effective": -130,
        "hot_water.temperature": -140,
        "hot_water.setpoint_normal": -150,
        "hot_water.setpoint_setback": -160,
        "hot_water.sg_ready_boost": -170,
        "heat_pump.flow_temp_b4": -180,
        "heat_pump.return_temp": -190,
        "heat_pump.evaporator_temp": -200,
        "heat_pump.suction_gas_temp": -210,
        "heat_pump.separator_temp_b2": -220,
        "heat_pump.regenerative_flow_b21": -230,
        "heat_pump.buffer_temp_b11": -240,
        "heat_pump.sum_flow_b7": -250,
        "secondary.limit_temp": -260,
        "secondary.bivalence_temp_heating": -270,
        "secondary.bivalence_temp_hot_water": -280,
    }

    for name, temperature in temperatures.items():
        assert temperature.raw == expected_raws[name], name


def test_sync_decodes_temperature_sentinel_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = make_sync_connection(
        system_inputs=[0x8000, 0x8001, 65535, 65535, 1, OperatingState.HEATING],
        system_holdings=[SystemMode.HEATING, 1234],
        hk_inputs=[0x8001, 0x8000, 55, 0x8001, 0x8000],
        hk_holdings=[
            HeatingCircuitConfig.PUMP_CIRCUIT,
            RequestType.WEATHER_COMPENSATED,
            HeatingCircuitMode.AUTOMATIC,
            25,
            0x8000,
            0x8001,
            0x8000,
            7,
            15,
            0x8001,
            0x8000,
            0x8001,
        ],
        hot_water_inputs=[0x8000, 0x8001],
        hot_water_holdings=[HotWaterConfig.PUMP, 0, 0x8001, 0x8000, 0x8001],
        heat_pump_inputs=[
            OperatingState.HEATING,
            1,
            50,
            0x8000,
            0x8001,
            0x8000,
            0x8001,
            0x8000,
            0x8001,
            0x8000,
            0x8001,
        ],
        heat_pump_holdings=[
            HeatPumpConfig.HEATING_ONLY,
            0,
            0,
            50,
            50,
            50,
            50,
            10,
            10,
            10,
        ],
        secondary_inputs=[0, 0, 0, 0, 0, 0, 0],
        secondary_holdings=[0, 5, 6, 0x8001, 0x8000, 0x8001],
    )
    client = make_client(
        n_heating_circuits=1,
        connection=connection,
        monkeypatch=monkeypatch,
    )

    asyncio.run(client.sync())

    assert client._state_cache["outdoor_temp_1"].is_no_sensor
    assert client._state_cache["outdoor_temp_2"].is_sensor_fault
    assert client.system.outdoor_temp_1.is_no_sensor
    assert client.system.outdoor_temp_2.is_sensor_fault
    assert client.heating_circuits[0].setpoint_normal.is_sensor_fault
    assert client.hot_water.temperature.is_sensor_fault
    assert client.heat_pump.evaporator_temp.is_no_sensor
    assert client.secondary_heat.limit_temp.is_sensor_fault
