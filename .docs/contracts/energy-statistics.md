# Energy Statistics Contract

[`EnergyStatistics`](../../src/wab11/models/energy.py) exposes the four legacy
groups `total`, `heating`, `hot_water`, and `cooling`, followed by optional
`electrical: EnergyPeriod | None = None`. Existing constructor positions,
total aliases, percentages, and representation retain their meaning. Evidence
indicates that the legacy groups describe thermal energy generated; `total`
is not redirected to electrical input.

## Registers and precision

`ENERGY_REGISTERS` in
[`definitions.py`](../../src/wab11/registers/definitions.py) owns the 20
read-only input-register definitions, aggregated into `ALL_REGISTERS`. The
existing
36101–36404 groups retain their keys, addresses, formats, and permissions.
The four optional definitions are:

| Key | Address | Period |
| --- | ---: | --- |
| `energy_electrical_today` | 36701 | Today |
| `energy_electrical_yesterday` | 36702 | Yesterday |
| `energy_electrical_month` | 36703 | Current calendar month |
| `energy_electrical_year` | 36704 | Current calendar year |

All use input registers (function code 4), `UNSIGNED_16`, and kWh. Reads use
the package's full addresses: `read_input_registers(36701, 4)`, without an
offset. Raw `2` is `2 kWh`, converted to `2.0` in `EnergyPeriod`; floats do
not imply fractional-kWh source precision. Both `0` and `65535` are valid
numeric readings. No undocumented invalid sentinel or monotonicity rule is
applied. Periods overlap: do not sum today, yesterday, month, and year.
`total_recent` retains its existing today-plus-yesterday behavior.

## Synchronization and availability

[`energy_sync.py`](../../src/wab11/energy_sync.py) owns energy reads for
[`WAB11Client`](../../src/wab11/client.py). `sync_energy()` reads mandatory
blocks 36101, 36201, 36301, and 36401 in order, each with count 4, then reads
optional block 36701 with count 4. A complete response of four unsigned
16-bit integers is required before publishing a new electrical period.

| Most recent energy synchronization | `electrical` | Result |
| --- | --- | --- |
| Not attempted | `None` | Model access does not raise |
| Complete valid electrical response, including four zeros | New complete `EnergyPeriod` | Success |
| Optional block returns exception 2 (Illegal Data Address) | `None` | Success; legacy values remain available |
| Another optional Modbus exception, including 4 or 10 | `None` | Typed error propagates |
| Timeout, disconnect, malformed optional response, or failed mandatory read | `None` | Error propagates |
| Later poll succeeds after an unsupported or failed read | New complete `EnergyPeriod` | Automatic recovery |

`None` means unavailable, never zero consumption. Energy synchronization
clears electrical data before any I/O, so failures and cancellation cannot
retain the previous period as available. Legacy groups
retain their existing incremental update behavior; the method is not an
atomic snapshot of all five groups. Only exception 2 on the optional block
is suppressed. That response establishes an unavailable block on this device,
not a definitive explanation of its firmware. Expected rejection is logged
at debug level with address and exception code. Transport retry behavior is
unchanged, and every energy synchronization retries the optional block;
support is not permanently cached.
The transport also logs exception 2 at debug specifically for input request
`(36701, 4)`, while still raising the same typed exception. Other request
shapes and exception codes retain their existing warning behavior.

Normal `sync()` does not read energy registers. Async background polling
uses the existing `energy_interval=300` seconds schedule for all five groups;
there is no additional polling task. Availability records the last energy
synchronization outcome, not indefinite freshness after polling stops.
Applications must also track their connection/coordinator freshness.
[`WAB11SyncClient`](../../src/wab11/sync_client.py) exposes the same model and
delegates `sync_energy()` with the same error behavior.

Both generic named reads and the high-level energy model expose the new
registers. Before this feature, candidate addresses could only be read through
the generic connection-level input-register API. A generic
`read_register("energy_electrical_today")` returns a decoded integer without
updating the model and propagates normal Modbus errors, including exception 2.
Optional handling belongs only to high-level energy synchronization. Generic
writes remain prohibited for these input registers.

## Evidence and compatibility limits

The address mapping is empirical and potentially firmware-dependent. The
implementation handoff records these sources and observations:

- The inspected 1/2025-11 edition of the manufacturer's
  [Modbus data-point list 83807301](https://www.weishaupt.de/uploads/tx_weishaupt_documents/documents/83807301.pdf)
  documents legacy energy groups as unsigned 16-bit kWh and request register
  33103 as a percentage. It does not document 36701–36704.
- The [controller instructions 83805901, statistics section](https://www.weishaupt.de/uploads/tx_weishaupt_documents/documents/83805901.pdf#page=10)
  distinguish generated thermal energy and consumed electrical energy. That
  distinction does not establish the new Modbus addresses.
- A firsthand [WBB investigation in discussion 179](https://github.com/OStrama/weishaupt_modbus/discussions/179)
  reports input registers 36701–36704 as electrical today, yesterday, month,
  and year in integer kWh. This is evidence from another controller family,
  not a guarantee for all WAB firmware.
- A read-only probe of the user's WAB installation on 2026-09-08 at
  14:05:19 UTC returned `[0, 7, 26, 7997]` at 36101–36104 and
  `[0, 2, 10, 1916]` at 36701–36704. Firmware was not captured. This confirms
  accessibility on that installation, not every label or measurement boundary.

Controller-display comparison, exact model/firmware, local clock, and day
rollover validation remain required for a hardware-specific compatibility
claim. Month/year reset behavior is expected calendar behavior, not
exhaustively verified firmware behavior. Overflow and rollover details remain
unknown. It is also unknown whether the electrical counter includes compressor,
auxiliary heaters, circulation pumps, or controller consumption; do not call it
a dedicated whole-unit electricity meter. The
[`validation workflow`](../workflows/validation.md) defines the read-only
follow-up evidence to collect.

These counters provide energy, not instantaneous electrical power, automatic
COP, reconstructed fractional energy, or a daily historical archive. Neither
percentage request register 33103 nor the writable W-valued request/setpoint
at 40002 measures electrical input power. Deriving power or COP requires a
separate validated model and suitable measurement boundaries.

## Consumers and serialization

[`energy_reporting.py`](../../src/wab11/energy_reporting.py) provides the
energy serialization, CSV flattening, and text formatting used by
[`scripts/report.py`](../../scripts/report.py). It retains distinct legacy
groups and adds `energy.electrical` as four numeric period fields when present, or
JSON `null` when unavailable. Dataclass serialization adds the same optional
field, so consumers enforcing exact schemas must allow it. Text reports show
unavailability explicitly; CSV represents unavailable electrical values with
empty fields, not zero. Numeric zero remains present in all formats.
CSV append requires the current header schema. An existing CSV with the old
columns raises an error before appending; start a new file for the expanded
schema.

Usage and the full register surface are documented in
[`README.md`](../../README.md) and
[`variables-reference.md`](../../docs/variables-reference.md). The Home
Assistant integration, its existing entity identities and estimator, and
InfluxDB configuration are separate consumers requiring a later integration
change. Existing thermal history must not be relabeled as electrical energy.

Behavioral evidence is maintained in
[`test_electrical_energy.py`](../../tests/test_electrical_energy.py),
[`test_electrical_integration.py`](../../tests/test_electrical_integration.py),
fixture/report tests, and the opt-in live test, mapped in
[`code-relationships.md`](../code-relationships.md).
