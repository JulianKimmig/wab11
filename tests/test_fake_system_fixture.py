from __future__ import annotations

import asyncio

from wab11 import HeatingCircuitConfig, SystemMode
from wab11.registers.definitions import ALL_REGISTERS


def test_fake_system_fixture_supports_full_sync(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    asyncio.run(client.sync())
    asyncio.run(client.sync_energy())

    assert client.system.outdoor_temp_1.celsius == 4.5
    assert client.system.system_mode == SystemMode.HEATING
    assert client.hot_water.temperature.celsius == 48.7
    assert client.heating_circuits[0].config == HeatingCircuitConfig.PUMP_CIRCUIT
    assert client.heating_circuits[2].config == HeatingCircuitConfig.NOT_CONFIGURED
    assert client.secondary_heat.limit_temp.celsius == -12.0
    assert client.energy.total.year == 1240.0


def test_fake_system_fixture_supports_every_defined_register_read(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    async def read_all_registers() -> dict[str, object]:
        values: dict[str, object] = {}
        for name in sorted(ALL_REGISTERS):
            values[name] = await client.read_register(name)
        return values

    values = asyncio.run(read_all_registers())

    assert set(values) == set(ALL_REGISTERS)
    assert values["system_mode"] == SystemMode.HEATING
    assert values["energy_total_year"] == 1240
    assert values["hk3_config"] == HeatingCircuitConfig.NOT_CONFIGURED


def test_fake_system_fixture_applies_holding_register_writes(
    fake_system_config: dict,
    fake_system_connection,
    make_test_client,
) -> None:
    client = make_test_client(
        fake_system_connection,
        n_heating_circuits=fake_system_config["client"]["n_heating_circuits"],
    )

    async def write_and_read_back() -> int:
        await client.write_register("power_request", 9500)
        return await client.read_register("power_request")

    read_back = asyncio.run(write_and_read_back())

    assert fake_system_connection.writes[-1] == (40002, 9500)
    assert read_back == 9500
