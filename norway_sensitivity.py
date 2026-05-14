"""Broad one-parameter sensitivity runs for Norway-localized B2U cases.

The scenario presets in ``norway_scenarios.py`` are combined planning cases.
This script starts from the Norway base case and varies one parameter at a time.
It includes Leaf modules, simplified Leaf Gen 1 packs, and Tesla Model S-style
modules.

All monetary inputs are expressed in the scenario currency. For Norway cases,
this is NOK excluding VAT.  The B2U output keeps historical ``*_usd`` fields for
compatibility and also adds currency-specific aliases such as ``total_npv_nok``.
"""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import b2u
from Batterycomponents import Batterymodule, pack
from max_purchase_price import solve_npv_break_even_selling_price
from norway_scenarios import (
    NOK_PER_USD,
    make_leaf_gen1_module,
    make_leaf_gen1_pack,
    make_norway_scenario,
    make_tesla_model_s_gen1_module,
    nok_from_usd,
)

# Deliberately broad ranges for stress-testing. These are wider than the
# scenario-document ranges and should be interpreted as sensitivity bounds, not
# as all equally likely planning assumptions.
FAULT_RATE_RANGE = (1e-6, 1e-5, 5e-5, 2e-4, 1e-3, 5e-3, 1e-2)
LEAF_SOH_MEAN_RANGE = (0.50, 0.56, 0.60, 0.64, 0.68, 0.72, 0.80)
TESLA_SOH_MEAN_RANGE = (0.60, 0.70, 0.76, 0.80, 0.84, 0.88, 0.95)
SOH_STD_RANGE = (0.00, 0.02, 0.04, 0.08, 0.12, 0.16)
MIN_USABLE_SOH_RANGE = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80)
DISCOUNT_RATE_RANGE = (0.06, 0.08, 0.10, 0.12, 0.15, 0.18)

# Sensitivity sweeps run many model evaluations. Use a smaller Monte Carlo
# sample count by default for practical runtime, and increase this value for
# final thesis figures if needed.
SENSITIVITY_SAMPLES = 1_000
SENSITIVITY_SEED = 20260601

LEAF_PURCHASE_PRICE_USD_PER_KWH_RANGE = (0.0, 10.0, 20.0, 40.0, 60.0, 80.0)
TESLA_PURCHASE_PRICE_USD_PER_KWH_RANGE = (0.0, 15.0, 30.0, 45.0, 60.0, 90.0)
LEAF_SELLING_PRICE_USD_PER_KWH_RANGE = (50.0, 75.0, 100.0, 150.0, 200.0, 250.0)
TESLA_SELLING_PRICE_USD_PER_KWH_RANGE = (40.0, 55.0, 75.0, 100.0, 150.0, 200.0)

Component = Batterymodule | pack


def make_base_component(component_kind: str) -> Component:
    if component_kind == "leaf":
        return make_leaf_gen1_module("base")
    if component_kind == "leaf_pack":
        return make_leaf_gen1_pack("base")
    if component_kind == "tesla":
        return make_tesla_model_s_gen1_module("base")
    raise ValueError("component_kind must be 'leaf', 'leaf_pack', or 'tesla'")


def clone_module(module: Batterymodule, **overrides: float) -> Batterymodule:
    kwargs = {
        "nameplate_energy_kWh": module.nameplate_energy_kWh,
        "weight_kg": module.weight_kg,
        "purchase_price": module.purchase_price,
        "height_mm": module.height_mm,
        "width_mm": module.width_mm,
        "length_mm": module.length_mm,
        "percent_remaining_energy": module.nominal_cell_soh,
        "seriescells": module.seriescells,
        "paralellcells": module.paralellcells,
        "cell_fault_rate": module.cell_fault_rate,
        "forced_selling_price_per_kWh": module.forced_selling_price_per_kWh,
        "chemistry": module.chemistry,
        "cell_soh_std": module.cell_soh_std,
        "min_cell_soh": module.min_cell_soh,
        "max_cell_soh": module.max_cell_soh,
    }
    kwargs.update(overrides)
    return Batterymodule(**kwargs)


def clone_component(component: Component, **overrides: float) -> Component:
    if isinstance(component, Batterymodule):
        return clone_module(component, **overrides)

    cloned_strings = []
    for module_string in component.modules:
        cloned_strings.append([
            clone_module(module, **overrides) for module in module_string
        ])
    return pack(cloned_strings)


def representative_module(component: Component) -> Batterymodule:
    if isinstance(component, Batterymodule):
        return component
    return component.modules[0][0]


def with_reliability_threshold(
    scenario: b2u.B2UScenario,
    min_remaining_energy_fraction: float,
) -> b2u.B2UScenario:
    reliability = replace(
        scenario.reliability,
        min_remaining_energy_fraction=min_remaining_energy_fraction,
    )
    return replace(scenario, reliability=reliability)


def with_discount_rate(
    scenario: b2u.B2UScenario,
    discount_rate: float,
) -> b2u.B2UScenario:
    economics = replace(scenario.economics, discount_rate=discount_rate)
    return replace(scenario, economics=economics)


