"""Throughput scaling runs for Norway-localized B2U cases.

This script tests whether scaling annual nameplate throughput can move the
model toward positive NPV. It also includes a simplified Leaf Gen 1 pack case,
so module-level and pack-level handling can be compared directly.

The calculation remains currency-neutral. For these Norway cases, all monetary
inputs are NOK excluding VAT.
"""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import b2u
from Batterycomponents import Batterymodule, pack
from norway_scenarios import (
    LEAF_GEN1_MODULES_PER_PACK,
    LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
    LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
    NOK_PER_USD,
    TESLA_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
    make_leaf_gen1_module,
    make_leaf_gen1_module_from_pack_purchase,
    make_leaf_gen1_pack,
    make_leaf_pack_triage_pathway,
    make_norway_scenario,
    make_tesla_model_s_gen1_module,
    nok_from_usd,
    set_component_selling_price,
    with_leaf_pack_disassembly,
)

Component = Batterymodule | pack

THROUGHPUT_KWH_RANGE = (
    250_000,
    500_000,
    1_000_000,
    2_000_000,
    5_000_000,
    10_000_000,
    20_000_000,
    50_000_000,
)

SCALING_SAMPLES = 1_000
SCALING_SEED = 20260602


def _currency_value(section: dict, key: str, currency: str):
    """Return a value from a currency-neutral result section."""
    return section.get(key)


def with_throughput(
    scenario: b2u.B2UScenario,
    target_annual_throughput_kwh: float,
) -> b2u.B2UScenario:
    facility = replace(
        scenario.facility,
        target_annual_throughput_kwh=target_annual_throughput_kwh,
    )
    reliability = replace(
        scenario.reliability,
        samples=SCALING_SAMPLES,
        seed=SCALING_SEED,
    )
    return replace(scenario, facility=facility, reliability=reliability)


def with_market_assumptions(
    component: Component,
    scenario: b2u.B2UScenario,
    component_kind: str,
    variant: str,
) -> tuple[Component, b2u.B2UScenario]:
    """Return component/scenario modified for a scaling variant.

    ``base`` uses the documented Norway base assumptions. ``optimistic`` uses
    the documented Norway optimistic scenario. ``market_push`` is deliberately
    more aggressive: it tests whether higher selling prices, lower acquisition
    prices, and shorter handling times can make repurposing profitable. Treat it
    as an exploratory upper-bound case, not as a calibrated market forecast.
    """
    if variant in {"base", "optimistic"}:
        return component, scenario

    if variant != "market_push":
        raise ValueError("variant must be 'base', 'optimistic', or 'market_push'")

    if component_kind in {"leaf", "leaf_pack", "leaf_pack_to_modules", "leaf_pack_triage"}:
        selling_price_nok_per_kwh = LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
        purchase_price_nok_per_kwh = LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH
    else:
        selling_price_nok_per_kwh = TESLA_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
        purchase_price_nok_per_kwh = nok_from_usd(20.0)

    def update_module(module: Batterymodule) -> Batterymodule:
        return Batterymodule(
            nameplate_energy_kWh=module.nameplate_energy_kWh,
            weight_kg=module.weight_kg,
            purchase_price=(
                purchase_price_nok_per_kwh * module.nameplate_energy_kWh
            ),
            height_mm=module.height_mm,
            width_mm=module.width_mm,
            length_mm=module.length_mm,
            percent_remaining_energy=module.nominal_cell_soh,
            seriescells=module.seriescells,
            paralellcells=module.paralellcells,
            cell_fault_rate=module.cell_fault_rate,
            forced_selling_price_per_kWh=selling_price_nok_per_kwh,
            chemistry=module.chemistry,
            cell_soh_std=module.cell_soh_std,
            min_cell_soh=module.min_cell_soh,
            max_cell_soh=module.max_cell_soh,
        )

    if isinstance(component, Batterymodule):
        component = update_module(component)
    else:
        component = pack([
            [update_module(module) for module in module_string]
            for module_string in component.modules
        ])

    labor = replace(
        scenario.labor,
        receiving_inspection_time_s=900.0,
        connection_initiation_time_s=180.0,
        electrical_testing_time_s=1800.0,
        disconnect_time_s=120.0,
        final_inspection_time_s=900.0,
        minimum_inspection_time_s=120.0,
        minimum_connection_time_s=60.0,
        minimum_testing_time_s=300.0,
        minimum_disconnect_time_s=45.0,
        minimum_packing_time_s=120.0,
    )
    economics = replace(
        scenario.economics,
        insurance_fraction_of_direct_costs=0.02,
        warranty_fraction_of_revenue=0.03,
    )
    learning = replace(
        scenario.learning,
        initial_utilization=0.80,
        max_utilization=0.95,
        utilization_improvement_per_year=0.05,
        handling_time_improvement_per_year=0.05,
        testing_time_improvement_per_year=0.05,
        packing_time_improvement_per_year=0.05,
    )
    scenario = replace(
        scenario,
        labor=labor,
        economics=economics,
        learning=learning,
    )
    return component, scenario


