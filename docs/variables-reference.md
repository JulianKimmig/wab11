# WAB11 Variables, Registers, Models, and Home Assistant Reference

This is the complete reference for values the current `wab11` package can read,
record in its state models, or write, plus the subset exposed by the
`hacs_wab11` Home Assistant integration. It is generated conceptually from the
authoritative register catalog in
[`definitions.py`](../src/wab11/registers/definitions.py), codecs in
[`formats.py`](../src/wab11/registers/formats.py), every model under
[`src/wab11/models`](../src/wab11/models/), client synchronization and write
methods in [`client.py`](../src/wab11/client.py), and the integration platforms
under
[`submodules/hacs-wab11/custom_components/hacs_wab11`](../submodules/hacs-wab11/custom_components/hacs_wab11/).

The library's circuit-discovery rules are specified separately in the
[`heating-circuit discovery contract`](../.docs/contracts/heating-circuit-discovery.md).
The integration's configuration, entity, service, and diagnostics guarantees
are specified in its
[`Home Assistant contract`](../submodules/hacs-wab11/.docs/contracts/home-assistant.md).

## How to read this reference

- **Raw register** means an entry in `ALL_REGISTERS`. Every one can be read by
  name with `WAB11Client.read_register()` and `WAB11SyncClient.read_register()`.
- **Model field** means decoded state populated by `sync()` or `sync_energy()`.
  It is accessed through `client.system`, `heating_circuits`, `hot_water`,
  `heat_pump`, `secondary_heat`, `inputs`, or `energy`.
- **Derived** means a property calculated from model fields; it has no register.
- **Writable in catalog** means generic `write_register()` accepts the key
  after validation. It does not mean Home Assistant exposes it.
- **High-level write** means a curated `set_*`, party/pause, or hot-water-push
  method exists and also updates the corresponding local model.
- **HACS** lists the entity key or service. Write entities are absent unless
  `enable_write_entities` is true. Advanced and energy sensors have their own
  options.

Input registers (`30xxx`–`36xxx`) are read-only. Holding registers
(`40xxx`–`45xxx`) may still be cataloged read-only when they are commissioning
values. Addresses below are the logical addresses used by this package.

## Formats, units, and sentinels

| Format | Decoded Python value | Encoding and special values |
| --- | --- | --- |
| `temp` | `Temperature` | Signed 16-bit tenths; Celsius is raw / 10. `Temperature.NO_SENSOR = -32768` means no sensor/no value and `Temperature.SENSOR_FAULT = -32767` means sensor fault; both expose `.celsius is None`. |
| `u16` | `int` | Unsigned `0..65535`. Register-specific sentinels are documented below. |
| `s16` | `int` | Signed `-32768..32767`, transported as unsigned 16-bit. No current catalog entry uses this format directly. |
| `bool` | `bool` | Raw zero is false; any nonzero value decodes true. Writes encode false/true as `0`/`1`. |
| `percent` | `int | None` | Raw `65535` decodes to `None`; otherwise the integer is returned. `None` encodes as `65535`. |
| Enum formats | Corresponding `IntEnum`, or raw `int` for an unknown code when using `read_register()` | Known values are listed in the enum table. Model synchronization generally retains its previous/default enum when the raw value is unknown. |

Catalog min/max values are raw values. For `temp`, divide them by 10 for °C.
Where the catalog declares no min/max, generic writes only have type/16-bit
encoding constraints; this reference does not infer a safe device range.
`system_mode` and `power_request` require `confirmed=True` when confirmation is
enabled. All writes are rate-limited by default and recorded in the audit log.

## Complete raw register catalog

The catalog contains **166 keys**: 81 fixed keys plus 17 circuit templates
repeated for circuits 1–5. Of these, 84 are marked writable (55 are the 11
writable circuit templates repeated five times).

### System

| Key | Address | R/W | Format/unit | Meaning and limits | Model / high-level / HACS |
| --- | ---: | --- | --- | --- | --- |
| `outdoor_temp_1` | 30001 | R | `temp`, °C | Primary outdoor temperature | `system.outdoor_temp_1`; derived `outdoor_temp`; HACS `sensor.outdoor_temperature` |
| `outdoor_temp_2` | 30002 | R | `temp`, °C | Secondary outdoor temperature | `system.outdoor_temp_2`; HACS `sensor.outdoor_temperature_2` |
| `error_code` | 30003 | R | `u16` | Error code; `65535` = no error | `system.error_code`; derived `has_error`; HACS sensor (sentinel becomes unavailable) and `binary_sensor.has_error` |
| `warning_code` | 30004 | R | `u16` | Warning code; `65535` = no warning | `system.warning_code`; derived `has_warning`; HACS sensor and binary sensor, both disabled by default |
| `ok_flag` | 30005 | R | `bool` | Controller error-free flag | `system.is_error_free`; diagnostics |
| `operating_state` | 30006 | R | `OperatingState` | Current controller operating state | `system.operating_state`; derived state flags; HACS enum sensor plus disabled system-state binary sensors |
| `system_mode` | 40001 | R/W | `SystemMode` | Raw `0..5`; critical write | `system.system_mode`; `set_system_mode(mode, confirmed)`; HACS `select.system_mode` |
| `power_request` | 40002 | R/W | `u16`, W | `0..30000`; critical write | `system.power_request_watts`; generic write only; HACS `sensor.power_request` |

