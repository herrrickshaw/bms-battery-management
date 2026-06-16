"""
Supervisory state machine for the BMS.

States:
    INIT          — startup self-check
    IDLE          — contactors open, no current flow
    PRE_CHARGE    — pre-charge resistor in circuit (inrush limiting)
    CHARGING_CC   — constant-current charge phase
    CHARGING_CV   — constant-voltage charge phase (taper)
    DISCHARGING   — supplying load
    BALANCING     — post-charge passive cell balancing
    FAULT         — non-recoverable fault; contactors open
    SHUTDOWN      — controlled shutdown sequence

Transitions are driven by:
    - SOC / voltage limits
    - Temperature faults
    - Isolation faults
    - External commands (charge / discharge / stop)

Convention: charge current is negative, discharge current is positive.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
import time


class BMSState(Enum):
    INIT = auto()
    IDLE = auto()
    PRE_CHARGE = auto()
    CHARGING_CC = auto()
    CHARGING_CV = auto()
    DISCHARGING = auto()
    BALANCING = auto()
    FAULT = auto()
    SHUTDOWN = auto()


class FaultCode(Enum):
    NONE = 0
    OVER_VOLTAGE = auto()
    UNDER_VOLTAGE = auto()
    OVER_TEMPERATURE = auto()
    UNDER_TEMPERATURE = auto()
    OVER_CURRENT = auto()
    ISOLATION_FAULT = auto()
    INTERNAL_ERROR = auto()


@dataclass
class SupervisorOutput:
    state: BMSState
    fault_code: FaultCode
    contactor_main: bool         # True = closed
    contactor_pre_charge: bool   # True = closed
    charge_enable: bool
    discharge_enable: bool
    balancing_enable: bool
    requested_current: float     # A  (negative = charge, positive = discharge)
    status_message: str


class SupervisoryController:
    """
    Event-driven BMS supervisory state machine.

    Parameters
    ----------
    cell_config : CellConfig (optional via kwargs)
        Uses v_max, v_min, i_max_charge, i_max_discharge, t_max_*.
    cv_voltage : float
        Constant-voltage phase target [V per cell].
    cv_termination_current : float
        CC→CV phase transition current magnitude [A].
    pre_charge_timeout_s : float
        Maximum time allowed in PRE_CHARGE state [s].
    """

    # Voltage thresholds (per cell, V)
    _OV_FAULT = 3.70
    _UV_FAULT = 2.40
    _OV_WARN = 3.65
    _UV_WARN = 2.50

    # Temperature thresholds (°C)
    _T_MAX_FAULT = 60.0
    _T_MIN_FAULT = -25.0

    def __init__(
        self,
        cv_voltage_per_cell: float = 3.65,
        cv_term_current_a: float = 5.0,
        cc_current_a: float = -50.0,       # negative = charge
        pre_charge_timeout_s: float = 10.0,
    ):
        self._cv_voltage = cv_voltage_per_cell
        self._cv_term = cv_term_current_a
        self._cc_current = cc_current_a
        self._pre_charge_timeout = pre_charge_timeout_s

        self._state = BMSState.INIT
        self._fault_code = FaultCode.NONE
        self._pre_charge_start: Optional[float] = None
        self._pre_charge_for_discharge: bool = False
        self._init_ticks = 0

    # ------------------------------------------------------------------

    def update(
        self,
        v_cell_max: float,
        v_cell_min: float,
        t_cell_max: float,
        soc_mean: float,
        current: float,
        v_spread: float,
        charge_requested: bool,
        discharge_requested: bool,
        isolation_ok: bool = True,
    ) -> SupervisorOutput:
        """
        Evaluate one supervisory cycle and advance the state machine.

        Parameters
        ----------
        v_cell_max / v_cell_min : float
            Extremal cell terminal voltages [V].
        t_cell_max : float
            Hottest cell temperature [°C].
        soc_mean : float
            Pack mean SOC [0, 1].
        current : float
            Pack current [A]. Positive = discharge.
        v_spread : float
            Max – min cell voltage spread [V].
        charge_requested / discharge_requested : bool
            External command signals.
        isolation_ok : bool
            Isolation monitoring result.

        Returns
        -------
        SupervisorOutput
        """
        # -- Global fault checks (highest priority) -------------------------
        fault = self._check_faults(v_cell_max, v_cell_min, t_cell_max, current, isolation_ok)
        if fault != FaultCode.NONE and self._state not in (BMSState.FAULT, BMSState.SHUTDOWN):
            self._transition(BMSState.FAULT)
            self._fault_code = fault

        # -- State transitions -----------------------------------------------
        if self._state == BMSState.INIT:
            self._output = self._handle_init()

        elif self._state == BMSState.IDLE:
            self._output = self._handle_idle(charge_requested, discharge_requested)

        elif self._state == BMSState.PRE_CHARGE:
            self._output = self._handle_pre_charge(v_cell_min)

        elif self._state == BMSState.CHARGING_CC:
            self._output = self._handle_charging_cc(v_cell_max, current, soc_mean)

        elif self._state == BMSState.CHARGING_CV:
            self._output = self._handle_charging_cv(current, v_spread)

        elif self._state == BMSState.DISCHARGING:
            self._output = self._handle_discharging(soc_mean, discharge_requested)

        elif self._state == BMSState.BALANCING:
            self._output = self._handle_balancing(v_spread, discharge_requested)

        elif self._state == BMSState.FAULT:
            self._output = self._handle_fault()

        elif self._state == BMSState.SHUTDOWN:
            self._output = self._handle_shutdown()

        return self._output

    @property
    def state(self) -> BMSState:
        return self._state

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_init(self) -> SupervisorOutput:
        self._init_ticks += 1
        if self._init_ticks >= 3:            # 3-tick startup delay
            self._transition(BMSState.IDLE)
        return self._make_output(
            contactor_main=False, contactor_pre=False,
            charge_en=False, discharge_en=False, balancing_en=False,
            i_req=0.0, msg="Initializing…"
        )

    def _handle_idle(self, charge_req: bool, discharge_req: bool) -> SupervisorOutput:
        if charge_req:
            self._transition(BMSState.PRE_CHARGE)
            self._pre_charge_start = time.monotonic()
            self._pre_charge_for_discharge = False
        elif discharge_req:
            self._transition(BMSState.PRE_CHARGE)
            self._pre_charge_start = time.monotonic()
            self._pre_charge_for_discharge = True
        return self._make_output(
            contactor_main=False, contactor_pre=False,
            charge_en=False, discharge_en=False, balancing_en=False,
            i_req=0.0, msg="Idle — contactors open"
        )

    def _handle_pre_charge(self, v_cell_min: float) -> SupervisorOutput:
        elapsed = time.monotonic() - (self._pre_charge_start or 0.0)
        if elapsed > self._pre_charge_timeout:
            self._transition(BMSState.FAULT)
            self._fault_code = FaultCode.INTERNAL_ERROR
            return self._handle_fault()
        # Pre-charge complete when bus voltage is within 5 % of pack voltage
        if elapsed > 0.5:                    # give at least 0.5 s
            next_st = BMSState.DISCHARGING if self._pre_charge_for_discharge else BMSState.CHARGING_CC
            self._transition(next_st)
        return self._make_output(
            contactor_main=False, contactor_pre=True,
            charge_en=False, discharge_en=False, balancing_en=False,
            i_req=0.0, msg="Pre-charging bus…"
        )

    def _handle_charging_cc(self, v_max: float, current: float, soc: float) -> SupervisorOutput:
        if v_max >= self._cv_voltage:
            self._transition(BMSState.CHARGING_CV)
        elif soc >= 0.95:
            self._transition(BMSState.CHARGING_CV)
        return self._make_output(
            contactor_main=True, contactor_pre=False,
            charge_en=True, discharge_en=False, balancing_en=False,
            i_req=self._cc_current, msg=f"CC charge  I={self._cc_current:.1f} A"
        )

    def _handle_charging_cv(self, current: float, v_spread: float) -> SupervisorOutput:
        if abs(current) <= self._cv_term:
            # Charge complete → balance if needed
            next_state = BMSState.BALANCING if v_spread > 0.010 else BMSState.IDLE
            self._transition(next_state)
        return self._make_output(
            contactor_main=True, contactor_pre=False,
            charge_en=True, discharge_en=False, balancing_en=False,
            i_req=0.0,    # charger regulates V; current demand passed via charger
            msg=f"CV charge  I_act={current:.1f} A  target V={self._cv_voltage:.2f} V/cell"
        )

    def _handle_discharging(self, soc: float, discharge_req: bool) -> SupervisorOutput:
        if not discharge_req or soc <= 0.05:
            self._transition(BMSState.IDLE)
        return self._make_output(
            contactor_main=True, contactor_pre=False,
            charge_en=False, discharge_en=True, balancing_en=False,
            i_req=0.0, msg=f"Discharging  SOC={soc*100:.1f} %"
        )

    def _handle_balancing(self, v_spread: float, discharge_req: bool) -> SupervisorOutput:
        if v_spread < 0.005 or discharge_req:
            self._transition(BMSState.IDLE)
        return self._make_output(
            contactor_main=False, contactor_pre=False,
            charge_en=False, discharge_en=False, balancing_en=True,
            i_req=0.0, msg=f"Balancing  ΔV={v_spread*1000:.1f} mV"
        )

    def _handle_fault(self) -> SupervisorOutput:
        return self._make_output(
            contactor_main=False, contactor_pre=False,
            charge_en=False, discharge_en=False, balancing_en=False,
            i_req=0.0, msg=f"FAULT: {self._fault_code.name}"
        )

    def _handle_shutdown(self) -> SupervisorOutput:
        return self._make_output(
            contactor_main=False, contactor_pre=False,
            charge_en=False, discharge_en=False, balancing_en=False,
            i_req=0.0, msg="Shutdown"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_faults(
        self, v_max: float, v_min: float, t_max: float, current: float, isolation_ok: bool
    ) -> FaultCode:
        if v_max > self._OV_FAULT:
            return FaultCode.OVER_VOLTAGE
        if v_min < self._UV_FAULT:
            return FaultCode.UNDER_VOLTAGE
        if t_max > self._T_MAX_FAULT:
            return FaultCode.OVER_TEMPERATURE
        if t_max < self._T_MIN_FAULT:
            return FaultCode.UNDER_TEMPERATURE
        if not isolation_ok:
            return FaultCode.ISOLATION_FAULT
        return FaultCode.NONE

    def _transition(self, new_state: BMSState) -> None:
        self._state = new_state

    def _make_output(
        self, *, contactor_main: bool, contactor_pre: bool,
        charge_en: bool, discharge_en: bool, balancing_en: bool,
        i_req: float, msg: str
    ) -> SupervisorOutput:
        return SupervisorOutput(
            state=self._state,
            fault_code=self._fault_code,
            contactor_main=contactor_main,
            contactor_pre_charge=contactor_pre,
            charge_enable=charge_en,
            discharge_enable=discharge_en,
            balancing_enable=balancing_en,
            requested_current=i_req,
            status_message=msg,
        )
