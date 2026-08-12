# WAB11 Code Relationships

This map records ownership and behavioral evidence for the package areas
affected by heating-circuit sizing. Public semantics are defined in the
[`heating-circuit discovery contract`](contracts/heating-circuit-discovery.md),
and validation commands are defined in
[`workflows/validation.md`](workflows/validation.md).

| Responsibility | Source | Behavioral evidence |
| --- | --- | --- |
| Async client constructor, circuit collection, first-sync discovery, and circuit-index validation | [`src/wab11/client.py`](../src/wab11/client.py) | [`tests/test_client_behaviors.py`](../tests/test_client_behaviors.py) covers explicit validation, discovery termination, and error propagation; [`tests/test_preflight_fixes.py`](../tests/test_preflight_fixes.py) covers the initial auto-detect state and explicit-count write bounds |
| Structured Modbus exception-response preservation | [`src/wab11/connection.py`](../src/wab11/connection.py), [`src/wab11/exceptions.py`](../src/wab11/exceptions.py) | [`tests/test_connection_and_sync_client.py`](../tests/test_connection_and_sync_client.py) exercises connection reads/retries and exception types; discovery behavior is exercised through the structured exception in [`tests/test_client_behaviors.py`](../tests/test_client_behaviors.py) |
| Synchronous constructor forwarding | [`src/wab11/sync_client.py`](../src/wab11/sync_client.py) | [`tests/test_connection_and_sync_client.py`](../tests/test_connection_and_sync_client.py) verifies the explicit or omitted circuit-count value forwarded to `WAB11Client` |
| Public imports and package boundary | [`src/wab11/__init__.py`](../src/wab11/__init__.py), [`pyproject.toml`](../pyproject.toml) | Package tests import the clients and public exception hierarchy through these boundaries |
| Deterministic multi-circuit fixture behavior | [`tests/fixtures/fake_system.json`](../tests/fixtures/fake_system.json), [`tests/conftest.py`](../tests/conftest.py) | Existing model, read, write, and live-device tests pass an explicit fixture/device circuit count when deterministic sizing is required |
| Home Assistant consumer | [`submodules/hacs-wab11/custom_components/hacs_wab11`](../submodules/hacs-wab11/custom_components/hacs_wab11/) | The submodule's config-flow and lifecycle tests verify optional manual input, persisted detected count, and deterministic runtime construction; its public behavior is recorded in [`submodules/hacs-wab11/.docs/contracts/home-assistant.md`](../submodules/hacs-wab11/.docs/contracts/home-assistant.md) |

The dependency direction is transport exceptions to client discovery, then
client state to consumers. `WAB11Connection` does not decide how many circuits
exist. `WAB11Client` alone interprets a qualifying response while probing a
later sequential circuit. Consumers such as the synchronous adapter and Home
Assistant integration choose auto-detection or an explicit count through the
client constructor rather than implementing their own register probing.