def sensitivity_cases(
    component_kind: str,
    scenario_name: str = "base",
) -> Iterable[tuple[str, str, float, Component, b2u.B2UScenario]]:
    base_component = make_base_component(component_kind)
    base_module = representative_module(base_component)
    base_scenario = make_norway_scenario(scenario_name)
    base_reliability = replace(
        base_scenario.reliability,
        samples=SENSITIVITY_SAMPLES,
        seed=SENSITIVITY_SEED,
    )
    base_scenario = replace(base_scenario, reliability=base_reliability)

    for value in FAULT_RATE_RANGE:
        yield (
            component_kind,
            "cell_fault_rate",
            value,
            clone_component(base_component, cell_fault_rate=value),
            base_scenario,
        )

    soh_range = (
        TESLA_SOH_MEAN_RANGE if component_kind == "tesla" else LEAF_SOH_MEAN_RANGE
    )
    for value in soh_range:
        yield (
            component_kind,
            "cell_soh_mean",
            value,
            clone_component(base_component, percent_remaining_energy=value),
            base_scenario,
        )

    for value in SOH_STD_RANGE:
        yield (
            component_kind,
            "cell_soh_std",
            value,
            clone_component(base_component, cell_soh_std=value),
            base_scenario,
        )

    for value in MIN_USABLE_SOH_RANGE:
        yield (
            component_kind,
            "min_remaining_energy_fraction",
            value,
            base_component,
            with_reliability_threshold(base_scenario, value),
        )

    purchase_range = (
        TESLA_PURCHASE_PRICE_USD_PER_KWH_RANGE
        if component_kind == "tesla"
        else LEAF_PURCHASE_PRICE_USD_PER_KWH_RANGE
    )
    for value in purchase_range:
        purchase_price_nok = nok_from_usd(value) * base_module.nameplate_energy_kWh
        yield (
            component_kind,
            "purchase_price_usd_per_kwh_nameplate",
            value,
            clone_component(base_component, purchase_price=purchase_price_nok),
            base_scenario,
        )

    selling_range = (
        TESLA_SELLING_PRICE_USD_PER_KWH_RANGE
        if component_kind == "tesla"
        else LEAF_SELLING_PRICE_USD_PER_KWH_RANGE
    )
    for value in selling_range:
        yield (
            component_kind,
            "selling_price_usd_per_kwh",
            value,
            clone_component(
                base_component,
                forced_selling_price_per_kWh=nok_from_usd(value),
            ),
            base_scenario,
        )

    for value in DISCOUNT_RATE_RANGE:
        yield (
            component_kind,
            "discount_rate",
            value,
            base_component,
            with_discount_rate(base_scenario, value),
        )


def _currency_value(section: dict, key: str, currency: str):
    currency_key = f"{key[:-4]}_{currency.lower()}" if key.endswith("_usd") else key
    return section.get(currency_key, section.get(key))


def run_sensitivity_case(
    component_kind: str,
    parameter: str,
    value: float,
    component: Component,
    scenario: b2u.B2UScenario,
) -> dict[str, float | str]:
    result = b2u.run_b2u_scenario(component, scenario).to_dict()
    currency = result["currency"]["currency"]
    reliability = result["reliability"]
    revenue_npv = result["revenue_npv"]
    annual_expenses = result["annual_expenses"]
    throughput = result["throughput"]
    unit_economics = result.get("unit_economics", {})

    npv_be_solver = solve_npv_break_even_selling_price(component, scenario)

    return {
        "component": component_kind,
        "parameter": parameter,
        "value": value,
        "currency": currency,
        "nok_per_usd": NOK_PER_USD,
        "npv": _currency_value(revenue_npv, "total_npv_usd", currency),
        "year_1_revenue": _currency_value(
            revenue_npv["cashflows"][1], "revenue_usd", currency
        ),
        "year_1_expenses": _currency_value(
            revenue_npv["cashflows"][1], "expenses_usd", currency
        ),
        "total_annual_expenses": _currency_value(
            annual_expenses, "total_annual_expenses_usd", currency
        ),
        "cost_per_sellable_kwh": _currency_value(
            unit_economics, "cost_usd_per_sellable_kwh", currency
        ),
        "revenue_per_sellable_kwh": _currency_value(
            unit_economics, "revenue_usd_per_sellable_kwh", currency
        ),
        "break_even_selling_price_per_kwh": _currency_value(
            unit_economics, "annual_break_even_selling_price_usd_per_kwh", currency
        ),
        "annual_break_even_selling_price_per_kwh": _currency_value(
            unit_economics, "annual_break_even_selling_price_usd_per_kwh", currency
        ),
        "npv_break_even_selling_price_per_kwh": (
            npv_be_solver.npv_break_even_selling_price_per_kwh
        ),
        "break_even_purchase_price_per_unit": _currency_value(
            unit_economics, "break_even_purchase_price_usd_per_unit", currency
        ),
        "annual_profit_before_discounting": _currency_value(
            unit_economics, "annual_profit_before_discounting_usd", currency
        ),
        "actual_units_per_year": throughput["actual_units_per_year"],
        "actual_annual_throughput_kwh": throughput["actual_annual_throughput_kwh"],
        "usable_fraction": reliability["usable_fraction"],
        "rejected_fraction": reliability["rejected_fraction"],
        "mean_remaining_energy_fraction": reliability[
            "mean_remaining_energy_fraction"
        ],
        "mean_sellable_energy_kwh_per_unit": reliability[
            "mean_sellable_energy_kwh_per_unit"
        ],
    }


def run_all_sensitivities() -> list[dict[str, float | str]]:
    rows = []
    for component_kind in ("leaf", "leaf_pack", "tesla"):
        for case in sensitivity_cases(component_kind):
            rows.append(run_sensitivity_case(*case))
    return rows


def write_sensitivity_csv(
    path: str | Path = "data/norway_sensitivity_results.csv",
) -> Path:
    rows = run_all_sensitivities()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output_path


if __name__ == "__main__":
    output_path = write_sensitivity_csv()
    print(f"Wrote Norway sensitivity results to {output_path}")
