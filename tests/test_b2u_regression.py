import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Batterycomponents import Batterymodule
import b2u


class TestB2URegressionInvariants(unittest.TestCase):
    def setUp(self):
        self.module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=10.0,
            height_mm=100.0,
            width_mm=200.0,
            length_mm=300.0,
            percent_remaining_energy=0.7,
            purchase_price=50.0,
            seriescells=10,
            paralellcells=10,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
            chemistry="NCA",
        )

    def test_target_units_per_year_matches_floor_rule(self):
        result = b2u.run_b2u_model(self.module)
        expected = math.floor(1_000_000 / self.module.nameplate_energy_kWh)
        self.assertEqual(result.throughput.target_units_per_year, expected)

    def test_actual_units_per_day_derived_from_annual(self):
        result = b2u.run_b2u_model(self.module)
        expected_day = math.floor(result.throughput.actual_units_per_year / 365)
        self.assertEqual(result.throughput.actual_units_per_day, expected_day)

    def test_purchase_price_per_kwh_nameplate(self):
        result = b2u.run_b2u_model(self.module)
        expected = self.module.purchase_price / self.module.nameplate_energy_kWh
        self.assertAlmostEqual(
            result.purchase_price.purchase_price_per_kwh_nameplate,
            expected,
        )

    def test_zero_fault_rate_gives_full_yield(self):
        result = b2u.run_b2u_model(self.module)
        self.assertAlmostEqual(result.revenue_npv.yield_on_units, 1.0)

    def test_actual_throughput_never_exceeds_target(self):
        result = b2u.run_b2u_model(self.module)
        self.assertLessEqual(
            result.throughput.actual_units_per_year,
            result.throughput.target_units_per_year,
        )


if __name__ == '__main__':
    unittest.main()
