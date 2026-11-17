"""Unit tests for small helpers extracted from bms_controller / vehicles."""
from __future__ import annotations

import dataclasses

from bms.bms_controller import BMSController, _profile_attr
from bms.chemistries import LFP, NMC
from bms.supervisor import BMSState, FaultCode
from bms.vehicles import TWO_WHEELER, with_cell_config


def test_profile_attr_defaults_without_profile():
    assert _profile_attr(None, "t_fan_on_c", 35.0) == 35.0


def test_profile_attr_reads_profile_and_falls_back():
    assert _profile_attr(TWO_WHEELER, "t_fan_on_c", -1.0) == TWO_WHEELER.t_fan_on_c
    assert _profile_attr(TWO_WHEELER, "no_such_attr", 7) == 7


def test_with_cell_config_swaps_only_cell_config():
    cell = dataclasses.replace(NMC.cell_config, nominal_capacity_ah=42.0)
    out = with_cell_config(LFP, cell)
    assert out.cell_config is cell
    assert out.name == LFP.name and out.ocv_table is LFP.ocv_table
    assert out.float_voltage_v == LFP.float_voltage_v


def test_reset_fault_returns_supervisor_to_idle_with_no_fault():
    bms = BMSController(n_cells=4)
    bms._supervisor._fault_code = FaultCode.OVER_VOLTAGE
    bms._supervisor._transition(BMSState.FAULT)
    bms.reset_fault()
    assert bms.bms_state is BMSState.IDLE
    assert bms._supervisor._fault_code is FaultCode.NONE
