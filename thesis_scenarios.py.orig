"""Four-case thesis analysis for the B2U model.

The thesis uses a compact scenario set:

1. NREL-inspired reference case in USD.
2. Norway base/reference case in NOK: selling price calibrated so that NPV ≈ 0
   using the NPV break-even selling price solver.
3. Norway market case in NOK: observed-market-inspired assumptions, no calibration.
4. Norway feasibility case in NOK: high-value/improved-process pathway.

The NPV-based maximum purchase price is reported for each case.  This is closer
to the original NREL logic than comparing NPV for arbitrary acquisition prices,
because the NREL repurposing-cost model estimates what a repurposer can afford
to pay for used batteries under a chosen selling-price and cost structure.

Each output row carries three metadata columns:
  case_type             – one of nrel_reference / base_break_even_reference /
                          market / feasibility
  calibrated_variable   – which variable was set by calibration, or "none"
  calibration_target    – what target was optimised for, or "none"
"""

from __future__ import annotations

import csv
import math
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_ROOT / "outputs"
TABLES_DIR = OUTPUT_DIR / "tables"
TABLES_DIR.mkdir(parents=True, exist_ok=True)

import b2u
from Batterycomponents import Batterymodule, pack
from max_purchase_price import solve_max_purchase_price, solve_npv_break_even_selling_price
from norway_scenarios import (
    LEAF_FEASIBILITY_PACK_ACQUISITION_PRICE_NOK_PER_KWH,
    LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
    LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
    LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
    TESLA_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
    make_leaf_gen1_module_from_pack_purchase,
    make_leaf_gen1_pack,
    make_leaf_gen1_pack_from_pack_purchase,
    make_leaf_pack_triage_pathway,
    make_norway_scenario,
    make_tesla_model_s_gen1_module,
    set_component_selling_price,
    with_leaf_pack_disassembly,
)


NREL_REFERENCE_PURCHASE_PRICE_USD_PER_KWH = 19.62
NREL_REFERENCE_SELLING_PRICE_USD_PER_KWH = 44.0


def make_nrel_reference_module() -> Batterymodule:
    """Create the generic 5 kWh module used in the NREL spreadsheet baseline."""
    # The original calculator uses 150 Wh/L and 115 Wh/kg. For 5 kWh this gives
    # 33.33 L and 43.48 kg. The dimensions below reproduce the spreadsheet's
    # rectangular module approximation: X = volume / Y / Z and Y = Z = (V/2)^(1/3).
    return Batterymodule(
        nameplate_energy_kWh=5.0,
        weight_kg=5_000.0 / 115.0,
        purchase_price=NREL_REFERENCE_PURCHASE_PRICE_USD_PER_KWH * 5.0,
        height_mm=254.7,
        width_mm=254.7,
        length_mm=509.4,
        percent_remaining_energy=0.70,
        seriescells=68,
        paralellcells=1,
        cell_fault_rate=1e-5,
        forced_selling_price_per_kWh=NREL_REFERENCE_SELLING_PRICE_USD_PER_KWH,
        chemistry="generic_nrel",
        cell_soh_std=0.0,
        min_cell_soh=0.0,
        max_cell_soh=1.0,
    )


