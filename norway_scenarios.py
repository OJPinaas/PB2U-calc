"""Norway-localized scenario and module presets for the B2U model.

The B2U calculation is currency-neutral: all monetary values are interpreted
in the scenario currency.  In the scenarios below, the values passed into B2U
are NOK excluding VAT.  The NOK/USD conversion rate is used only while building
these Norway presets from the documented assumption set; it is not used inside
the B2U calculation itself.

VAT is intentionally excluded from profitability calculations. For the assumed
B2B setting, VAT is treated as a pass-through tax. Any end-user VAT effect
should be discussed as a market-price effect, not as an operating cost.
"""

from __future__ import annotations

from dataclasses import replace

import b2u
from Batterycomponents import Batterymodule, pack
from reliability_model import component_reliability_summary

NOK_PER_USD = 9.32
VAT_RATE = 0.25
NORWAY_DISCOUNT_RATE = 0.10
LEAF_GEN1_MODULES_PER_PACK = 48

# Norway-facing price assumptions are intentionally separated into acquisition
# and selling-price levels. Public listings on FINN/retailer pages are asking
# prices for raw used parts, not realised wholesale transaction prices. The
# acquisition prices below therefore sit below observed retail/listing prices,
# while selling prices distinguish complete packs, individual modules, and
# higher-value tested second-life products.
LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH = 150.0
LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH = 111.84
LEAF_FEASIBILITY_PACK_ACQUISITION_PRICE_NOK_PER_KWH = 93.20
# sellable prices per actual kWh of remaining energy, not per nameplate kWh
LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH = 900
LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH = 1600.0
LEAF_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH = 2200.0

TESLA_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH = 1400.0
TESLA_HIGH_VALUE_PRODUCT_SELLING_PRICE_NOK_PER_KWH = 1900.0


def nok_from_usd(value_usd: float) -> float:
    return value_usd * NOK_PER_USD


def nok_per_m_from_usd_per_km(value_usd_per_km: float) -> float:
    return nok_from_usd(value_usd_per_km) / 1000.0


# Module presets describe the incoming battery stream.  The SoH lower bound is
# a physical/statistical truncation limit for sampled cell SoH values.  It is
# deliberately separate from the usability threshold in SCENARIO_PRESETS ->
# reliability -> min_remaining_energy_fraction.  This allows the Monte Carlo
# intake model to sample modules below the acceptance threshold and reject them.
MODULE_PRESETS = {
    "base": {
        "leaf": {
            "percent_remaining_energy": 0.64,
            "cell_soh_std": 0.04,
            "min_cell_soh": 0.45,
            "max_cell_soh": 0.95,
            "cell_fault_rate": 5e-5,
            "purchase_price_reference_usd": 18.0,
        },
        "tesla": {
            "percent_remaining_energy": 0.80,
            "cell_soh_std": 0.04,
            "min_cell_soh": 0.55,
            "max_cell_soh": 0.98,
            "cell_fault_rate": 5e-5,
            "purchase_price_reference_usd": 230.0,
        },
    },
    "conservative": {
        "leaf": {
            "percent_remaining_energy": 0.60,
            "cell_soh_std": 0.06,
            "min_cell_soh": 0.35,
            "max_cell_soh": 0.95,
            "cell_fault_rate": 2e-4,
            "purchase_price_reference_usd": 25.0,
        },
        "tesla": {
            "percent_remaining_energy": 0.74,
            "cell_soh_std": 0.05,
            "min_cell_soh": 0.45,
            "max_cell_soh": 0.98,
            "cell_fault_rate": 2e-4,
            "purchase_price_reference_usd": 280.0,
        },
    },
    "optimistic": {
        "leaf": {
            "percent_remaining_energy": 0.70,
            "cell_soh_std": 0.03,
            "min_cell_soh": 0.50,
            "max_cell_soh": 0.98,
            "cell_fault_rate": 1e-5,
            "purchase_price_reference_usd": 12.0,
        },
        "tesla": {
            "percent_remaining_energy": 0.86,
            "cell_soh_std": 0.03,
            "min_cell_soh": 0.60,
            "max_cell_soh": 0.99,
            "cell_fault_rate": 1e-5,
            "purchase_price_reference_usd": 170.0,
        },
    },
    "high_failure": {
        "leaf": {
            "percent_remaining_energy": 0.64,
            "cell_soh_std": 0.08,
            "min_cell_soh": 0.35,
            "max_cell_soh": 0.95,
            "cell_fault_rate": 1e-3,
            "purchase_price_reference_usd": 18.0,
        },
        "tesla": {
            "percent_remaining_energy": 0.80,
            "cell_soh_std": 0.07,
            "min_cell_soh": 0.45,
            "max_cell_soh": 0.98,
            "cell_fault_rate": 1e-3,
            "purchase_price_reference_usd": 230.0,
        },
    },
}

