"""
Write validation for WAB11 Modbus operations.

Ensures all write operations are within documented limits
and safety rules are enforced.
"""

from __future__ import annotations

from typing import Any, Tuple

from ..exceptions import (
    ReadOnlyError,
    SafetyError,
    UnknownRegisterError,
    ValidationError,
)
from ..registers.definitions import ALL_REGISTERS, DataFormat, RegisterDef
from ..registers.formats import FormatCodec


class WriteValidator:
    """
    Validates write operations against documented limits and safety rules.

    Security principles:
    1. Only known, writable registers can be written
    2. All values must be within documented min/max bounds
    3. Safety-critical operations require explicit confirmation
    4. Temperature values are validated against safe ranges

    Usage:
        validator = WriteValidator()
        raw_value, reg_def = validator.validate_write("hk1_setpoint_comfort", 21.5)
    """

    # Registers that require explicit confirmation before writing
    CRITICAL_REGISTERS = {
        "system_mode",  # Changing system mode affects entire system
        "power_request",  # Direct power control
    }

    # Additional temperature limits beyond register-level limits
    # These provide defense-in-depth for common setpoints
    TEMPERATURE_LIMITS = {
        # Heating setpoints: reasonable room temperatures
        "setpoint_comfort": (150, 300),  # 15-30°C
        "setpoint_normal": (150, 300),  # 15-30°C
        "setpoint_setback": (100, 250),  # 10-25°C
        # Hot water: safe water temperatures
        "ww_normal": (300, 650),  # 30-65°C
        "ww_setback": (200, 600),  # 20-60°C
    }

    def __init__(self, require_confirmation: bool = True) -> None:
        """
        Initialize validator.

        Args:
            require_confirmation: If True, critical register writes require
                                 explicit confirmation via confirmed=True
        """
        self._require_confirmation = require_confirmation

    @property
    def critical_registers(self) -> set[str]:
        """Get set of registers requiring confirmation."""
        return self.CRITICAL_REGISTERS.copy()

    def validate_write(
        self,
        register_name: str,
        value: Any,
        confirmed: bool = False,
    ) -> Tuple[int, RegisterDef]:
        """
        Validate a write operation.

        Checks that the register exists, is writable, and the value
        is within allowed bounds. For critical registers, requires
        explicit confirmation.

        Args:
            register_name: Name of the register to write
            value: Value to write (Python type, will be encoded)
            confirmed: If True, confirms critical operation

        Returns:
            Tuple of (raw_value, register_definition)

        Raises:
            UnknownRegisterError: If register name not found
            ReadOnlyError: If register is not writable
            SafetyError: If critical operation not confirmed
            ValidationError: If value out of bounds
        """
        # Check register exists
        if register_name not in ALL_REGISTERS:
            raise UnknownRegisterError(f"Unknown register: {register_name}")

        reg = ALL_REGISTERS[register_name]

        # Check register is writable
        if not reg.writable:
            raise ReadOnlyError(
                f"Register '{register_name}' is read-only and cannot be written"
            )

        # Check critical operations
        if register_name in self.CRITICAL_REGISTERS:
            if self._require_confirmation and not confirmed:
                raise SafetyError(
                    f"Writing to '{register_name}' requires explicit confirmation. "
                    "This is a safety-critical operation. "
                    "Pass confirmed=True to proceed."
                )

        # Encode value
        try:
            raw_value = FormatCodec.encode(reg.fmt, value)
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"Cannot encode value '{value}' for register '{register_name}': {e}"
            ) from e

        # Check register-level min/max bounds
        if reg.min_value is not None and raw_value < reg.min_value:
            raise ValidationError(
                f"Value {value} (raw={raw_value}) is below minimum "
                f"{reg.min_value} for register '{register_name}'"
            )

        if reg.max_value is not None and raw_value > reg.max_value:
            raise ValidationError(
                f"Value {value} (raw={raw_value}) is above maximum "
                f"{reg.max_value} for register '{register_name}'"
            )

        # Additional temperature validation
        self._validate_temperature_limits(register_name, reg, raw_value, value)

        return raw_value, reg

    def _validate_temperature_limits(
        self,
        register_name: str,
        reg: RegisterDef,
        raw_value: int,
        original_value: Any,
    ) -> None:
        """
        Apply additional temperature safety limits.

        This provides defense-in-depth for common temperature setpoints,
        ensuring values stay within reasonable ranges even if register
        limits are more permissive.
        """
        if reg.fmt != DataFormat.TEMPERATURE:
            return

        for pattern, (min_raw, max_raw) in self.TEMPERATURE_LIMITS.items():
            if pattern in register_name:
                if not (min_raw <= raw_value <= max_raw):
                    min_temp = min_raw / 10.0
                    max_temp = max_raw / 10.0
                    raise ValidationError(
                        f"Temperature {original_value}°C is outside safe range "
                        f"{min_temp}-{max_temp}°C for '{register_name}'"
                    )
                break

    def validate_bulk_write(
        self,
        writes: dict[str, Any],
        confirmed: bool = False,
    ) -> list[Tuple[str, int, RegisterDef]]:
        """
        Validate multiple writes atomically.

        All writes are validated before any are returned.
        If any validation fails, an error is raised with all failures.

        Args:
            writes: Dictionary mapping register names to values
            confirmed: If True, confirms critical operations

        Returns:
            List of (register_name, raw_value, register_def) tuples

        Raises:
            ValidationError: If any validation fails (includes all errors)
        """
        validated = []
        errors = []

        for name, value in writes.items():
            try:
                raw, reg = self.validate_write(name, value, confirmed)
                validated.append((name, raw, reg))
            except (
                ValidationError,
                SafetyError,
                UnknownRegisterError,
                ReadOnlyError,
            ) as e:
                errors.append(f"  - {name}: {e}")

        if errors:
            error_list = "\n".join(errors)
            raise ValidationError(f"Bulk validation failed:\n{error_list}")

        return validated

    def is_critical(self, register_name: str) -> bool:
        """
        Check if a register is safety-critical.

        Args:
            register_name: Name of the register

        Returns:
            True if the register requires confirmation
        """
        return register_name in self.CRITICAL_REGISTERS

    def get_register_limits(
        self,
        register_name: str,
    ) -> Tuple[int | None, int | None]:
        """
        Get the min/max limits for a register.

        Args:
            register_name: Name of the register

        Returns:
            Tuple of (min_value, max_value), either may be None

        Raises:
            UnknownRegisterError: If register not found
        """
        if register_name not in ALL_REGISTERS:
            raise UnknownRegisterError(f"Unknown register: {register_name}")

        reg = ALL_REGISTERS[register_name]
        return (reg.min_value, reg.max_value)