def make_nrel_reference_scenario() -> b2u.B2UScenario:
    """Create a USD reference scenario close to the NREL spreadsheet baseline.

    The process-time model is NREL-scaled: the step times below are treated as
    the complete NREL reference-module times, and other modules/packs are scaled
    from them by mass or nameplate energy.  This keeps the benchmark close to
    the spreadsheet logic while avoiding fixed-time plus variable-time
    double-counting.
    """
    learning = b2u.LearningAssumptions(
        analysis_years=5,
        initial_utilization=1.0,
        max_utilization=1.0,
        utilization_improvement_per_year=0.0,
        handling_time_improvement_per_year=0.0,
        testing_time_improvement_per_year=0.0,
        packing_time_improvement_per_year=0.0,
        forklift_time_improvement_per_year=0.0,
    )
    reliability = b2u.ReliabilityAssumptions(
        enabled=False,
        min_remaining_energy_fraction=0.60,
        use_remaining_energy_for_revenue=False,
    )
    nrel_labor = b2u.LaborAssumptions(
        process_time_model="nrel_scaled",
        reference_nameplate_energy_kwh=5.0,
        reference_specific_energy_wh_per_kg=115.0,
        receiving_inspection_time_s=1_200.0,
        connection_initiation_time_s=300.0,
        electrical_testing_time_s=4_300.0,
        disconnect_time_s=300.0,
        final_inspection_time_s=1_200.0,
        charging_time_s=2_700.0,
        average_c_rate=1.0,
        charging_efficiency=0.85,
        pallet_move_time_s=900.0,
    )
    return b2u.B2UScenario(
        name="nrel_reference",
        facility=b2u.FacilityAssumptions(
            target_annual_throughput_kwh=1_000_000.0,
            work_days_per_year=252,
            working_hours_per_day=8.0,
            calendar_days_per_year=365,
            station_hours_per_day=24.0,
            design_utilization=1.0,
        ),
        labor=nrel_labor,
        economics=b2u.EconomicAssumptions(
            forced_selling_price_per_kwh=None,
            discount_rate=0.15,
            federal_tax_rate=0.393,
            state_tax_rate=0.0,
            electricity_testing_cost_per_kwh=0.104,
            hvac_lighting_cost_per_m2_year=2.27 / b2u.M2_PER_FT2,
            rent_per_m2_year=9.70 / b2u.M2_PER_FT2,
            other_direct_cost_fraction_of_wages=0.02,
            insurance_fraction_of_direct_costs=0.03,
            ga_fraction_of_direct_costs=0.05,
            warranty_fraction_of_revenue=0.05,
            rnd_fraction_of_direct_costs=0.03,
        ),
        learning=learning,
        reliability=reliability,
        currency=b2u.CurrencyAssumptions(currency="USD"),
        collection_scale="Regional",
    )


def _is_valid_number(value) -> bool:
    """Return True if value is a non-NaN finite number."""
    try:
        return not math.isnan(value)
    except (TypeError, ValueError):
        return False


def _currency_value(section: dict, key: str, currency: str):
    """Return a value from a currency-neutral result section."""
    return section.get(key)


def make_norway_market_leaf_pack_case() -> tuple[str, pack, b2u.B2UScenario]:
    """Market case: buy complete Leaf packs at bulk intake price and sell tested packs."""
    component = make_leaf_gen1_pack_from_pack_purchase(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
    )
    set_component_selling_price(component, LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH)
    return "leaf_pack_market", component, make_norway_scenario("base")


def make_norway_leaf_pack_to_modules_market_case() -> tuple[str, Batterymodule, b2u.B2UScenario]:
    """Market pathway: buy complete Leaf packs, disassemble, sell modules.

    The component is a Leaf module because testing and resale are module-level.
    Purchase price is based on complete-pack acquisition, and the scenario adds
    average disassembly labour per module.
    """
    component = make_leaf_gen1_module_from_pack_purchase(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
    )
    component.forced_selling_price_per_kWh = LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH
    scenario = with_leaf_pack_disassembly(make_norway_scenario("base"))
    return "leaf_pack_to_modules_market", component, scenario


def make_norway_leaf_pack_triage_market_case() -> tuple[str, pack, b2u.B2UScenario]:
    """Market pathway: test Leaf packs first, recover modules from failures."""
    component, scenario = make_leaf_pack_triage_pathway(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
        pack_acceptance_threshold=0.55,
        module_acceptance_threshold=0.55,
        disassembly_time_s_per_module=240.0,
        module_recovery_testing_time_s_per_module=300.0,
        pack_selling_price_nok_per_kwh=LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
        recovered_module_selling_price_nok_per_kwh=LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
    )
    return "leaf_pack_triage_market", component, scenario


def make_norway_market_tesla_case() -> tuple[str, Batterymodule, b2u.B2UScenario]:
    """Market case: base assumptions, tesla module, no calibration."""
    return (
        "tesla_market",
        make_tesla_model_s_gen1_module("base"),
        make_norway_scenario("base"),
    )