### Heating circuits (complete template repeated for N = 1, 2, 3, 4, 5)

For circuit `N`, input addresses are `31N01..31N05` and holding addresses are
`41N01..41N12`. The literal catalog keys replace `N` with the number, for
example `hk3_mode` at `41303`. Only circuits selected explicitly or detected
sequentially exist in `client.heating_circuits`; HACS creates circuit entities
only when that model's `is_configured` is true.

| Key template | Address template | R/W | Format/unit | Meaning and limits | Model / high-level / HACS |
| --- | ---: | --- | --- | --- | --- |
| `hkN_room_setpoint_effective` | `31N01` | R | `temp`, °C | Effective room setpoint | `.room_setpoint_effective`; HACS `sensor.hkN_room_effective_setpoint` |
| `hkN_room_temp` | `31N02` | R | `temp`, °C | Measured room temperature | `.room_temp`; HACS `sensor.hkN_room_temperature` |
| `hkN_room_humidity` | `31N03` | R | `percent`, % | Room humidity; `65535` = unavailable | `.room_humidity`; HACS `sensor.hkN_room_humidity` |
| `hkN_flow_setpoint` | `31N04` | R | `temp`, °C | Calculated flow-temperature target | `.flow_setpoint`; HACS `sensor.hkN_flow_setpoint` |
| `hkN_flow_temp` | `31N05` | R | `temp`, °C | Measured flow temperature | `.flow_temp`; HACS `sensor.hkN_flow_temperature` |
| `hkN_config` | `41N01` | R | `HeatingCircuitConfig` | Commissioning configuration | `.config`; gates circuit entities; HACS disabled `sensor.hkN_config` |
| `hkN_request_type` | `41N02` | R/W | `RequestType` | Catalog raw `0..3`; known codes `0,1,3` | `.request_type`; generic write; HACS disabled `sensor.hkN_request_type` |
| `hkN_mode` | `41N03` | R/W | `HeatingCircuitMode` | Raw `0..4` | `.mode`; `set_heating_circuit_mode()`; HACS `select.hkN_mode` |
| `hkN_party_pause` | `41N04` | R/W | `u16` | `1..24` pause 12..0.5 h; `25` automatic; `26..48` party 0.5..12 h | `.party_pause`; high-level/services; HACS disabled `sensor.hkN_party_pause` |
| `hkN_setpoint_comfort` | `41N05` | R/W | `temp`, °C | Raw `150..300` = `15..30 °C` | `.setpoint_comfort`; `set_heating_circuit_setpoint(..., "comfort", ...)`; HACS `number.hkN_comfort_setpoint`, step 0.5 |
| `hkN_setpoint_normal` | `41N06` | R/W | `temp`, °C | Raw `150..300` = `15..30 °C` | `.setpoint_normal`; high-level normal setter; HACS `number.hkN_normal_setpoint`, step 0.5 |
| `hkN_setpoint_setback` | `41N07` | R/W | `temp`, °C | Raw `100..250` = `10..25 °C` | `.setpoint_setback`; high-level setback setter; HACS `number.hkN_setback_setpoint`, step 0.5 |
| `hkN_heating_curve` | `41N08` | R/W | `u16` | Heating-curve slope; no catalog range | `.heating_curve_slope`; generic write; HACS `sensor.hkN_heating_curve` |
| `hkN_summer_winter_threshold` | `41N09` | R/W | `u16` | Summer/winter switching value; no catalog range/unit | `.summer_winter_threshold`; generic write; HACS sensor currently labels the integer °C |
| `hkN_constant_temp_heating` | `41N10` | R/W | `temp`, °C | Constant heating temperature; no catalog range | `.constant_temp_heating`; generic write; HACS sensor |
| `hkN_constant_temp_heating_setback` | `41N11` | R/W | `temp`, °C | Constant heating setback; no catalog range | `.constant_temp_heating_setback`; generic write; HACS sensor |
| `hkN_constant_temp_cooling` | `41N12` | R/W | `temp`, °C | Constant cooling temperature; no catalog range | `.constant_temp_cooling`; generic write; HACS sensor |

`HeatingCircuit.status` and its derived `is_heating`/`is_cooling` properties are
model variables, but no current register definition or synchronization
assignment populates `status`. HACS intentionally exposes neither the field nor
status-derived circuit binary sensors.

### Hot water

