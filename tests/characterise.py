"""Characterisation harness: deterministic digests of BMS simulation output.

``collect()`` runs seeded/deterministic simulations and returns a dict of
sha256 digests (console output, and float.hex() of every numeric result) so a
refactor can be proven bit-identical.  ``tests/golden/baseline.json`` was
generated from the pre-refactor code with ``python tests/characterise.py``.
"""
from __future__ import annotations

import contextlib
import dataclasses
import enum
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden" / "baseline.json"


def _walk(obj, out):
    """Flatten *obj* into a list of exact string tokens (floats as hex)."""
    if isinstance(obj, enum.Enum):
        out.append(f"{type(obj).__name__}.{obj.name}")
    elif isinstance(obj, bool) or obj is None or isinstance(obj, (str, int)):
        out.append(repr(obj))
    elif isinstance(obj, float) or hasattr(obj, "hex") and hasattr(obj, "is_integer"):
        out.append(float(obj).hex())
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            out.append(f.name)
            _walk(getattr(obj, f.name), out)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk(k, out)
            _walk(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, out)
    elif hasattr(obj, "tolist"):
        _walk(obj.tolist(), out)
    else:
        out.append(repr(obj))


def digest(obj) -> str:
    """sha256 over the exact flattened representation of *obj*."""
    toks: list = []
    _walk(obj, toks)
    return hashlib.sha256("\x1f".join(toks).encode()).hexdigest()


def _run(fn, *args, **kwargs):
    """Call *fn*, return sha256 of its stdout plus a digest of its return value."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ret = fn(*args, **kwargs)
    return {"stdout": hashlib.sha256(buf.getvalue().encode()).hexdigest(),
            "result": digest(_strip_profiles(ret))}


def _strip_profiles(ret):
    """Replace VehicleProfile/DrivingConditions values with their repr digest."""
    if isinstance(ret, dict):
        return {k: _strip_profiles(v) for k, v in ret.items()}
    if isinstance(ret, list):
        return [_strip_profiles(v) for v in ret]
    return ret


def collect() -> dict:
    """Run every characterised scenario; returns {scenario: digests}."""
    sys.path.insert(0, str(ROOT))
    from bms import simulation as sim
    from bms.vehicles import (TWO_WHEELER, FOUR_WHEELER_RETRO,
                              FOUR_WHEELER_MODERN, ELECTRIC_BUS, VEHICLE_REGISTRY)
    from bms.manufacturer_profiles import MANUFACTURER_REGISTRY, MANUFACTURER_DRIVING
    from bms.chemistries import CHEMISTRY_REGISTRY

    res: dict = {}
    res["profiles"] = {
        "vehicles": digest({k: repr(v) for k, v in VEHICLE_REGISTRY.items()}),
        "manufacturers": digest({k: repr(v) for k, v in MANUFACTURER_REGISTRY.items()}),
        "manufacturer_driving": digest({k: repr(v) for k, v in MANUFACTURER_DRIVING.items()}),
        "chemistries": digest({k: repr(v) for k, v in CHEMISTRY_REGISTRY.items()}),
        "vehicle_summaries": digest([p.summary() for p in VEHICLE_REGISTRY.values()]),
    }
    res["comparison_table"] = _run(sim.print_comparison_table)
    for name, prof in [("2w", TWO_WHEELER), ("4w_retro", FOUR_WHEELER_RETRO),
                       ("4w_modern", FOUR_WHEELER_MODERN), ("bus", ELECTRIC_BUS)]:
        res[f"charge_discharge_{name}"] = _run(
            sim._simulate_charge_discharge, prof, soc_init=0.3,
            charge_s=300, discharge_s=200, print_interval=100)
        res[f"degradation_{name}"] = _run(sim.simulate_degradation, prof, n_cycles=120)
        res[f"cold_{name}"] = _run(sim.simulate_cold_temperature, prof,
                                   ambient_temps_c=[25.0, -10.0, -30.0], max_discharge_s=60)
        res[f"driving_{name}"] = _run(sim.simulate_driving_degradation, prof,
                                      simulation_years=6)
    res["manufacturers"] = _run(_manufacturers_stripped, sim)
    res["two_wheeler_full"] = _run(sim.simulate_two_wheeler)
    for flag in ("--degradation", "--driving", "--manufacturers", "--datasets", "--cold"):
        res[f"cli{flag}"] = _run(_cli, sim, flag)
    for veh in ("2W", "4W_RETRO", "BUS"):
        res[f"cli--vehicle-{veh}"] = _run(_cli, sim, "--vehicle", veh)
    return res


def _cli(sim, *flags):
    """Run the simulation CLI as ``python -m bms.simulation <flags>``."""
    old = sys.argv
    sys.argv = ["bms.simulation", *flags]
    try:
        sim.main()
    finally:
        sys.argv = old


def _manufacturers_stripped(sim):
    out = sim.simulate_manufacturer_comparison(simulation_years=8)
    return {k: {kk: vv for kk, vv in v.items() if kk not in ("profile", "driving")}
            for k, v in out.items()}


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else GOLDEN
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(collect(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {out}")
