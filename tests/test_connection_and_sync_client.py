from __future__ import annotations

import asyncio

import pytest

import wab11.connection as connection_module
import wab11.sync_client as sync_client_module
from wab11 import HeatingCircuitMode, SystemMode
from wab11.connection import ConnectionConfig, WAB11Connection, _check_pymodbus


class FakeResponse:
    def __init__(self, registers: list[int] | None = None, error: bool = False) -> None:
        self.registers = registers or []
        self._error = error

    def isError(self) -> bool:
        return self._error


class FakeAsyncModbusClient:
    instances: list["FakeAsyncModbusClient"] = []
    connect_results: list[object] = []
    input_results: list[object] = []
    holding_results: list[object] = []
    write_results: list[object] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.slave = None
        self.closed = False
        self.input_calls: list[tuple[int, int]] = []
        self.holding_calls: list[tuple[int, int]] = []
        self.write_calls: list[tuple[int, int]] = []
        self.connect_calls = 0
        self.__class__.instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.connect_results = []
        cls.input_results = []
        cls.holding_results = []
        cls.write_results = []

    async def connect(self) -> bool:
        self.connect_calls += 1
        result = self.connect_results.pop(0) if self.connect_results else True
        if isinstance(result, Exception):
            raise result
        return result

    def close(self) -> None:
        self.closed = True

    async def read_input_registers(self, address: int, count: int):
        self.input_calls.append((address, count))
        result = self.input_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def read_holding_registers(self, address: int, count: int):
        self.holding_calls.append((address, count))
        result = self.holding_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def write_register(self, address: int, value: int):
        self.write_calls.append((address, value))
        result = self.write_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class DummyAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        self.connected = False
        self.calls: list[tuple[str, tuple, dict]] = []
        self.system = "system"
        self.heating_circuits = ["hk1"]
        self.hot_water = "hot_water"
        self.heat_pump = "heat_pump"
        self.secondary_heat = "secondary"
        self.inputs = "inputs"
        self.energy = "energy"
        self.audit_log = "audit"

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def connect(self) -> None:
        self.connected = True
        self.calls.append(("connect", (), {}))

    async def disconnect(self) -> None:
        self.connected = False
        self.calls.append(("disconnect", (), {}))

    async def sync(self) -> None:
        self.calls.append(("sync", (), {}))

    async def sync_energy(self) -> None:
        self.calls.append(("sync_energy", (), {}))

    def on_change(self, callback) -> None:
        self.calls.append(("on_change", (callback,), {}))

    async def set_system_mode(self, mode, confirmed=False) -> None:
        self.calls.append(("set_system_mode", (mode, confirmed), {}))

    async def set_heating_circuit_mode(self, circuit, mode) -> None:
        self.calls.append(("set_heating_circuit_mode", (circuit, mode), {}))

    async def set_heating_circuit_setpoint(self, circuit, level, temperature) -> None:
        self.calls.append(
            ("set_heating_circuit_setpoint", (circuit, level, temperature), {})
        )

    async def set_heating_party_pause(self, circuit, mode, hours) -> None:
        self.calls.append(("set_heating_party_pause", (circuit, mode, hours), {}))

    async def set_hot_water_setpoint(self, level, temperature) -> None:
        self.calls.append(("set_hot_water_setpoint", (level, temperature), {}))

    async def trigger_hot_water_push(self, minutes) -> None:
        self.calls.append(("trigger_hot_water_push", (minutes,), {}))

    async def cancel_hot_water_push(self) -> None:
        self.calls.append(("cancel_hot_water_push", (), {}))

    async def read_register(self, register_name) -> str:
        self.calls.append(("read_register", (register_name,), {}))
        return f"value:{register_name}"

    async def write_register(self, register_name, value, confirmed=False) -> None:
        self.calls.append(("write_register", (register_name, value, confirmed), {}))


def setup_fake_pymodbus(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncModbusClient.reset()
    monkeypatch.setattr(connection_module, "PYMODBUS_AVAILABLE", True)
    monkeypatch.setattr(
        connection_module, "AsyncModbusTcpClient", FakeAsyncModbusClient
    )
    monkeypatch.setattr(connection_module, "ModbusException", RuntimeError)


def test_check_pymodbus_raises_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connection_module, "PYMODBUS_AVAILABLE", False)

    with pytest.raises(ImportError):
        _check_pymodbus()