def _calibrate_to_npv_zero(
    component: Batterymodule | pack,
    scenario: b2u.B2UScenario,
) -> b2u.B2UScenario:
    """Return a scenario with selling price calibrated so that NPV ≈ 0.

    Calls ``solve_npv_break_even_selling_price`` and sets
    ``forced_selling_price_per_kwh`` on the returned scenario.  If the
    solver returns NaN the original scenario is returned unchanged.
    """
    solver_result = solve_npv_break_even_selling_price(component, scenario)
    be_price = solver_result.npv_break_even_selling_price_per_kwh
    if _is_valid_number(be_price) and be_price > 0:
        economics = replace(
            scenario.economics,
            forced_selling_price_per_kwh=be_price,
        )
        return replace(scenario, economics=economics)
    return scenario


def make_norway_reference_leaf_pack_case(
    calibration_samples: int = 5_000,
) -> tuple[str, pack, b2u.B2UScenario]:
    """Base/reference case: base assumptions, leaf pack, NPV calibrated to ≈ 0."""
    component = make_leaf_gen1_pack("base")
    scenario = make_norway_scenario("base")
    reliability = replace(scenario.reliability, samples=calibration_samples)
    scenario = replace(scenario, reliability=reliability)
    calibrated = _calibrate_to_npv_zero(component, scenario)
    return "leaf_pack_reference", component, calibrated


def make_norway_reference_tesla_case(
    calibration_samples: int = 5_000,
) -> tuple[str, Batterymodule, b2u.B2UScenario]:
    """Base/reference case: base assumptions, tesla module, NPV calibrated to ≈ 0."""
    component = make_tesla_model_s_gen1_module("base")
    scenario = make_norway_scenario("base")
    reliability = replace(scenario.reliability, samples=calibration_samples)
    scenario = replace(scenario, reliability=reliability)
    calibrated = _calibrate_to_npv_zero(component, scenario)
    return "tesla_reference", component, calibrated


def _feasibility_scenario() -> b2u.B2UScenario:
    scenario = make_norway_scenario("base")
    labor = replace(
        scenario.labor,
        # More efficient reference-process times than the base case, while
        # retaining NREL-scaled mass/energy dependence.
        receiving_inspection_time_s=900.0,
        connection_initiation_time_s=240.0,
        electrical_testing_time_s=3000.0,
        disconnect_time_s=180.0,
        final_inspection_time_s=900.0,
        minimum_inspection_time_s=180.0,
        minimum_connection_time_s=90.0,
        minimum_testing_time_s=600.0,
        minimum_disconnect_time_s=60.0,
        minimum_packing_time_s=180.0,
    )
    economics = replace(
        scenario.economics,
        warranty_fraction_of_revenue=0.03,
        insurance_fraction_of_direct_costs=0.02,
    )
    learning = replace(
        scenario.learning,
        initial_utilization=0.80,
        max_utilization=0.95,
        handling_time_improvement_per_year=0.05,
        testing_time_improvement_per_year=0.05,
        packing_time_improvement_per_year=0.05,
    )
    reliability = replace(
        scenario.reliability,
        min_remaining_energy_fraction=0.55,
        samples=50_000,
        seed=20260603,
    )
    return replace(
        scenario,
        name="norway_feasibility",
        labor=labor,
        economics=economics,
        learning=learning,
        reliability=reliability,
    )


def make_feasibility_leaf_pack_case() -> tuple[str, pack, b2u.B2UScenario]:
    component = make_leaf_gen1_pack("base")
    # Feasibility case tests whether higher value of the final second-life
    # product can support a positive acquisition price.
    for module_string in component.modules:
        for module in module_string:
            module.forced_selling_price_per_kWh = LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
    component.calculate_pack_properties()
    return "feasibility_leaf_pack", component, _feasibility_scenario()


def make_feasibility_leaf_pack_to_modules_case() -> tuple[str, Batterymodule, b2u.B2UScenario]:
    """Feasibility pathway: buy complete Leaf packs and sell accepted modules."""
    component = make_leaf_gen1_module_from_pack_purchase(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_FEASIBILITY_PACK_ACQUISITION_PRICE_NOK_PER_KWH,
    )
    component.forced_selling_price_per_kWh = LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
    scenario = with_leaf_pack_disassembly(
        _feasibility_scenario(),
        disassembly_time_s_per_module=180.0,
    )
    return "feasibility_leaf_pack_to_modules", component, scenario


