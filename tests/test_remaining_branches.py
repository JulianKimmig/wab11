from __future__ import annotations

import asyncio

import pytest

from wab11 import (
    InputFunction,
    InputsState,
    PartyPauseCode,
    SecondaryHeatSourceState,
)
from wab11.registers.definitions import (
    DataFormat,
    RegisterDef,
    RegisterType,
    generate_heating_circuit_registers,
)
from wab11.registers.formats import FormatCodec
from wab11.security.rate_limiter import RateLimiter


def test_format_codec_scalar_and_fallback_paths() -> None:
    assert FormatCodec.decode("custom", 12) == 12
    assert FormatCodec.encode(DataFormat.HEATING_STATUS, 7) == 7
    assert FormatCodec.encode(DataFormat.HEATING_CONFIG, 4) == 4
    assert FormatCodec.encode(DataFormat.HOT_WATER_STATUS, 5) == 5
    assert FormatCodec.encode(DataFormat.HOT_WATER_CONFIG, 9) == 9
    assert FormatCodec.encode(DataFormat.HEAT_PUMP_CONFIG, 3) == 3
    assert FormatCodec.encode(DataFormat.REQUEST_TYPE, 2) == 2
    assert FormatCodec.encode("custom", "12") == 12


def test_register_definition_helpers_and_generation_boundaries() -> None:
    input_register = RegisterDef(
        name="outdoor_temp_1",
        address=30005,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
    )
    holding_register = RegisterDef(
        name="system_mode",
        address=40002,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.SYSTEM_MODE,
        writable=True,
    )
    hk5_registers = generate_heating_circuit_registers(5)

    assert input_register.offset == 4
    assert input_register.is_input is True
    assert input_register.is_holding is False
    assert holding_register.offset == 1
    assert holding_register.is_input is False
    assert holding_register.is_holding is True
    assert hk5_registers["hk5_room_temp"].address == 31502
    assert hk5_registers["hk5_mode"].address == 41503

    with pytest.raises(ValueError, match="circuit_id must be 1-5"):
        generate_heating_circuit_registers(0)


def test_rate_limiter_waits_for_per_register_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 100.0
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        nonlocal current_time
        sleep_calls.append(seconds)
        current_time += seconds

    monkeypatch.setattr("wab11.security.rate_limiter.time.time", lambda: current_time)
    monkeypatch.setattr("wab11.security.rate_limiter.asyncio.sleep", fake_sleep)

    limiter = RateLimiter(
        global_limit=10, per_register_limit=2, cooldown=0.0, window=10.0
    )

    async def exercise() -> None:
        await limiter.acquire("hk1")
        await limiter.acquire("hk1")
        assert pytest.approx(limiter.get_wait_time("hk1"), rel=1e-6) == 10.0
        assert limiter.can_write_immediately("hk1") is False
        await limiter.acquire("hk1")

    asyncio.run(exercise())

    assert sleep_calls == [10.1]


def test_inputs_secondary_heat_and_party_pause_edge_paths() -> None:
    inputs = InputsState(
        sg_ready_2=True,
        input_h13=True,
        input_h14=True,
        input_de2=True,
    )
    secondary = SecondaryHeatSourceState(config_e2=6, status_e2=True)

    assert inputs.get_active_inputs() == ["SGR2", "H1.3", "H1.4", "DE2"]
    assert "DE2" in repr(inputs)
    assert repr(secondary) == "SecondaryHeatSourceState(active=[E2])"
    assert InputFunction.SYSTEM_STANDBY.value == 10

    with pytest.raises(ValueError, match="Pause hours must be 0.5-12.0"):
        PartyPauseCode.pause_hours(0.25)

    with pytest.raises(ValueError, match="Party hours must be 0.5-12.0"):
        PartyPauseCode.party_hours(12.5)
