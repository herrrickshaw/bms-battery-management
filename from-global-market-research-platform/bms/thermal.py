"""
Thermal management and cooling fan controller.

Derived from IJAREEIE (2019) paper learnings:
  - Temperature is the most important parameter for internal resistance,
    charge/discharge rate, and battery life
  - Optimum: 25–33 °C (lead-acid); 15–35 °C (LFP)
  - Dangerous: above 50 °C (lead-acid), above 60 °C (LFP)
  - Fan can be configured for ON/OFF or variable PWM speed
  - Fan fault monitoring (no rotation when commanded = error)
  - Fan also heats battery when ambient is too cold

Fan speed control law (PWM 0–100 %):
    T < T_low_fan   → 0 %   (fan off, or heater on if T < T_heat)
    T_low_fan ≤ T < T_high  → linear ramp 20 % → 80 %
    T ≥ T_high      → 100 % (full speed)
"""

from dataclasses import dataclass
from enum import Enum, auto


class FanFaultCode(Enum):
    NONE = 0
    FAN_STUCK = auto()       # fan commanded but no speed feedback
    FAN_OVERCURRENT = auto() # fan draws too much current


@dataclass
class ThermalManagementState:
    temperature: float          # measured cell temperature [°C]
    fan_pwm_pct: float          # fan duty cycle [0–100 %]
    heater_on: bool             # true when warming is needed
    cooling_active: bool
    fan_fault: FanFaultCode
    cooling_mode: str           # "OFF" / "FAN_LOW" / "FAN_HIGH" / "HEATER"


class FanController:
    """
    PWM cooling fan controller for battery thermal management.

    Parameters
    ----------
    t_fan_on : float
        Temperature at which fan starts [°C].
    t_fan_full : float
        Temperature for full fan speed [°C].
    t_heat_on : float
        Temperature below which heater activates [°C].
    hysteresis : float
        Dead-band to avoid chattering [°C].
    """

    def __init__(
        self,
        t_fan_on: float = 35.0,
        t_fan_full: float = 50.0,
        t_heat_on: float = 5.0,
        hysteresis: float = 3.0,
    ):
        self._t_fan_on = t_fan_on
        self._t_fan_full = t_fan_full
        self._t_heat_on = t_heat_on
        self._hysteresis = hysteresis
        self._fan_on = False
        self._heater_on = False
        self._fault = FanFaultCode.NONE

    def update(
        self,
        temperature: float,
        fan_speed_feedback: float = None,  # % actual speed; None if no sensor
    ) -> ThermalManagementState:
        """
        Compute fan PWM command and heater state.

        Parameters
        ----------
        temperature : float
            Maximum cell temperature [°C].
        fan_speed_feedback : float or None
            Actual fan speed as % of commanded (from hall sensor).
            None means no feedback available.

        Returns
        -------
        ThermalManagementState
        """
        t = temperature

        # Fan hysteresis logic
        t_on = self._t_fan_on - (self._hysteresis if self._fan_on else 0.0)
        t_off = self._t_fan_on - self._hysteresis

        # Fan PWM calculation
        if t < t_off:
            fan_pwm = 0.0
            self._fan_on = False
        elif t >= self._t_fan_full:
            fan_pwm = 100.0
            self._fan_on = True
        elif t >= t_on:
            span = self._t_fan_full - self._t_fan_on
            fan_pwm = 20.0 + 80.0 * (t - self._t_fan_on) / span if span > 0 else 100.0
            fan_pwm = max(20.0, min(100.0, fan_pwm))
            self._fan_on = True
        else:
            fan_pwm = 0.0
            self._fan_on = False

        # Heater logic (warm battery when too cold)
        heater = t < self._t_heat_on

        # Fan fault detection
        self._fault = FanFaultCode.NONE
        if fan_speed_feedback is not None and fan_pwm > 30.0:
            if fan_speed_feedback < 10.0:
                self._fault = FanFaultCode.FAN_STUCK

        # Mode label
        if heater:
            mode = "HEATER"
        elif fan_pwm >= 80.0:
            mode = "FAN_HIGH"
        elif fan_pwm > 0.0:
            mode = "FAN_LOW"
        else:
            mode = "OFF"

        return ThermalManagementState(
            temperature=temperature,
            fan_pwm_pct=round(fan_pwm, 1),
            heater_on=heater,
            cooling_active=fan_pwm > 0.0,
            fan_fault=self._fault,
            cooling_mode=mode,
        )

    @property
    def has_fault(self) -> bool:
        return self._fault != FanFaultCode.NONE
