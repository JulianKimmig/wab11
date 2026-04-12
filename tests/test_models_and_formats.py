from __future__ import annotations

from wab11 import (
    HeatPumpConfig,
    HeatingCircuit,
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HeatingCircuitStatus,
    HotWaterConfig,
    HotWaterState,
    HotWaterStatus,
    InputFunction,
    InputsState,
    OperatingState,
    PartyPauseCode,
    RequestType,
    SGReadyState,
    SystemMode,
    Temperature,
)
from wab11.models.base import decode_signed_16, encode_signed_16
from wab11.models.energy import EnergyPeriod, EnergyStatistics
from wab11.models.heat_pump import HeatPumpState
from wab11.models.secondary_heat import SecondaryHeatSourceState
from wab11.models.system import SystemState
from wab11.registers.definitions import DataFormat
from wab11.registers.formats import FormatCodec


def test_temperature_helpers_and_signed_16_helpers() -> None:
    temp = Temperature(215)
    no_sensor = Temperature.no_value()
    sensor_fault = Temperature(Temperature.SENSOR_FAULT)

    assert temp.celsius == 21.5
    assert temp.is_valid is True
    assert temp.is_sensor_fault is False
    assert temp.is_no_sensor is False
    assert Temperature.from_celsius(21.46).raw == 215
    assert no_sensor.celsius is None
    assert no_sensor.is_no_sensor is True
    assert sensor_fault.celsius is None
    assert sensor_fault.is_sensor_fault is True
    assert repr(temp) == "Temperature(21.5°C)"
    assert repr(no_sensor) == "Temperature(NO_SENSOR)"
    assert repr(sensor_fault) == "Temperature(SENSOR_FAULT)"
    assert temp == Temperature(215)
    assert len({temp, Temperature(215), no_sensor}) == 2
    assert decode_signed_16(0x8000) == -32768
    assert decode_signed_16(42) == 42
    assert encode_signed_16(-1) == 0xFFFF
    assert encode_signed_16(42) == 42


def test_party_pause_code_boundaries_and_predicates() -> None:
    assert PartyPauseCode.pause_hours(0.5) == 24
    assert PartyPauseCode.pause_hours(12.0) == 1
    assert PartyPauseCode.party_hours(0.5) == 26
    assert PartyPauseCode.party_hours(12.0) == 49
    assert PartyPauseCode.decode(PartyPauseCode.AUTOMATIC) == ("automatic", None)
    assert PartyPauseCode.decode(21) == ("pause", 2.0)
    assert PartyPauseCode.decode(31) == ("party", 3.0)
    assert PartyPauseCode.is_automatic(25) is True
    assert PartyPauseCode.is_party(31) is True
    assert PartyPauseCode.is_pause(21) is True


def test_heating_circuit_state_properties_and_repr() -> None:
    hk = HeatingCircuit(circuit_id=2)

    assert hk.is_configured is False
    assert hk.input_register_base == 31200
    assert hk.holding_register_base == 41200
    assert "NOT_CONFIGURED" in repr(hk)

    hk.config = HeatingCircuitConfig.MIXER_CIRCUIT
    hk.status = HeatingCircuitStatus.COOLING
    hk.mode = HeatingCircuitMode.COMFORT
    hk.room_temp = Temperature.from_celsius(20.0)
    hk.room_setpoint_effective = Temperature.from_celsius(21.0)
    hk.party_pause = 31

    assert hk.is_configured is True
    assert hk.is_mixer_circuit is True
    assert hk.is_pump_circuit is False
    assert hk.is_heating is False
    assert hk.is_cooling is True
    assert hk.party_pause_info == ("party", 3.0)
    assert hk.is_party_active is True
    assert hk.is_pause_active is False
    assert "mode=COMFORT" in repr(hk)


