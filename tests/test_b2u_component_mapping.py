import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Batterycomponents import Batterymodule, pack
import b2u


class TestBatterymoduleCreation(unittest.TestCase):
    def test_leaf_module_creation(self):
        module = Batterymodule(
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
            forced_selling_price_per_kWh=44.0,
            chemistry="LMO",
        )
        self.assertAlmostEqual(module.nameplate_energy_kWh, 0.5)
        self.assertAlmostEqual(module.weight_kg, 3.8)
        self.assertAlmostEqual(module.purchase_price, 20.0)
        self.assertEqual(module.number_of_cells, 4)
        self.assertLessEqual(module.remaining_energy_kWh, module.nameplate_energy_kWh)

    def test_tesla_module_creation(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            percent_remaining_energy=0.8,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.00001,
            forced_selling_price_per_kWh=55.0,
            chemistry="NCA",
        )
        self.assertAlmostEqual(module.nameplate_energy_kWh, 5.3)
        self.assertAlmostEqual(module.weight_kg, 25.6)
        self.assertAlmostEqual(module.purchase_price, 220.0)
        self.assertEqual(module.number_of_cells, 6 * 74)
        self.assertLessEqual(module.remaining_energy_kWh, module.nameplate_energy_kWh)

    def test_module_purchase_price_per_unit_field(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=55.0,
        )
        result = b2u.run_b2u_model(module)
        self.assertAlmostEqual(
            result.module["purchase_price_per_unit"],
            220.0,
        )


class TestPackEnergyTopology(unittest.TestCase):
    def _make_module(self, nameplate_kwh=1.0, soh=1.0):
        return Batterymodule(
            nameplate_energy_kWh=nameplate_kwh,
            weight_kg=5.0,
            height_mm=50.0,
            width_mm=100.0,
            length_mm=200.0,
            percent_remaining_energy=soh,
            seriescells=4,
            paralellcells=4,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
        )

    def test_pack_nameplate_energy_is_sum_of_modules(self):
        modules = [self._make_module(1.0) for _ in range(4)]
        p = pack(modules=[modules])
        self.assertAlmostEqual(p.nameplate_energy_kWh, 4.0)

    def test_pack_remaining_energy_limited_by_weakest_module_in_string(self):
        strong = self._make_module(1.0, soh=1.0)
        weak = self._make_module(1.0, soh=0.5)
        # single string of [strong, weak, strong]: the weakest module caps
        # each module's usable contribution; total = weakest_energy * string_length
        p = pack(modules=[[strong, weak, strong]])
        expected = weak.remaining_energy_kWh * 3
        self.assertAlmostEqual(p.remaining_energy_kWh, expected)
        # also verify the pack energy is less than if all modules were at full SoH
        full_pack = pack(modules=[[strong, strong, strong]])
        self.assertLess(p.remaining_energy_kWh, full_pack.remaining_energy_kWh)

    def test_pack_remaining_energy_le_nameplate(self):
        modules = [self._make_module(1.0, soh=0.7) for _ in range(6)]
        p = pack(modules=[modules[:3], modules[3:]])
        self.assertLessEqual(p.remaining_energy_kWh, p.nameplate_energy_kWh)

    def test_parallel_strings_accumulate_energy(self):
        m = self._make_module(2.0, soh=0.8)
        # two parallel strings of 1 module each
        p = pack(modules=[[m], [m]])
        # each string contributes m.remaining_energy_kWh
        self.assertAlmostEqual(
            p.remaining_energy_kWh,
            m.remaining_energy_kWh * 2,
        )


class TestPurchasePricePropagation(unittest.TestCase):
    def test_purchase_price_appears_in_purchase_price_result(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=10.0,
            purchase_price=100.0,
            height_mm=100.0,
            width_mm=200.0,
            length_mm=300.0,
            seriescells=10,
            paralellcells=10,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
        )
        result = b2u.run_b2u_model(module)
        expected = 100.0 / 5.0
        self.assertAlmostEqual(
            result.purchase_price.purchase_price_per_kwh_nameplate,
            expected,
        )

    def test_higher_purchase_price_increases_annual_expenses(self):
        base_module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=10.0,
            purchase_price=50.0,
            height_mm=100.0,
            width_mm=200.0,
            length_mm=300.0,
            seriescells=10,
            paralellcells=10,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
        )
        costly_module = Batterymodule(
            nameplate_energy_kWh=5.0,
            weight_kg=10.0,
            purchase_price=500.0,
            height_mm=100.0,
            width_mm=200.0,
            length_mm=300.0,
            seriescells=10,
            paralellcells=10,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
        )
        base_result = b2u.run_b2u_model(base_module)
        costly_result = b2u.run_b2u_model(costly_module)
        self.assertGreater(
            costly_result.annual_expenses.total_annual_expenses,
            base_result.annual_expenses.total_annual_expenses,
        )


if __name__ == '__main__':
    unittest.main()