def test_connection_connect_disconnect_context_and_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_fake_pymodbus(monkeypatch)
    config = ConnectionConfig(host="10.0.0.1", port=502, unit_id=7, timeout=1.5)
    conn = WAB11Connection(config)

    async def exercise() -> None:
        assert conn.config == config
        assert conn.host == "10.0.0.1"
        assert conn.port == 502
        assert "disconnected" in repr(conn)

        await conn.connect()
        client = FakeAsyncModbusClient.instances[-1]
        assert conn.is_connected is True
        assert client.slave == 7
        assert "connected" in repr(conn)

        await conn.connect()
        assert client.connect_calls == 1

        await conn.disconnect()
        assert conn.is_connected is False
        assert client.closed is True

        async with WAB11Connection(config) as managed:
            assert managed.is_connected is True
        assert managed.is_connected is False

    asyncio.run(exercise())


def test_connection_connect_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_fake_pymodbus(monkeypatch)
    FakeAsyncModbusClient.connect_results = [False]
    conn = WAB11Connection(ConnectionConfig(host="10.0.0.2"))

    async def failed_connect() -> None:
        with pytest.raises(
            connection_module.ConnectionError, match="Failed to connect"
        ):
            await conn.connect()

    asyncio.run(failed_connect())

    FakeAsyncModbusClient.reset()
    setup_fake_pymodbus(monkeypatch)
    FakeAsyncModbusClient.connect_results = [RuntimeError("boom")]
    conn = WAB11Connection(ConnectionConfig(host="10.0.0.3"))

    async def exploding_connect() -> None:
        with pytest.raises(
            connection_module.ConnectionError, match="Connection failed: boom"
        ):
            await conn.connect()

    asyncio.run(exploding_connect())


def test_connection_chunked_reads_and_auto_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_fake_pymodbus(monkeypatch)
    FakeAsyncModbusClient.input_results = [
        FakeResponse([1, 2, 3, 4, 5]),
        FakeResponse([6, 7]),
    ]
    FakeAsyncModbusClient.holding_results = [
        FakeResponse([10, 11, 12, 13, 14]),
        FakeResponse([15]),
    ]

    conn = WAB11Connection(ConnectionConfig(host="10.0.0.4", max_registers_per_read=5))

    async def exercise() -> None:
        assert await conn.read_input_registers(30001, 7) == [1, 2, 3, 4, 5, 6, 7]
        assert await conn.read_holding_registers(40001, 6) == [10, 11, 12, 13, 14, 15]

    asyncio.run(exercise())

    client = FakeAsyncModbusClient.instances[-1]
    assert client.input_calls == [(30001, 5), (30006, 2)]
    assert client.holding_calls == [(40001, 5), (40006, 1)]


def test_connection_read_and_write_retry_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    setup_fake_pymodbus(monkeypatch)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(connection_module.asyncio, "sleep", fake_sleep)

    conn = WAB11Connection(ConnectionConfig(host="10.0.0.5", max_retries=3))

    async def exercise() -> None:
        await conn.connect()
        client = FakeAsyncModbusClient.instances[-1]

        FakeAsyncModbusClient.input_results = [
            asyncio.TimeoutError(),
            RuntimeError("modbus"),
            FakeResponse([21, 22]),
        ]
        assert await conn._read_input_with_retry(30001, 2) == [21, 22]

        FakeAsyncModbusClient.holding_results = [
            FakeResponse(error=True),
            RuntimeError("modbus"),
            FakeResponse([31]),
        ]
        assert await conn._read_holding_with_retry(40001, 1) == [31]

        FakeAsyncModbusClient.write_results = [
            asyncio.TimeoutError(),
            RuntimeError("modbus"),
            FakeResponse(),
        ]
        await conn._write_with_retry(40001, 99)
        assert client.write_calls[-1] == (40001, 99)

    asyncio.run(exercise())

    assert sleep_calls == [0.5, 1.0, 0.5, 1.0, 0.5, 1.0]


