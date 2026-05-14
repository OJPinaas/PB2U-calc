"""Tests for the B2U break-even selling price fixes.

Covers:
1. annual_break_even_selling_price is independent of actual selling price input
2. annual_break_even_selling_price increases with warranty fraction
3. Zero sellable energy gives NaN for annual break-even selling price
4. NPV break-even selling price solver returns a price with NPV ≈ 0
5. Leaf base/reference case has positive sellable energy
6. Norway plot x-values for USD price parameters are converted to NOK
7. Selling price is excluded from break-even-selling-price tornado plots
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import b2u
from Batterycomponents import Batterymodule
from max_purchase_price import solve_npv_break_even_selling_price
from norway_scenarios import (
    NOK_PER_USD,
    make_leaf_gen1_module,
    make_leaf_gen1_pack,
    make_norway_scenario,
    make_tesla_model_s_gen1_module,
)
from plot_norway_extended_analysis import (
    _BREAK_EVEN_SELLING_PRICE_METRICS,
    _METRIC_LABELS,
    _USD_PRICE_PARAMETERS,
    _convert_parameter_value_to_nok,
)


def _make_simple_module(selling_price: float, warranty_fraction: float = 0.05) -> tuple:
    """Return a simple module and scenario for unit-economics tests."""
    module = Batterymodule(
        nameplate_energy_kWh=5.0,
        weight_kg=43.0,
        purchase_price=100.0,
        percent_remaining_energy=0.80,
        seriescells=6,
        paralellcells=10,
        cell_fault_rate=1e-5,
        forced_selling_price_per_kWh=selling_price,
        chemistry="NMC",
    )
    scenario = b2u.B2UScenario(
        economics=b2u.EconomicAssumptions(
            warranty_fraction_of_revenue=warranty_fraction,
        )
    )
    return module, scenario


def _annual_break_even(module, scenario):
    result = b2u.run_b2u_scenario(module, scenario).to_dict()
    return result["unit_economics"]["annual_break_even_selling_price_usd_per_kwh"]


class TestAnnualBreakEvenSellingPriceIndependence(unittest.TestCase):
    """annual_break_even_selling_price must not depend on actual selling price."""

    def test_break_even_does_not_change_with_selling_price(self):
        module_low, scenario = _make_simple_module(selling_price=30.0)
        module_high, _ = _make_simple_module(selling_price=200.0)

        be_low = _annual_break_even(module_low, scenario)
        be_high = _annual_break_even(module_high, scenario)

        self.assertFalse(math.isnan(be_low))
        self.assertAlmostEqual(be_low, be_high, places=1,
                               msg="annual_break_even_selling_price must be "
                                   "independent of actual selling price")

    def test_break_even_changes_with_warranty_fraction(self):
        module_low_w, scenario_low_w = _make_simple_module(selling_price=100.0, warranty_fraction=0.02)
        module_high_w, scenario_high_w = _make_simple_module(selling_price=100.0, warranty_fraction=0.10)

        be_low = _annual_break_even(module_low_w, scenario_low_w)
        be_high = _annual_break_even(module_high_w, scenario_high_w)

        self.assertFalse(math.isnan(be_low))
        self.assertFalse(math.isnan(be_high))
        # Higher warranty fraction → higher break-even price (warranty cost is
        # proportional to revenue, so the remaining non-warranty expenses must
        # be recovered from a smaller effective margin per kWh)
        self.assertGreater(be_high, be_low,
                           msg="annual_break_even_selling_price should increase "
                               "with warranty_fraction")

    def test_zero_sellable_energy_gives_nan(self):
        # Force all cells to fail by setting a very high fault rate
        module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=43.0,
            purchase_price=100.0,
            percent_remaining_energy=0.80,
            seriescells=6,
            paralellcells=10,
            cell_fault_rate=1.0,  # 100 % fault rate → all cells fail
            forced_selling_price_per_kWh=100.0,
            chemistry="NMC",
        )
        scenario = b2u.B2UScenario()
        result = b2u.run_b2u_scenario(module, scenario).to_dict()
        be = result["unit_economics"]["annual_break_even_selling_price_usd_per_kwh"]
        self.assertTrue(math.isnan(be),
                        msg="annual_break_even_selling_price should be NaN "
                            "when sellable energy is zero")

    def test_warranty_fraction_at_one_gives_nan(self):
        module, _ = _make_simple_module(selling_price=100.0, warranty_fraction=1.0)
        scenario = b2u.B2UScenario(
            economics=b2u.EconomicAssumptions(warranty_fraction_of_revenue=1.0)
        )
        result = b2u.run_b2u_scenario(module, scenario).to_dict()
        be = result["unit_economics"]["annual_break_even_selling_price_usd_per_kwh"]
        self.assertTrue(math.isnan(be),
                        msg="annual_break_even_selling_price should be NaN "
                            "when warranty_fraction >= 1")

    def test_legacy_break_even_field_aliases_corrected_annual_value(self):
        module, scenario = _make_simple_module(selling_price=100.0)
        result = b2u.run_b2u_scenario(module, scenario).to_dict()
        unit_economics = result["unit_economics"]
        self.assertAlmostEqual(
            unit_economics["break_even_selling_price_usd_per_kwh"],
            unit_economics["annual_break_even_selling_price_usd_per_kwh"],
            msg="Legacy break_even_selling_price field must not keep the old circular value",
        )


class TestNpvBreakEvenSellingPriceSolver(unittest.TestCase):
    """NPV break-even selling price solver should return a price where NPV ≈ 0."""

    def _npv_at_price(self, component, scenario, price_per_kwh: float) -> float:
        from dataclasses import replace
        economics = replace(
            scenario.economics,
            forced_selling_price_usd_per_kwh=price_per_kwh,
        )
        s = replace(scenario, economics=economics)
        result = b2u.run_b2u_scenario(component, s).to_dict()
        currency = result["currency"].get("currency", "USD").lower()
        return float(
            result["revenue_npv"].get(
                f"total_npv_{currency}",
                result["revenue_npv"]["total_npv_usd"],
            )
        )

    def test_solver_returns_near_zero_npv_for_tesla(self):
        module = make_tesla_model_s_gen1_module("base")
        scenario = make_norway_scenario("base")
        from dataclasses import replace
        scenario = replace(
            scenario,
            reliability=replace(scenario.reliability, samples=2000, seed=42),
        )
        solver_result = solve_npv_break_even_selling_price(module, scenario)
        be_price = solver_result.npv_break_even_selling_price_per_kwh
        self.assertFalse(math.isnan(be_price),
                         msg="Solver should return a valid price for Tesla module")
        npv_at_be = self._npv_at_price(module, scenario, be_price)
        # NPV at break-even price should be approximately zero (within 1% of
        # annual revenue magnitude)
        npv_at_zero = solver_result.npv_at_zero_selling_price
        scale = max(abs(npv_at_zero), 1.0)
        self.assertAlmostEqual(npv_at_be / scale, 0.0, places=1,
                               msg="NPV at break-even selling price should be ≈ 0")

    def test_solver_returns_near_zero_npv_for_leaf(self):
        module = make_leaf_gen1_module("base")
        scenario = make_norway_scenario("base")
        from dataclasses import replace
        scenario = replace(
            scenario,
            reliability=replace(scenario.reliability, samples=2000, seed=42),
        )
        solver_result = solve_npv_break_even_selling_price(module, scenario)
        be_price = solver_result.npv_break_even_selling_price_per_kwh
        self.assertFalse(math.isnan(be_price),
                         msg="Solver should return a valid price for Leaf module")
        # Verify NPV at break-even price is close to zero
        npv_at_be = self._npv_at_price(module, scenario, be_price)
        npv_at_zero = solver_result.npv_at_zero_selling_price
        scale = max(abs(npv_at_zero), 1.0)
        self.assertAlmostEqual(npv_at_be / scale, 0.0, places=1,
                               msg="NPV at break-even selling price should be ≈ 0")

    def test_solver_returns_near_zero_npv_for_leaf_pack(self):
        pack_component = make_leaf_gen1_pack("base", modules_per_pack=4)
        scenario = make_norway_scenario("base")
        from dataclasses import replace
        scenario = replace(
            scenario,
            reliability=replace(scenario.reliability, samples=500, seed=42),
        )
        solver_result = solve_npv_break_even_selling_price(pack_component, scenario)
        be_price = solver_result.npv_break_even_selling_price_per_kwh
        self.assertFalse(math.isnan(be_price),
                         msg="Solver should return a valid price for Leaf pack")

    def test_no_sellable_energy_returns_nan(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=43.0,
            purchase_price=100.0,
            percent_remaining_energy=0.80,
            seriescells=6,
            paralellcells=10,
            cell_fault_rate=1.0,  # all cells fail → no sellable energy
            forced_selling_price_per_kWh=100.0,
            chemistry="NMC",
        )
        scenario = b2u.B2UScenario()
        result = solve_npv_break_even_selling_price(module, scenario)
        self.assertTrue(math.isnan(result.npv_break_even_selling_price_per_kwh),
                        msg="Solver should return NaN when there is no sellable energy")


class TestLeafBaseCasePositiveSellableEnergy(unittest.TestCase):
    """Leaf base/reference case must have positive sellable energy."""

    def test_leaf_base_has_positive_sellable_energy(self):
        module = make_leaf_gen1_module("base")
        scenario = make_norway_scenario("base")
        from dataclasses import replace
        scenario = replace(
            scenario,
            reliability=replace(scenario.reliability, samples=2000, seed=42),
        )
        result = b2u.run_b2u_scenario(module, scenario)
        sellable = result.reliability["mean_sellable_energy_kwh_per_unit"]
        usable = result.reliability["usable_fraction"]
        self.assertGreater(usable, 0.0,
                           msg="Leaf base case must have positive usable fraction")
        self.assertGreater(sellable, 0.0,
                           msg="Leaf base case must have positive sellable energy per unit")

    def test_leaf_base_threshold_is_55_percent(self):
        scenario = make_norway_scenario("base")
        self.assertAlmostEqual(
            scenario.reliability.min_remaining_energy_fraction,
            0.55,
            msg="Leaf base case acceptance threshold should be 0.55",
        )


class TestNorwayPlotNokConversion(unittest.TestCase):
    """Norway plot x-values for USD price parameters should be converted to NOK."""

    def test_selling_price_parameter_is_usd_price_parameter(self):
        self.assertIn("selling_price_usd_per_kwh", _USD_PRICE_PARAMETERS)

    def test_purchase_price_parameter_is_usd_price_parameter(self):
        self.assertIn("purchase_price_usd_per_kwh_nameplate", _USD_PRICE_PARAMETERS)

    def test_convert_parameter_value_to_nok_selling_price(self):
        usd_value = 100.0
        nok_value = _convert_parameter_value_to_nok(
            "selling_price_usd_per_kwh", usd_value, NOK_PER_USD
        )
        self.assertAlmostEqual(nok_value, usd_value * NOK_PER_USD)

    def test_convert_parameter_value_to_nok_purchase_price(self):
        usd_value = 50.0
        nok_value = _convert_parameter_value_to_nok(
            "purchase_price_usd_per_kwh_nameplate", usd_value, NOK_PER_USD
        )
        self.assertAlmostEqual(nok_value, usd_value * NOK_PER_USD)

    def test_non_price_parameter_is_not_converted(self):
        value = 0.04
        converted = _convert_parameter_value_to_nok("discount_rate", value, NOK_PER_USD)
        self.assertAlmostEqual(converted, value,
                               msg="Non-price parameters should not be converted")

    def test_tornado_metric_labels_include_nok_units(self):
        self.assertEqual(_METRIC_LABELS["npv"], "NPV [MNOK]")
        self.assertIn("[NOK/kWh]", _METRIC_LABELS["npv_break_even_selling_price_per_kwh"])


class TestSellingPriceExclusionFromBreakEvenTornados(unittest.TestCase):
    """Break-even-selling-price metrics must have selling_price in the exclusion set."""

    def test_annual_break_even_metric_triggers_selling_price_exclusion(self):
        self.assertIn(
            "annual_break_even_selling_price_per_kwh",
            _BREAK_EVEN_SELLING_PRICE_METRICS,
            msg="annual_break_even_selling_price_per_kwh must be in the exclusion set "
                "so that selling_price_usd_per_kwh is excluded from its tornado plot",
        )

    def test_break_even_metric_triggers_selling_price_exclusion(self):
        self.assertIn(
            "break_even_selling_price_per_kwh",
            _BREAK_EVEN_SELLING_PRICE_METRICS,
            msg="break_even_selling_price_per_kwh must be in the exclusion set "
                "so that selling_price_usd_per_kwh is excluded from its tornado plot",
        )

    def test_npv_break_even_metric_triggers_selling_price_exclusion(self):
        self.assertIn(
            "npv_break_even_selling_price_per_kwh",
            _BREAK_EVEN_SELLING_PRICE_METRICS,
            msg="npv_break_even_selling_price_per_kwh must be in the exclusion set "
                "so that selling_price_usd_per_kwh is excluded from its tornado plot",
        )

    def test_npv_metric_does_not_trigger_selling_price_exclusion(self):
        self.assertNotIn(
            "npv",
            _BREAK_EVEN_SELLING_PRICE_METRICS,
            msg="npv must NOT be in the exclusion set; "
                "selling_price_usd_per_kwh should appear in NPV tornado plots",
        )


class TestThesisCaseMetadata(unittest.TestCase):
    """iter_thesis_cases must emit the expected case_type metadata."""

    def setUp(self):
        import sys
        from pathlib import Path
        PROJECT_ROOT = Path(__file__).resolve().parents[1]
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

    def test_iter_thesis_cases_yields_four_tuples(self):
        from thesis_scenarios import iter_thesis_cases
        for item in iter_thesis_cases():
            self.assertEqual(
                len(item), 4,
                msg="iter_thesis_cases must yield (label, component, scenario, metadata)",
            )
            break  # one is enough to verify structure

    def test_base_break_even_reference_cases_present(self):
        from thesis_scenarios import iter_thesis_cases
        case_types = [metadata["case_type"] for _, _, _, metadata in iter_thesis_cases()]
        self.assertIn(
            "base_break_even_reference",
            case_types,
            msg="At least one base_break_even_reference case must be present",
        )

    def test_market_cases_present(self):
        from thesis_scenarios import iter_thesis_cases
        case_types = [metadata["case_type"] for _, _, _, metadata in iter_thesis_cases()]
        self.assertIn("market", case_types)

    def test_feasibility_cases_present(self):
        from thesis_scenarios import iter_thesis_cases
        case_types = [metadata["case_type"] for _, _, _, metadata in iter_thesis_cases()]
        self.assertIn("feasibility", case_types)

    def test_reference_case_has_calibration_metadata(self):
        from thesis_scenarios import iter_thesis_cases
        for _, _, _, metadata in iter_thesis_cases():
            if metadata["case_type"] == "base_break_even_reference":
                self.assertEqual(metadata["calibrated_variable"], "selling_price_per_kwh")
                self.assertEqual(metadata["calibration_target"], "NPV_approximately_zero")
                return
        self.fail("No base_break_even_reference case found")

    def test_market_case_has_no_calibration(self):
        from thesis_scenarios import iter_thesis_cases
        for _, _, _, metadata in iter_thesis_cases():
            if metadata["case_type"] == "market":
                self.assertEqual(metadata["calibrated_variable"], "none")
                self.assertEqual(metadata["calibration_target"], "none")
                return
        self.fail("No market case found")

    def test_break_even_selling_price_is_not_circular(self):
        """break_even_selling_price_per_kwh must equal annual_break_even."""
        from thesis_scenarios import run_case, make_norway_market_tesla_case
        from dataclasses import replace
        label, component, scenario = make_norway_market_tesla_case()
        scenario = replace(
            scenario,
            reliability=replace(scenario.reliability, samples=500, seed=42),
        )
        row = run_case(label, component, scenario)
        self.assertAlmostEqual(
            row["break_even_selling_price_per_kwh"],
            row["annual_break_even_selling_price_per_kwh"],
            msg="break_even_selling_price_per_kwh must alias annual_break_even",
        )


if __name__ == "__main__":
    unittest.main()
