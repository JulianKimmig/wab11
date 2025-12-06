"""
Digital inputs and SG-Ready state model for the WAB11.

Handles the digital input states and SG-Ready (Smart Grid) functionality
for demand response and grid interaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class InputFunction(IntEnum):
    """
    Possible functions assignable to digital inputs.

    These correspond to the configuration options in the
    WAB controller's input configuration menu.
    """

    DISABLED = 0
    EVU_LOCK = 1  # Grid operator lock
    ELEVATED_OPERATION = 2  # Increased operation
    HK_LOCK = 3  # Heating circuit lock
    HEATING_COOLING_SWITCH = 4  # Switch between heating/cooling
    HOT_WATER_STANDBY = 5
    HOT_WATER_SETBACK = 6
    HOT_WATER_NORMAL = 7
    HOT_WATER_PUSH = 8
    DEW_POINT_MONITOR = 9
    SYSTEM_STANDBY = 10
    COMPRESSOR_LOCK = 11


class SGReadyState(IntEnum):
    """
    SG-Ready combined state (from SGR1 and SGR2 inputs).

    The SG-Ready interface uses two binary inputs to represent
    four operating states for smart grid interaction.
    """

    NORMAL = 0  # SGR1=0, SGR2=0 - Normal operation
    EVU_LOCK = 1  # SGR1=1, SGR2=0 - Grid operator lock (reduced/off)
    RECOMMENDED = 2  # SGR1=0, SGR2=1 - Increased operation recommended
    MAXIMUM = 3  # SGR1=1, SGR2=1 - Maximum operation (PV surplus)


@dataclass
class InputsState:
    """
    Digital inputs and SG-Ready state model.

    Input registers: 35xxx (current status)
    Holding registers: 45xxx (configuration)

    The WAB11 has multiple digital inputs:
    - SGR1, SGR2: SG-Ready inputs for smart grid
    - H1.2-H1.5: General purpose inputs on expansion module
    - DE1, DE2: Digital inputs on controller

    Attributes:
        sg_ready_1: SG-Ready input 1 state
        sg_ready_2: SG-Ready input 2 state
        input_h12: Input H1.2 state
        input_h13: Input H1.3 state
        input_h14: Input H1.4 state
        input_h15: Input H1.5 state
        input_de1: Digital input DE1 state
        input_de2: Digital input DE2 state
        config_sgr1: Function assigned to SGR1
        config_sgr2: Function assigned to SGR2
        config_h12-h15: Functions assigned to H1.x inputs
        config_de1-de2: Functions assigned to DE inputs
    """

    # Input registers (current status)
    sg_ready_1: bool = False
    sg_ready_2: bool = False
    input_h12: bool = False
    input_h13: bool = False
    input_h14: bool = False
    input_h15: bool = False
    input_de1: bool = False
    input_de2: bool = False

    # Holding registers (configuration)
    config_sgr1: int = 0
    config_sgr2: int = 0
    config_h12: int = 0
    config_h13: int = 0
    config_h14: int = 0
    config_h15: int = 0
    config_de1: int = 0
    config_de2: int = 0

    @property
    def sg_ready_state(self) -> SGReadyState:
        """
        Get combined SG-Ready state.

        The state is determined by combining SGR1 and SGR2:
        - 0 (00): Normal operation
        - 1 (01): EVU lock (grid operator request to reduce)
        - 2 (10): Increased operation recommended
        - 3 (11): Maximum operation (e.g., PV surplus)

        Returns:
            Combined SGReadyState enum value
        """
        value = (int(self.sg_ready_2) << 1) | int(self.sg_ready_1)
        return SGReadyState(value)

    @property
    def is_evu_lock(self) -> bool:
        """Check if EVU (grid operator) lock is active."""
        return self.sg_ready_state == SGReadyState.EVU_LOCK

    @property
    def is_sg_maximum(self) -> bool:
        """Check if SG-Ready maximum mode is active (PV surplus)."""
        return self.sg_ready_state == SGReadyState.MAXIMUM

    @property
    def is_sg_recommended(self) -> bool:
        """Check if SG-Ready recommends increased operation."""
        return self.sg_ready_state == SGReadyState.RECOMMENDED

    @property
    def is_sg_normal(self) -> bool:
        """Check if SG-Ready is in normal mode."""
        return self.sg_ready_state == SGReadyState.NORMAL

    @property
    def any_input_active(self) -> bool:
        """Check if any digital input is currently active."""
        return any(
            [
                self.sg_ready_1,
                self.sg_ready_2,
                self.input_h12,
                self.input_h13,
                self.input_h14,
                self.input_h15,
                self.input_de1,
                self.input_de2,
            ]
        )

    def get_active_inputs(self) -> list[str]:
        """
        Get list of currently active input names.

        Returns:
            List of active input names (e.g., ['SGR1', 'DE1'])
        """
        active = []
        if self.sg_ready_1:
            active.append("SGR1")
        if self.sg_ready_2:
            active.append("SGR2")
        if self.input_h12:
            active.append("H1.2")
        if self.input_h13:
            active.append("H1.3")
        if self.input_h14:
            active.append("H1.4")
        if self.input_h15:
            active.append("H1.5")
        if self.input_de1:
            active.append("DE1")
        if self.input_de2:
            active.append("DE2")
        return active

    def __repr__(self) -> str:
        sg_state = self.sg_ready_state.name
        active = self.get_active_inputs()
        active_str = ", ".join(active) if active else "none"
        return f"InputsState(sg_ready={sg_state}, active=[{active_str}])"

