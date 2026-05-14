import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import b2u

from norway_scenarios import (
    LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
    LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
    LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
    NOK_PER_USD,
    make_leaf_gen1_module,
    make_leaf_gen1_module_from_pack_purchase,
    make_leaf_gen1_pack,
    make_leaf_gen1_pack_from_pack_purchase,
    make_leaf_pack_triage_pathway,
    make_norway_scenario,
)
from norway_sensitivity import sensitivity_cases


class TestNorwayScenarioAssumptions(unittest.TestCase):
    def test_economic_rates_are_not_currency_converted(self):
        scenario = make_norway_scenario("base")
        self.assertAlmostEqual(scenario.economics.discount_rate, 0.10)
        self.assertAlmostEqual(scenario.economics.federal_tax_rate, 0.22)
        self.assertAlmostEqual(
            scenario.economics.warranty_fraction_of_revenue,
            0.04,
        )
        self.assertAlmostEqual(
            scenario.economics.insurance_fraction_of_direct_costs,
            0.025,
        )

    def test_monetary_economic_values_are_converted_to_nok(self):
        scenario = make_norway_scenario("base")
        self.assertAlmostEqual(
            scenario.economics.electricity_testing_usd_per_kwh,
            0.10 * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.economics.rent_usd_per_m2_year,
            170.0 * NOK_PER_USD,
        )


    def test_norway_capital_defaults_are_converted_to_nok(self):
        scenario = make_norway_scenario("base")
        b2u_defaults = b2u.CapitalCostAssumptions()

        self.assertAlmostEqual(
            scenario.capital.test_channel_cost_usd_per_station,
            b2u_defaults.test_channel_cost_usd_per_station * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.capital.can_hardware_cost_usd_per_station,
            b2u_defaults.can_hardware_cost_usd_per_station * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.capital.computer_cost_usd,
            b2u_defaults.computer_cost_usd * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.capital.conveyor_cost_usd_per_m2,
            b2u_defaults.conveyor_cost_usd_per_m2 * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.capital.storage_rack_cost_usd,
            120.0 * NOK_PER_USD,
        )

    def test_regional_truck_purchase_cost_is_converted_to_nok(self):
        scenario = make_norway_scenario("base")
        regional_profile = b2u.TRANSPORT_PROFILES["Regional"]

        self.assertAlmostEqual(
            scenario.road_freight.truck_purchase_cost,
            regional_profile.truck_purchase_cost_usd * NOK_PER_USD,
        )
        self.assertAlmostEqual(
            scenario.road_freight.truck_operating_cost_per_m,
            1.25 * NOK_PER_USD / 1000.0,
        )

    def test_cell_soh_lower_bound_is_separate_from_acceptance_threshold(self):
        module = make_leaf_gen1_module("base")
        scenario = make_norway_scenario("base")
        self.assertLess(
            module.min_cell_soh,
            scenario.reliability.min_remaining_energy_fraction,
        )

    def test_sensitivity_cases_include_broad_failure_sweep(self):
        cases = list(sensitivity_cases("leaf"))
        fault_values = [
            value for _, name, value, _, _ in cases
            if name == "cell_fault_rate"
        ]
        self.assertEqual(
            fault_values,
            [1e-6, 1e-5, 5e-5, 2e-4, 1e-3, 5e-3, 1e-2],
        )

    def test_leaf_pack_preset_contains_48_modules(self):
        component = make_leaf_gen1_pack("base")
        self.assertEqual(component.number_of_modules, 48)
        self.assertAlmostEqual(component.nameplate_energy_kWh, 24.0)

    def test_leaf_acquisition_and_resale_prices_are_separated(self):
        pack_component = make_leaf_gen1_pack_from_pack_purchase(
            "base",
            pack_purchase_price_usd_per_kwh=None,
            pack_purchase_price_nok_per_kwh=LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
        )
        module_component = make_leaf_gen1_module_from_pack_purchase(
            "base",
            pack_purchase_price_usd_per_kwh=None,
            pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
        )

        self.assertLess(
            LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
            LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
        )
        self.assertLess(
            LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
            LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
        )
        self.assertAlmostEqual(
            pack_component.purchase_price / pack_component.nameplate_energy_kWh,
            LEAF_PACK_BULK_ACQUISITION_PRICE_NOK_PER_KWH,
        )
        self.assertAlmostEqual(
            module_component.purchase_price / module_component.nameplate_energy_kWh,
            LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
        )

    def test_triage_uses_weighted_output_price_when_pack_and_module_prices_differ(self):
        component, scenario = make_leaf_pack_triage_pathway(
            "base",
            pack_purchase_price_usd_per_kwh=None,
            pack_purchase_price_nok_per_kwh=LEAF_PACK_TO_MODULES_ACQUISITION_PRICE_NOK_PER_KWH,
            pack_acceptance_threshold=0.55,
            module_acceptance_threshold=0.55,
            pack_selling_price_nok_per_kwh=LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH,
            recovered_module_selling_price_nok_per_kwh=LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH,
        )
        summary = scenario.reliability.summary_override
        self.assertIsNotNone(summary)
        effective_price = component.modules[0][0].forced_selling_price_per_kWh
        self.assertGreaterEqual(
            effective_price,
            min(LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH, LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH),
        )
        self.assertLessEqual(
            effective_price,
            max(LEAF_PACK_MARKET_SELLING_PRICE_NOK_PER_KWH, LEAF_MODULE_MARKET_SELLING_PRICE_NOK_PER_KWH),
        )


if __name__ == "__main__":
    unittest.main()

class TestCurrencyNeutralCalculation(unittest.TestCase):
    def test_scenario_currency_is_metadata_not_conversion_logic(self):
        import b2u
        from Batterycomponents import Batterymodule

        module = Batterymodule(
            nameplate_energy_kWh=1.0,
            weight_kg=10.0,
            purchase_price=100.0,
            percent_remaining_energy=0.8,
            forced_selling_price_per_kWh=150.0,
        )
        usd = b2u.B2UScenario(currency=b2u.CurrencyAssumptions(currency="USD"))
        nok = b2u.B2UScenario(currency=b2u.CurrencyAssumptions(currency="NOK"))

        usd_result = b2u.run_b2u_scenario(module, usd).to_dict()
        nok_result = b2u.run_b2u_scenario(module, nok).to_dict()

        self.assertAlmostEqual(
            usd_result["revenue_npv"]["total_npv_usd"],
            nok_result["revenue_npv"]["total_npv_usd"],
        )
        self.assertIn("total_npv_nok", nok_result["revenue_npv"])
        self.assertAlmostEqual(
            nok_result["revenue_npv"]["total_npv_usd"],
            nok_result["revenue_npv"]["total_npv_nok"],
        )
        self.assertIn("unit_economics", nok_result)
        self.assertIn(
            "break_even_selling_price_nok_per_kwh",
            nok_result["unit_economics"],
        )