SCENARIO_PRESETS = {
    "base": {
        "facility": {
            "work_days_per_year": 230,
            "design_utilization": 0.90,
        },
        "capital": {
            "storage_rack_cost": 120.0,
            "forklift_cost": 18000.0,
            "workstation_cost": 800.0,
            "office_and_other_cost": 150000.0,
            "shipping_container_cost": 3200.0,
        },
        "wages": {
            "technician_wage_per_year": 93000.0,
            "forklift_operator_wage_per_year": 61700.0,
            "truck_driver_wage_per_year": 63000.0,
            "supervisor_wage_per_year": 95000.0,
            "chief_executive_wage_per_year": 260000.0,
            "electrical_engineer_wage_per_year": 100000.0,
            "sales_manager_wage_per_year": 100000.0,
            "admin_assistant_wage_per_year": 60000.0,
            "security_guard_wage_per_year": 54000.0,
            "hr_manager_wage_per_year": 105000.0,
            "operations_manager_wage_per_year": 120000.0,
            "janitor_wage_per_year": 52000.0,
            "non_wage_compensation_fraction": 0.30,
        },
        "economics": {
            "discount_rate": NORWAY_DISCOUNT_RATE,
            "electricity_testing_cost_per_kwh": 0.10,
            "hvac_lighting_cost_per_m2_year": 12.0,
            "rent_per_m2_year": 170.0,
            "other_direct_cost_fraction_of_wages": 0.02,
            "insurance_fraction_of_direct_costs": 0.025,
            "warranty_fraction_of_revenue": 0.04,
        },
        "learning": {
            "initial_utilization": 0.70,
            "max_utilization": 0.92,
            "utilization_improvement_per_year": 0.05,
            "handling_time_improvement_per_year": 0.03,
            "testing_time_improvement_per_year": 0.03,
            "packing_time_improvement_per_year": 0.03,
            "forklift_time_improvement_per_year": 0.02,
        },
        "reliability": {
            "samples": 50000,
            "seed": 20260429,
            "min_remaining_energy_fraction": 0.55,
        },
        "road_freight_reference_usd_per_km": 1.25,
    },
    "conservative": {
        "facility": {
            "work_days_per_year": 225,
            "design_utilization": 0.85,
        },
        "capital": {
            "storage_rack_cost": 130.0,
            "forklift_cost": 20000.0,
            "workstation_cost": 900.0,
            "office_and_other_cost": 170000.0,
            "shipping_container_cost": 3800.0,
        },
        "wages": {
            "technician_wage_per_year": 98000.0,
            "forklift_operator_wage_per_year": 65000.0,
            "truck_driver_wage_per_year": 67000.0,
            "supervisor_wage_per_year": 102000.0,
            "chief_executive_wage_per_year": 280000.0,
            "electrical_engineer_wage_per_year": 107000.0,
            "sales_manager_wage_per_year": 107000.0,
            "admin_assistant_wage_per_year": 63000.0,
            "security_guard_wage_per_year": 56000.0,
            "hr_manager_wage_per_year": 112000.0,
            "operations_manager_wage_per_year": 128000.0,
            "janitor_wage_per_year": 54000.0,
            "non_wage_compensation_fraction": 0.32,
        },
        "economics": {
            "discount_rate": NORWAY_DISCOUNT_RATE,
            "electricity_testing_cost_per_kwh": 0.13,
            "hvac_lighting_cost_per_m2_year": 16.0,
            "rent_per_m2_year": 215.0,
            "other_direct_cost_fraction_of_wages": 0.025,
            "insurance_fraction_of_direct_costs": 0.03,
            "warranty_fraction_of_revenue": 0.05,
        },
        "learning": {
            "initial_utilization": 0.65,
            "max_utilization": 0.88,
            "utilization_improvement_per_year": 0.04,
            "handling_time_improvement_per_year": 0.02,
            "testing_time_improvement_per_year": 0.02,
            "packing_time_improvement_per_year": 0.02,
            "forklift_time_improvement_per_year": 0.01,
        },
        "reliability": {
            "samples": 75000,
            "seed": 20260430,
            "min_remaining_energy_fraction": 0.65,
        },
        "road_freight_reference_usd_per_km": 1.45,
    },
    "optimistic": {
        "facility": {
            "work_days_per_year": 235,
            "design_utilization": 0.92,
        },
        "capital": {
            "storage_rack_cost": 110.0,
            "forklift_cost": 16000.0,
            "workstation_cost": 750.0,
            "office_and_other_cost": 130000.0,
            "shipping_container_cost": 2600.0,
        },
        "wages": {
            "technician_wage_per_year": 88000.0,
            "forklift_operator_wage_per_year": 58000.0,
            "truck_driver_wage_per_year": 60000.0,
            "supervisor_wage_per_year": 90000.0,
            "chief_executive_wage_per_year": 245000.0,
            "electrical_engineer_wage_per_year": 96000.0,
            "sales_manager_wage_per_year": 96000.0,
            "admin_assistant_wage_per_year": 57000.0,
            "security_guard_wage_per_year": 52000.0,
            "hr_manager_wage_per_year": 100000.0,
            "operations_manager_wage_per_year": 115000.0,
            "janitor_wage_per_year": 50000.0,
            "non_wage_compensation_fraction": 0.28,
        },
        "economics": {
            "discount_rate": NORWAY_DISCOUNT_RATE,
            "electricity_testing_cost_per_kwh": 0.08,
            "hvac_lighting_cost_per_m2_year": 8.0,
            "rent_per_m2_year": 145.0,
            "other_direct_cost_fraction_of_wages": 0.02,
            "insurance_fraction_of_direct_costs": 0.02,
            "warranty_fraction_of_revenue": 0.03,
        },
        "learning": {
            "initial_utilization": 0.75,
            "max_utilization": 0.95,
            "utilization_improvement_per_year": 0.05,
            "handling_time_improvement_per_year": 0.05,
            "testing_time_improvement_per_year": 0.04,
            "packing_time_improvement_per_year": 0.04,
            "forklift_time_improvement_per_year": 0.03,
        },
        "reliability": {
            "samples": 50000,
            "seed": 20260502,
            "min_remaining_energy_fraction": 0.55,
        },
        "road_freight_reference_usd_per_km": 1.10,
    },
    "high_failure": {
        "facility": {
            "work_days_per_year": 230,
            "design_utilization": 0.88,
        },
        "capital": {
            "storage_rack_cost": 120.0,
            "forklift_cost": 18000.0,
            "workstation_cost": 800.0,
            "office_and_other_cost": 160000.0,
            "shipping_container_cost": 3200.0,
        },
        "wages": {
            "technician_wage_per_year": 93000.0,
            "forklift_operator_wage_per_year": 61700.0,
            "truck_driver_wage_per_year": 63000.0,
            "supervisor_wage_per_year": 95000.0,
            "chief_executive_wage_per_year": 260000.0,
            "electrical_engineer_wage_per_year": 100000.0,
            "sales_manager_wage_per_year": 100000.0,
            "admin_assistant_wage_per_year": 60000.0,
            "security_guard_wage_per_year": 54000.0,
            "hr_manager_wage_per_year": 105000.0,
            "operations_manager_wage_per_year": 120000.0,
            "janitor_wage_per_year": 52000.0,
            "non_wage_compensation_fraction": 0.30,
        },
        "economics": {
            "discount_rate": NORWAY_DISCOUNT_RATE,
            "electricity_testing_cost_per_kwh": 0.10,
            "hvac_lighting_cost_per_m2_year": 12.0,
            "rent_per_m2_year": 170.0,
            "other_direct_cost_fraction_of_wages": 0.02,
            "insurance_fraction_of_direct_costs": 0.03,
            "warranty_fraction_of_revenue": 0.06,
        },
        "learning": {
            "initial_utilization": 0.70,
            "max_utilization": 0.90,
            "utilization_improvement_per_year": 0.04,
            "handling_time_improvement_per_year": 0.03,
            "testing_time_improvement_per_year": 0.03,
            "packing_time_improvement_per_year": 0.02,
            "forklift_time_improvement_per_year": 0.02,
        },
        "reliability": {
            "samples": 100000,
            "seed": 20260503,
            "min_remaining_energy_fraction": 0.60,
        },
        "road_freight_reference_usd_per_km": 1.35,
    },
}


