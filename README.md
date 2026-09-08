# WAB11 Python Library

A Python library for controlling Weishaupt WAB11 heat pump controllers via Modbus TCP.

## Features

- **Digital Twin Pattern**: Maintains a synchronized local representation of the heat pump state
- **Type-Safe Models**: Pydantic-based models for all WAB11 components
- **Secure by Default**: Validated writes, rate limiting, and confirmation for critical operations
- **Async & Sync Support**: Both asyncio-based and synchronous interfaces
- **Event System**: Subscribe to state changes with callbacks
- **Comprehensive Audit Log**: Full trail of all operations

## Installation

```bash
pip install wab11
```

Or install from source:

```bash
git clone https://github.com/your-repo/wab11.git
cd wab11
pip install -e .
```

## Requirements

- Python 3.10+
- pymodbus >= 3.5
- pydantic >= 2.0

## Quick Start

### Async Usage

```python
import asyncio
from wab11 import WAB11Client, SystemMode

async def main():
    async with WAB11Client("192.168.1.100") as wab:
        # Sync state from device
        await wab.sync()

        # Read values
        print(f"Outdoor temperature: {wab.system.outdoor_temp}°C")
        print(f"System mode: {wab.system.system_mode.name}")
        print(f"Operating state: {wab.system.operating_state.name}")

        # Check for errors
        if wab.system.has_error:
            print(f"⚠️ Error code: {wab.system.error_code}")

        # Heating circuit info
        for i, hk in enumerate(wab.heating_circuits, 1):
            if hk.is_configured:
                print(f"HK{i}: {hk.room_temp.celsius}°C → {hk.room_setpoint_effective.celsius}°C")

        # Hot water
        print(f"Hot water: {wab.hot_water.temperature.celsius}°C")

asyncio.run(main())
```

### Sync Usage

```python
from wab11 import WAB11SyncClient, SystemMode

with WAB11SyncClient("192.168.1.100") as wab:
    wab.sync()
    print(f"Outdoor: {wab.system.outdoor_temp}°C")
    print(f"Mode: {wab.system.system_mode.name}")
```

## Setting Values

```python
async with WAB11Client("192.168.1.100") as wab:
    # Change system mode (requires confirmation for safety)
    await wab.set_system_mode(SystemMode.HEATING, confirmed=True)

    # Set heating circuit setpoint
    await wab.set_heating_circuit_setpoint(
        circuit=1,
        level="comfort",  # "comfort", "normal", or "setback"
        temperature=22.0
    )

    # Activate party mode for 3 hours
    await wab.set_heating_party_pause(circuit=1, mode="party", hours=3.0)

    # Hot water boost
    await wab.trigger_hot_water_push(minutes=30)
```

## Continuous Monitoring

```python
async with WAB11Client("192.168.1.100") as wab:
    # Subscribe to changes
    def on_change(event):
        print(f"{event.register}: {event.old_value} → {event.new_value}")

    wab.on_change(on_change)

    # Start background polling
    await wab.start_polling(interval=5.0)

    # Keep running
    await asyncio.sleep(3600)
```

## Energy Statistics

Call `sync_energy()` to read energy statistics; normal `sync()` alone does not
populate them. Background polling uses `energy_interval=300` seconds by
default. Both asynchronous and synchronous clients expose `energy.electrical`.
With an asynchronous client:

```python
await client.sync_energy()

period = client.energy.electrical
if period is None:
    print("Electrical energy unavailable")
else:
    print(f"Electrical energy today: {period.today} kWh")
    print(f"Electrical energy yesterday: {period.yesterday} kWh")
```

For a synchronous client, call `client.sync_energy()` without `await` and use
the same availability check.

The legacy `total`, `heating`, `hot_water`, and `cooling` groups and their
aliases remain unchanged. Available evidence indicates they describe thermal
energy generated. The separate electrical group has `today`, `yesterday`,
`month`, and `year` periods from optional input registers 36701–36704.
All 20 energy definitions are read-only; four are optional at runtime.

`electrical` defaults to `None`, and becomes unavailable again if an energy
synchronization fails. Illegal Data Address (Modbus exception 2) on the
optional block leaves legacy data usable; other communication errors still
propagate. The block is retried on subsequent energy synchronizations.
Successful zero readings are valid, not missing data. Consumers must also
track connection/polling freshness. Generic named reads such as
`read_register("energy_electrical_today")` expose the same registers but
propagate ordinary errors, including exception 2, without updating the model.

Source resolution is integer kWh: raw `2` becomes `2.0 kWh`, without decimal
scaling. Periods overlap and must not be summed together. Calendar resets are
expected; exact firmware rollover and overflow behavior remains unverified.
These values are not instantaneous power or automatic COP. Neither request
register 33103 (%) nor writable request/setpoint register 40002 (W) measures
electrical input power.

