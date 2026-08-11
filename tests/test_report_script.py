from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


REPORT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "report.py"


def load_report_module():
    spec = importlib.util.spec_from_file_location("report_script", REPORT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_defaults_to_five_heating_circuits() -> None:
    report = load_report_module()

    args = report.parse_args(["--host", "127.0.0.1"])

    assert args.n_heating_circuits == 5


def test_parse_args_accepts_custom_heating_circuit_count() -> None:
    report = load_report_module()

    args = report.parse_args(["--host", "127.0.0.1", "--heating-circuits", "3"])

    assert args.n_heating_circuits == 3


def test_parse_args_rejects_out_of_range_heating_circuit_count() -> None:
    report = load_report_module()

    with pytest.raises(SystemExit):
        report.parse_args(["--host", "127.0.0.1", "--heating-circuits", "6"])


def test_create_client_forwards_heating_circuit_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = load_report_module()
    captured: dict[str, object] = {}

    class FakeSyncClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(report, "WAB11SyncClient", FakeSyncClient)

    args = SimpleNamespace(
        host="127.0.0.1",
        port=1502,
        timeout=4.0,
        n_heating_circuits=2,
    )

    report.create_client(args)

    assert captured["args"] == ()
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 1502,
        "timeout": 4.0,
        "n_heating_circuits": 2,
        "require_write_confirmation": True,
        "enable_rate_limiting": False,
    }