def _reference_usd_values_to_nok(values: dict[str, float]) -> dict[str, float]:
    converted = {}
    for key, value in values.items():
        if key == "non_wage_compensation_fraction":
            converted[key] = value
        else:
            converted[key] = nok_from_usd(value)
    return converted


def _economic_reference_usd_values_to_nok(values: dict[str, float | None]) -> dict[str, float | None]:
    """Convert monetary economic reference values from USD to NOK.

    Rate and fraction fields must not be converted by the currency factor.
    """
    monetary_keys = {
        "forced_selling_price_per_kwh",
        "electricity_testing_cost_per_kwh",
        "hvac_lighting_cost_per_m2_year",
        "rent_per_m2_year",
    }
    converted = {}
    for key, value in values.items():
        if value is not None and key in monetary_keys:
            converted[key] = nok_from_usd(value)
        else:
            converted[key] = value
    return converted


def make_leaf_gen1_module(scenario_name: str = "base") -> Batterymodule:
    preset = MODULE_PRESETS[scenario_name]["leaf"]
    return Batterymodule(
        nameplate_energy_kWh=0.5,
        weight_kg=3.8,
        purchase_price=nok_from_usd(preset["purchase_price_reference_usd"]),
        height_mm=35.0,
        width_mm=223.0,
        length_mm=303.0,
        percent_remaining_energy=preset["percent_remaining_energy"],
        seriescells=2,
        paralellcells=2,
        cell_fault_rate=preset["cell_fault_rate"],
        cell_soh_std=preset["cell_soh_std"],
        min_cell_soh=preset["min_cell_soh"],
        max_cell_soh=preset["max_cell_soh"],
        forced_selling_price_per_kWh=LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
        chemistry="LMO",
    )