def make_case(component_kind: str, variant: str) -> tuple[str, Component, b2u.B2UScenario]:
    scenario_name = "optimistic" if variant == "optimistic" else "base"
    scenario = make_norway_scenario(scenario_name)

    if component_kind == "leaf":
        component = make_leaf_gen1_module(scenario_name)
    elif component_kind == "leaf_pack":
        component = make_leaf_gen1_pack(scenario_name)
        if variant == "base":
            set_component_selling_price(component, LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH)
    elif component_kind == "leaf_pack_to_modules":
        component = make_leaf_gen1_module_from_pack_purchase(
            scenario_name,
            pack_purchase_price_reference_usd_per_kwh=None,
            pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
        )
        component.forced_selling_price_per_kWh = LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH
        scenario = with_leaf_pack_disassembly(scenario)
    elif component_kind == "leaf_pack_triage":
        component, scenario = make_leaf_pack_triage_pathway(
            scenario_name,
            pack_purchase_price_reference_usd_per_kwh=None,
            pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
            pack_acceptance_threshold=0.60,
            module_acceptance_threshold=0.55,
            pack_selling_price_nok_per_kwh=LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
            recovered_module_selling_price_nok_per_kwh=LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
        )
    elif component_kind == "tesla":
        component = make_tesla_model_s_gen1_module(scenario_name)
    else:
        raise ValueError(
            "component_kind must be 'leaf', 'leaf_pack', 'leaf_pack_to_modules', 'leaf_pack_triage', or 'tesla'"
        )

    component, scenario = with_market_assumptions(
        component=component,
        scenario=scenario,
        component_kind=component_kind,
        variant=variant,
    )
    return f"{component_kind}_{variant}", component, scenario


def run_scaling_case(
    label: str,
    component: Component,
    scenario: b2u.B2UScenario,
    target_annual_throughput_kwh: float,
) -> dict[str, float | str]:
    scenario = with_throughput(scenario, target_annual_throughput_kwh)
    result = b2u.run_b2u_scenario(component, scenario).to_dict()
    currency = result["currency"]["currency"]
    revenue_npv = result["revenue_npv"]
    throughput = result["throughput"]
    reliability = result["reliability"]
    unit_economics = result.get("unit_economics", {})

    return {
        "case": label,
        "target_annual_throughput_kwh": target_annual_throughput_kwh,
        "currency": currency,
        "nok_per_usd": NOK_PER_USD,
        "npv": _currency_value(revenue_npv, "total_npv", currency),
        "actual_annual_throughput_kwh_year_1": throughput[
            "actual_annual_throughput_kwh"
        ],
        "actual_units_per_year_year_1": throughput["actual_units_per_year"],
        "usable_fraction": reliability["usable_fraction"],
        "mean_sellable_energy_kwh_per_unit": reliability[
            "mean_sellable_energy_kwh_per_unit"
        ],
        "cost_per_sellable_kwh": _currency_value(
            unit_economics, "cost_per_sellable_kwh", currency
        ),
        "revenue_per_sellable_kwh": _currency_value(
            unit_economics, "revenue_per_sellable_kwh", currency
        ),
        "break_even_selling_price_per_kwh": _currency_value(
            unit_economics, "annual_break_even_selling_price_per_kwh", currency
        ),
        "annual_profit_before_discounting": _currency_value(
            unit_economics, "annual_profit_before_discounting", currency
        ),
    }


def run_all_scaling() -> list[dict[str, float | str]]:
    rows = []
    for component_kind in ("leaf", "leaf_pack_to_modules", "leaf_pack_triage", "leaf_pack", "tesla"):
        for variant in ("base", "optimistic", "market_push"):
            label, component, scenario = make_case(component_kind, variant)
            for throughput in THROUGHPUT_KWH_RANGE:
                rows.append(run_scaling_case(label, component, scenario, throughput))
    return rows


