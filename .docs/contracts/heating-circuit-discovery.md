# Heating-Circuit Count and Discovery Contract

This contract applies to `WAB11Client` and the `WAB11SyncClient` adapter. Its
implementation ownership is described in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md), and behavioral tests are mapped in
[`../code-relationships.md`](../code-relationships.md).

## Constructor input

`n_heating_circuits` accepts an integer from `1` through `5`, inclusive, or
`None`. The default is `None`.

- An explicit integer fixes the collection size immediately. The client
  creates exactly that many sequential models, and synchronization reads
  exactly those circuit blocks. Values outside `1..5` raise `ValidationError`.
- `None`, whether passed explicitly or supplied by omission, enables automatic
  detection. Before the first circuit synchronization, `heating_circuits` is
  empty. The first circuit synchronization discovers the count and retains it;
  later synchronizations update the retained models rather than probing again.
- `WAB11SyncClient` forwards the value unchanged to its async client, including
  `None`.

Callers that already know the controller layout or need deterministic reads
without probing may use an explicit value. Integrations that auto-detect once
may persist the resulting `len(client.heating_circuits)` and use that explicit
value for later client instances.

## Sequential auto-detection

Auto-detection probes circuit register blocks in order from circuit 1 through
circuit 5. A circuit is appended only after its normal input and holding reads
complete successfully. Detection has no gap-skipping behavior: the first
qualifying absent-block response ends the sequential list.

The only response treated as the end of the list is a
`ModbusResponseError` whose `exception_code` is `10`, received while probing a
later circuit (`2..5`). A successful fifth circuit completes discovery without
an absent-block probe. Circuit 1 must always synchronize successfully, so code
10 on circuit 1 is an error rather than an empty-controller result.

Every other failure propagates, including timeouts, connection errors, generic
Modbus failures, and `ModbusResponseError` values with exception codes other
than 10. A failure must not be converted into a shorter circuit list.

## Structured Modbus response errors

When `pymodbus` returns an error response for an input or holding-register
read, the connection layer raises `ModbusResponseError`. The exception retains
the controller's `function_code`, `exception_code`, and a description of the
failed operation, and remains within the package's `ConnectionError` /
`WAB11Error` hierarchy. Read retries must preserve this structured exception
as the final failure so discovery can distinguish the one supported
end-of-list response from all other failures.

The executable contract is covered by
[`tests/test_client_behaviors.py`](../../tests/test_client_behaviors.py),
[`tests/test_preflight_fixes.py`](../../tests/test_preflight_fixes.py), and
[`tests/test_connection_and_sync_client.py`](../../tests/test_connection_and_sync_client.py).
The validation suite is described in
[`../workflows/validation.md`](../workflows/validation.md).