The electrical mapping is empirical: a WBB investigation reports it and a WAB
probe confirms accessibility on one installation. It is not documented in the
inspected manufacturer Modbus list. Exact model/firmware, display matching,
included electrical loads, and rollovers need device-specific validation.
See the [energy statistics contract](.docs/contracts/energy-statistics.md)
for sources, compatibility limits, and error semantics, and the
[variable reference](docs/variables-reference.md#energy-statistics) for keys.

Reports add `energy.electrical` as four numeric fields or JSON `null`; text
reports show unavailable data explicitly and CSV leaves those values empty.
Consumers with strict serialized schemas must accept the additive field.
Start a new CSV file when upgrading an existing report with the old columns;
appending to a mismatched header raises an error before modifying the file.
Home Assistant entities and InfluxDB deployment require a separate update.

## Security

The library implements several security measures:

### Write Validation

All writes are validated against documented limits:

```python
# This will raise ValidationError
await wab.set_heating_circuit_setpoint(1, "comfort", 50.0)  # Too high!
```

### Critical Operation Confirmation

Safety-critical operations require explicit confirmation:

```python
# This raises SafetyError
await wab.set_system_mode(SystemMode.STANDBY)

# This works
await wab.set_system_mode(SystemMode.STANDBY, confirmed=True)
```

### Rate Limiting

Write operations are rate-limited to protect the controller:

- Max 10 writes per minute globally
- Max 2 writes per register per minute
- 1 second cooldown between same-register writes

### Audit Logging

All operations are logged:

```python
# Get recent write operations
for entry in wab.audit_log.get_writes():
    print(f"{entry.timestamp}: {entry.register} = {entry.new_value}")
```

## Network Security Warning

⚠️ **Important**: The Modbus TCP interface is unencrypted. As per Weishaupt documentation, the controller should only be accessible on an isolated network segment, not your general home LAN.

## API Reference

### WAB11Client

The main async client class.

**Properties:**

- `system` - Global system state
- `heating_circuits` - List of 5 heating circuits (HK1-HK5)
- `hot_water` - Hot water state
- `heat_pump` - Heat pump state
- `secondary_heat` - Secondary heat source state
- `inputs` - Digital inputs and SG-Ready state
- `energy` - Energy statistics
- `is_connected` - Connection status
- `last_sync` - Timestamp of last sync

**Methods:**

- `connect()` / `disconnect()` - Connection management
- `sync()` - Synchronize state with device
- `sync_energy()` - Synchronize legacy and optional electrical energy statistics
- `start_polling(interval)` / `stop_polling()` - Background polling
- `on_change(callback)` - Subscribe to state changes
- `set_system_mode(mode, confirmed)` - Set system mode
- `set_heating_circuit_mode(circuit, mode)` - Set HK mode
- `set_heating_circuit_setpoint(circuit, level, temp)` - Set temperature
- `set_heating_party_pause(circuit, mode, hours)` - Party/pause mode
- `set_hot_water_setpoint(level, temp)` - Set hot water temp
- `trigger_hot_water_push(minutes)` - Hot water boost
- `read_register(name)` / `write_register(name, value)` - Raw access

### Enums

```python
from wab11 import (
    SystemMode,           # AUTOMATIC, HEATING, COOLING, SUMMER, STANDBY, SECOND_HEAT
    OperatingState,       # Current state (HEATING, COOLING, HOT_WATER, DEFROST, etc.)
    HeatingCircuitMode,   # AUTOMATIC, COMFORT, NORMAL, SETBACK, STANDBY
    SGReadyState,         # NORMAL, EVU_LOCK, RECOMMENDED, MAXIMUM
)
```

### Exceptions

```python
from wab11 import (
    WAB11Error,           # Base exception
    ConnectionError,      # Connection failures
    ValidationError,      # Invalid values
    SafetyError,          # Unconfirmed critical operation
    RateLimitError,       # Rate limit exceeded
)
```

## Supported Registers

The library supports documented WAB11 Modbus registers and the empirically
observed optional electrical energy group:

| Range | Description                                 |
| ----- | ------------------------------------------- |
| 30xxx | System status (outdoor temp, errors, state) |
| 31xxx | Heating circuit status (HK1-HK5)            |
| 32xxx | Hot water status                            |
| 33xxx | Heat pump status                            |
| 34xxx | Secondary heat source status                |
| 35xxx | Digital inputs, SG-Ready                    |
| 36xxx | Energy statistics                           |
| 40xxx | System parameters                           |
| 41xxx | Heating circuit parameters                  |
| 42xxx | Hot water parameters                        |
| 43xxx | Heat pump parameters                        |
| 44xxx | Secondary heat source parameters            |
| 45xxx | Input configuration                         |

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run the default test suite
uv run pytest

# Type checking
uv run mypy src/wab11

# Linting
uv run ruff check src/wab11
```

### Testing

The default test suite uses a fake Modbus system defined in
`tests/fixtures/fake_system.json`. That fixture is used for normal
regression tests and is safe to run on any machine because it does not
talk to a real controller.

The repository also includes a `warm` live-device test in
`tests/test_warm_live_device.py`. This test is skipped by default and
must be enabled explicitly. It is designed to be read-only:

- It only connects, syncs state, syncs energy values, and reads registers
- It does not call any library write API
- It replaces the connection write method with a failing guard, so the test aborts immediately if any write is attempted

Run the warm test only when you intentionally want to exercise a real
WAB11 device:

```bash
pytest tests/test_warm_live_device.py \
  --run-warm \
  --warm-host <ip-or-host>
```

Heating circuits are auto-detected when the option is omitted. Pass
`--warm-heating-circuits <1-5>` only to override detection manually.

You can also provide the live-device settings through environment
variables:

- `WAB11_TEST_HOST`
- `WAB11_TEST_PORT`
- `WAB11_TEST_UNIT_ID`
- `WAB11_TEST_TIMEOUT`
- `WAB11_TEST_HEATING_CIRCUITS`

## License

MIT License - see LICENSE file.

## Disclaimer

This is an unofficial library. Use at your own risk. Always verify operations with the official Weishaupt documentation and ensure you understand the effects of any changes you make to your heating system.