| Key | Address | R/W | Format/unit | Meaning and limits | Model / high-level / HACS |
| --- | ---: | --- | --- | --- | --- |
| `ww_setpoint_effective` | 32101 | R | `temp`, °C | Effective hot-water target | `.setpoint_effective`; HACS effective-setpoint and derived difference sensors |
| `ww_temp` | 32102 | R | `temp`, °C | Measured hot-water temperature | `.temperature`; derived `current_temp`; HACS `sensor.hot_water_temperature` |
| `ww_config` | 42101 | R | `HotWaterConfig` | Commissioning configuration | `.config`; HACS disabled `sensor.hot_water_config` |
| `ww_push_minutes` | 42102 | R/W | `u16`, min | Catalog `0..240`; high-level API accepts `0` or `5..240` | `.push_minutes`; trigger/cancel methods; HACS number `0..240`, step 5, two buttons, and two services |
| `ww_normal` | 42103 | R/W | `temp`, °C | `30..65 °C` | `.setpoint_normal`; high-level setter; HACS number, step 1 |
| `ww_setback` | 42104 | R/W | `temp`, °C | `20..60 °C` | `.setpoint_setback`; high-level setter; HACS number, step 1 |
| `ww_sg_ready_boost` | 42105 | R/W | `temp`, K | Description specifies `0..30 K`; raw `-32768` = off; catalog declares no enforced min/max | `.sg_ready_boost`; generic write; HACS sensor |

`HotWaterState.status` and derived charging properties have no current raw
register definition or synchronization assignment. They remain at the default
`OFF` unless an application modifies the model. HACS intentionally does not
expose `status` or the derived hot-water-charging state until a real synchronized
source exists.

### Heat pump

| Key | Address | R/W | Format/unit | Meaning and limits | Model / HACS |
| --- | ---: | --- | --- | --- | --- |
| `wp_operating_state` | 33101 | R | `OperatingState` | Heat-pump operating state | `.operating_state`; HACS advanced enum sensor and disabled mode binary sensors |
| `wp_error_free` | 33102 | R | `bool` | Heat-pump error-free flag | `.is_error_free`; HACS disabled binary sensor |
| `wp_power_request` | 33103 | R | `percent`, % | Power request; `65535` decodes `None` generically, but sync stores the raw integer | `.power_request_percent`; HACS advanced percentage sensor and enabled running binary sensor |
| `wp_flow_temp_b4` | 33104 | R | `temp`, °C | Flow sensor B4 | `.flow_temp_b4`; HACS optional advanced flow-temperature sensor |
| `wp_return_temp` | 33105 | R | `temp`, °C | Return temperature | `.return_temp`; HACS optional advanced return-temperature sensor |
| `wp_evaporator_temp` | 33106 | R | `temp`, °C | Evaporator temperature | `.evaporator_temp`; HACS advanced sensor |
| `wp_suction_gas_temp` | 33107 | R | `temp`, °C | Suction-gas temperature | `.suction_gas_temp`; HACS advanced sensor |
| `wp_separator_temp_b2` | 33108 | R | `temp`, °C | Hydraulic-separator B2 | `.separator_temp_b2`; HACS optional advanced separator sensor |
| `wp_regenerative_flow_b21` | 33109 | R | `temp`, °C | Regenerative flow B2.1 | `.regenerative_flow_b21`; HACS advanced sensor |
| `wp_buffer_temp_b11` | 33110 | R | `temp`, °C | Buffer B11 | `.buffer_temp_b11`; HACS optional advanced buffer sensor |
| `wp_sum_flow_b7` | 33111 | R | `temp`, °C | Sum flow B7 | `.sum_flow_b7`; HACS advanced sensor |
| `wp_config` | 43101 | R | `HeatPumpConfig` | Commissioning configuration | `.config`; HACS disabled advanced sensor |
| `wp_quiet_mode` | 43102 | R/W | `u16` | Quiet mode; zero = off; no catalog range | `.quiet_mode`; generic write; HACS disabled advanced sensor and disabled derived binary sensor |
| `wp_pump_start_mode` | 43103 | R/W | `u16` | Pump start-mode configuration; no catalog range | `.pump_start_mode`; generic write; HACS disabled advanced sensor |
| `wp_pump_power_heating` | 43104 | R/W | `percent`, % | `20..100` | `.pump_power_heating`; generic write; HACS advanced sensor |
| `wp_pump_power_cooling` | 43105 | R/W | `percent`, % | `20..100` | `.pump_power_cooling`; generic write; HACS advanced sensor |
| `wp_pump_power_hot_water` | 43106 | R/W | `percent`, % | `20..100` | `.pump_power_hot_water`; generic write; HACS advanced sensor |
| `wp_pump_power_defrost` | 43107 | R/W | `percent`, % | No catalog range | `.pump_power_defrost`; generic write; HACS advanced sensor |
| `wp_flow_rate_heating` | 43108 | R/W | `u16`, m³/h | Catalog notes scaled value but defines no scale/range | `.flow_rate_heating`; generic write; HACS disabled advanced sensor without unit metadata |
| `wp_flow_rate_cooling` | 43109 | R/W | `u16`, m³/h | Catalog notes scaled value but defines no scale/range | `.flow_rate_cooling`; generic write; HACS disabled advanced sensor without unit metadata |
| `wp_flow_rate_hot_water` | 43110 | R/W | `u16`, m³/h | Catalog notes scaled value but defines no scale/range | `.flow_rate_hot_water`; generic write; HACS disabled advanced sensor without unit metadata |