def first_positive_npv(rows: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    summary = []
    for case in sorted({row["case"] for row in rows}):
        case_rows = [row for row in rows if row["case"] == case]
        positives = [row for row in case_rows if float(row["npv"]) > 0]
        if positives:
            best = min(positives, key=lambda row: float(row["target_annual_throughput_kwh"]))
            summary.append({
                "case": case,
                "first_positive_target_annual_throughput_kwh": best[
                    "target_annual_throughput_kwh"
                ],
                "npv": best["npv"],
            })
        else:
            best = max(case_rows, key=lambda row: float(row["npv"]))
            summary.append({
                "case": case,
                "first_positive_target_annual_throughput_kwh": "not_reached",
                "npv": best["npv"],
            })
    return summary


def throughput_unit_requirements(target_annual_throughput_kwh: float = 1_000_000.0) -> list[dict[str, float | str]]:
    """Return physical work-item counts needed to reach the target throughput.

    ``primary_units_per_year`` is the first physical handling unit in the
    pathway: modules for direct module pathways, complete packs for pack-level
    pathways. ``additional_module_tests_per_year`` represents extra module tests
    after pack disassembly. This distinction is useful for the hybrid triage
    pathway, where only packs that fail pack-level screening are disassembled.
    """
    leaf_module = make_leaf_gen1_module("base")
    leaf_pack = make_leaf_gen1_pack("base")
    tesla_module = make_tesla_model_s_gen1_module("base")
    # Use the same pack-level acceptance threshold as the thesis triage scenarios.
    # The previous 0.60 value was useful as a stress case, but it made the
    # unit-requirement figure look almost identical to full pack-to-modules
    # disassembly.  At 0.55, the figure illustrates the intended staged-screening
    # logic: many packs are sold whole, and only failed packs receive module tests.
    triage_component, triage_scenario = make_leaf_pack_triage_pathway(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
        pack_acceptance_threshold=0.55,
        module_acceptance_threshold=0.55,
        pack_selling_price_nok_per_kwh=LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
        recovered_module_selling_price_nok_per_kwh=LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
    )
    triage_summary = triage_scenario.reliability.summary_override or {}
    triage_failed_pack_fraction = float(triage_summary.get("pack_disassembly_fraction", 0.0))

    leaf_module_tests = target_annual_throughput_kwh / leaf_module.nameplate_energy_kWh
    leaf_input_packs = target_annual_throughput_kwh / leaf_pack.nameplate_energy_kWh
    tesla_module_tests = target_annual_throughput_kwh / tesla_module.nameplate_energy_kWh
    triage_input_packs = target_annual_throughput_kwh / triage_component.nameplate_energy_kWh
    triage_module_tests = triage_input_packs * triage_failed_pack_fraction * LEAF_GEN1_MODULES_PER_PACK

    return [
        {
            "pathway": "Leaf modules",
            "handling_unit": "module",
            "energy_per_handling_unit_kwh": leaf_module.nameplate_energy_kWh,
            "primary_units_per_year": leaf_module_tests,
            "additional_module_tests_per_year": 0.0,
            "processed_units_per_year": leaf_module_tests,
            "input_packs_per_year": 0.0,
            "module_tests_per_year": leaf_module_tests,
            "failed_pack_fraction": 0.0,
        },
        {
            "pathway": "Leaf pack-to-modules",
            "handling_unit": "complete pack plus module tests",
            "energy_per_handling_unit_kwh": leaf_pack.nameplate_energy_kWh,
            "primary_units_per_year": leaf_input_packs,
            "additional_module_tests_per_year": leaf_module_tests,
            "processed_units_per_year": leaf_input_packs + leaf_module_tests,
            "input_packs_per_year": leaf_input_packs,
            "module_tests_per_year": leaf_module_tests,
            "failed_pack_fraction": 1.0,
        },
        {
            "pathway": "Leaf pack triage",
            "handling_unit": "pack first, modules if failed",
            "energy_per_handling_unit_kwh": triage_component.nameplate_energy_kWh,
            "primary_units_per_year": triage_input_packs,
            "additional_module_tests_per_year": triage_module_tests,
            "processed_units_per_year": triage_input_packs + triage_module_tests,
            "input_packs_per_year": triage_input_packs,
            "module_tests_per_year": triage_module_tests,
            "failed_pack_fraction": triage_failed_pack_fraction,
        },
        {
            "pathway": "Leaf packs",
            "handling_unit": "pack",
            "energy_per_handling_unit_kwh": leaf_pack.nameplate_energy_kWh,
            "primary_units_per_year": leaf_input_packs,
            "additional_module_tests_per_year": 0.0,
            "processed_units_per_year": leaf_input_packs,
            "input_packs_per_year": leaf_input_packs,
            "module_tests_per_year": 0.0,
            "failed_pack_fraction": 0.0,
        },
        {
            "pathway": "Tesla modules",
            "handling_unit": "module",
            "energy_per_handling_unit_kwh": tesla_module.nameplate_energy_kWh,
            "primary_units_per_year": tesla_module_tests,
            "additional_module_tests_per_year": 0.0,
            "processed_units_per_year": tesla_module_tests,
            "input_packs_per_year": 0.0,
            "module_tests_per_year": tesla_module_tests,
            "failed_pack_fraction": 0.0,
        },
    ]


def write_csvs(
    results_path: str | Path = "data/norway_throughput_scaling_results.csv",
    summary_path: str | Path = "data/norway_throughput_scaling_summary.csv",
) -> tuple[Path, Path]:
    rows = run_all_scaling()
    results_path = Path(results_path)
    summary_path = Path(summary_path)
    results_path.parent.mkdir(parents=True, exist_ok=True)

    with results_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = first_positive_npv(rows)
    with summary_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    unit_req_path = Path("data/throughput_unit_requirements_1gwh.csv")
    with unit_req_path.open("w", newline="") as csvfile:
        unit_rows = throughput_unit_requirements(1_000_000.0)
        writer = csv.DictWriter(csvfile, fieldnames=list(unit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(unit_rows)

    return results_path, summary_path


if __name__ == "__main__":
    results_path, summary_path = write_csvs()
    print(f"Wrote throughput scaling results to {results_path}")
    print(f"Wrote throughput scaling summary to {summary_path}")