def test_connection_final_retry_failures_and_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_fake_pymodbus(monkeypatch)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(connection_module.asyncio, "sleep", fake_sleep)

    conn = WAB11Connection(
        ConnectionConfig(host="10.0.0.6", reconnect_delay=2.0, max_retries=2)
    )

    async def exercise() -> None:
        await conn.connect()

        FakeAsyncModbusClient.input_results = [
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
        ]
        with pytest.raises(
            connection_module.TimeoutError,
            match="Timeout reading input register 30001",
        ):
            await conn._read_input_with_retry(30001, 1)

        FakeAsyncModbusClient.holding_results = [
            FakeResponse(error=True),
            FakeResponse(error=True),
        ]
        with pytest.raises(
            connection_module.ConnectionError,
            match="Read failed: Modbus error reading holding register 40001",
        ):
            await conn._read_holding_with_retry(40001, 1)

        FakeAsyncModbusClient.write_results = [
            FakeResponse(error=True),
            FakeResponse(error=True),
        ]
        with pytest.raises(
            connection_module.ConnectionError,
            match="Write failed: Modbus error writing register 40001",
        ):
            await conn._write_with_retry(40001, 1)

        first_client = FakeAsyncModbusClient.instances[-1]
        await conn.reconnect()
        second_client = FakeAsyncModbusClient.instances[-1]
        assert first_client is not second_client

    asyncio.run(exercise())
    assert sleep_calls[-1] == 2.0


def test_sync_client_wrapper_behaviour(monkeypatch: pytest.MonkeyPatch) -> None:
    created_clients: list[DummyAsyncClient] = []

    def fake_client_factory(*args, **kwargs):
        client = DummyAsyncClient(*args, **kwargs)
        client.init_args = args
        client.init_kwargs = kwargs
        created_clients.append(client)
        return client

    monkeypatch.setattr(sync_client_module, "WAB11Client", fake_client_factory)

    sync = sync_client_module.WAB11SyncClient(
        "10.0.0.7",
        port=1502,
        unit_id=9,
        require_write_confirmation=False,
        enable_rate_limiting=False,
        timeout=4.0,
    )

    with pytest.raises(RuntimeError, match="Client not connected"):
        sync._ensure_connected()

    loop = sync._get_loop()
    assert loop is sync._get_loop()

    sync.connect()
    client = created_clients[-1]
    assert client.init_args == ("10.0.0.7", 1502, 9)
    assert client.init_kwargs == {
        "require_write_confirmation": False,
        "enable_rate_limiting": False,
        "timeout": 4.0,
        "n_heating_circuits": 5,
    }
    assert sync.is_connected is True
    assert sync.host == "10.0.0.7"
    assert sync.system == "system"
    assert sync.heating_circuits == ["hk1"]
    assert sync.hot_water == "hot_water"
    assert sync.heat_pump == "heat_pump"
    assert sync.secondary_heat == "secondary"
    assert sync.inputs == "inputs"
    assert sync.energy == "energy"
    assert sync.audit_log == "audit"

    def callback(event) -> None:
        pass

    sync.on_change(callback)
    sync.sync()
    sync.sync_energy()
    sync.set_system_mode(SystemMode.HEATING, confirmed=True)
    sync.set_heating_circuit_mode(1, HeatingCircuitMode.COMFORT)
    sync.set_heating_circuit_setpoint(1, "comfort", 21.5)
    sync.set_heating_party_pause(1, "party", 2.0)
    sync.set_hot_water_setpoint("normal", 50.0)
    sync.trigger_hot_water_push(10)
    sync.cancel_hot_water_push()
    assert sync.read_register("outdoor_temp_1") == "value:outdoor_temp_1"
    sync.write_register("system_mode", 1, confirmed=True)
    assert "connected" in repr(sync)

    sync.disconnect()
    assert sync.is_connected is False
    assert "disconnected" in repr(sync)

    sync.connect()
    with sync_client_module.WAB11SyncClient("10.0.0.8") as managed:
        assert managed.is_connected is True
    assert managed._loop is not None and managed._loop.is_closed()


def test_sync_client_forwards_custom_heating_circuit_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[DummyAsyncClient] = []

    def fake_client_factory(*args, **kwargs):
        client = DummyAsyncClient(*args, **kwargs)
        client.init_kwargs = kwargs
        created_clients.append(client)
        return client

    monkeypatch.setattr(sync_client_module, "WAB11Client", fake_client_factory)

    sync = sync_client_module.WAB11SyncClient(
        "10.0.0.9",
        n_heating_circuits=3,
    )

    sync.connect()

    assert created_clients[-1].init_kwargs["n_heating_circuits"] == 3

    sync.disconnect()