### Secondary heat sources

| Key | Address | R/W | Format/unit | Meaning and limits | Model / HACS |
| --- | ---: | --- | --- | --- | --- |
| `wez2_status` | 34101 | R | `u16` | Second heat-source status | `secondary_heat.status_wez2`; derived active flags |
| `wez2_operating_hours` | 34102 | R | `u16`, h | Second heat-source hours | `.operating_hours_wez2`; derived total hours |
| `wez2_switching_cycles` | 34103 | R | `u16` | Second heat-source switching cycles | `.switching_cycles_wez2` |
| `e1_status` | 34104 | R | `bool` | Electric heater stage 1 status | `.status_e1`; derived active flags |
| `e2_status` | 34105 | R | `bool` | Electric heater stage 2 status | `.status_e2`; derived active flags |
| `e1_operating_hours` | 34106 | R | `u16`, h | Stage 1 hours | `.operating_hours_e1`; derived total hours |
| `e2_operating_hours` | 34107 | R | `u16`, h | Stage 2 hours | `.operating_hours_e2`; derived total hours |
| `wez2_config` | 44101 | R/W | `u16` | `255` off, `0` active; no enforced catalog range | `.config_wez2`; generic write only |
| `e1_config` | 44102 | R/W | `u16` | `255` off, `5` active; no enforced catalog range | `.config_e1`; generic write only |
| `e2_config` | 44103 | R/W | `u16` | `255` off, `6` active; no enforced catalog range | `.config_e2`; generic write only |
| `limit_temp` | 44104 | R/W | `temp`, °C | Heat-pump lock threshold; no catalog range | `.limit_temp`; derived `should_lock_heat_pump()`; generic write only |
| `bivalence_temp_heating` | 44105 | R/W | `temp`, °C | Heating bivalence threshold; no catalog range | `.bivalence_temp_heating`; derived `should_activate_backup()`; generic write only |
| `bivalence_temp_hot_water` | 44106 | R/W | `temp`, °C | Hot-water bivalence threshold; no catalog range | `.bivalence_temp_hot_water`; generic write only |

HACS exposes the status/counters/thresholds as sensors, configuration codes as
disabled sensors, aggregate and per-source active binary sensors, and all
fields in diagnostics.

### Digital inputs and SG-Ready

| Key | Address | R/W | Format | Meaning | Model / HACS |
| --- | ---: | --- | --- | --- | --- |
| `sgr1_status` | 35101 | R | `bool` | SG-Ready input 1 | `inputs.sg_ready_1`; HACS binary sensor; contributes to SG enum sensor |
| `sgr2_status` | 35102 | R | `bool` | SG-Ready input 2 | `.sg_ready_2`; HACS binary sensor; contributes to SG enum sensor |
| `h12_status` | 35103 | R | `bool` | H1.2 input | `.input_h12`; HACS binary sensor |
| `h13_status` | 35104 | R | `bool` | H1.3 input | `.input_h13`; HACS binary sensor |
| `h14_status` | 35105 | R | `bool` | H1.4 input | `.input_h14`; HACS binary sensor |
| `h15_status` | 35106 | R | `bool` | H1.5 input | `.input_h15`; HACS binary sensor |
| `de1_status` | 35107 | R | `bool` | DE1 input | `.input_de1`; HACS binary sensor |
| `de2_status` | 35108 | R | `bool` | DE2 input | `.input_de2`; HACS binary sensor |
| `sgr1_config` | 45101 | R/W | `u16` | SGR1 assigned function; no catalog range | `inputs.config_sgr1` exists, but `sync()` does not currently read configuration registers; generic read/write only |
| `sgr2_config` | 45102 | R/W | `u16` | SGR2 assigned function | `.config_sgr2`; generic read/write only |
| `h12_config` | 45103 | R/W | `u16` | H1.2 assigned function | `.config_h12`; generic read/write only |
| `h13_config` | 45104 | R/W | `u16` | H1.3 assigned function | `.config_h13`; generic read/write only |
| `h14_config` | 45105 | R/W | `u16` | H1.4 assigned function | `.config_h14`; generic read/write only |
| `h15_config` | 45106 | R/W | `u16` | H1.5 assigned function | `.config_h15`; generic read/write only |
| `de1_config` | 45107 | R/W | `u16` | DE1 assigned function | `.config_de1`; generic read/write only |
| `de2_config` | 45108 | R/W | `u16` | DE2 assigned function | `.config_de2`; generic read/write only |