def set_component_selling_price(
    component: Batterymodule | pack,
    selling_price_nok_per_kwh: float,
) -> Batterymodule | pack:
    """Set the selling price on a module or on all modules inside a pack."""
    if isinstance(component, Batterymodule):
        component.forced_selling_price_per_kWh = selling_price_nok_per_kwh
        return component

    for module_string in component.modules:
        for module in module_string:
            module.forced_selling_price_per_kWh = selling_price_nok_per_kwh
    component.calculate_pack_properties()
    return component


def make_leaf_gen1_module_from_pack_purchase(
    scenario_name: str = "base",
    pack_purchase_price_reference_usd_per_kwh: float | None = 12.0,
    pack_purchase_price_nok_per_kwh: float | None = None,
) -> Batterymodule:
    """Create a Leaf module when the facility buys complete packs, not modules.

    The model still processes and sells individual modules, but the acquisition
    price is based on buying complete packs in larger units.  This represents a
    pack-to-modules pathway: buy a complete Leaf pack, disassemble it, test the
    modules individually, and sell the accepted modules.  A lower purchase price
    per kWh is used because the facility buys complete packs rather than already
    separated, screened modules.
    """
    module = make_leaf_gen1_module(scenario_name)
    if pack_purchase_price_nok_per_kwh is None:
        if pack_purchase_price_reference_usd_per_kwh is None:
            raise ValueError(
                "Specify either pack_purchase_price_reference_usd_per_kwh or "
                "pack_purchase_price_nok_per_kwh"
            )
        pack_purchase_price_nok_per_kwh = nok_from_usd(pack_purchase_price_reference_usd_per_kwh)
    module.purchase_price = pack_purchase_price_nok_per_kwh * module.nameplate_energy_kWh
    return module


