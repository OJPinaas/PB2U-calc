import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import b2u
from Batterycomponents import Batterymodule


class B2UEnhancedTests(unittest.TestCase):
    def setUp(self):
        self.tesla = Batterymodule(
            nameplate_energy_kWh=5.3,
            weight_kg=25.6,
            purchase_price=220.0,
            height_mm=79.0,
            width_mm=300.0,
            length_mm=685.0,
            percent_remaining_energy=0.67,
            seriescells=6,
            paralellcells=74,
            cell_fault_rate=0.00001,
            forced_selling_price_per_kWh=55.0,
            chemistry="NCA",
        )

    def test_yearly_operations_have_learning_and_ramp_up(self):
        result = b2u.run_b2u_model(self.tesla)
        years = result.yearly_operations
        self.assertEqual(len(years), 5)
        self.assertLess(years[0]["utilization"], years[-1]["utilization"])
        self.assertLessEqual(
            years[0]["actual_units_per_year"],
            years[-1]["actual_units_per_year"],
        )

    def test_actual_throughput_never_exceeds_target(self):
        result = b2u.run_b2u_model(self.tesla)
        self.assertLessEqual(
            result.throughput.actual_units_per_year,
            result.throughput.target_units_per_year,
        )

    def test_scenario_override_changes_results(self):
        base = b2u.B2UScenario(name="base")
        slower = b2u.B2UScenario(
            name="slower",
            learning=b2u.LearningAssumptions(
                analysis_years=5,
                initial_utilization=0.55,
                max_utilization=0.75,
                utilization_improvement_per_year=0.03,
                handling_time_improvement_per_year=0.01,
                testing_time_improvement_per_year=0.01,
                packing_time_improvement_per_year=0.01,
                forklift_time_improvement_per_year=0.01,
            ),
        )
        base_result = b2u.run_b2u_scenario(self.tesla, base)
        slower_result = b2u.run_b2u_scenario(self.tesla, slower)
        self.assertGreater(
            base_result.yearly_operations[-1]["actual_units_per_year"],
            slower_result.yearly_operations[-1]["actual_units_per_year"],
        )


if __name__ == "__main__":
    unittest.main()


class B2UProcessTimeScalingTests(unittest.TestCase):
    def _module(self, energy_kwh, mass_kg):
        return Batterymodule(
            nameplate_energy_kWh=energy_kwh,
            weight_kg=mass_kg,
            purchase_price=0.0,
            height_mm=100.0,
            width_mm=200.0,
            length_mm=300.0,
            percent_remaining_energy=0.7,
            seriescells=10,
            paralellcells=10,
            cell_fault_rate=0.0,
            forced_selling_price_per_kWh=44.0,
        )

    def test_nrel_scaled_reference_module_reproduces_reference_times(self):
        reference = self._module(5.0, 5000.0 / 115.0)
        labor = b2u.LaborAssumptions(
            process_time_model="nrel_scaled",
            receiving_inspection_time_s=1200.0,
            connection_initiation_time_s=300.0,
            electrical_testing_time_s=4300.0,
            disconnect_time_s=300.0,
            final_inspection_time_s=1200.0,
        )
        scenario = b2u.B2UScenario(labor=labor)

        result = b2u.run_b2u_scenario(reference, scenario)
        times = result.handling.process_times

        self.assertAlmostEqual(times["inspection_time_per_unit_s"], 1200.0)
        self.assertAlmostEqual(times["connection_time_per_unit_s"], 300.0)
        self.assertAlmostEqual(times["testing_time_per_unit_s"], 4300.0)
        self.assertAlmostEqual(times["disconnect_time_per_unit_s"], 300.0)
        self.assertAlmostEqual(times["packing_time_per_unit_s"], 1200.0)

    def test_nrel_scaled_small_module_has_shorter_process_time(self):
        reference = self._module(5.0, 5000.0 / 115.0)
        leaf_like = self._module(0.5, 3.8)
        labor = b2u.LaborAssumptions(
            process_time_model="nrel_scaled",
            receiving_inspection_time_s=1200.0,
            connection_initiation_time_s=300.0,
            electrical_testing_time_s=4300.0,
            disconnect_time_s=300.0,
            final_inspection_time_s=1200.0,
        )
        scenario = b2u.B2UScenario(labor=labor)

        ref_times = b2u.run_b2u_scenario(reference, scenario).handling.process_times
        leaf_times = b2u.run_b2u_scenario(leaf_like, scenario).handling.process_times

        self.assertLess(
            leaf_times["technician_touch_time_per_unit_s"],
            ref_times["technician_touch_time_per_unit_s"],
        )
        self.assertLess(
            leaf_times["testing_time_per_unit_s"],
            ref_times["testing_time_per_unit_s"],
        )

    def test_minimum_process_times_act_as_lower_bounds(self):
        tiny = self._module(0.05, 0.5)
        labor = b2u.LaborAssumptions(
            process_time_model="nrel_scaled",
            minimum_inspection_time_s=100.0,
            minimum_connection_time_s=50.0,
            minimum_testing_time_s=200.0,
            minimum_disconnect_time_s=25.0,
            minimum_packing_time_s=100.0,
        )
        scenario = b2u.B2UScenario(labor=labor)

        times = b2u.run_b2u_scenario(tiny, scenario).handling.process_times

        self.assertGreaterEqual(times["inspection_time_per_unit_s"], 100.0)
        self.assertGreaterEqual(times["connection_time_per_unit_s"], 50.0)
        self.assertGreaterEqual(times["testing_time_per_unit_s"], 200.0)
        self.assertGreaterEqual(times["disconnect_time_per_unit_s"], 25.0)
        self.assertGreaterEqual(times["packing_time_per_unit_s"], 100.0)