The status fields derive `sg_ready_state`, four SG convenience flags,
`any_input_active`, and `get_active_inputs()`. HACS exposes the SG enum sensor
and all eight synchronized statuses as binary sensors. It intentionally does
not expose `config_*`, because full synchronization never reads 45101–45108;
their model values are defaults rather than controller observations.

### Energy statistics

All 16 keys are read-only `u16` values in kWh. `sync_energy()` converts them to
`float` model fields. Replace `CATEGORY` with `total`, `heating`, `hot_water`,
or `cooling`; each row therefore names four literal catalog keys.

| Key template | Addresses by category | Model | HACS |
| --- | --- | --- | --- |
| `energy_CATEGORY_today` | total 36101; heating 36201; hot water 36301; cooling 36401 | `energy.CATEGORY.today` | HACS `sensor.CATEGORY_energy_today` when enabled |
| `energy_CATEGORY_yesterday` | 36102; 36202; 36302; 36402 | `.yesterday` | HACS `sensor.CATEGORY_energy_yesterday` |
| `energy_CATEGORY_month` | 36103; 36203; 36303; 36403 | `.month` | HACS `sensor.CATEGORY_energy_month` |
| `energy_CATEGORY_year` | 36104; 36204; 36304; 36404 | `.year` | HACS `sensor.CATEGORY_energy_year` |

Each `EnergyPeriod` also derives `total_recent`. `EnergyStatistics` derives
`today_total`, `yesterday_total`, `month_total`, `year_total`,
`heating_percentage_today`, and `hot_water_percentage_today`; percentages are
`None` when total energy today is zero.

## Complete decoded model surface

The raw tables map register-backed fields individually. This table accounts for
the remaining metadata and every derived field/property.

| Object | Non-register or derived variables | Meaning |
| --- | --- | --- |
| `Temperature` | `raw`, `celsius`, `is_valid`, `is_sensor_fault`, `is_no_sensor` | Raw signed tenths, optional Celsius value, and sentinel classification |
| `SystemState` | `last_updated`; `has_error`, `has_warning`, `outdoor_temp`, `is_heating`, `is_cooling`, `is_hot_water`, `is_defrosting`, `is_standby` | Sync timestamp and predicates derived from codes/state |
| `HeatingCircuit` | `circuit_id`, `status`; `is_configured`, `is_heating`, `is_cooling`, `is_mixer_circuit`, `is_pump_circuit`, `party_pause_info`, `is_party_active`, `is_pause_active`, `input_register_base`, `holding_register_base` | Circuit identity/addressing and predicates; note the current `status` limitation above |
| `HotWaterState` | `status`; `is_configured`, `is_push_active`, `is_charging`, `is_priority_charging`, `current_temp`, `target_temp`, `temp_difference` | Configuration/action/temperature helpers; note the current `status` limitation above |
| `HeatPumpState` | `is_configured`, `supports_cooling`, `is_running`, `is_heating`, `is_cooling`, `is_defrosting`, `is_hot_water`, `spread`, `is_quiet_mode` | Predicates and flow-minus-return spread in K |
| `SecondaryHeatSourceState` | `is_wez2_configured`, `is_wez2_active`, `is_e1_configured`, `is_e2_configured`, `is_e1_active`, `is_e2_active`, `any_backup_active`, `total_operating_hours`; `should_activate_backup(outdoor_temp)`, `should_lock_heat_pump(outdoor_temp)` | Backup configuration/activity aggregation and temperature-threshold helpers |
| `InputsState` | `sg_ready_state`, `is_evu_lock`, `is_sg_maximum`, `is_sg_recommended`, `is_sg_normal`, `any_input_active`; `get_active_inputs()` | Combined two-bit SG state and input aggregation |
| `EnergyPeriod` | `total_recent` | Today plus yesterday |
| `EnergyStatistics` | `today_total`, `yesterday_total`, `month_total`, `year_total`, `heating_percentage_today`, `hot_water_percentage_today` | Aliases for total-period values and today's shares |
| `WAB11Client` | `host`, `is_connected`, `is_polling`, `last_sync`, `audit_log` | Connection/polling metadata, most recent full-sync time, and write audit history |

## Complete enum values