def make_leaf_gen1_pack_from_pack_purchase(
    scenario_name: str = "base",
    pack_purchase_price_reference_usd_per_kwh: float | None = 12.0,
    pack_purchase_price_nok_per_kwh: float | None = None,
) -> pack:
    """Create a Leaf pack bought as a complete used pack at pack-level price."""
    component = make_leaf_gen1_pack(scenario_name)
    if pack_purchase_price_nok_per_kwh is None:
        if pack_purchase_price_reference_usd_per_kwh is None:
            raise ValueError(
                "Specify either pack_purchase_price_reference_usd_per_kwh or "
                "pack_purchase_price_nok_per_kwh"
            )
        pack_purchase_price_nok_per_kwh = nok_from_usd(pack_purchase_price_reference_usd_per_kwh)
    purchase_nok_per_kwh = pack_purchase_price_nok_per_kwh
    for module_string in component.modules:
        for module in module_string:
            module.purchase_price = purchase_nok_per_kwh * module.nameplate_energy_kWh
    component.calculate_pack_properties()
    return component


def _leaf_triage_reliability_summary(
    component: pack,
    scenario: b2u.B2UScenario,
    pack_acceptance_threshold: float,
    module_acceptance_threshold: float,
) -> dict:
    """Build a mixed-output reliability summary for Leaf pack-first triage.

    Incoming packs are first screened as complete packs. Passing packs are sold
    as packs. Packs that fail complete-pack screening are disassembled and the
    modules are screened individually. The returned summary is expressed per
    incoming pack so it can be used by the B2U facility model as an operational
    pathway sensitivity.
    """
    samples = scenario.reliability.samples
    seed = scenario.reliability.seed

    pack_summary = component_reliability_summary(
        component=component,
        samples=samples,
        min_remaining_energy_fraction=pack_acceptance_threshold,
        seed=seed,
        use_remaining_energy_for_revenue=True,
    )

    representative_module = component.modules[0][0]
    module_summary = component_reliability_summary(
        component=representative_module,
        samples=samples,
        min_remaining_energy_fraction=module_acceptance_threshold,
        seed=None if seed is None else seed + 17,
        use_remaining_energy_for_revenue=True,
    )

    pack_pass_fraction = float(pack_summary["usable_fraction"])
    pack_fail_fraction = 1.0 - pack_pass_fraction
    module_usable_fraction = float(module_summary["usable_fraction"])
    modules_per_pack = LEAF_GEN1_MODULES_PER_PACK

    sellable_energy_from_packs = float(pack_summary["mean_sellable_energy_kwh_per_unit"])
    sellable_energy_from_recovered_modules = (
        pack_fail_fraction
        * modules_per_pack
        * float(module_summary["mean_sellable_energy_kwh_per_unit"])
    )
    total_sellable_energy = sellable_energy_from_packs + sellable_energy_from_recovered_modules

    probability_no_recovered_module = (1.0 - module_usable_fraction) ** modules_per_pack
    usable_fraction = pack_pass_fraction + pack_fail_fraction * (1.0 - probability_no_recovered_module)

    return {
        "method": "leaf_pack_first_triage",
        "samples": samples,
        "seed": seed,
        "min_remaining_energy_fraction": pack_acceptance_threshold,
        "module_acceptance_threshold": module_acceptance_threshold,
        "cell_fault_rate": pack_summary.get("cell_fault_rate"),
        "cells_per_unit": pack_summary.get("cells_per_unit"),
        "seriescells": pack_summary.get("seriescells"),
        "paralellcells": pack_summary.get("paralellcells"),
        "usable_fraction": usable_fraction,
        "rejected_fraction": 1.0 - usable_fraction,
        "mean_failed_cells": pack_summary.get("mean_failed_cells", 0.0),
        "mean_failed_series_groups": pack_summary.get("mean_failed_series_groups", 0.0),
        "mean_failed_strings": pack_summary.get("mean_failed_strings", 0.0),
        "mean_remaining_energy_kwh": pack_summary.get("mean_remaining_energy_kwh"),
        "mean_remaining_energy_fraction": pack_summary.get("mean_remaining_energy_fraction"),
        "mean_sellable_energy_kwh_per_unit": total_sellable_energy,
        "p05_remaining_energy_fraction": pack_summary.get("p05_remaining_energy_fraction"),
        "p50_remaining_energy_fraction": pack_summary.get("p50_remaining_energy_fraction"),
        "p95_remaining_energy_fraction": pack_summary.get("p95_remaining_energy_fraction"),
        "pack_pass_fraction": pack_pass_fraction,
        "pack_disassembly_fraction": pack_fail_fraction,
        "module_recovery_usable_fraction": module_usable_fraction,
        "sellable_energy_from_packs_kwh_per_input_pack": sellable_energy_from_packs,
        "sellable_energy_from_recovered_modules_kwh_per_input_pack": sellable_energy_from_recovered_modules,
    }