def test_system_heat_pump_hot_water_and_secondary_heat_properties() -> None:
    system = SystemState(
        outdoor_temp_1=Temperature.from_celsius(3.0),
        error_code=7,
        warning_code=5,
        is_error_free=False,
        operating_state=OperatingState.HEATING,
        system_mode=SystemMode.HEATING,
    )
    assert system.has_error is True
    assert system.has_warning is True
    assert system.outdoor_temp == 3.0
    assert system.is_heating is True
    assert system.is_cooling is False
    assert system.is_hot_water is False
    assert system.is_defrosting is False
    assert system.is_standby is False
    assert "ERROR(7)" in repr(system)

    system.operating_state = OperatingState.PASSIVE_COOLING
    assert system.is_cooling is True
    system.operating_state = OperatingState.HOT_WATER
    assert system.is_hot_water is True
    system.operating_state = OperatingState.DEFROST
    assert system.is_defrosting is True
    system.operating_state = OperatingState.STANDBY
    assert system.is_standby is True

    hp = HeatPumpState(
        config=HeatPumpConfig.HEATING_AND_COOLING,
        operating_state=OperatingState.COOLING,
        power_request_percent=40,
        flow_temp_b4=Temperature.from_celsius(28.0),
        return_temp=Temperature.from_celsius(23.5),
        quiet_mode=1,
    )
    assert hp.is_configured is True
    assert hp.supports_cooling is True
    assert hp.is_running is True
    assert hp.is_heating is False
    assert hp.is_cooling is True
    assert hp.is_defrosting is False
    assert hp.is_hot_water is False
    assert hp.spread == 4.5
    assert hp.is_quiet_mode is True
    assert "power=40%" in repr(hp)
    hp.config = HeatPumpConfig.NOT_CONFIGURED
    assert repr(hp) == "HeatPumpState(NOT_CONFIGURED)"
    hp.operating_state = OperatingState.HOT_WATER
    assert hp.is_hot_water is True
    hp.operating_state = OperatingState.MANUAL_DEFROST
    assert hp.is_defrosting is True
    hp.operating_state = OperatingState.HEATING
    assert hp.is_heating is True
    hp.flow_temp_b4 = Temperature.no_value()
    assert hp.spread is None

    hw = HotWaterState(
        config=HotWaterConfig.PUMP,
        status=HotWaterStatus.PRIORITY_CHARGING,
        setpoint_effective=Temperature.from_celsius(50.0),
        temperature=Temperature.from_celsius(47.5),
        push_minutes=15,
    )
    assert hw.is_configured is True
    assert hw.is_push_active is True
    assert hw.is_charging is True
    assert hw.is_priority_charging is True
    assert hw.current_temp == 47.5
    assert hw.target_temp == 50.0
    assert hw.temp_difference == 2.5
    assert "push=15min" in repr(hw)
    hw.config = HotWaterConfig.DISABLED
    assert repr(hw) == "HotWaterState(NOT_CONFIGURED)"
    hw.setpoint_effective = Temperature.no_value()
    assert hw.target_temp is None
    assert hw.temp_difference is None

    secondary = SecondaryHeatSourceState(
        status_wez2=1,
        status_e1=True,
        status_e2=False,
        operating_hours_wez2=10,
        operating_hours_e1=20,
        operating_hours_e2=30,
        config_wez2=0,
        config_e1=5,
        config_e2=6,
        limit_temp=Temperature.from_celsius(-12.0),
        bivalence_temp_heating=Temperature.from_celsius(-4.0),
    )
    assert secondary.is_wez2_configured is True
    assert secondary.is_wez2_active is True
    assert secondary.is_e1_configured is True
    assert secondary.is_e2_configured is True
    assert secondary.is_e1_active is True
    assert secondary.is_e2_active is False
    assert secondary.any_backup_active is True
    assert secondary.total_operating_hours == 60
    assert secondary.should_activate_backup(-5.0) is True
    assert secondary.should_activate_backup(-3.0) is False
    assert secondary.should_activate_backup(None) is False
    assert secondary.should_lock_heat_pump(-13.0) is True
    assert secondary.should_lock_heat_pump(None) is False
    assert "WEZ2" in repr(secondary)


def test_secondary_heat_sensor_none_paths() -> None:
    secondary = SecondaryHeatSourceState(
        limit_temp=Temperature.no_value(),
        bivalence_temp_heating=Temperature.no_value(),
    )

    assert secondary.should_activate_backup(-10.0) is False
    assert secondary.should_lock_heat_pump(-10.0) is False
    assert repr(secondary) == "SecondaryHeatSourceState(active=[none])"


