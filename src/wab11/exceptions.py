"""
Custom exception hierarchy for the WAB11 library.

All exceptions inherit from WAB11Error for easy catching.
"""

from __future__ import annotations


class WAB11Error(Exception):
    """Base exception for all WAB11 library errors."""

    pass


class ConnectionError(WAB11Error):
    """Raised when connection to WAB11 fails or is lost."""

    pass


class ModbusResponseError(ConnectionError):
    """Raised when a controller returns a Modbus exception response.

    Args:
        function_code: Modbus function code returned by the controller.
        exception_code: Modbus exception code returned by the controller.
        operation: Human-readable description of the failed operation.
    """

    def __init__(
        self,
        *,
        function_code: int,
        exception_code: int,
        operation: str,
    ) -> None:
        self.function_code = function_code
        self.exception_code = exception_code
        self.operation = operation
        super().__init__(
            f"Modbus exception {exception_code} during {operation} "
            f"(function code {function_code})"
        )


class TimeoutError(ConnectionError):
    """Raised when a Modbus operation times out."""

    pass


class ValidationError(WAB11Error):
    """Raised when a value fails validation."""

    pass


class SafetyError(WAB11Error):
    """
    Raised when a safety-critical operation is not confirmed.

    This indicates the operation could potentially cause issues
    and requires explicit confirmation via confirmed=True.
    """

    pass


class RateLimitError(WAB11Error):
    """Raised when write rate limit is exceeded."""

    pass


class RegisterError(WAB11Error):
    """Base for register-related errors."""

    pass


class ReadOnlyError(RegisterError):
    """Raised when attempting to write a read-only register."""

    pass


class UnknownRegisterError(RegisterError):
    """Raised when referencing an unknown register name."""

    pass


class DeviceError(WAB11Error):
    """Raised when the WAB11 reports an error condition."""

    def __init__(self, error_code: int, message: str = "") -> None:
        self.error_code = error_code
        super().__init__(f"Device error {error_code}: {message}")


class DeviceWarning(WAB11Error):
    """Raised when the WAB11 reports a warning condition."""

    def __init__(self, warning_code: int, message: str = "") -> None:
        self.warning_code = warning_code
        super().__init__(f"Device warning {warning_code}: {message}")
