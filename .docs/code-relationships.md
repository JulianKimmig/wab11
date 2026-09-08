# WAB11 Code Relationships

This map records ownership and behavioral evidence for the package areas
affected by heating-circuit sizing and energy statistics. Public semantics are
defined in the
[`heating-circuit discovery contract`](contracts/heating-circuit-discovery.md),
the [`energy statistics contract`](contracts/energy-statistics.md), and
validation commands are defined in
[`workflows/validation.md`](workflows/validation.md).

| Responsibility | Source | Behavioral evidence |
| --- | --- | --- |
| Async client constructor, circuit collection, first-sync discovery, and circuit-index validation | [`src/wab11/client.py`](../src/wab11/client.py) | [`tests/test_client_behaviors.py`](../tests/test_client_behaviors.py) covers explicit validation, discovery termination, and error propagation; [`tests/test_preflight_fixes.py`](../tests/test_preflight_fixes.py) covers the initial auto-detect state and explicit-count write bounds |
| Structured Modbus exception-response preservation | [`src/wab11/connection.py`](../src/wab11/connection.py), [`src/wab11/exceptions.py`](../src/wab11/exceptions.py) | [`tests/test_connection_and_sync_client.py`](../tests/test_connection_and_sync_client.py) exercises connection reads/retries and exception types; discovery behavior is exercised through the structured exception in [`tests/test_client_behaviors.py`](../tests/test_client_behaviors.py) |
| Synchronous constructor forwarding | [`src/wab11/sync_client.py`](../src/wab11/sync_client.py) | [`tests/test_connection_and_sync_client.py`](../tests/test_connection_and_sync_client.py) verifies the explicit or omitted circuit-count value forwarded to `WAB11Client` |
| Public imports and package boundary | [`src/wab11/__init__.py`](../src/wab11/__init__.py), [`pyproject.toml`](../pyproject.toml) | Package tests import the clients and public exception hierarchy through these boundaries |
| Deterministic multi-circuit fixture behavior | [`tests/fixtures/fake_system.json`](../tests/fixtures/fake_system.json), [`tests/conftest.py`](../tests/conftest.py) | Existing model, read, write, and live-device tests pass an explicit fixture/device circuit count when deterministic sizing is required |
| Energy definitions and optional model | `ENERGY_REGISTERS` and `ALL_REGISTERS` in [`src/wab11/registers/definitions.py`](../src/wab11/registers/definitions.py); [`models/energy.py`](../src/wab11/models/energy.py) | [`tests/test_electrical_energy.py`](../tests/test_electrical_energy.py) verifies register identity/permissions, integer precision, optional model defaults, and legacy compatibility |
| Energy synchronization, optional failure handling, and polling | [`src/wab11/energy_sync.py`](../src/wab11/energy_sync.py), called by [`client.py`](../src/wab11/client.py); synchronous access through [`sync_client.py`](../src/wab11/sync_client.py) | [`tests/test_electrical_energy.py`](../tests/test_electrical_energy.py) covers successful/unsupported/failed reads, stale-data clearing, recovery, and resets; [`tests/test_electrical_integration.py`](../tests/test_electrical_integration.py) covers full-client fixture behavior, polling, and synchronous parity |
| Optional energy report schema | [`src/wab11/energy_reporting.py`](../src/wab11/energy_reporting.py), used by [`scripts/report.py`](../scripts/report.py) | [`tests/test_electrical_integration.py`](../tests/test_electrical_integration.py) covers distinct legacy/electrical data, absence in JSON/text/CSV, and safe rejection of an old CSV header; [`tests/test_report_script.py`](../tests/test_report_script.py) retains CLI coverage; [`tests/test_fake_system_fixture.py`](../tests/test_fake_system_fixture.py) uses realistic separate fixture values |
| Expected optional-block transport logging | [`src/wab11/connection.py`](../src/wab11/connection.py) | [`tests/test_electrical_integration.py`](../tests/test_electrical_integration.py) verifies exception 2 for `(36701, 4)` logs at debug while other requests/codes retain warnings; typed exceptions still propagate to the caller |
| Optional controller compatibility checks | [`tests/test_warm_live_device.py`](../tests/test_warm_live_device.py), [`tests/test_warm_energy.py`](../tests/test_warm_energy.py) | Opt-in read-only checks accept exception 2 for electrical registers; focused energy capture records UTC/raw values; display, firmware, and rollover evidence remains a separate manual validation step in [`validation.md`](workflows/validation.md) |
| Home Assistant consumer | [`submodules/hacs-wab11/custom_components/hacs_wab11`](../submodules/hacs-wab11/custom_components/hacs_wab11/) | The submodule's config-flow and lifecycle tests verify optional manual input, persisted detected count, and deterministic runtime construction; its public behavior is recorded in [`submodules/hacs-wab11/.docs/contracts/home-assistant.md`](../submodules/hacs-wab11/.docs/contracts/home-assistant.md) |

The dependency direction is transport exceptions to client discovery, then
client state to consumers. `WAB11Connection` does not decide how many circuits
exist. `WAB11Client` alone interprets a qualifying response while probing a
later sequential circuit. Consumers such as the synchronous adapter and Home
Assistant integration choose auto-detection or an explicit count through the
client constructor rather than implementing their own register probing.
