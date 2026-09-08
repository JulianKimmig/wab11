"""Strict external-device doubles shared by electrical energy behavior tests."""

from __future__ import annotations

from typing import Any

from conftest import ConfigBackedFakeConnection

from wab11.exceptions import ModbusResponseError


def modbus_error(code: int) -> ModbusResponseError:
    """Return an input-register exception response for the supplied integer code."""
    return ModbusResponseError(
        function_code=132, exception_code=code, operation="reading input registers"
    )


class EnergyConnection(ConfigBackedFakeConnection):
    """Fixture device with recorded reads and explicit per-address fault responses."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize fixture blocks from kwargs and empty read/fault records."""
        super().__init__(**kwargs)
        self.reads: list[tuple[int, int]] = []
        self.responses: dict[int, Any] = {}

    async def read_input_registers(self, address: int, count: int = 1) -> list[int]:
        """Read the requested block, or return/raise its explicitly configured fault."""
        self.reads.append((address, count))
        if address in self.responses:
            response = self.responses[address]
            if isinstance(response, BaseException):
                raise response
            return response
        return await super().read_input_registers(address, count)