| Enum | Numeric values |
| --- | --- |
| `SystemMode` | `AUTOMATIC=0`, `HEATING=1`, `COOLING=2`, `SUMMER=3`, `STANDBY=4`, `SECOND_HEAT=5` |
| `OperatingState` | `UNDEFINED=0`, `RELAY_TEST=1`, `EMERGENCY_OFF=2`, `DIAGNOSTICS=3`, `MANUAL=4`, `MANUAL_HEATING=5`, `MANUAL_COOLING=6`, `MANUAL_DEFROST=7`, `DEFROST=8`, `SECOND_HEAT_SOURCE=9`, `EVU_LOCK=10`, `SG_TARIFF=11`, `SG_MAXIMUM=12`, `TARIFF_CHARGING=13`, `ELEVATED_OPERATION=14`, `IDLE_TIME=15`, `STANDBY=16`, `FLUSH=17`, `FROST_PROTECTION=18`, `HEATING=19`, `HOT_WATER=20`, `LEGIONELLA_PROTECTION=21`, `HEATING_COOLING_SWITCH=22`, `COOLING=23`, `PASSIVE_COOLING=24`, `SUMMER=25`, `POOL=26`, `VACATION=27`, `SCREED=28`, `LOCKED=29`, `AT_LOCK=30`, `SUMMER_LOCK=31`, `WINTER_LOCK=32`, `OPERATING_LIMIT=33`, `HK_LOCK=34`, `SETBACK=35` |
| `HeatingCircuitMode` | `AUTOMATIC=0`, `COMFORT=1`, `NORMAL=2`, `SETBACK=3`, `STANDBY=4` |
| `HeatingCircuitStatus` | `OFF=0`, `HEATING=1`, `COOLING=2`, `HEATING_BLOCKED=3`, `COOLING_BLOCKED=4` |
| `HeatingCircuitConfig` | `NOT_CONFIGURED=0`, `PUMP_CIRCUIT=1`, `MIXER_CIRCUIT=2`, `SETPOINT_PUMP_M1=3` |
| `RequestType` | `OFF=0`, `WEATHER_COMPENSATED=1`, `CONSTANT=3` |
| `HotWaterStatus` | `OFF=0`, `NO_REQUEST=1`, `PRIORITY_CHARGING=2`, `PARALLEL_CHARGING=3`, `REQUEST_BLOCKED=4` |
| `HotWaterConfig` | `DISABLED=0`, `DIVERTER_VALVE=1`, `PUMP=8` |
| `HeatPumpConfig` | `NOT_CONFIGURED=0`, `HEATING_ONLY=1`, `HEATING_AND_COOLING=2` |
| `HeatPumpRelease` | `NONE=0`, `HEATING_ONLY=1`, `COOLING_ONLY=2`, `HEATING_AND_COOLING=3`; exported model enum, but no current register/model field uses it |
| `InputFunction` | `DISABLED=0`, `EVU_LOCK=1`, `ELEVATED_OPERATION=2`, `HK_LOCK=3`, `HEATING_COOLING_SWITCH=4`, `HOT_WATER_STANDBY=5`, `HOT_WATER_SETBACK=6`, `HOT_WATER_NORMAL=7`, `HOT_WATER_PUSH=8`, `DEW_POINT_MONITOR=9`, `SYSTEM_STANDBY=10`, `COMPRESSOR_LOCK=11`; describes input configuration codes, though configuration model fields are currently plain integers |
| `SGReadyState` | `NORMAL=0`, `EVU_LOCK=1`, `RECOMMENDED=2`, `MAXIMUM=3` |

## Library read, record, and control APIs

| API | Scope | Notes |
| --- | --- | --- |
| `sync()` | Records system, selected/detected heating circuits, hot water, heat pump, input statuses, and secondary heat | Does not update energy or input-configuration holdings. Circuit discovery details are in the linked contract. |
| `sync_energy()` | Records all 16 energy values | Kept separate for lower-frequency polling. |
| `read_register(key)` | Reads any of the 166 raw catalog keys | Uses the catalog codec and returns a decoded scalar/value object; it does not update the state model. |
| `write_register(key, value, confirmed=False)` | Writes any of the 84 catalog keys marked writable | Validates writability/type/range/critical confirmation, rate-limits, audits, and emits a local change event. Prefer high-level methods; generic writes do not synchronize the corresponding model field. |
| `set_system_mode(mode, confirmed=False)` | `system_mode` | Critical write; updates `system.system_mode`. |
| `set_heating_circuit_mode(N, mode)` | `hkN_mode` | N must exist in the selected/detected collection; updates `.mode`. |
| `set_heating_circuit_setpoint(N, level, °C)` | `hkN_setpoint_comfort|normal|setback` | Enforces named level and catalog safety ranges; updates the selected `Temperature`. |
| `set_heating_party_pause(N, mode, hours=2)` | `hkN_party_pause` | Mode `party`, `pause`, or `auto`; duration `0.5..12 h` for party/pause; updates code. |
| `set_hot_water_setpoint(level, °C)` | `ww_normal|ww_setback` | Level normal/setback and its documented range; updates model. |
| `trigger_hot_water_push(minutes=30)` | `ww_push_minutes` | Accepts zero or `5..240`; updates model. |
| `cancel_hot_water_push()` | `ww_push_minutes=0` | Delegates to trigger with zero. |
| `start_polling(interval=5, energy_interval=300)` / `stop_polling()` | Background sync | Async client only; logs and continues after non-cancellation errors. |
| `on_change(callback)` / `remove_change_callback(callback)` | Change events | `StateChangeEvent` records timestamp, source (`device` or `local`), register key, old value, and new value. Device change caching is currently applied to system sync values; local writes emit events through the write path. |
| `audit_log` | Write records | Exposes successful and failed write audit entries. |