def test_energy_statistics_and_inputs_properties() -> None:
    period = EnergyPeriod(today=4.0, yesterday=3.5)
    assert period.total_recent == 7.5

    stats = EnergyStatistics(
        total=EnergyPeriod(today=10.0, yesterday=9.0, month=100.0, year=1000.0),
        heating=EnergyPeriod(today=7.0),
        hot_water=EnergyPeriod(today=3.0),
    )
    assert stats.today_total == 10.0
    assert stats.yesterday_total == 9.0
    assert stats.month_total == 100.0
    assert stats.year_total == 1000.0
    assert stats.heating_percentage_today == 70.0
    assert stats.hot_water_percentage_today == 30.0
    assert "today=10.0kWh" in repr(stats)

    zero_stats = EnergyStatistics()
    assert zero_stats.heating_percentage_today is None
    assert zero_stats.hot_water_percentage_today is None

    inputs = InputsState(
        sg_ready_1=True,
        sg_ready_2=False,
        input_h12=True,
        input_h15=True,
        input_de1=True,
    )
    assert inputs.sg_ready_state == SGReadyState.EVU_LOCK
    assert inputs.is_evu_lock is True
    assert inputs.is_sg_maximum is False
    assert inputs.is_sg_recommended is False
    assert inputs.is_sg_normal is False
    assert inputs.any_input_active is True
    assert inputs.get_active_inputs() == ["SGR1", "H1.2", "H1.5", "DE1"]
    assert "sg_ready=EVU_LOCK" in repr(inputs)

    inputs.sg_ready_1 = False
    inputs.sg_ready_2 = True
    assert inputs.sg_ready_state == SGReadyState.RECOMMENDED
    assert inputs.is_sg_recommended is True
    inputs.sg_ready_1 = True
    assert inputs.sg_ready_state == SGReadyState.MAXIMUM
    assert inputs.is_sg_maximum is True
    inputs.sg_ready_2 = False
    inputs.input_h12 = False
    inputs.input_h15 = False
    inputs.input_de1 = False
    assert inputs.any_input_active is True
    inputs.sg_ready_1 = False
    assert inputs.sg_ready_state == SGReadyState.NORMAL
    assert inputs.is_sg_normal is True
    assert inputs.any_input_active is False
    assert inputs.get_active_inputs() == []

    assert InputFunction.SYSTEM_STANDBY.value == 10


def test_format_codec_decode_paths() -> None:
    assert FormatCodec.decode(DataFormat.TEMPERATURE, 0xFFF6).raw == -10
    assert FormatCodec.decode(DataFormat.BOOL, 1) is True
    assert FormatCodec.decode(DataFormat.BOOL, 0) is False
    assert FormatCodec.decode(DataFormat.SYSTEM_MODE, 1) == SystemMode.HEATING
    assert FormatCodec.decode(DataFormat.SYSTEM_MODE, 99) == 99
    assert FormatCodec.decode(DataFormat.OPERATING_STATE, 19) == OperatingState.HEATING
    assert FormatCodec.decode(DataFormat.OPERATING_STATE, 99) == 99
    assert FormatCodec.decode(DataFormat.HEATING_MODE, 1) == HeatingCircuitMode.COMFORT
    assert FormatCodec.decode(DataFormat.HEATING_MODE, 99) == 99
    assert FormatCodec.decode(DataFormat.HEATING_STATUS, 2) == HeatingCircuitStatus.COOLING
    assert FormatCodec.decode(DataFormat.HEATING_STATUS, 99) == 99
    assert FormatCodec.decode(DataFormat.HEATING_CONFIG, 2) == HeatingCircuitConfig.MIXER_CIRCUIT
    assert FormatCodec.decode(DataFormat.HEATING_CONFIG, 99) == 99
    assert FormatCodec.decode(DataFormat.HOT_WATER_STATUS, 3) == HotWaterStatus.PARALLEL_CHARGING
    assert FormatCodec.decode(DataFormat.HOT_WATER_STATUS, 99) == 99
    assert FormatCodec.decode(DataFormat.HOT_WATER_CONFIG, 8) == HotWaterConfig.PUMP
    assert FormatCodec.decode(DataFormat.HOT_WATER_CONFIG, 99) == 99
    assert FormatCodec.decode(DataFormat.HEAT_PUMP_CONFIG, 2) == HeatPumpConfig.HEATING_AND_COOLING
    assert FormatCodec.decode(DataFormat.HEAT_PUMP_CONFIG, 99) == 99
    assert FormatCodec.decode(DataFormat.REQUEST_TYPE, 3) == RequestType.CONSTANT
    assert FormatCodec.decode(DataFormat.REQUEST_TYPE, 99) == 99
    assert FormatCodec.decode(DataFormat.PERCENTAGE, 55) == 55
    assert FormatCodec.decode(DataFormat.PERCENTAGE, 0xFFFF) is None
    assert FormatCodec.decode(DataFormat.SIGNED_16, 0xFFFF) == -1
    assert FormatCodec.decode(DataFormat.UNSIGNED_16, 123) == 123