def make_leaf_pack_triage_pathway(
    scenario_name: str = "base",
    pack_purchase_price_reference_usd_per_kwh: float | None = 12.0,
    pack_purchase_price_nok_per_kwh: float | None = None,
    pack_acceptance_threshold: float = 0.55,
    module_acceptance_threshold: float = 0.55,
    disassembly_time_s_per_module: float = 240.0,
    module_recovery_testing_time_s_per_module: float = 300.0,
    pack_selling_price_nok_per_kwh: float | None = None,
    recovered_module_selling_price_nok_per_kwh: float | None = None,
) -> tuple[pack, b2u.B2UScenario]:
    """Create a Leaf pack-first triage pathway.

    Complete packs are bought and screened first. Packs passing the pack-level
    threshold are sold as packs. Packs failing the pack-level threshold are
    disassembled and recovered modules are screened individually. The additional
    recovery labour is averaged over incoming packs using the simulated fraction
    of packs that fail pack-level screening.
    """
    component = make_leaf_gen1_pack_from_pack_purchase(
        scenario_name,
        pack_purchase_price_reference_usd_per_kwh=pack_purchase_price_reference_usd_per_kwh,
        pack_purchase_price_nok_per_kwh=pack_purchase_price_nok_per_kwh,
    )
    scenario = make_norway_scenario(scenario_name)
    reliability_summary = _leaf_triage_reliability_summary(
        component=component,
        scenario=scenario,
        pack_acceptance_threshold=pack_acceptance_threshold,
        module_acceptance_threshold=module_acceptance_threshold,
    )
    failed_pack_fraction = float(reliability_summary["pack_disassembly_fraction"])

    if (
        pack_selling_price_nok_per_kwh is not None
        and recovered_module_selling_price_nok_per_kwh is not None
    ):
        # The B2U core accepts one selling price per processed unit. For the
        # triage pathway, output is mixed: passing packs are sold whole and
        # failed packs may contribute recovered modules. Represent this as an
        # energy-weighted average product price rather than forcing raw-pack and
        # recovered-module energy to have the same value.
        pack_energy = float(
            reliability_summary["sellable_energy_from_packs_kwh_per_input_pack"]
        )
        recovered_module_energy = float(
            reliability_summary[
                "sellable_energy_from_recovered_modules_kwh_per_input_pack"
            ]
        )
        total_sellable_energy = pack_energy + recovered_module_energy
        if total_sellable_energy > 0:
            weighted_selling_price = (
                pack_energy * pack_selling_price_nok_per_kwh
                + recovered_module_energy * recovered_module_selling_price_nok_per_kwh
            ) / total_sellable_energy
            set_component_selling_price(component, weighted_selling_price)

    recovery_time_per_failed_pack = LEAF_GEN1_MODULES_PER_PACK * (
        disassembly_time_s_per_module + module_recovery_testing_time_s_per_module
    )
    labor = replace(
        scenario.labor,
        disassembly_time_s_per_unit=(failed_pack_fraction * recovery_time_per_failed_pack),
    )
    reliability = replace(
        scenario.reliability,
        min_remaining_energy_fraction=pack_acceptance_threshold,
        summary_override=reliability_summary,
    )
    return component, replace(
        scenario,
        name=f"norway_{scenario_name}_leaf_pack_triage",
        labor=labor,
        reliability=reliability,
    )


