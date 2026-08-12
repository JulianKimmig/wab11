"""
WAB11 Digital Twin Client.

The main client class that provides a synchronized view of the
WAB11 heat pump controller state with safe, validated control methods.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from .connection import ConnectionConfig, WAB11Connection
from .exceptions import ModbusResponseError, ValidationError
from .models.base import (
    HeatingCircuitConfig,
    HeatingCircuitMode,
    HeatPumpConfig,
    HotWaterConfig,
    OperatingState,
    RequestType,
    SystemMode,
    Temperature,
    decode_signed_16,
)
from .models.energy import EnergyStatistics
from .models.heat_pump import HeatPumpState
from .models.heating import HeatingCircuit, PartyPauseCode
from .models.hot_water import HotWaterState
from .models.inputs import InputsState
from .models.secondary_heat import SecondaryHeatSourceState
from .models.system import SystemState
from .registers.definitions import ALL_REGISTERS, RegisterType
from .registers.formats import FormatCodec
from .security.audit import AuditLog
from .security.rate_limiter import RateLimiter
from .security.validator import WriteValidator

logger = logging.getLogger(__name__)


def _decode_temperature(raw: int) -> Temperature:
    """Decode a raw 16-bit Modbus register into a Temperature."""
    return Temperature(decode_signed_16(raw))


@dataclass
class StateChangeEvent:
    """
    Event fired when state changes.

    Attributes:
        timestamp: When the change was detected
        source: Origin of change ("device" or "local")
        register: Name of the changed register
        old_value: Previous value
        new_value: New value
    """

    timestamp: datetime
    source: str  # "device" or "local"
    register: str
    old_value: Any
    new_value: Any


class WAB11Client:
    """
    Digital twin of the WAB11 heat pump controller.

    This class maintains a synchronized view of the heat pump's state
    and provides safe, validated methods to control it.

    Features:
        - Automatic state synchronization via polling
        - Type-safe property access for all values
        - Validated, rate-limited write operations
        - Event system for state changes
        - Full audit logging

    Usage:
        async with WAB11Client("192.168.1.100") as wab:
            # Start polling (updates state automatically)
            await wab.start_polling(interval=5.0)

            # Read current state
            print(f"Outdoor temp: {wab.system.outdoor_temp}°C")
            print(f"Mode: {wab.system.system_mode.name}")

            # Set values
            await wab.set_system_mode(SystemMode.HEATING, confirmed=True)
            await wab.set_heating_circuit_setpoint(1, "comfort", 21.5)

            # Subscribe to changes
            wab.on_change(lambda e: print(f"{e.register}: {e.new_value}"))
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        *,
        require_write_confirmation: bool = True,
        enable_rate_limiting: bool = True,
        timeout: float = 3.0,
        n_heating_circuits: int | None = None,
    ) -> None:
        """
        Initialize WAB11 client.

        Args:
            host: IP address of the WAB11 controller
            port: Modbus TCP port (default: 502)
            unit_id: Modbus unit/slave ID (default: 1)
            require_write_confirmation: Require explicit confirmation for critical writes
            enable_rate_limiting: Enable write rate limiting
            timeout: Connection timeout in seconds
            n_heating_circuits: Explicit number of heating circuits, or None to
                auto-detect sequential circuit blocks during the first sync.
        """
        if n_heating_circuits is not None and not 1 <= n_heating_circuits <= 5:
            raise ValidationError("n_heating_circuits must be 1-5")

        self._config = ConnectionConfig(
            host=host,
            port=port,
            unit_id=unit_id,
            timeout=timeout,
        )
        self._connection = WAB11Connection(self._config)

        # Security components
        self._validator = WriteValidator(
            require_confirmation=require_write_confirmation
        )
        self._rate_limiter = RateLimiter() if enable_rate_limiting else None
        self._audit = AuditLog()

        # State containers
        self._system = SystemState()
        self._configured_heating_circuit_count = n_heating_circuits
        self._heating_circuits: list[HeatingCircuit] = []
        if n_heating_circuits is not None:
            self._heating_circuits = [
                HeatingCircuit(circuit_id=i) for i in range(1, n_heating_circuits + 1)
            ]
        self._hot_water = HotWaterState()
        self._heat_pump = HeatPumpState()
        self._secondary_heat = SecondaryHeatSourceState()
        self._inputs = InputsState()
        self._energy = EnergyStatistics()

        # State tracking
        self._last_sync: Optional[datetime] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._change_callbacks: list[Callable[[StateChangeEvent], None]] = []

        # Internal state cache for change detection
        self._state_cache: dict[str, Any] = {}

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connection to the WAB11."""
        await self._connection.connect()

    async def disconnect(self) -> None:
        """Disconnect from the WAB11."""
        await self.stop_polling()
        await self._connection.disconnect()

    async def __aenter__(self) -> "WAB11Client":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if connected to WAB11."""
        return self._connection.is_connected

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._config.host

    def _get_heating_circuit(self, circuit: int) -> HeatingCircuit:
        """Return a configured heating circuit or raise ValidationError."""
        max_circuit = len(self._heating_circuits)
        if not 1 <= circuit <= max_circuit:
            raise ValidationError(f"Circuit must be 1-{max_circuit}")
        return self._heating_circuits[circuit - 1]

    # =========================================================================
    # State Properties (Read-Only Views)
    # =========================================================================

    @property
    def system(self) -> SystemState:
        """Global system state."""
        return self._system

    @property
    def heating_circuits(self) -> list[HeatingCircuit]:
        """Heating circuits HK1-HK5."""
        return self._heating_circuits

    @property
    def hot_water(self) -> HotWaterState:
        """Hot water (Warmwasser) state."""
        return self._hot_water

    @property
    def heat_pump(self) -> HeatPumpState:
        """Heat pump state."""
        return self._heat_pump

    @property
    def secondary_heat(self) -> SecondaryHeatSourceState:
        """Secondary heat source and electric heaters."""
        return self._secondary_heat

    @property
    def inputs(self) -> InputsState:
        """Digital inputs and SG-Ready state."""
        return self._inputs

    @property
    def energy(self) -> EnergyStatistics:
        """Energy statistics."""
        return self._energy

    @property
    def last_sync(self) -> Optional[datetime]:
        """Timestamp of last successful state sync."""
        return self._last_sync

    @property
    def audit_log(self) -> AuditLog:
        """Access to audit log."""
        return self._audit

    # =========================================================================
    # Polling / State Synchronization
    # =========================================================================

    async def sync(self) -> None:
        """
        Perform a full state synchronization with the WAB11.

        Reads all relevant registers and updates local state.
        Fires change events for any values that changed.
        """
        await self._sync_system_registers()
        await self._sync_heating_circuits()
        await self._sync_hot_water()
        await self._sync_heat_pump()
        await self._sync_inputs()
        await self._sync_secondary_heat()

        self._last_sync = datetime.now()
        self._system.last_updated = self._last_sync

    async def sync_energy(self) -> None:
        """Sync energy statistics (less frequently needed)."""
        await self._sync_energy_registers()

    async def start_polling(
        self,
        interval: float = 5.0,
        energy_interval: float = 300.0,
    ) -> None:
        """
        Start background polling for state updates.

        Args:
            interval: Seconds between state syncs
            energy_interval: Seconds between energy stats syncs
        """
        if self._polling_task is not None:
            return

        async def poll_loop():
            last_energy_sync = 0.0
            while True:
                try:
                    await self.sync()

                    # Sync energy less frequently
                    now = datetime.now().timestamp()
                    if (now - last_energy_sync) >= energy_interval:
                        await self.sync_energy()
                        last_energy_sync = now

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Polling error: {e}")

                await asyncio.sleep(interval)

        self._polling_task = asyncio.create_task(poll_loop())
        logger.info(f"Started polling with interval={interval}s")

    async def stop_polling(self) -> None:
        """Stop background polling."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
            logger.info("Stopped polling")

    @property
    def is_polling(self) -> bool:
        """Check if polling is active."""
        return self._polling_task is not None and not self._polling_task.done()

    # =========================================================================
    # Change Events
    # =========================================================================

    def on_change(self, callback: Callable[[StateChangeEvent], None]) -> None:
        """
        Register a callback for state changes.

        The callback receives a StateChangeEvent when any monitored
        value changes (either from device polling or local writes).

        Args:
            callback: Function to call on state changes
        """
        self._change_callbacks.append(callback)

    def remove_change_callback(
        self, callback: Callable[[StateChangeEvent], None]
    ) -> bool:
        """
        Remove a change callback.

        Args:
            callback: The callback to remove

        Returns:
            True if callback was found and removed
        """
        try:
            self._change_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    def _emit_change(
        self,
        register: str,
        old_value: Any,
        new_value: Any,
        source: str = "device",
    ) -> None:
        """Emit a change event to all registered callbacks."""
        if old_value == new_value:
            return

        event = StateChangeEvent(
            timestamp=datetime.now(),
            source=source,
            register=register,
            old_value=old_value,
            new_value=new_value,
        )

        for callback in self._change_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Change callback error: {e}")

    # =========================================================================
    # Write Operations (Validated & Rate-Limited)
    # =========================================================================

    async def _write_register(
        self,
        register_name: str,
        value: Any,
        confirmed: bool = False,
    ) -> None:
        """
        Internal method to write a register with full validation.
        """
        # Get current value for audit
        old_value = self._state_cache.get(register_name)

        try:
            # Validate
            raw_value, reg_def = self._validator.validate_write(
                register_name, value, confirmed
            )

            # Rate limit
            if self._rate_limiter:
                await self._rate_limiter.acquire(register_name)

            # Write
            await self._connection.write_register(reg_def.address, raw_value)

            # Update cache
            self._state_cache[register_name] = value

            # Log success
            self._audit.log_write(
                register=register_name,
                old_value=old_value,
                new_value=value,
                success=True,
            )

            # Emit change
            self._emit_change(register_name, old_value, value, source="local")

            logger.debug(f"Wrote {register_name} = {value} (raw={raw_value})")

        except Exception as e:
            self._audit.log_write(
                register=register_name,
                old_value=old_value,
                new_value=value,
                success=False,
                error=str(e),
            )
            raise

    # =========================================================================
    # High-Level Control Methods
    # =========================================================================

    async def set_system_mode(
        self,
        mode: SystemMode,
        confirmed: bool = False,
    ) -> None:
        """
        Set the system operating mode.

        Args:
            mode: Target mode (AUTOMATIC, HEATING, COOLING, SUMMER, STANDBY, SECOND_HEAT)
            confirmed: Confirm this critical operation

        Raises:
            SafetyError: If not confirmed
            ValidationError: If mode invalid for current config
        """
        await self._write_register("system_mode", mode, confirmed=confirmed)
        self._system.system_mode = mode

    async def set_heating_circuit_mode(
        self,
        circuit: int,
        mode: HeatingCircuitMode,
    ) -> None:
        """
        Set the operating mode for a heating circuit.

        Args:
            circuit: Circuit number (1-5)
            mode: Target mode (AUTOMATIC, COMFORT, NORMAL, SETBACK, STANDBY)

        Raises:
            ValidationError: If circuit or mode invalid
        """
        hk = self._get_heating_circuit(circuit)

        register_name = f"hk{circuit}_mode"
        await self._write_register(register_name, mode)
        hk.mode = mode

    async def set_heating_circuit_setpoint(
        self,
        circuit: int,
        level: str,
        temperature: float,
    ) -> None:
        """
        Set a temperature setpoint for a heating circuit.

        Args:
            circuit: Circuit number (1-5)
            level: Setpoint level ("comfort", "normal", "setback")
            temperature: Temperature in °C

        Raises:
            ValidationError: If parameters invalid
        """
        hk = self._get_heating_circuit(circuit)
        if level not in ("comfort", "normal", "setback"):
            raise ValidationError("Level must be 'comfort', 'normal', or 'setback'")

        register_name = f"hk{circuit}_setpoint_{level}"
        await self._write_register(register_name, temperature)

        # Update local state
        temp = Temperature.from_celsius(temperature)
        if level == "comfort":
            hk.setpoint_comfort = temp
        elif level == "normal":
            hk.setpoint_normal = temp
        else:
            hk.setpoint_setback = temp

    async def set_heating_party_pause(
        self,
        circuit: int,
        mode: str,
        hours: float = 2.0,
    ) -> None:
        """
        Set party/pause mode for a heating circuit.

        Args:
            circuit: Circuit number (1-5)
            mode: "party", "pause", or "auto"
            hours: Duration in hours (0.5-12, ignored for "auto")

        Raises:
            ValidationError: If parameters invalid
        """
        hk = self._get_heating_circuit(circuit)

        if mode == "auto":
            value = PartyPauseCode.AUTOMATIC
        elif mode == "party":
            value = PartyPauseCode.party_hours(hours)
        elif mode == "pause":
            value = PartyPauseCode.pause_hours(hours)
        else:
            raise ValidationError("Mode must be 'party', 'pause', or 'auto'")

        register_name = f"hk{circuit}_party_pause"
        await self._write_register(register_name, value)
        hk.party_pause = value

    async def set_hot_water_setpoint(
        self,
        level: str,
        temperature: float,
    ) -> None:
        """
        Set hot water temperature setpoint.

        Args:
            level: "normal" or "setback"
            temperature: Temperature in °C

        Raises:
            ValidationError: If parameters invalid
        """
        if level not in ("normal", "setback"):
            raise ValidationError("Level must be 'normal' or 'setback'")

        register_name = f"ww_{level}"
        await self._write_register(register_name, temperature)

        temp = Temperature.from_celsius(temperature)
        if level == "normal":
            self._hot_water.setpoint_normal = temp
        else:
            self._hot_water.setpoint_setback = temp

    async def trigger_hot_water_push(self, minutes: int = 30) -> None:
        """
        Trigger a hot water push (boost).

        Args:
            minutes: Push duration (0=off, 5-240)

        Raises:
            ValidationError: If minutes out of range
        """
        if minutes != 0 and not 5 <= minutes <= 240:
            raise ValidationError("Push minutes must be 0 (off) or 5-240")

        await self._write_register("ww_push_minutes", minutes)
        self._hot_water.push_minutes = minutes

    async def cancel_hot_water_push(self) -> None:
        """Cancel any active hot water push."""
        await self.trigger_hot_water_push(0)

    # =========================================================================
    # Generic Read/Write (for advanced use)
    # =========================================================================

    async def read_register(self, register_name: str) -> Any:
        """
        Read a single register by name.

        Args:
            register_name: Name of the register to read

        Returns:
            Decoded Python value

        Raises:
            ValidationError: If register not found
        """
        if register_name not in ALL_REGISTERS:
            raise ValidationError(f"Unknown register: {register_name}")

        reg = ALL_REGISTERS[register_name]

        if reg.reg_type == RegisterType.INPUT:
            raw_values = await self._connection.read_input_registers(reg.address, 1)
        else:
            raw_values = await self._connection.read_holding_registers(reg.address, 1)

        return FormatCodec.decode(reg.fmt, raw_values[0])

    async def write_register(
        self,
        register_name: str,
        value: Any,
        confirmed: bool = False,
    ) -> None:
        """
        Write a single register by name.

        This is a lower-level method; prefer the high-level set_* methods.

        Args:
            register_name: Name of the register
            value: Value to write
            confirmed: Confirm critical operations
        """
        await self._write_register(register_name, value, confirmed)

    # =========================================================================
    # Internal Sync Methods
    # =========================================================================

    async def _sync_system_registers(self) -> None:
        """Sync global system registers."""
        # Read input registers 30001-30006
        input_values = await self._connection.read_input_registers(30001, 6)

        # Read holding registers 40001-40002
        holding_values = await self._connection.read_holding_registers(40001, 2)

        # Update state with change detection
        self._update_cached_state(
            "outdoor_temp_1", _decode_temperature(input_values[0])
        )
        self._update_cached_state(
            "outdoor_temp_2", _decode_temperature(input_values[1])
        )
        self._update_cached_state("error_code", input_values[2])
        self._update_cached_state("warning_code", input_values[3])
        self._update_cached_state("ok_flag", bool(input_values[4]))
        self._update_cached_state("operating_state", input_values[5])
        self._update_cached_state("system_mode", holding_values[0])
        self._update_cached_state("power_request", holding_values[1])

        # Apply to model
        self._system.outdoor_temp_1 = _decode_temperature(input_values[0])
        self._system.outdoor_temp_2 = _decode_temperature(input_values[1])
        self._system.error_code = input_values[2]
        self._system.warning_code = input_values[3]
        self._system.is_error_free = bool(input_values[4])

        try:
            self._system.operating_state = OperatingState(input_values[5])
        except ValueError:
            pass  # Unknown state, keep previous

        try:
            self._system.system_mode = SystemMode(holding_values[0])
        except ValueError:
            pass

        self._system.power_request_watts = holding_values[1]

    async def _sync_heating_circuits(self) -> None:
        """Sync all heating circuits."""
        if self._configured_heating_circuit_count is None:
            await self._auto_detect_heating_circuits()
            return

        for i, hk in enumerate(self._heating_circuits, start=1):
            await self._sync_heating_circuit(i, hk)

    async def _auto_detect_heating_circuits(self) -> None:
        """Discover and sync sequential heating-circuit register blocks."""
        detected: list[HeatingCircuit] = []
        for circuit_id in range(1, 6):
            circuit = HeatingCircuit(circuit_id=circuit_id)
            try:
                await self._sync_heating_circuit(circuit_id, circuit)
            except ModbusResponseError as error:
                if circuit_id > 1 and error.exception_code == 10:
                    break
                raise
            detected.append(circuit)

        self._heating_circuits = detected
        self._configured_heating_circuit_count = len(detected)

    async def _sync_heating_circuit(self, circuit_id: int, hk: HeatingCircuit) -> None:
        """Sync a single heating circuit."""
        input_base = 31000 + (circuit_id * 100)
        holding_base = 41000 + (circuit_id * 100)

        # Read 5 input registers
        input_values = await self._connection.read_input_registers(input_base + 1, 5)

        # Read key holding registers
        holding_values = await self._connection.read_holding_registers(
            holding_base + 1, 12
        )

        # Check if configured
        try:
            config = HeatingCircuitConfig(holding_values[0])
        except ValueError:
            config = HeatingCircuitConfig.NOT_CONFIGURED

        hk.config = config

        if config == HeatingCircuitConfig.NOT_CONFIGURED:
            return

        # Input registers
        hk.room_setpoint_effective = _decode_temperature(input_values[0])
        hk.room_temp = _decode_temperature(input_values[1])
        hk.room_humidity = input_values[2] if input_values[2] != 0xFFFF else None
        hk.flow_setpoint = _decode_temperature(input_values[3])
        hk.flow_temp = _decode_temperature(input_values[4])

        # Holding registers
        try:
            hk.request_type = RequestType(holding_values[1])
        except ValueError:
            pass

        try:
            hk.mode = HeatingCircuitMode(holding_values[2])
        except ValueError:
            pass

        hk.party_pause = holding_values[3]
        hk.setpoint_comfort = _decode_temperature(holding_values[4])
        hk.setpoint_normal = _decode_temperature(holding_values[5])
        hk.setpoint_setback = _decode_temperature(holding_values[6])
        hk.heating_curve_slope = holding_values[7]
        hk.summer_winter_threshold = holding_values[8]
        hk.constant_temp_heating = _decode_temperature(holding_values[9])
        hk.constant_temp_heating_setback = _decode_temperature(holding_values[10])
        hk.constant_temp_cooling = _decode_temperature(holding_values[11])

    async def _sync_hot_water(self) -> None:
        """Sync hot water state."""
        input_values = await self._connection.read_input_registers(32101, 2)
        holding_values = await self._connection.read_holding_registers(42101, 5)

        self._hot_water.setpoint_effective = _decode_temperature(input_values[0])
        self._hot_water.temperature = _decode_temperature(input_values[1])

        try:
            self._hot_water.config = HotWaterConfig(holding_values[0])
        except ValueError:
            pass

        self._hot_water.push_minutes = holding_values[1]
        self._hot_water.setpoint_normal = _decode_temperature(holding_values[2])
        self._hot_water.setpoint_setback = _decode_temperature(holding_values[3])
        self._hot_water.sg_ready_boost = _decode_temperature(holding_values[4])

    async def _sync_heat_pump(self) -> None:
        """Sync heat pump state."""
        # Read input registers 33101-33111 (11 registers)
        input_values = await self._connection.read_input_registers(33101, 11)

        # Read holding registers 43101-43110 (10 registers)
        holding_values = await self._connection.read_holding_registers(43101, 10)

        # Input registers
        try:
            self._heat_pump.operating_state = OperatingState(input_values[0])
        except ValueError:
            pass

        self._heat_pump.is_error_free = bool(input_values[1])
        self._heat_pump.power_request_percent = input_values[2]
        self._heat_pump.flow_temp_b4 = _decode_temperature(input_values[3])
        self._heat_pump.return_temp = _decode_temperature(input_values[4])
        self._heat_pump.evaporator_temp = _decode_temperature(input_values[5])
        self._heat_pump.suction_gas_temp = _decode_temperature(input_values[6])
        self._heat_pump.separator_temp_b2 = _decode_temperature(input_values[7])
        self._heat_pump.regenerative_flow_b21 = _decode_temperature(input_values[8])
        self._heat_pump.buffer_temp_b11 = _decode_temperature(input_values[9])
        self._heat_pump.sum_flow_b7 = _decode_temperature(input_values[10])

        # Holding registers
        try:
            self._heat_pump.config = HeatPumpConfig(holding_values[0])
        except ValueError:
            pass

        self._heat_pump.quiet_mode = holding_values[1]
        self._heat_pump.pump_start_mode = holding_values[2]
        self._heat_pump.pump_power_heating = holding_values[3]
        self._heat_pump.pump_power_cooling = holding_values[4]
        self._heat_pump.pump_power_hot_water = holding_values[5]
        self._heat_pump.pump_power_defrost = holding_values[6]
        self._heat_pump.flow_rate_heating = holding_values[7]
        self._heat_pump.flow_rate_cooling = holding_values[8]
        self._heat_pump.flow_rate_hot_water = holding_values[9]

    async def _sync_secondary_heat(self) -> None:
        """Sync secondary heat source state."""
        input_values = await self._connection.read_input_registers(34101, 7)
        holding_values = await self._connection.read_holding_registers(44101, 6)

        self._secondary_heat.status_wez2 = input_values[0]
        self._secondary_heat.operating_hours_wez2 = input_values[1]
        self._secondary_heat.switching_cycles_wez2 = input_values[2]
        self._secondary_heat.status_e1 = bool(input_values[3])
        self._secondary_heat.status_e2 = bool(input_values[4])
        self._secondary_heat.operating_hours_e1 = input_values[5]
        self._secondary_heat.operating_hours_e2 = input_values[6]

        self._secondary_heat.config_wez2 = holding_values[0]
        self._secondary_heat.config_e1 = holding_values[1]
        self._secondary_heat.config_e2 = holding_values[2]
        self._secondary_heat.limit_temp = _decode_temperature(holding_values[3])
        self._secondary_heat.bivalence_temp_heating = _decode_temperature(
            holding_values[4]
        )
        self._secondary_heat.bivalence_temp_hot_water = _decode_temperature(
            holding_values[5]
        )

    async def _sync_inputs(self) -> None:
        """Sync digital inputs and SG-Ready state."""
        input_values = await self._connection.read_input_registers(35101, 8)

        self._inputs.sg_ready_1 = bool(input_values[0])
        self._inputs.sg_ready_2 = bool(input_values[1])
        self._inputs.input_h12 = bool(input_values[2])
        self._inputs.input_h13 = bool(input_values[3])
        self._inputs.input_h14 = bool(input_values[4])
        self._inputs.input_h15 = bool(input_values[5])
        self._inputs.input_de1 = bool(input_values[6])
        self._inputs.input_de2 = bool(input_values[7])

    async def _sync_energy_registers(self) -> None:
        """Sync energy statistics."""
        # Total energy (36101-36104)
        total = await self._connection.read_input_registers(36101, 4)
        self._energy.total.today = float(total[0])
        self._energy.total.yesterday = float(total[1])
        self._energy.total.month = float(total[2])
        self._energy.total.year = float(total[3])

        # Heating energy (36201-36204)
        heating = await self._connection.read_input_registers(36201, 4)
        self._energy.heating.today = float(heating[0])
        self._energy.heating.yesterday = float(heating[1])
        self._energy.heating.month = float(heating[2])
        self._energy.heating.year = float(heating[3])

        # Hot water energy (36301-36304)
        hw = await self._connection.read_input_registers(36301, 4)
        self._energy.hot_water.today = float(hw[0])
        self._energy.hot_water.yesterday = float(hw[1])
        self._energy.hot_water.month = float(hw[2])
        self._energy.hot_water.year = float(hw[3])

        # Cooling energy (36401-36404)
        cooling = await self._connection.read_input_registers(36401, 4)
        self._energy.cooling.today = float(cooling[0])
        self._energy.cooling.yesterday = float(cooling[1])
        self._energy.cooling.month = float(cooling[2])
        self._energy.cooling.year = float(cooling[3])

    def _update_cached_state(self, key: str, new_value: Any) -> None:
        """Update cached state with change detection."""
        old_value = self._state_cache.get(key)

        # Handle Temperature comparison
        if isinstance(new_value, Temperature) and isinstance(old_value, Temperature):
            if new_value.raw != old_value.raw:
                self._state_cache[key] = new_value
                self._emit_change(key, old_value, new_value, source="device")
        elif old_value != new_value:
            self._state_cache[key] = new_value
            self._emit_change(key, old_value, new_value, source="device")

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        polling = ", polling" if self.is_polling else ""
        return f"WAB11Client({self.host}, {status}{polling})"
