import math
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import b2u
from Batterycomponents import Batterymodule


class TestPalletContainerLogic(unittest.TestCase):
    def setUp(self):
        self.leaf = Batterymodule(
            nameplate_energy_kWh=0.5,
            weight_kg=3.8,
            purchase_price=20.0,
            height_mm=35.0,
            width_mm=223.0,
            length_mm=303.0,
            percent_remaining_energy=0.67,
            seriescells=2,
            paralellcells=2,
            cell_fault_rate=0.00001,
            forced_selling_price_per_kWh=75.0,
            chemistry="LMO",
        )

    def test_uses_euro_pallet_defaults(self):
        scenario = b2u.B2UScenario(name="base")
        result = b2u.run_b2u_scenario(self.leaf, scenario)
        self.assertEqual(result.transportation.container_type, "40ft")
        self.assertEqual(result.transportation.shipping_pallets_per_container, 18)
        self.assertEqual(result.transportation.units_per_shipping_pallet, 394)

    def test_20ft_requires_at_least_as_many_containers_as_40ft(self):
        base = b2u.B2UScenario(name="base")
        twenty = b2u.B2UScenario(
            name="20ft",
            shipping=b2u.ShippingAssumptions(container_type="20ft"),
        )
        result_40 = b2u.run_b2u_scenario(self.leaf, base)
        result_20 = b2u.run_b2u_scenario(self.leaf, twenty)
        self.assertGreaterEqual(
            result_20.transportation.shipping_containers,
            result_40.transportation.shipping_containers,
        )

    def test_container_count_uses_concurrent_truck_load(self):
        result = b2u.run_b2u_model(self.leaf)
        concurrent_units = (
            result.transportation.number_of_trucks_and_drivers
            * result.transportation.truck_unit_capacity
        )
        expected = math.ceil(
            concurrent_units / result.transportation.units_per_container
        )
        self.assertEqual(result.transportation.shipping_containers, expected)

    def test_shipping_pallet_and_container_positive(self):
        result = b2u.run_b2u_model(self.leaf)
        self.assertGreater(result.transportation.units_per_shipping_pallet, 0)
        self.assertGreater(result.transportation.units_per_container, 0)
        self.assertGreater(result.transportation.truck_unit_capacity, 0)


if __name__ == "__main__":
    unittest.main()