`WAB11SyncClient` mirrors connection, all state properties, `sync`,
`sync_energy`, callbacks, every high-level control, generic read/write, and the
audit log through a private event loop. It does not expose async background
polling or `last_sync` as its own property.

## Complete HACS/Home Assistant exposure

Entity unique IDs append the key below to the config-entry unique ID. All
entities share one WAB11 device. Baseline sensor/binary-sensor platforms always
load; registry-disabled defaults are noted explicitly.

### Read entities

The always-created sensor keys are:

| Group | Keys and values | Disabled by default |
| --- | --- | --- |
| System | `outdoor_temperature`, `outdoor_temperature_2` (°C); `operating_state` (enum); `error_code`, `warning_code`; `power_request` (W) | `warning_code` |
| Hot water | `hot_water_temperature`, `hot_water_effective_setpoint` (°C); `hot_water_sg_ready_boost`, `hot_water_temperature_difference` (K); `hot_water_config` (enum) | `hot_water_config` |
| Inputs | `sg_ready_state` enum | None |
| Secondary heat | `wez2_status`, `wez2_operating_hours`, `wez2_switching_cycles`, `e1_operating_hours`, `e2_operating_hours`, `secondary_heat_limit_temperature`, `bivalence_temperature_heating`, `bivalence_temperature_hot_water`, `secondary_heat_total_operating_hours`, `config_wez2`, `config_e1`, `config_e2` | The three `config_*` keys |

Every synchronized circuit whose `config` is not `NOT_CONFIGURED` adds 13
sensors:

| Key template | Value | Default |
| --- | --- | --- |
| `hkN_room_effective_setpoint`, `hkN_room_temperature`, `hkN_flow_setpoint`, `hkN_flow_temperature` | °C | Enabled |
| `hkN_room_humidity` | % or unavailable | Enabled |
| `hkN_heating_curve` | Integer | Enabled |
| `hkN_summer_winter_threshold` | Synchronized integer with current °C metadata | Enabled |
| `hkN_constant_temperature_heating`, `hkN_constant_temperature_heating_setback`, `hkN_constant_temperature_cooling` | °C | Enabled |
| `hkN_config`, `hkN_request_type` | Lowercase enum | Disabled |
| `hkN_party_pause` | Encoded integer | Disabled |

Always-created binary sensors are:

| Group | Keys | Disabled by default |
| --- | --- | --- |
| System | `has_error`, `has_warning`, `system_heating`, `system_cooling`, `system_hot_water`, `system_defrosting`, `system_standby` | Warning and all five operating-state helpers |
| Heat pump | `heat_pump_error_free`, `heat_pump_running`, `heat_pump_heating`, `heat_pump_cooling`, `heat_pump_defrosting`, `heat_pump_hot_water`, `heat_pump_quiet` | All except `heat_pump_running` |
| Secondary heat | `secondary_heat_active`, `wez2_active`, `electric_heater_1`, `electric_heater_2` | None |
| Inputs | `sg_ready_1`, `sg_ready_2`, `input_h12`, `input_h13`, `input_h14`, `input_h15`, `input_de1`, `input_de2` | None |

With `enable_advanced_sensors=true`, HACS adds 21 heat-pump sensors:

- Eight temperatures: `heat_pump_flow_temperature`,
  `heat_pump_return_temperature`, `heat_pump_buffer_temperature`,
  `heat_pump_separator_temperature`, `heat_pump_evaporator_temperature`,
  `heat_pump_suction_gas_temperature`,
  `heat_pump_regenerative_flow_temperature`, and
  `heat_pump_sum_flow_temperature`.
- `heat_pump_operating_state`, `heat_pump_power_request`,
  `heat_pump_temperature_spread`, `heat_pump_power_heating`,
  `heat_pump_power_cooling`, `heat_pump_power_hot_water`, and
  `heat_pump_power_defrost`.
- Disabled diagnostics/configuration: `heat_pump_config`,
  `heat_pump_quiet_mode`, `heat_pump_start_mode`,
  `heat_pump_flow_rate_heating`, `heat_pump_flow_rate_cooling`, and
  `heat_pump_flow_rate_hot_water`.

With `enable_energy_sensors=true` (default), all 16 kWh combinations named
`CATEGORY_energy_PERIOD` are created. `CATEGORY` is `total`, `heating`,
`hot_water`, or `cooling`; `PERIOD` is `today`, `yesterday`, `month`, or
`year`.

HACS intentionally does not create circuit-status, hot-water-status/charging,
or input-configuration entities. The corresponding model fields are not
populated by current synchronization, so their defaults are not controller
observations.

### Write entities

All require `enable_write_entities=true`. Each write is serialized with polling
by the runtime lock, rejected again by the runtime if writes are disabled, and
publishes the returned main snapshot immediately.

