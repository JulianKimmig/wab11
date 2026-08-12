from __future__ import annotations

import asyncio

import pytest

from wab11 import WAB11Client
from wab11.registers.definitions import ALL_REGISTERS


def _warm_register_names(n_heating_circuits: int) -> list[str]:
    names: list[str] = []
    for name in sorted(ALL_REGISTERS):
        if name.startswith("hk") and int(name[2]) > n_heating_circuits:
            continue
        names.append(name)
    return names


@pytest.mark.warm
def test_live_device_reads_all_configured_registers_without_writes(
    warm_device_settings: dict[str, object],
) -> None:
    async def exercise_live_device() -> None:
        client = WAB11Client(
            warm_device_settings["host"],
            port=warm_device_settings["port"],
            unit_id=warm_device_settings["unit_id"],
            timeout=warm_device_settings["timeout"],
            n_heating_circuits=warm_device_settings["n_heating_circuits"],
        )
        write_attempts: list[tuple[int, int]] = []

        async def fail_write(address: int, value: int) -> None:
            write_attempts.append((address, value))
            raise AssertionError(f"warm test attempted a write to {address}={value}")

        client._connection.write_register = fail_write  # type: ignore[method-assign]

        try:
            await client.connect()
            await client.sync()
            await client.sync_energy()

            read_failures: list[str] = []
            successful_reads = 0
            for register_name in _warm_register_names(len(client.heating_circuits)):
                try:
                    await client.read_register(register_name)
                    successful_reads += 1
                except Exception as exc:  # pragma: no cover - hardware-only path
                    read_failures.append(f"{register_name}: {exc}")

            assert not write_attempts, write_attempts
            assert successful_reads > 0
            assert not read_failures, "failed reads:\n" + "\n".join(read_failures)
        finally:
            await client.disconnect()

    asyncio.run(exercise_live_device())