def with_leaf_pack_disassembly(
    scenario: b2u.B2UScenario,
    disassembly_time_s_per_module: float = 240.0,
) -> b2u.B2UScenario:
    """Add pack-disassembly labour to a module-level Leaf pathway.

    The processed unit remains a Leaf module.  The added time represents the
    average labour required to break complete incoming packs into modules before
    module-level testing and resale.
    """
    labor = replace(
        scenario.labor,
        disassembly_time_s_per_unit=disassembly_time_s_per_module,
    )
    return replace(scenario, labor=labor)


def make_leaf_gen1_pack(
    scenario_name: str = "base",
    modules_per_pack: int = 48,
) -> pack:
    """Create a simplified Nissan Leaf Gen 1 pack from module presets.

    The first-generation 24 kWh Leaf pack is represented as 48 modules in a
    single series string. This keeps the pack case compatible with the existing
    component hierarchy while allowing the B2U model to compare module-level
    and pack-level handling. The pack object aggregates mass, volume, purchase
    price, and topology-aware remaining energy from the module objects.
    """
    if modules_per_pack < 1:
        raise ValueError("modules_per_pack must be at least 1")
    modules = [make_leaf_gen1_module(scenario_name) for _ in range(modules_per_pack)]
    return pack([modules])


def make_tesla_model_s_gen1_module(scenario_name: str = "base") -> Batterymodule:
    preset = MODULE_PRESETS[scenario_name]["tesla"]
    return Batterymodule(
        nameplate_energy_kWh=5.3,
        weight_kg=25.6,
        purchase_price=nok_from_usd(preset["purchase_price_reference_usd"]),
        height_mm=79.0,
        width_mm=300.0,
        length_mm=685.0,
        percent_remaining_energy=preset["percent_remaining_energy"],
        seriescells=6,
        paralellcells=74,
        cell_fault_rate=preset["cell_fault_rate"],
        cell_soh_std=preset["cell_soh_std"],
        min_cell_soh=preset["min_cell_soh"],
        max_cell_soh=preset["max_cell_soh"],
        forced_selling_price_per_kWh=TESLA_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
        chemistry="NCA",
    )