def test_format_codec_encode_paths() -> None:
    assert FormatCodec.encode(DataFormat.TEMPERATURE, Temperature.from_celsius(-3.0)) == 65506
    assert FormatCodec.encode(DataFormat.TEMPERATURE, 21.5) == 215
    assert FormatCodec.encode(DataFormat.BOOL, True) == 1
    assert FormatCodec.encode(DataFormat.SYSTEM_MODE, SystemMode.HEATING) == 1
    assert FormatCodec.encode(DataFormat.SYSTEM_MODE, 2) == 2
    assert FormatCodec.encode(DataFormat.SYSTEM_MODE, "summer") == 3
    assert FormatCodec.encode(DataFormat.OPERATING_STATE, OperatingState.HEATING) == 19
    assert FormatCodec.encode(DataFormat.OPERATING_STATE, 4) == 4
    assert FormatCodec.encode(DataFormat.HEATING_MODE, HeatingCircuitMode.NORMAL) == 2
    assert FormatCodec.encode(DataFormat.HEATING_MODE, 3) == 3
    assert FormatCodec.encode(DataFormat.HEATING_MODE, "standby") == 4
    assert FormatCodec.encode(DataFormat.HEATING_STATUS, HeatingCircuitStatus.HEATING) == 1
    assert FormatCodec.encode(DataFormat.HEATING_CONFIG, HeatingCircuitConfig.SETPOINT_PUMP_M1) == 3
    assert FormatCodec.encode(DataFormat.HOT_WATER_STATUS, HotWaterStatus.REQUEST_BLOCKED) == 4
    assert FormatCodec.encode(DataFormat.HOT_WATER_CONFIG, HotWaterConfig.DIVERTER_VALVE) == 1
    assert FormatCodec.encode(DataFormat.HEAT_PUMP_CONFIG, HeatPumpConfig.HEATING_ONLY) == 1
    assert FormatCodec.encode(DataFormat.REQUEST_TYPE, RequestType.WEATHER_COMPENSATED) == 1
    assert FormatCodec.encode(DataFormat.PERCENTAGE, None) == 0xFFFF
    assert FormatCodec.encode(DataFormat.PERCENTAGE, 42) == 42
    assert FormatCodec.encode(DataFormat.SIGNED_16, -2) == 0xFFFE
    assert FormatCodec.encode(DataFormat.UNSIGNED_16, 77) == 77


def test_format_codec_invalid_type_errors() -> None:
    try:
        FormatCodec.encode(DataFormat.TEMPERATURE, "bad")
    except TypeError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("Expected TypeError for bad temperature input")

    try:
        FormatCodec.encode(DataFormat.SYSTEM_MODE, object())
    except TypeError as exc:
        assert "SystemMode" in str(exc)
    else:
        raise AssertionError("Expected TypeError for bad system mode input")

    try:
        FormatCodec.encode(DataFormat.HEATING_MODE, object())
    except TypeError as exc:
        assert "HeatingCircuitMode" in str(exc)
    else:
        raise AssertionError("Expected TypeError for bad heating mode input")
