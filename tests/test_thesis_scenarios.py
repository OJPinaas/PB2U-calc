"""Tests for the reduced thesis scenario set."""

import unittest

import b2u
from max_purchase_price import solve_max_purchase_price
from thesis_scenarios import make_nrel_reference_module, make_nrel_reference_scenario


class TestNRELReferenceCase(unittest.TestCase):
    def test_nrel_reference_is_near_break_even(self):
        component = make_nrel_reference_module()
        scenario = make_nrel_reference_scenario()

        result = b2u.run_b2u_scenario(component, scenario).to_dict()
        npv = result["revenue_npv"]["total_npv"]

        # The NREL spreadsheet reference case is interpreted as a break-even
        # benchmark, not as an independent market forecast. Allow a small
        # numerical tolerance because the Python model is not a cell-by-cell
        # copy of the spreadsheet.
        self.assertLess(abs(npv), 10_000.0)

    def test_nrel_max_purchase_price_matches_reference(self):
        component = make_nrel_reference_module()
        scenario = make_nrel_reference_scenario()

        result = solve_max_purchase_price(component, scenario)

        self.assertAlmostEqual(
            result.maximum_purchase_price_per_kwh_nameplate,
            19.62,
            delta=0.1,
        )


if __name__ == "__main__":
    unittest.main()
