# Validation Workflow

The package test suite is configured by [`pytest.ini`](../../pytest.ini) and
the development environment is managed by `uv` through
[`pyproject.toml`](../../pyproject.toml) and [`uv.lock`](../../uv.lock). The
repository-level validation command is:

```bash
uv run pytest
```

Heating-circuit count behavior is split across focused behavioral tests:

- [`tests/test_client_behaviors.py`](../../tests/test_client_behaviors.py)
  verifies constructor validation, sequential auto-detection, the exception
  code 10 boundary, and propagation of other failures.
- [`tests/test_preflight_fixes.py`](../../tests/test_preflight_fixes.py)
  verifies the empty pre-discovery collection and explicit-count bounds used by
  circuit write operations.
- [`tests/test_connection_and_sync_client.py`](../../tests/test_connection_and_sync_client.py)
  verifies preservation of Modbus response information by the transport and
  forwarding of optional circuit counts through the synchronous adapter.
- Fixture-backed tests pass explicit counts where their register coverage must
  remain deterministic. The live-device test auto-detects when
  `--warm-heating-circuits` is omitted and accepts `1` through `5` as a manual
  diagnostic override.

[`py_test.yml`](../../.github/workflows/py_test.yml) runs `uv run pytest` on
Python 3.11, 3.12, and 3.13 across Linux, Windows, and macOS for pushes to
`dev` and `test`. [`version_publish_main.yml`](../../.github/workflows/version_publish_main.yml)
runs the same package tests before building and publishing on `main` or
`master`. The public behavior those checks protect is recorded in the
[`heating-circuit discovery contract`](../contracts/heating-circuit-discovery.md).
