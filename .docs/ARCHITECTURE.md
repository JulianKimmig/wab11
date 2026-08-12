# WAB11 Package Architecture

The `wab11` package provides asynchronous and synchronous Python clients for a
Weishaupt WAB11 controller over Modbus TCP. Public clients and model types are
exported from [`src/wab11/__init__.py`](../src/wab11/__init__.py), and the
package metadata and runtime dependencies are declared in
[`pyproject.toml`](../pyproject.toml).

```text
application or integration
  -> WAB11Client (state synchronization, validation, writes, events)
     -> WAB11Connection (Modbus TCP, chunking, retries, response errors)
     -> model objects (system, circuits, hot water, heat pump, inputs, energy)
  -> WAB11SyncClient -> dedicated event loop -> WAB11Client
```

[`client.py`](../src/wab11/client.py) owns the controller-level behavior. It
coordinates register reads, decodes them into model objects, validates and
rate-limits writes, and publishes state-change events. Heating circuits are a
sequential, controller-dependent collection of one through five models. A
caller may provide the collection size explicitly or let the async client
discover it during the first circuit synchronization. The full invariant is
defined in the
[`heating-circuit discovery contract`](contracts/heating-circuit-discovery.md).

[`connection.py`](../src/wab11/connection.py) owns transport behavior. It
connects through `pymodbus`, splits reads according to the controller's
five-register limit, retries transient operations, and preserves structured
Modbus exception responses as package exceptions. Controller-level discovery
uses that structured exception data; it does not inspect error-message text.

[`sync_client.py`](../src/wab11/sync_client.py) is a synchronous adapter. It
retains constructor options, creates one `WAB11Client` during `connect()`, and
runs asynchronous operations on its owned event loop. Consequently, explicit
and automatic heating-circuit sizing have the same meaning in both client
interfaces.

The module-to-test relationships are recorded in
[`code-relationships.md`](code-relationships.md), and the authoritative test
commands and automation are recorded in
[`workflows/validation.md`](workflows/validation.md).
