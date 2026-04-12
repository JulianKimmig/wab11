"""
Complete Modbus register definitions for the WAB11 controller.

This module contains all register definitions extracted from the
WAB11 Modbus documentation, organized by functional area.

Register addressing:
- Input registers: 30xxx (read-only)
- Holding registers: 40xxx (read/write)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RegisterType(Enum):
    """Type of Modbus register."""

    INPUT = "input"  # Read-only (30xxx, 31xxx, etc.)
    HOLDING = "holding"  # Read/write (40xxx, 41xxx, etc.)


class DataFormat(Enum):
    """
    Data format for register values.

    Determines how raw 16-bit values are encoded/decoded.
    """

    TEMPERATURE = "temp"  # Signed, /10 -> °C
    UNSIGNED_16 = "u16"  # Unsigned 16-bit integer
    SIGNED_16 = "s16"  # Signed 16-bit integer
    BOOL = "bool"  # Boolean (0/1)
    SYSTEM_MODE = "sys_mode"  # SystemMode enum
    OPERATING_STATE = "op_state"  # OperatingState enum
    HEATING_MODE = "hk_mode"  # HeatingCircuitMode enum
    HEATING_STATUS = "hk_status"  # HeatingCircuitStatus enum
    HEATING_CONFIG = "hk_config"  # HeatingCircuitConfig enum
    HOT_WATER_STATUS = "ww_status"  # HotWaterStatus enum
    HOT_WATER_CONFIG = "ww_config"  # HotWaterConfig enum
    HEAT_PUMP_CONFIG = "wp_config"  # HeatPumpConfig enum
    REQUEST_TYPE = "req_type"  # RequestType enum
    PERCENTAGE = "percent"  # 0-100%


@dataclass(frozen=True)
class RegisterDef:
    """
    Immutable register definition.

    Attributes:
        name: Unique register name (snake_case)
        address: Logical Modbus address (30001, 40001, etc.)
        reg_type: INPUT or HOLDING
        fmt: Data format for encoding/decoding
        description: Human-readable description
        writable: Whether the register can be written
        min_value: Minimum allowed raw value (for validation)
        max_value: Maximum allowed raw value (for validation)
        unit: Unit of measurement (°C, %, W, etc.)
    """

    name: str
    address: int
    reg_type: RegisterType
    fmt: DataFormat
    description: str = ""
    writable: bool = False
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    unit: str = ""

    @property
    def offset(self) -> int:
        """
        Get 0-based offset for pymodbus.

        Converts logical address (30001, 40001) to offset (0, 0).
        """
        if self.reg_type == RegisterType.INPUT:
            return self.address - 30001
        else:
            return self.address - 40001

    @property
    def is_input(self) -> bool:
        """Check if this is an input register."""
        return self.reg_type == RegisterType.INPUT

    @property
    def is_holding(self) -> bool:
        """Check if this is a holding register."""
        return self.reg_type == RegisterType.HOLDING


# =============================================================================
# System Registers (30xxx / 40xxx)
# =============================================================================

SYSTEM_REGISTERS: dict[str, RegisterDef] = {
    # Input registers (30xxx)
    "outdoor_temp_1": RegisterDef(
        name="outdoor_temp_1",
        address=30001,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Außentemperatur 1",
        unit="°C",
    ),
    "outdoor_temp_2": RegisterDef(
        name="outdoor_temp_2",
        address=30002,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Außentemperatur 2",
        unit="°C",
    ),
    "error_code": RegisterDef(
        name="error_code",
        address=30003,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Fehlercode (65535 = kein Fehler)",
    ),
    "warning_code": RegisterDef(
        name="warning_code",
        address=30004,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Warncode (65535 = keine Warnung)",
    ),
    "ok_flag": RegisterDef(
        name="ok_flag",
        address=30005,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Fehlerfrei (0=Fehler, 1=OK)",
    ),
    "operating_state": RegisterDef(
        name="operating_state",
        address=30006,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.OPERATING_STATE,
        description="Betriebsstatusanzeige",
    ),
    # Holding registers (40xxx)
    "system_mode": RegisterDef(
        name="system_mode",
        address=40001,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.SYSTEM_MODE,
        description="Systembetriebsart",
        writable=True,
        min_value=0,
        max_value=5,
    ),
    "power_request": RegisterDef(
        name="power_request",
        address=40002,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Leistungsvorgabe System",
        writable=True,
        min_value=0,
        max_value=30000,
        unit="W",
    ),
}


# =============================================================================
# Heating Circuit Registers (31xxx / 41xxx)
# =============================================================================


def generate_heating_circuit_registers(circuit_id: int) -> dict[str, RegisterDef]:
    """
    Generate register definitions for a heating circuit.

    Args:
        circuit_id: Circuit number (1-5)

    Returns:
        Dictionary of register definitions for this circuit
    """
    if not 1 <= circuit_id <= 5:
        raise ValueError("circuit_id must be 1-5")

    input_base = 31000 + (circuit_id * 100)
    holding_base = 41000 + (circuit_id * 100)
    prefix = f"hk{circuit_id}_"

    return {
        # Input registers (31x01-31x05)
        f"{prefix}room_setpoint_effective": RegisterDef(
            name=f"{prefix}room_setpoint_effective",
            address=input_base + 1,
            reg_type=RegisterType.INPUT,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Raumsolltemperatur (effektiv)",
            unit="°C",
        ),
        f"{prefix}room_temp": RegisterDef(
            name=f"{prefix}room_temp",
            address=input_base + 2,
            reg_type=RegisterType.INPUT,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Raumtemperatur",
            unit="°C",
        ),
        f"{prefix}room_humidity": RegisterDef(
            name=f"{prefix}room_humidity",
            address=input_base + 3,
            reg_type=RegisterType.INPUT,
            fmt=DataFormat.PERCENTAGE,
            description=f"HK{circuit_id} Raumfeuchte",
            unit="%",
        ),
        f"{prefix}flow_setpoint": RegisterDef(
            name=f"{prefix}flow_setpoint",
            address=input_base + 4,
            reg_type=RegisterType.INPUT,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Vorlaufsolltemperatur",
            unit="°C",
        ),
        f"{prefix}flow_temp": RegisterDef(
            name=f"{prefix}flow_temp",
            address=input_base + 5,
            reg_type=RegisterType.INPUT,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Vorlauftemperatur",
            unit="°C",
        ),
        # Holding registers (41x01-41x12)
        f"{prefix}config": RegisterDef(
            name=f"{prefix}config",
            address=holding_base + 1,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.HEATING_CONFIG,
            description=f"HK{circuit_id} Konfiguration",
            writable=False,  # Read-only from commissioning
        ),
        f"{prefix}request_type": RegisterDef(
            name=f"{prefix}request_type",
            address=holding_base + 2,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.REQUEST_TYPE,
            description=f"HK{circuit_id} Anforderungstyp",
            writable=True,
            min_value=0,
            max_value=3,
        ),
        f"{prefix}mode": RegisterDef(
            name=f"{prefix}mode",
            address=holding_base + 3,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.HEATING_MODE,
            description=f"HK{circuit_id} Betriebsart",
            writable=True,
            min_value=0,
            max_value=4,
        ),
        f"{prefix}party_pause": RegisterDef(
            name=f"{prefix}party_pause",
            address=holding_base + 4,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.UNSIGNED_16,
            description=f"HK{circuit_id} Party/Pause",
            writable=True,
            min_value=1,
            max_value=48,
        ),
        f"{prefix}setpoint_comfort": RegisterDef(
            name=f"{prefix}setpoint_comfort",
            address=holding_base + 5,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Raumsolltemperatur Komfort",
            writable=True,
            min_value=150,  # 15.0°C
            max_value=300,  # 30.0°C
            unit="°C",
        ),
        f"{prefix}setpoint_normal": RegisterDef(
            name=f"{prefix}setpoint_normal",
            address=holding_base + 6,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Raumsolltemperatur Normal",
            writable=True,
            min_value=150,
            max_value=300,
            unit="°C",
        ),
        f"{prefix}setpoint_setback": RegisterDef(
            name=f"{prefix}setpoint_setback",
            address=holding_base + 7,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Raumsolltemperatur Absenk",
            writable=True,
            min_value=100,  # 10.0°C
            max_value=250,  # 25.0°C
            unit="°C",
        ),
        f"{prefix}heating_curve": RegisterDef(
            name=f"{prefix}heating_curve",
            address=holding_base + 8,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.UNSIGNED_16,
            description=f"HK{circuit_id} Heizkennlinie Steilheit",
            writable=True,
        ),
        f"{prefix}summer_winter_threshold": RegisterDef(
            name=f"{prefix}summer_winter_threshold",
            address=holding_base + 9,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.UNSIGNED_16,
            description=f"HK{circuit_id} Sommer/Winter Umschaltung",
            writable=True,
        ),
        f"{prefix}constant_temp_heating": RegisterDef(
            name=f"{prefix}constant_temp_heating",
            address=holding_base + 10,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Heizen Konstanttemperatur",
            writable=True,
            unit="°C",
        ),
        f"{prefix}constant_temp_heating_setback": RegisterDef(
            name=f"{prefix}constant_temp_heating_setback",
            address=holding_base + 11,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Heizen Konstanttemp Absenk",
            writable=True,
            unit="°C",
        ),
        f"{prefix}constant_temp_cooling": RegisterDef(
            name=f"{prefix}constant_temp_cooling",
            address=holding_base + 12,
            reg_type=RegisterType.HOLDING,
            fmt=DataFormat.TEMPERATURE,
            description=f"HK{circuit_id} Kühlen Konstanttemperatur",
            writable=True,
            unit="°C",
        ),
    }


# Pre-generate all heating circuit registers
HEATING_CIRCUIT_REGISTERS: dict[str, RegisterDef] = {}
for i in range(1, 6):
    HEATING_CIRCUIT_REGISTERS.update(generate_heating_circuit_registers(i))


# =============================================================================
# Hot Water Registers (32xxx / 42xxx)
# =============================================================================

HOT_WATER_REGISTERS: dict[str, RegisterDef] = {
    # Input registers (32xxx)
    "ww_setpoint_effective": RegisterDef(
        name="ww_setpoint_effective",
        address=32101,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Warmwasser-Solltemperatur effektiv",
        unit="°C",
    ),
    "ww_temp": RegisterDef(
        name="ww_temp",
        address=32102,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Warmwasser-Isttemperatur",
        unit="°C",
    ),
    # Holding registers (42xxx)
    "ww_config": RegisterDef(
        name="ww_config",
        address=42101,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.HOT_WATER_CONFIG,
        description="Warmwasser Konfiguration",
        writable=False,
    ),
    "ww_push_minutes": RegisterDef(
        name="ww_push_minutes",
        address=42102,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Warmwasser Push (0=Aus, 5-240 min)",
        writable=True,
        min_value=0,
        max_value=240,
        unit="min",
    ),
    "ww_normal": RegisterDef(
        name="ww_normal",
        address=42103,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="Warmwasser Normal-Solltemperatur",
        writable=True,
        min_value=300,  # 30.0°C
        max_value=650,  # 65.0°C
        unit="°C",
    ),
    "ww_setback": RegisterDef(
        name="ww_setback",
        address=42104,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="Warmwasser Absenk-Solltemperatur",
        writable=True,
        min_value=200,  # 20.0°C
        max_value=600,  # 60.0°C
        unit="°C",
    ),
    "ww_sg_ready_boost": RegisterDef(
        name="ww_sg_ready_boost",
        address=42105,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="SG Ready Anhebung (0-30K, -32768=Aus)",
        writable=True,
        unit="K",
    ),
}


# =============================================================================
# Heat Pump Registers (33xxx / 43xxx)
# =============================================================================

HEAT_PUMP_REGISTERS: dict[str, RegisterDef] = {
    # Input registers (33xxx)
    "wp_operating_state": RegisterDef(
        name="wp_operating_state",
        address=33101,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.OPERATING_STATE,
        description="Wärmepumpe Betrieb",
    ),
    "wp_error_free": RegisterDef(
        name="wp_error_free",
        address=33102,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Wärmepumpe störungsfrei",
    ),
    "wp_power_request": RegisterDef(
        name="wp_power_request",
        address=33103,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.PERCENTAGE,
        description="Leistungsanforderung",
        unit="%",
    ),
    "wp_flow_temp_b4": RegisterDef(
        name="wp_flow_temp_b4",
        address=33104,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Vorlauftemperatur B4",
        unit="°C",
    ),
    "wp_return_temp": RegisterDef(
        name="wp_return_temp",
        address=33105,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Rücklauftemperatur",
        unit="°C",
    ),
    "wp_evaporator_temp": RegisterDef(
        name="wp_evaporator_temp",
        address=33106,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Verdampfungstemperatur",
        unit="°C",
    ),
    "wp_suction_gas_temp": RegisterDef(
        name="wp_suction_gas_temp",
        address=33107,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Sauggastemperatur",
        unit="°C",
    ),
    "wp_separator_temp_b2": RegisterDef(
        name="wp_separator_temp_b2",
        address=33108,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Weichentemperatur B2",
        unit="°C",
    ),
    "wp_regenerative_flow_b21": RegisterDef(
        name="wp_regenerative_flow_b21",
        address=33109,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="VL-Regenerativ B2.1",
        unit="°C",
    ),
    "wp_buffer_temp_b11": RegisterDef(
        name="wp_buffer_temp_b11",
        address=33110,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Puffertemperatur B11",
        unit="°C",
    ),
    "wp_sum_flow_b7": RegisterDef(
        name="wp_sum_flow_b7",
        address=33111,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.TEMPERATURE,
        description="Summenvorlauf B7",
        unit="°C",
    ),
    # Holding registers (43xxx)
    "wp_config": RegisterDef(
        name="wp_config",
        address=43101,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.HEAT_PUMP_CONFIG,
        description="Konfiguration Wärmepumpe",
        writable=False,
    ),
    "wp_quiet_mode": RegisterDef(
        name="wp_quiet_mode",
        address=43102,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Ruhemodus (0=Aus)",
        writable=True,
    ),
    "wp_pump_start_mode": RegisterDef(
        name="wp_pump_start_mode",
        address=43103,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Pumpe Einschaltart",
        writable=True,
    ),
    "wp_pump_power_heating": RegisterDef(
        name="wp_pump_power_heating",
        address=43104,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.PERCENTAGE,
        description="Pumpe Leistung Heizen",
        writable=True,
        min_value=20,
        max_value=100,
        unit="%",
    ),
    "wp_pump_power_cooling": RegisterDef(
        name="wp_pump_power_cooling",
        address=43105,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.PERCENTAGE,
        description="Pumpe Leistung Kühlen",
        writable=True,
        min_value=20,
        max_value=100,
        unit="%",
    ),
    "wp_pump_power_hot_water": RegisterDef(
        name="wp_pump_power_hot_water",
        address=43106,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.PERCENTAGE,
        description="Pumpe Leistung Warmwasser",
        writable=True,
        min_value=20,
        max_value=100,
        unit="%",
    ),
    "wp_pump_power_defrost": RegisterDef(
        name="wp_pump_power_defrost",
        address=43107,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.PERCENTAGE,
        description="Pumpe Leistung Abtaubetrieb",
        writable=True,
        unit="%",
    ),
    "wp_flow_rate_heating": RegisterDef(
        name="wp_flow_rate_heating",
        address=43108,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Volumenstrom Heizen",
        writable=True,
        unit="m³/h",
    ),
    "wp_flow_rate_cooling": RegisterDef(
        name="wp_flow_rate_cooling",
        address=43109,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Volumenstrom Kühlen",
        writable=True,
        unit="m³/h",
    ),
    "wp_flow_rate_hot_water": RegisterDef(
        name="wp_flow_rate_hot_water",
        address=43110,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Volumenstrom Warmwasser",
        writable=True,
        unit="m³/h",
    ),
}


# =============================================================================
# Secondary Heat Source Registers (34xxx / 44xxx)
# =============================================================================

SECONDARY_HEAT_REGISTERS: dict[str, RegisterDef] = {
    # Input registers (34xxx)
    "wez2_status": RegisterDef(
        name="wez2_status",
        address=34101,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Status 2. WEZ",
    ),
    "wez2_operating_hours": RegisterDef(
        name="wez2_operating_hours",
        address=34102,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Betriebsstunden 2. WEZ",
        unit="h",
    ),
    "wez2_switching_cycles": RegisterDef(
        name="wez2_switching_cycles",
        address=34103,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Schaltspiele 2. WEZ",
    ),
    "e1_status": RegisterDef(
        name="e1_status",
        address=34104,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Status E-Heizung 1",
    ),
    "e2_status": RegisterDef(
        name="e2_status",
        address=34105,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Status E-Heizung 2",
    ),
    "e1_operating_hours": RegisterDef(
        name="e1_operating_hours",
        address=34106,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Betriebsstunden E1",
        unit="h",
    ),
    "e2_operating_hours": RegisterDef(
        name="e2_operating_hours",
        address=34107,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Betriebsstunden E2",
        unit="h",
    ),
    # Holding registers (44xxx)
    "wez2_config": RegisterDef(
        name="wez2_config",
        address=44101,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration 2. WEZ (255=Aus, 0=aktiv)",
        writable=True,
    ),
    "e1_config": RegisterDef(
        name="e1_config",
        address=44102,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration E1 (255=Aus, 5=aktiv)",
        writable=True,
    ),
    "e2_config": RegisterDef(
        name="e2_config",
        address=44103,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration E2 (255=Aus, 6=aktiv)",
        writable=True,
    ),
    "limit_temp": RegisterDef(
        name="limit_temp",
        address=44104,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="Grenztemperatur",
        writable=True,
        unit="°C",
    ),
    "bivalence_temp_heating": RegisterDef(
        name="bivalence_temp_heating",
        address=44105,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="Bivalenztemperatur Heizen",
        writable=True,
        unit="°C",
    ),
    "bivalence_temp_hot_water": RegisterDef(
        name="bivalence_temp_hot_water",
        address=44106,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.TEMPERATURE,
        description="Bivalenztemperatur Warmwasser",
        writable=True,
        unit="°C",
    ),
}


# =============================================================================
# Input / SG-Ready Registers (35xxx / 45xxx)
# =============================================================================

INPUTS_REGISTERS: dict[str, RegisterDef] = {
    # Input registers (35xxx) - Status
    "sgr1_status": RegisterDef(
        name="sgr1_status",
        address=35101,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="SG-Ready 1 Status",
    ),
    "sgr2_status": RegisterDef(
        name="sgr2_status",
        address=35102,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="SG-Ready 2 Status",
    ),
    "h12_status": RegisterDef(
        name="h12_status",
        address=35103,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang H1.2 Status",
    ),
    "h13_status": RegisterDef(
        name="h13_status",
        address=35104,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang H1.3 Status",
    ),
    "h14_status": RegisterDef(
        name="h14_status",
        address=35105,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang H1.4 Status",
    ),
    "h15_status": RegisterDef(
        name="h15_status",
        address=35106,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang H1.5 Status",
    ),
    "de1_status": RegisterDef(
        name="de1_status",
        address=35107,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang DE1 Status",
    ),
    "de2_status": RegisterDef(
        name="de2_status",
        address=35108,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.BOOL,
        description="Eingang DE2 Status",
    ),
    # Holding registers (45xxx) - Configuration
    "sgr1_config": RegisterDef(
        name="sgr1_config",
        address=45101,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration SGR1",
        writable=True,
    ),
    "sgr2_config": RegisterDef(
        name="sgr2_config",
        address=45102,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration SGR2",
        writable=True,
    ),
    "h12_config": RegisterDef(
        name="h12_config",
        address=45103,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration H1.2",
        writable=True,
    ),
    "h13_config": RegisterDef(
        name="h13_config",
        address=45104,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration H1.3",
        writable=True,
    ),
    "h14_config": RegisterDef(
        name="h14_config",
        address=45105,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration H1.4",
        writable=True,
    ),
    "h15_config": RegisterDef(
        name="h15_config",
        address=45106,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration H1.5",
        writable=True,
    ),
    "de1_config": RegisterDef(
        name="de1_config",
        address=45107,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration DE1",
        writable=True,
    ),
    "de2_config": RegisterDef(
        name="de2_config",
        address=45108,
        reg_type=RegisterType.HOLDING,
        fmt=DataFormat.UNSIGNED_16,
        description="Konfiguration DE2",
        writable=True,
    ),
}


# =============================================================================
# Energy Statistics Registers (36xxx)
# =============================================================================

ENERGY_REGISTERS: dict[str, RegisterDef] = {
    # Total energy
    "energy_total_today": RegisterDef(
        name="energy_total_today",
        address=36101,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Gesamt Energie heute",
        unit="kWh",
    ),
    "energy_total_yesterday": RegisterDef(
        name="energy_total_yesterday",
        address=36102,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Gesamt Energie gestern",
        unit="kWh",
    ),
    "energy_total_month": RegisterDef(
        name="energy_total_month",
        address=36103,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Gesamt Energie Monat",
        unit="kWh",
    ),
    "energy_total_year": RegisterDef(
        name="energy_total_year",
        address=36104,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Gesamt Energie Jahr",
        unit="kWh",
    ),
    # Heating energy
    "energy_heating_today": RegisterDef(
        name="energy_heating_today",
        address=36201,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Heizen Energie heute",
        unit="kWh",
    ),
    "energy_heating_yesterday": RegisterDef(
        name="energy_heating_yesterday",
        address=36202,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Heizen Energie gestern",
        unit="kWh",
    ),
    "energy_heating_month": RegisterDef(
        name="energy_heating_month",
        address=36203,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Heizen Energie Monat",
        unit="kWh",
    ),
    "energy_heating_year": RegisterDef(
        name="energy_heating_year",
        address=36204,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Heizen Energie Jahr",
        unit="kWh",
    ),
    # Hot water energy
    "energy_hot_water_today": RegisterDef(
        name="energy_hot_water_today",
        address=36301,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Warmwasser Energie heute",
        unit="kWh",
    ),
    "energy_hot_water_yesterday": RegisterDef(
        name="energy_hot_water_yesterday",
        address=36302,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Warmwasser Energie gestern",
        unit="kWh",
    ),
    "energy_hot_water_month": RegisterDef(
        name="energy_hot_water_month",
        address=36303,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Warmwasser Energie Monat",
        unit="kWh",
    ),
    "energy_hot_water_year": RegisterDef(
        name="energy_hot_water_year",
        address=36304,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Warmwasser Energie Jahr",
        unit="kWh",
    ),
    # Cooling energy
    "energy_cooling_today": RegisterDef(
        name="energy_cooling_today",
        address=36401,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Kühlen Energie heute",
        unit="kWh",
    ),
    "energy_cooling_yesterday": RegisterDef(
        name="energy_cooling_yesterday",
        address=36402,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Kühlen Energie gestern",
        unit="kWh",
    ),
    "energy_cooling_month": RegisterDef(
        name="energy_cooling_month",
        address=36403,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Kühlen Energie Monat",
        unit="kWh",
    ),
    "energy_cooling_year": RegisterDef(
        name="energy_cooling_year",
        address=36404,
        reg_type=RegisterType.INPUT,
        fmt=DataFormat.UNSIGNED_16,
        description="Kühlen Energie Jahr",
        unit="kWh",
    ),
}


# =============================================================================
# Complete Register Catalog
# =============================================================================

ALL_REGISTERS: dict[str, RegisterDef] = {}
ALL_REGISTERS.update(SYSTEM_REGISTERS)
ALL_REGISTERS.update(HEATING_CIRCUIT_REGISTERS)
ALL_REGISTERS.update(HOT_WATER_REGISTERS)
ALL_REGISTERS.update(HEAT_PUMP_REGISTERS)
ALL_REGISTERS.update(SECONDARY_HEAT_REGISTERS)
ALL_REGISTERS.update(INPUTS_REGISTERS)
ALL_REGISTERS.update(ENERGY_REGISTERS)