def make_feasibility_leaf_pack_triage_case() -> tuple[str, pack, b2u.B2UScenario]:
    """Feasibility pathway: pack-first screening plus module recovery."""
    component, scenario = make_leaf_pack_triage_pathway(
        "base",
        pack_purchase_price_reference_usd_per_kwh=None,
        pack_purchase_price_nok_per_kwh=LEAF_FEASIBILITY_PACK_ACQUISITION_PRICE_NOK_PER_KWH,
        pack_acceptance_threshold=0.55,
        module_acceptance_threshold=0.55,
        disassembly_time_s_per_module=180.0,
        module_recovery_testing_time_s_per_module=240.0,
        pack_selling_price_nok_per_kwh=LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
        recovered_module_selling_price_nok_per_kwh=LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH,
    )
    for module_string in component.modules:
        for module in module_string:
            module.forced_selling_price_per_kWh = LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
    component.calculate_pack_properties()

    base_feasibility = _feasibility_scenario()
    scenario = replace(
        scenario,
        economics=base_feasibility.economics,
        learning=base_feasibility.learning,
        labor=replace(
            base_feasibility.labor,
            disassembly_time_s_per_unit=scenario.labor.disassembly_time_s_per_unit,
        ),
        reliability=scenario.reliability,
        name="norway_feasibility_leaf_pack_triage",
    )
    return "feasibility_leaf_pack_triage", component, scenario


def make_feasibility_tesla_case() -> tuple[str, Batterymodule, b2u.B2UScenario]:
    component = make_tesla_model_s_gen1_module("base")
    component.forced_selling_price_per_kWh = TESLA_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH
    return "feasibility_tesla_module", component, _feasibility_scenario()


def _use_script_sample_count(scenario: b2u.B2UScenario) -> b2u.B2UScenario:
    """Keep command-line runs practical; increase for final published runs."""
    if not scenario.reliability.enabled:
        return scenario
    reliability = replace(scenario.reliability, samples=5_000)
    return replace(scenario, reliability=reliability)


def iter_thesis_cases():
    """Yield (label, component, scenario, metadata) for every thesis case.

    metadata is a dict with keys ``case_type``, ``calibrated_variable``, and
    ``calibration_target``.
    """
    yield (
        "nrel_reference",
        make_nrel_reference_module(),
        make_nrel_reference_scenario(),
        {
            "case_type": "nrel_reference",
            "calibrated_variable": "none",
            "calibration_target": "none",
        },
    )
    # Reference cases are calibrated so NPV ≈ 0 at the break-even selling price.
    # _use_script_sample_count is applied inside the reference factory functions
    # (calibration_samples=5_000), so the scenario sample count is already low.
    for label, component, scenario in (
        make_norway_reference_leaf_pack_case(),
        make_norway_reference_tesla_case(),
    ):
        yield (
            label,
            component,
            scenario,
            {
                "case_type": "base_break_even_reference",
                "calibrated_variable": "selling_price_per_kwh",
                "calibration_target": "NPV_approximately_zero",
            },
        )
    # Market cases: observed-market-inspired assumptions, no calibration.
    for label, component, scenario in (
        make_norway_market_leaf_pack_case(),
        make_norway_leaf_pack_to_modules_market_case(),
        make_norway_leaf_pack_triage_market_case(),
        make_norway_market_tesla_case(),
    ):
        yield (
            label,
            component,
            _use_script_sample_count(scenario),
            {
                "case_type": "market",
                "calibrated_variable": "none",
                "calibration_target": "none",
            },
        )
    # Feasibility cases: improvement pathway, no calibration.
    for label, component, scenario in (
        make_feasibility_leaf_pack_case(),
        make_feasibility_leaf_pack_to_modules_case(),
        make_feasibility_leaf_pack_triage_case(),
        make_feasibility_tesla_case(),
    ):
        yield (
            label,
            component,
            _use_script_sample_count(scenario),
            {
                "case_type": "feasibility",
                "calibrated_variable": "none",
                "calibration_target": "none",
            },
        )


