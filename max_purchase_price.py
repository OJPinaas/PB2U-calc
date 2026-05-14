"""Utilities for estimating maximum allowable battery acquisition price.

The B2U model reports NPV for a given component purchase price.  For thesis
analysis it is often more informative to invert this relation and estimate the
maximum purchase price that gives zero total NPV.  Negative values are allowed:
a negative maximum purchase price means the repurposing operator would need to
be paid to take the battery under the selected assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import b2u
from Batterycomponents import Batterymodule, pack

Component = Batterymodule | pack


@dataclass(frozen=True)
class MaxPurchasePriceResult:
    """NPV-based maximum purchase price result in scenario currency."""

    maximum_purchase_price_per_unit: float
    maximum_purchase_price_per_kwh_nameplate: float
    npv_at_zero_purchase_price: float
    npv_at_current_purchase_price: float
    current_purchase_price_per_unit: float
    current_purchase_price_per_kwh_nameplate: float
    feasible_at_zero_purchase_price: bool
    solver_iterations: int


@dataclass(frozen=True)
class NpvBreakEvenSellingPriceResult:
    """NPV-based break-even selling price result in scenario currency per kWh."""

    npv_break_even_selling_price_per_kwh: float
    npv_at_zero_selling_price: float
    npv_at_current_selling_price: float
    current_selling_price_per_kwh: float
    feasible_at_current_selling_price: bool
    solver_iterations: int


def _nameplate_energy(component: Component) -> float:
    return float(component.nameplate_energy_kWh)


def _purchase_price(component: Component) -> float:
    return float(component.purchase_price)


def _clone_module_with_purchase_price(
    module: Batterymodule,
    purchase_price_per_kwh_nameplate: float,
) -> Batterymodule:
    return Batterymodule(
        nameplate_energy_kWh=module.nameplate_energy_kWh,
        weight_kg=module.weight_kg,
        purchase_price=purchase_price_per_kwh_nameplate * module.nameplate_energy_kWh,
        height_mm=module.height_mm,
        width_mm=module.width_mm,
        length_mm=module.length_mm,
        percent_remaining_energy=module.nominal_cell_soh,
        seriescells=module.seriescells,
        paralellcells=module.paralellcells,
        cell_fault_rate=module.cell_fault_rate,
        forced_selling_price_per_kWh=module.forced_selling_price_per_kWh,
        chemistry=module.chemistry,
        cell_soh_std=module.cell_soh_std,
        min_cell_soh=module.min_cell_soh,
        max_cell_soh=module.max_cell_soh,
        rng_seed=module.rng_seed,
    )


def clone_component_with_purchase_price(
    component: Component,
    purchase_price_per_kwh_nameplate: float,
) -> Component:
    """Return component clone with uniform purchase price per nameplate kWh."""
    if isinstance(component, Batterymodule):
        return _clone_module_with_purchase_price(
            component,
            purchase_price_per_kwh_nameplate,
        )

    cloned_strings = []
    for module_string in component.modules:
        cloned_strings.append([
            _clone_module_with_purchase_price(module, purchase_price_per_kwh_nameplate)
            for module in module_string
        ])
    return pack(cloned_strings)


def _total_npv(component: Component, scenario: b2u.B2UScenario) -> float:
    result = b2u.run_b2u_scenario(component, scenario).to_dict()
    currency = result["currency"].get("currency", "USD").lower()
    revenue_npv = result["revenue_npv"]
    return float(revenue_npv.get(f"total_npv_{currency}", revenue_npv["total_npv"]))


def solve_max_purchase_price(
    component: Component,
    scenario: b2u.B2UScenario,
    lower_per_kwh: float = -5000.0,
    upper_per_kwh: float = 5000.0,
    tolerance: float = 1e-3,
    max_iterations: int = 60,
) -> MaxPurchasePriceResult:
    """Estimate purchase price per nameplate kWh that gives zero NPV.

    The B2U model is effectively linear in acquisition price: purchase price
    enters as annual battery-unit cost and as year-0 upfront inventory cost.
    This function therefore estimates the NPV slope from two model evaluations
    rather than performing many repeated Monte Carlo evaluations.  This is much
    faster and avoids resampling reliability for every bisection step.

    Parameters are kept for backwards compatibility with the earlier bisection
    implementation.  Values are in scenario currency.
    """
    current_price_per_unit = _purchase_price(component)
    energy = _nameplate_energy(component)
    current_price_per_kwh = current_price_per_unit / energy

    current_npv = _total_npv(component, scenario)
    zero_component = clone_component_with_purchase_price(component, 0.0)
    zero_npv = _total_npv(zero_component, scenario)

    if abs(current_price_per_kwh) > 1e-12:
        slope = (current_npv - zero_npv) / current_price_per_kwh
    else:
        probe_price_per_kwh = 1.0
        probe_component = clone_component_with_purchase_price(
            component,
            probe_price_per_kwh,
        )
        probe_npv = _total_npv(probe_component, scenario)
        slope = (probe_npv - zero_npv) / probe_price_per_kwh

    if abs(slope) < 1e-12:
        max_price_per_kwh = float("nan")
    else:
        max_price_per_kwh = -zero_npv / slope

    return MaxPurchasePriceResult(
        maximum_purchase_price_per_unit=max_price_per_kwh * energy,
        maximum_purchase_price_per_kwh_nameplate=max_price_per_kwh,
        npv_at_zero_purchase_price=zero_npv,
        npv_at_current_purchase_price=current_npv,
        current_purchase_price_per_unit=current_price_per_unit,
        current_purchase_price_per_kwh_nameplate=current_price_per_kwh,
        feasible_at_zero_purchase_price=zero_npv >= 0.0,
        solver_iterations=2 if abs(current_price_per_kwh) > 1e-12 else 3,
    )


def _get_current_selling_price_per_kwh(
    component: Component,
    scenario: b2u.B2UScenario,
) -> float:
    """Return the effective selling price per kWh for the given component/scenario."""
    if scenario.economics.forced_selling_price_per_kwh is not None:
        return float(scenario.economics.forced_selling_price_per_kwh)
    if isinstance(component, Batterymodule):
        return float(component.forced_selling_price_per_kWh)
    return float(component.modules[0][0].forced_selling_price_per_kWh)


def _scenario_with_selling_price(
    scenario: b2u.B2UScenario,
    selling_price_per_kwh: float,
) -> b2u.B2UScenario:
    """Return a scenario clone with forced_selling_price_per_kwh set."""
    economics = replace(
        scenario.economics,
        forced_selling_price_per_kwh=selling_price_per_kwh,
    )
    return replace(scenario, economics=economics)


def _mean_sellable_energy_per_unit(component: Component, scenario: b2u.B2UScenario) -> float:
    """Return mean sellable energy per unit to check if solving is meaningful."""
    result = b2u.run_b2u_scenario(component, scenario)
    return float(result.reliability["mean_sellable_energy_kwh_per_unit"])


def solve_npv_break_even_selling_price(
    component: Component,
    scenario: b2u.B2UScenario,
    price_cap: float = 10_000.0,
    tolerance: float = 1.0,
    max_iterations: int = 60,
) -> NpvBreakEvenSellingPriceResult:
    """Estimate selling price per kWh that gives zero total NPV via bisection.

    NPV may be piecewise linear in selling price due to tax clipping
    (``max(0, profit) * tax_rate``) or other threshold effects in the model.
    This solver brackets the zero-crossing and bisects rather than
    extrapolating from two points.

    Algorithm
    ---------
    1. Evaluate NPV at selling price = 0.  If no sellable energy exists the NPV
       will not change when price increases; the function returns NaN.
    2. If NPV at zero price is already ≥ 0 the break-even price is ≤ 0; return
       0.0 (lowest meaningful non-negative price).
    3. Expand the upper bound geometrically until NPV ≥ 0 or the cap is
       reached.  Return NaN if the cap is reached without a sign change.
    4. Bisect the bracket ``[lo, hi]`` until ``hi - lo ≤ tolerance``.

    Parameters
    ----------
    price_cap:
        Upper bound for the bracket expansion.  The default of 10 000 is
        expressed in the scenario currency (NOK or USD per kWh).
    tolerance:
        Convergence criterion in scenario currency per kWh.
    max_iterations:
        Maximum bisection steps after the bracket is established.

    Returns NaN for ``npv_break_even_selling_price_per_kwh`` when:
    * sellable energy is zero (NPV insensitive to selling price), or
    * no positive price below ``price_cap`` produces non-negative NPV.
    """
    current_price_per_kwh = _get_current_selling_price_per_kwh(component, scenario)

    # Minimum probe price: large enough to produce a detectable NPV change even
    # for scenarios with very few kWh of sellable energy.
    _MIN_PROBE_PRICE = 10.0

    # ── step 1: evaluate at zero selling price ──────────────────────────────
    scenario_at_zero = _scenario_with_selling_price(scenario, 0.0)
    zero_npv = _total_npv(component, scenario_at_zero)
    iterations = 1

    # Evaluate at current price for reporting purposes
    scenario_at_current = _scenario_with_selling_price(scenario, current_price_per_kwh)
    current_npv = _total_npv(component, scenario_at_current)
    iterations += 1

    # Probe at a large price to detect whether NPV is sensitive to price.
    # If NPV does not change between zero and probe, there is no sellable
    # energy and the break-even price cannot be determined.
    probe_price = max(current_price_per_kwh, price_cap / _MIN_PROBE_PRICE, _MIN_PROBE_PRICE)
    scenario_at_probe = _scenario_with_selling_price(scenario, probe_price)
    probe_npv = _total_npv(component, scenario_at_probe)
    iterations += 1

    scale = max(abs(zero_npv), abs(probe_npv), 1.0)
    if abs(probe_npv - zero_npv) < 1e-6 * scale:
        # NPV is insensitive to selling price → no sellable energy
        return NpvBreakEvenSellingPriceResult(
            npv_break_even_selling_price_per_kwh=float("nan"),
            npv_at_zero_selling_price=zero_npv,
            npv_at_current_selling_price=current_npv,
            current_selling_price_per_kwh=current_price_per_kwh,
            feasible_at_current_selling_price=current_npv >= 0.0,
            solver_iterations=iterations,
        )

    # ── step 2: handle trivially feasible case ───────────────────────────────
    if zero_npv >= 0.0:
        return NpvBreakEvenSellingPriceResult(
            npv_break_even_selling_price_per_kwh=0.0,
            npv_at_zero_selling_price=zero_npv,
            npv_at_current_selling_price=current_npv,
            current_selling_price_per_kwh=current_price_per_kwh,
            feasible_at_current_selling_price=current_npv >= 0.0,
            solver_iterations=iterations,
        )

    # ── step 3: establish bracket [lo, hi] with NPV(lo) < 0 < NPV(hi) ───────
    lo, lo_npv = 0.0, zero_npv  # lo_npv < 0 by this point

    # Reuse probe evaluation if it already has NPV ≥ 0; otherwise expand.
    hi, hi_npv = probe_price, probe_npv
    while hi_npv < 0.0:
        if hi >= price_cap:
            return NpvBreakEvenSellingPriceResult(
                npv_break_even_selling_price_per_kwh=float("nan"),
                npv_at_zero_selling_price=zero_npv,
                npv_at_current_selling_price=current_npv,
                current_selling_price_per_kwh=current_price_per_kwh,
                feasible_at_current_selling_price=current_npv >= 0.0,
                solver_iterations=iterations,
            )
        hi = min(hi * 2.0, price_cap)
        hi_npv = _total_npv(component, _scenario_with_selling_price(scenario, hi))
        iterations += 1

    # ── step 4: bisect ───────────────────────────────────────────────────────
    for _ in range(max_iterations):
        if (hi - lo) <= tolerance:
            break
        mid = (lo + hi) / 2.0
        mid_npv = _total_npv(component, _scenario_with_selling_price(scenario, mid))
        iterations += 1
        if mid_npv < 0.0:
            lo, lo_npv = mid, mid_npv
        else:
            hi, hi_npv = mid, mid_npv

    break_even_price = (lo + hi) / 2.0

    return NpvBreakEvenSellingPriceResult(
        npv_break_even_selling_price_per_kwh=break_even_price,
        npv_at_zero_selling_price=zero_npv,
        npv_at_current_selling_price=current_npv,
        current_selling_price_per_kwh=current_price_per_kwh,
        feasible_at_current_selling_price=current_npv >= 0.0,
        solver_iterations=iterations,
    )


def max_purchase_price_to_dict(result: MaxPurchasePriceResult) -> dict[str, Any]:
    return {
        "maximum_purchase_price_per_unit": result.maximum_purchase_price_per_unit,
        "maximum_purchase_price_per_kwh_nameplate": (
            result.maximum_purchase_price_per_kwh_nameplate
        ),
        "npv_at_zero_purchase_price": result.npv_at_zero_purchase_price,
        "npv_at_current_purchase_price": result.npv_at_current_purchase_price,
        "current_purchase_price_per_unit": result.current_purchase_price_per_unit,
        "current_purchase_price_per_kwh_nameplate": (
            result.current_purchase_price_per_kwh_nameplate
        ),
        "feasible_at_zero_purchase_price": result.feasible_at_zero_purchase_price,
        "solver_iterations": result.solver_iterations,
    }