| Platform/key | Source/register | Allowed values | Repetition |
| --- | --- | --- | --- |
| `select.system_mode` | `system.system_mode` / 40001 | `automatic`, `heating`, `cooling`, `summer`, `standby`, `second_heat` | One |
| `select.hkN_mode` | circuit `.mode` / `41N03` | `automatic`, `comfort`, `normal`, `setback`, `standby` | Each selected circuit reported configured |
| `number.hkN_comfort_setpoint` | `.setpoint_comfort` / `41N05` | `15..30 °C`, step 0.5 | Each configured circuit |
| `number.hkN_normal_setpoint` | `.setpoint_normal` / `41N06` | `15..30 °C`, step 0.5 | Each configured circuit |
| `number.hkN_setback_setpoint` | `.setpoint_setback` / `41N07` | `10..25 °C`, step 0.5 | Each configured circuit |
| `number.hot_water_normal_setpoint` | `.setpoint_normal` / 42103 | `30..65 °C`, step 1 | One |
| `number.hot_water_setback_setpoint` | `.setpoint_setback` / 42104 | `20..60 °C`, step 1 | One |
| `number.hot_water_push_minutes` | `.push_minutes` / 42102 | `0..240 min`, step 5 | One |
| `button.trigger_hot_water_push` | 42102 | Writes 30 minutes | One |
| `button.cancel_hot_water_push` | 42102 | Writes zero | One |

### Domain services

| Service | Inputs | Register/action |
| --- | --- | --- |
| `hacs_wab11.set_party_pause` | optional `entry_id`; required circuit `1..5`; mode `party|pause`; hours `0.5..12`, default 2 | Encodes and writes `hkN_party_pause` |
| `hacs_wab11.cancel_party_pause` | optional `entry_id`; required circuit `1..5` | Writes automatic code 25 to `hkN_party_pause` |
| `hacs_wab11.trigger_hot_water_push` | optional `entry_id`; minutes `0..240`, default 30 | Writes `ww_push_minutes` |
| `hacs_wab11.cancel_hot_water_push` | optional `entry_id` | Writes zero to `ww_push_minutes` |

When one entry is loaded, `entry_id` may be omitted. With multiple entries it
is required. No loaded entry, an unknown/ambiguous target, or disabled writes
raises `HomeAssistantError`.

### Diagnostics

Diagnostics expose config-entry `entry` data (with `host`, `port`, and
`unit_id` redacted), all options, the complete `Wab11MainData` snapshot, and
the complete `EnergyStatistics` snapshot. Thus fields not represented by
entities remain observable in diagnostics. Dataclasses and collections are
recursive, enums become their uppercase names, datetimes become ISO strings,
and `Temperature` becomes its optional Celsius value. Configuration data such
as the heating-circuit count is not redacted; connection coordinates are.
Unsynchronized model defaults—including circuit/hot-water status and input
configuration—also serialize, but are not evidence of controller state.

## Source and test traceability

- Raw catalog and generation: [`definitions.py`](../src/wab11/registers/definitions.py),
  covered in
  [`test_remaining_branches.py`](../tests/test_remaining_branches.py) and
  [`test_models_and_formats.py`](../tests/test_models_and_formats.py).
- Formats and sentinels: [`formats.py`](../src/wab11/registers/formats.py) and
  [`base.py`](../src/wab11/models/base.py), covered in
  [`test_models_and_formats.py`](../tests/test_models_and_formats.py).
- Sync/model mapping and controls: [`client.py`](../src/wab11/client.py),
  covered by [`test_client_behaviors.py`](../tests/test_client_behaviors.py),
  [`test_preflight_fixes.py`](../tests/test_preflight_fixes.py), and
  [`test_fake_system_fixture.py`](../tests/test_fake_system_fixture.py).
- Write validation: [`validator.py`](../src/wab11/security/validator.py),
  covered by [`test_security_helpers.py`](../tests/test_security_helpers.py).
- Synchronous parity: [`sync_client.py`](../src/wab11/sync_client.py), covered
  by
  [`test_connection_and_sync_client.py`](../tests/test_connection_and_sync_client.py).
- HACS entity mapping and actions:
  [`sensor.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/sensor.py),
  [`sensor_descriptions.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/sensor_descriptions.py),
  [`sensor_circuit_descriptions.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/sensor_circuit_descriptions.py),
  [`binary_sensor.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/binary_sensor.py),
  [`select.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/select.py),
  [`number.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/number.py),
  [`button.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/button.py),
  and [`__init__.py`](../submodules/hacs-wab11/custom_components/hacs_wab11/__init__.py),
  covered by
  [`test_entities.py`](../submodules/hacs-wab11/tests/test_entities.py),
  [`test_services.py`](../submodules/hacs-wab11/tests/test_services.py), and
  [`test_diagnostics.py`](../submodules/hacs-wab11/tests/test_diagnostics.py).
