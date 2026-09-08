# Validation Workflow

The package test suite is configured by [`pytest.ini`](../../pytest.ini) and
the development environment is managed by `uv` through
[`pyproject.toml`](../../pyproject.toml) and [`uv.lock`](../../uv.lock). The
repository-level validation command is:

```bash
uv sync --group dev
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
[`heating-circuit discovery contract`](../contracts/heating-circuit-discovery.md)
and [`energy statistics contract`](../contracts/energy-statistics.md).

## Electrical energy checks

The ordinary suite uses fake Modbus connections; no controller or network is
required. Focused checks are:

```bash
uv run pytest tests/test_electrical_energy.py tests/test_electrical_integration.py tests/test_report_script.py tests/test_fake_system_fixture.py
```

The electrical tests cover exact input addresses and read-only permissions,
model compatibility, integer-kWh precision including zero and 65535, mandatory
and optional failure behavior, full-period publication, clearing old data,
recovery, calendar decreases, and synchronous/polling parity. Report tests
verify numeric data and explicit absence. The full suite remains necessary
to detect regressions in existing reads and consumers.

[`py_test.yml`](../../.github/workflows/py_test.yml) contains no separate lint
or type job. [`pyproject.toml`](../../pyproject.toml) declares Ruff, Flake8,
and mypy development dependencies; it does not configure mypy or Ruff.
The configured [`pre-commit hooks`](../../.pre-commit-config.yaml) run Ruff
lint/format and Flake8 with [`.flake8`](../../.flake8), plus YAML, whitespace,
lockfile, branch, and commit-message checks. Use non-mutating lint/format
checks on changed Python files during review, and record baseline failures
separately from new failures. Run `git diff --check` before committing.

## Optional read-only hardware validation

Inspect [`test_warm_live_device.py`](../../tests/test_warm_live_device.py) and
[`test_warm_energy.py`](../../tests/test_warm_energy.py) before opting into a
device run. The full test connects, synchronizes, and reads with a write guard.
The focused energy test reads only the legacy total and optional electrical
blocks and records raw responses and a UTC timestamp as test properties.
Supply connection settings explicitly; never commit a private
LAN address in an example or validation record:

```bash
uv run pytest tests/test_warm_live_device.py --run-warm --warm-host <host> --warm-port <port> --warm-unit-id <unit-id>
uv run pytest tests/test_warm_energy.py --run-warm --warm-host <host> --warm-port <port> --warm-unit-id <unit-id> --junitxml=/tmp/wab11-warm-energy.xml
```

The test accepts Illegal Data Address (exception 2) on optional electrical
registers as a valid compatibility outcome. Other electrical errors and
mandatory-register failures still fail. Successful access alone does not
validate measurement semantics. For a model/firmware compatibility claim,
record a sanitized note containing:

- Controller model, firmware, controller local date/time and timezone, and UTC
  observation timestamp.
- Raw 36101–36104 and 36701–36704 responses or the unsupported response.
- Corresponding displayed thermal and electrical period values; compare all
  four periods, validating yesterday across a date rollover if it is not shown.
- Observations across a day rollover, and month/year rollover when practical.
- Evidence identifying included electrical loads, or an explicit unknown
  boundary for compressor, auxiliary heat, pumps, and controller consumption.

The handoff's WAB probe established address accessibility only. Display
matching, exact firmware, measurement boundaries, and rollovers remain pending
until such observations are recorded. Ordinary fake tests cannot prove them.

## Version and publication boundary

Version changes keep `project.version` in
[`pyproject.toml`](../../pyproject.toml) and the public `__version__` in
[`src/wab11/_version.py`](../../src/wab11/_version.py) aligned, then regenerate
[`uv.lock`](../../uv.lock) with `uv lock`. Version 0.3.0 introduces optional
electrical energy statistics while retaining the legacy energy API.

The existing publish workflow reads the version already in
[`pyproject.toml`](../../pyproject.toml), tests, builds, publishes, and creates
a version tag on `main`/`master`. It does not automatically increment the
version. Implementing and committing this library feature does not publish a
release or deploy Home Assistant/InfluxDB changes. A release must use a version
chosen through the repository's release process; do not assume committing on
`dev` makes a new package available to consumers.
