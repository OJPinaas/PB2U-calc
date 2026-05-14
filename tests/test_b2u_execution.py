import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unittest

from Batterycomponents import Batterymodule, pack
import b2u


class TestB2UExecutionLeaf(unittest.TestCase):
    def setUp(self):
        self.module = Batterymodule(
            nameplate_energy_kWh=0.5,
            weight_kg=3.8,
            height_mm=35.0,
            width_mm=223.0,
            length_mm=303.0,
            percent_remaining_energy=0.67,
            seriescells=2,
            paralellcells=2,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
            chemistry="LMO",
        )
        self.pack = pack(modules=[[self.module for _ in range(8)]])

    def test_run_model_for_module(self):
        result = b2u.run_b2u_model(self.module)
        self.assertGreater(result.throughput.actual_units_per_year, 0)
        self.assertGreater(result.transportation.truck_unit_capacity, 0)
        self.assertGreater(result.facility_size.total_facility_area_m2, 0)
        self.assertGreater(result.capital_costs.total_capital_cost, 0)
        self.assertGreater(result.annual_expenses.total_annual_expenses, 0)

    def test_run_model_for_pack(self):
        result = b2u.run_b2u_model(self.pack)
        self.assertGreater(result.throughput.actual_units_per_year, 0)
        self.assertGreater(result.transportation.truck_unit_capacity, 0)
        self.assertGreater(result.facility_size.total_facility_area_m2, 0)
        self.assertGreater(result.capital_costs.total_capital_cost, 0)
        self.assertGreater(result.annual_expenses.total_annual_expenses, 0)

    def test_forced_selling_price_is_taken_from_component(self):
        result = b2u.run_b2u_model(self.module)
        expected = self.module.forced_selling_price_per_kWh * self.module.nameplate_energy_kWh
        self.assertAlmostEqual(result.revenue_npv.selling_price_per_unit, expected)

    def test_actual_throughput_does_not_exceed_target(self):
        result = b2u.run_b2u_model(self.module)
        self.assertLessEqual(
            result.throughput.actual_units_per_year,
            result.throughput.target_units_per_year,
        )


class TestB2UExecutionTesla(unittest.TestCase):
    def setUp(self):
        self.module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            percent_remaining_energy=0.8,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=55.0,
            chemistry="NCA",
        )

    def test_run_model_for_tesla_module(self):
        result = b2u.run_b2u_model(self.module)
        self.assertGreater(result.throughput.actual_units_per_year, 0)
        self.assertGreater(result.transportation.truck_unit_capacity, 0)
        self.assertGreater(result.transportation.units_per_shipping_pallet, 0)
        self.assertGreater(result.transportation.units_per_container, 0)
        self.assertIsInstance(result.revenue_npv.total_npv, float)

    def test_actual_throughput_does_not_exceed_target(self):
        result = b2u.run_b2u_model(self.module)
        self.assertLessEqual(
            result.throughput.actual_units_per_year,
            result.throughput.target_units_per_year,
        )


if __name__ == '__main__':
    unittest.main()
