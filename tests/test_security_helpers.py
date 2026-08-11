from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

import pytest

from wab11.exceptions import (
    DeviceError,
    DeviceWarning,
    ReadOnlyError,
    SafetyError,
    UnknownRegisterError,
    ValidationError,
)
from wab11.security.audit import AuditEntry, AuditLog
from wab11.security.rate_limiter import RateLimiter
from wab11.security.validator import WriteValidator


class FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.debugs: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def debug(self, message: str) -> None:
        self.debugs.append(message)


def test_write_validator_happy_path_and_helpers() -> None:
    validator = WriteValidator(require_confirmation=False)

    raw, reg = validator.validate_write("hk1_setpoint_comfort", 21.5)

    assert raw == 215
    assert reg.name == "hk1_setpoint_comfort"
    assert validator.is_critical("system_mode") is True
    assert validator.is_critical("hk1_mode") is False
    assert validator.get_register_limits("hk1_setpoint_comfort") == (150, 300)
    assert validator.critical_registers == {"system_mode", "power_request"}


def test_write_validator_error_paths_and_bulk_errors() -> None:
    validator = WriteValidator()

    with pytest.raises(UnknownRegisterError):
        validator.validate_write("missing_register", 1)

    with pytest.raises(ReadOnlyError):
        validator.validate_write("outdoor_temp_1", 20.0)

    with pytest.raises(SafetyError):
        validator.validate_write("system_mode", 1)

    with pytest.raises(ValidationError, match="above maximum"):
        validator.validate_write("hk1_setpoint_comfort", 35.0)

    with pytest.raises(ValidationError, match="below minimum"):
        validator.validate_write("ww_push_minutes", -1)

    with pytest.raises(ValidationError, match="Cannot encode"):
        validator.validate_write("hk1_setpoint_comfort", object())

    with pytest.raises(ValidationError, match="Bulk validation failed"):
        validator.validate_bulk_write(
            {
                "system_mode": 1,
                "outdoor_temp_1": 20.0,
                "missing_register": 1,
            }
        )

    validated = validator.validate_bulk_write(
        {"ww_push_minutes": 5, "ww_normal": 50.0},
        confirmed=True,
    )
    assert [name for name, _, _ in validated] == ["ww_push_minutes", "ww_normal"]

    with pytest.raises(UnknownRegisterError):
        validator.get_register_limits("missing_register")


def test_rate_limiter_cooldown_global_and_register_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = 1000.0
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        nonlocal current_time
        sleep_calls.append(seconds)
        current_time += seconds

    monkeypatch.setattr("wab11.security.rate_limiter.time.time", lambda: current_time)
    monkeypatch.setattr("wab11.security.rate_limiter.asyncio.sleep", fake_sleep)

    limiter = RateLimiter(
        global_limit=2, per_register_limit=2, cooldown=1.0, window=10.0
    )

    async def exercise() -> None:
        await limiter.acquire("hk1")
        assert limiter.can_write_immediately("hk1") is False
        assert pytest.approx(limiter.get_wait_time("hk1"), rel=1e-6) == 1.0

        await limiter.acquire("hk1")
        assert sleep_calls[0] == 1.0

        await limiter.acquire("hk2")
        assert sleep_calls[1] > 9.0
        assert len(limiter._global_writes) == 2
        assert limiter.get_stats()["register_counts"] == {"hk1": 1, "hk2": 1}

        limiter.reset()
        assert limiter.can_write_immediately("hk1") is True
        assert limiter.get_stats()["global_writes"] == 0

    asyncio.run(exercise())


def test_rate_limiter_cleanup_and_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wab11.security.rate_limiter.time.time", lambda: 20.0)
    limiter = RateLimiter(
        global_limit=9, per_register_limit=2, cooldown=2.5, window=10.0
    )
    limiter._global_writes = [1.0, 15.0, 19.0]
    limiter._register_writes = defaultdict(list, {"hk1": [15.0, 18.0]})

    assert limiter.global_limit == 9
    assert limiter.per_register_limit == 2
    assert limiter.cooldown == 2.5
    assert limiter._cleanup_old_writes(limiter._global_writes) == [15.0, 19.0]
    assert limiter.get_wait_time("hk1") == 5.0


def test_audit_log_operations_and_export() -> None:
    log = AuditLog(max_entries=3)
    fake_logger = FakeLogger()
    log._logger = fake_logger

    ok_write = log.log_write("system_mode", 0, 1, success=True)
    failed_write = log.log_write(
        "power_request", 1000, 2000, success=False, error="boom"
    )
    failed_read = log.log_read("outdoor_temp_1", None, success=False, error="timeout")
    success_read = log.log_read("outdoor_temp_2", 42, success=True)

    assert len(log) == 3
    recent = log.get_recent(2)
    assert recent == [failed_write, failed_read] or recent == [
        failed_read,
        success_read,
    ]
    assert log.get_writes() == [failed_write]
    assert log.get_writes(register="power_request") == [failed_write]
    assert log.get_by_register("outdoor_temp_2") == [success_read]
    assert log.get_failures() == [failed_write, failed_read]
    assert list(iter(log)) == log.get_recent(10)
    exported = log.export()
    assert exported[-1]["register"] == "outdoor_temp_2"
    assert fake_logger.infos
    assert fake_logger.warnings
    assert fake_logger.debugs == ["READ FAILED outdoor_temp_1: timeout"]
    assert "WRITE system_mode" in repr(ok_write)
    assert "READ outdoor_temp_2" in repr(success_read)

    now = datetime.now()
    assert log.get_writes(since=now + timedelta(days=1)) == []
    assert log.get_failures(since=now + timedelta(days=1)) == []

    log.clear()
    assert len(log) == 0


def test_exception_messages() -> None:
    assert "Device error 7" in str(DeviceError(7, "fault"))
    assert "Device warning 8" in str(DeviceWarning(8, "warn"))
    entry = AuditEntry(datetime.now(), "read", "r", None, 1, True)
    assert "READ r: 1" in repr(entry)
