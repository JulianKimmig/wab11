from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import wab11.client as client_module
from wab11 import WAB11Client

FAKE_SYSTEM_CONFIG_PATH = Path(__file__).parent / "fixtures" / "fake_system.json"


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


class ConfigBackedFakeConnection:
    """Fake Modbus connection backed by block data from a fixture config."""

    def __init__(
        self,
        *,
        input_blocks: dict[int, list[int]],
        holding_blocks: dict[int, list[int]],
    ) -> None:
        self.input_blocks = {
            address: list(values) for address, values in input_blocks.items()
        }
        self.holding_blocks = {
            address: list(values) for address, values in holding_blocks.items()
        }
        self.writes: list[tuple[int, int]] = []
        self.is_connected = True

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ConfigBackedFakeConnection":
        register_blocks = config["register_blocks"]
        return cls(
            input_blocks={
                int(address): values
                for address, values in register_blocks["input"].items()
            },
            holding_blocks={
                int(address): values
                for address, values in register_blocks["holding"].items()
            },
        )

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read_input_registers(self, address: int, count: int = 1) -> list[int]:
        return self._read_block(
            self.input_blocks, address, count, register_type="input"
        )

    async def read_holding_registers(self, address: int, count: int = 1) -> list[int]:
        return self._read_block(
            self.holding_blocks, address, count, register_type="holding"
        )

    async def write_register(self, address: int, value: int) -> None:
        self.writes.append((address, value))
        self._write_holding_value(address, value)

    def _read_block(
        self,
        block_map: dict[int, list[int]],
        address: int,
        count: int,
        *,
        register_type: str,
    ) -> list[int]:
        for base_address in sorted(block_map):
            values = block_map[base_address]
            offset = address - base_address
            if offset < 0:
                continue
            if offset + count <= len(values):
                return list(values[offset : offset + count])

        raise AssertionError(
            f"Unexpected {register_type} register read: address={address}, count={count}"
        )

    def _write_holding_value(self, address: int, value: int) -> None:
        for base_address in sorted(self.holding_blocks):
            values = self.holding_blocks[base_address]
            offset = address - base_address
            if 0 <= offset < len(values):
                values[offset] = value
                return

        self.holding_blocks[address] = [value]


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("wab11")
    group.addoption(
        "--run-warm",
        action="store_true",
        default=False,
        help="Run warm tests against a real WAB11 device.",
    )
    group.addoption(
        "--warm-host",
        action="store",
        default=os.getenv("WAB11_TEST_HOST"),
        help="Host or IP of the real WAB11 device.",
    )
    group.addoption(
        "--warm-port",
        action="store",
        type=int,
        default=_env_int("WAB11_TEST_PORT", 502),
        help="Modbus TCP port for the real WAB11 device.",
    )
    group.addoption(
        "--warm-unit-id",
        action="store",
        type=int,
        default=_env_int("WAB11_TEST_UNIT_ID", 1),
        help="Modbus unit ID for the real WAB11 device.",
    )
    group.addoption(
        "--warm-timeout",
        action="store",
        type=float,
        default=_env_float("WAB11_TEST_TIMEOUT", 3.0),
        help="Modbus timeout for the real WAB11 device.",
    )
    group.addoption(
        "--warm-heating-circuits",
        action="store",
        type=int,
        default=(
            int(os.environ["WAB11_TEST_HEATING_CIRCUITS"])
            if "WAB11_TEST_HEATING_CIRCUITS" in os.environ
            else None
        ),
        help="Explicit heating-circuit count (1-5); omit to auto-detect.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "warm: read-only live-device tests that require --run-warm and a real WAB11",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if config.getoption("--run-warm"):
        return

    skip_warm = pytest.mark.skip(
        reason="warm tests require --run-warm and a real WAB11"
    )
    for item in items:
        if item.get_closest_marker("warm") is not None:
            item.add_marker(skip_warm)


@pytest.fixture(scope="session")
def fake_system_config() -> dict[str, Any]:
    return json.loads(FAKE_SYSTEM_CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def fake_system_connection(
    fake_system_config: dict[str, Any],
) -> ConfigBackedFakeConnection:
    return ConfigBackedFakeConnection.from_config(deepcopy(fake_system_config))


@pytest.fixture
def make_test_client(monkeypatch: pytest.MonkeyPatch):
    def factory(
        connection: ConfigBackedFakeConnection,
        *,
        n_heating_circuits: int | None = None,
    ) -> WAB11Client:
        monkeypatch.setattr(client_module, "WAB11Connection", lambda config: connection)

        client_kwargs: dict[str, Any] = {
            "require_write_confirmation": False,
            "enable_rate_limiting": False,
        }
        if n_heating_circuits is not None:
            client_kwargs["n_heating_circuits"] = n_heating_circuits

        client = WAB11Client("127.0.0.1", **client_kwargs)
        client._connection = connection
        return client

    return factory


@pytest.fixture(scope="session")
def warm_device_settings(pytestconfig: pytest.Config) -> dict[str, Any]:
    if not pytestconfig.getoption("--run-warm"):
        pytest.skip("warm tests require --run-warm and a real WAB11")

    host = pytestconfig.getoption("--warm-host")
    if not host:
        raise pytest.UsageError(
            "--run-warm requires --warm-host or the WAB11_TEST_HOST environment variable"
        )

    n_heating_circuits = pytestconfig.getoption("--warm-heating-circuits")
    if n_heating_circuits is not None and not 1 <= n_heating_circuits <= 5:
        raise pytest.UsageError("--warm-heating-circuits must be between 1 and 5")

    return {
        "host": host,
        "port": pytestconfig.getoption("--warm-port"),
        "unit_id": pytestconfig.getoption("--warm-unit-id"),
        "timeout": pytestconfig.getoption("--warm-timeout"),
        "n_heating_circuits": n_heating_circuits,
    }
