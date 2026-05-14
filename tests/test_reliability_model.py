import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import b2u
from Batterycomponents import Batterymodule
from reliability_model import simulate_module_population


class TestCellLevelSoHAndFailures(unittest.TestCase):
    def test_seeded_module_failures_are_reproducible(self):
        module_a = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.01,
            rng_seed=123,
        )
        module_b = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.01,
            rng_seed=123,
        )
        self.assertEqual(module_a.failed_cells_count, module_b.failed_cells_count)
        self.assertEqual(module_a.failed_strings_count, module_b.failed_strings_count)

    def test_zero_fault_rate_gives_no_failures(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.0,
            rng_seed=0,
        )
        self.assertEqual(module.failed_cells_count, 0)

    def test_high_fault_rate_reduces_remaining_energy(self):
        low_fault = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.0,
            rng_seed=0,
        )
        high_fault = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=1.0,
            rng_seed=0,
        )
        self.assertGreaterEqual(
            low_fault.remaining_energy_kWh,
            high_fault.remaining_energy_kWh,
        )

    def test_remaining_energy_le_nameplate(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.01,
            rng_seed=42,
        )
        self.assertLessEqual(module.remaining_energy_kWh, module.nameplate_energy_kWh)


class TestMonteCarloReliability(unittest.TestCase):
    def test_population_simulation_returns_reasonable_summary(self):
        module = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.001,
        )
        result = simulate_module_population(
            module,
            samples=5000,
            min_remaining_energy_fraction=0.6,
            seed=42,
        )
        self.assertGreaterEqual(result.usable_fraction, 0.0)
        self.assertLessEqual(result.usable_fraction, 1.0)
        self.assertGreater(result.mean_remaining_energy_kwh, 0.0)
        self.assertGreaterEqual(result.mean_sellable_energy_kwh_per_unit, 0.0)

    def test_b2u_reliability_summary_is_added_to_result(self):
        module = Batterymodule(
            nameplate_energy_kWh=0.5,
            weight_kg=3.8,
            purchase_price=20.0,
            height_mm=35.0,
            width_mm=223.0,
            length_mm=303.0,
            seriescells=2,
            paralellcells=2,
            cell_fault_rate=0.00001,
            forced_selling_price_per_kWh=75.0,
        )
        scenario = b2u.B2UScenario(
            reliability=b2u.ReliabilityAssumptions(
                enabled=True,
                samples=1000,
                seed=7,
                min_remaining_energy_fraction=0.6,
            )
        )
        result = b2u.run_b2u_scenario(module, scenario).to_dict()
        self.assertEqual(result["reliability"]["method"], "monte_carlo_cell_soh")
        self.assertIn("mean_sellable_energy_kwh_per_unit", result["reliability"])
        self.assertGreaterEqual(result["reliability"]["usable_fraction"], 0.0)
        self.assertLessEqual(result["reliability"]["usable_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