def run_case(
    label: str,
    component: Batterymodule | pack,
    scenario: b2u.B2UScenario,
    metadata: dict | None = None,
) -> dict:
    """Run one thesis case and return a result dict including metadata."""
    if metadata is None:
        metadata = {"case_type": "unknown", "calibrated_variable": "none",
                    "calibration_target": "none"}
    result = b2u.run_b2u_scenario(component, scenario).to_dict()
    currency = result["currency"]["currency"]
    max_purchase = solve_max_purchase_price(component, scenario)
    npv_be_selling = solve_npv_break_even_selling_price(component, scenario)
    unit_economics = result["unit_economics"]
    revenue_npv = result["revenue_npv"]
    purchase_price = result["purchase_price"]
    return {
        "case": label,
        "case_type": metadata["case_type"],
        "calibrated_variable": metadata["calibrated_variable"],
        "calibration_target": metadata["calibration_target"],
        "scenario": scenario.name,
        "currency": currency,
        "npv": _currency_value(revenue_npv, "total_npv", currency),
        "current_purchase_price_per_kwh_nameplate": _currency_value(
            purchase_price,
            "purchase_price_per_kwh_nameplate",
            currency,
        ),
        "maximum_purchase_price_per_kwh_nameplate": (
            max_purchase.maximum_purchase_price_per_kwh_nameplate
        ),
        "maximum_purchase_price_per_unit": max_purchase.maximum_purchase_price_per_unit,
        "npv_at_zero_purchase_price": max_purchase.npv_at_zero_purchase_price,
        "feasible_at_zero_purchase_price": max_purchase.feasible_at_zero_purchase_price,
        # break_even_selling_price_per_kwh aliases annual_break_even to avoid
        # the circular formula where total_expenses includes warranty based on
        # the actual (input) selling price rather than the break-even price.
        "break_even_selling_price_per_kwh": _currency_value(
            unit_economics,
            "annual_break_even_selling_price_per_kwh",
            currency,
        ),
        "annual_break_even_selling_price_per_kwh": _currency_value(
            unit_economics,
            "annual_break_even_selling_price_per_kwh",
            currency,
        ),
        "npv_break_even_selling_price_per_kwh": (
            npv_be_selling.npv_break_even_selling_price_per_kwh
        ),
        "revenue_per_sellable_kwh": _currency_value(
            unit_economics,
            "revenue_per_sellable_kwh",
            currency,
        ),
        "cost_per_sellable_kwh": _currency_value(
            unit_economics,
            "cost_per_sellable_kwh",
            currency,
        ),
        "usable_fraction": result["reliability"]["usable_fraction"],
        "mean_sellable_energy_kwh_per_unit": result["reliability"][
            "mean_sellable_energy_kwh_per_unit"
        ],
    }


def main() -> None:
    rows = [
        run_case(label, component, scenario, metadata)
        for label, component, scenario, metadata in iter_thesis_cases()
    ]
    out_path = TABLES_DIR / "thesis_scenario_results.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(f"\n=== {row['case']} ({row['case_type']}) ===")
        print(f"Currency: {row['currency']}")
        print(f"NPV: {row['npv']:.2f}")
        print(
            "Maximum purchase price: "
            f"{row['maximum_purchase_price_per_kwh_nameplate']:.2f} "
            f"{row['currency']}/kWh-nameplate"
        )
        print(
            "Current purchase price: "
            f"{row['current_purchase_price_per_kwh_nameplate']:.2f} "
            f"{row['currency']}/kWh-nameplate"
        )
        print(f"Feasible at zero purchase price: {row['feasible_at_zero_purchase_price']}")
        print(f"Usable fraction: {row['usable_fraction']:.4f}")
        print(
            f"Mean sellable energy: "
            f"{row['mean_sellable_energy_kwh_per_unit']:.4f} kWh/unit"
        )
        npv_be = row["npv_break_even_selling_price_per_kwh"]
        ann_be = row["annual_break_even_selling_price_per_kwh"]
        if _is_valid_number(npv_be):
            print(f"NPV break-even selling price: {npv_be:.2f} {row['currency']}/kWh")
        if _is_valid_number(ann_be):
            print(f"Annual break-even selling price: {ann_be:.2f} {row['currency']}/kWh")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