def make_norway_scenario(scenario_name: str = "base") -> b2u.B2UScenario:
    preset = SCENARIO_PRESETS[scenario_name]

    base_facility = b2u.FacilityAssumptions()
    facility = replace(base_facility, **preset["facility"])

    base_capital = b2u.CapitalCostAssumptions()
    # Convert the default B2U reference capital set first, then apply
    # scenario-specific Norwegian overrides. This prevents inherited reference
    # values, such as test-channel and computer costs, from leaking through as
    # unconverted USD values in NOK scenarios.
    capital_values = _reference_usd_values_to_nok(vars(base_capital))
    capital_values.update(_reference_usd_values_to_nok(preset["capital"]))
    capital = b2u.CapitalCostAssumptions(**capital_values)

    wages = b2u.WageAssumptions(
        **_reference_usd_values_to_nok(preset["wages"])
    )

    base_economics = b2u.EconomicAssumptions(
        federal_tax_rate=0.22,
        state_tax_rate=0.0,
    )
    economics = replace(
        base_economics,
        **_economic_reference_usd_values_to_nok(preset["economics"]),
    )

    base_learning = b2u.LearningAssumptions()
    learning = replace(base_learning, **preset["learning"])

    reliability = b2u.ReliabilityAssumptions(
        enabled=True,
        use_remaining_energy_for_revenue=True,
        **preset["reliability"],
    )

    currency = b2u.CurrencyAssumptions(
        currency="NOK",
        nok_per_usd=NOK_PER_USD,
        monetary_values_are_ex_vat=True,
        vat_rate=VAT_RATE,
        include_vat_in_profit=False,
    )

    collection_scale = "Regional"
    transport_profile = b2u.TRANSPORT_PROFILES[collection_scale]
    road_freight = b2u.RoadFreightAssumptions(
        truck_operating_cost_per_m=nok_per_m_from_usd_per_km(
            preset["road_freight_reference_usd_per_km"]
        ),
        truck_purchase_cost=nok_from_usd(
            transport_profile.truck_purchase_cost
        ),
    )

    return b2u.B2UScenario(
        name=f"norway_{scenario_name}",
        facility=facility,
        capital=capital,
        wages=wages,
        economics=economics,
        learning=learning,
        reliability=reliability,
        currency=currency,
        road_freight=road_freight,
        collection_scale=collection_scale,
    )


def make_norway_case(
    chemistry: str,
    scenario_name: str = "base",
) -> tuple[str, Batterymodule | pack, b2u.B2UScenario]:
    scenario = make_norway_scenario(scenario_name)
    if chemistry == "leaf":
        return (
            f"leaf_{scenario.name}",
            make_leaf_gen1_module(scenario_name),
            scenario,
        )
    if chemistry == "leaf_pack":
        return (
            f"leaf_pack_{scenario.name}",
            make_leaf_gen1_pack(scenario_name),
            scenario,
        )
    if chemistry == "tesla":
        return (
            f"tesla_{scenario.name}",
            make_tesla_model_s_gen1_module(scenario_name),
            scenario,
        )
    raise ValueError("chemistry must be 'leaf', 'leaf_pack', or 'tesla'")


def iter_core_norway_cases(include_leaf_pack: bool = True):
    for scenario_name in ("base", "high_failure"):
        yield make_norway_case("leaf", scenario_name)
        if include_leaf_pack:
            yield make_norway_case("leaf_pack", scenario_name)
        yield make_norway_case("tesla", scenario_name)


def iter_all_norway_cases(include_leaf_pack: bool = True):
    for scenario_name in ("base", "conservative", "optimistic", "high_failure"):
        yield make_norway_case("leaf", scenario_name)
        if include_leaf_pack:
            yield make_norway_case("leaf_pack", scenario_name)
        yield make_norway_case("tesla", scenario_name)


if __name__ == "__main__":
    import json

    for label, component, scenario in iter_core_norway_cases():
        result = b2u.run_b2u_scenario(component, scenario)
        output = result.to_dict()
        print(f"\n=== {label} ===")
        currency = output["currency"]["currency"]
        npv_key = f"total_npv_{currency.lower()}"
        print(f"Currency: {currency}")
        print(f"NPV: {output['revenue_npv'].get(npv_key, output['revenue_npv']['total_npv']):.0f}")
        print(json.dumps(output["reliability"], indent=2))
