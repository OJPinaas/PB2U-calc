import numpy as np


DEFAULT_MODULE_RNG_SEED = 42


class pack:
    def __init__(self, modules: list):
        self.modules = modules
        if not self.modules:
            raise ValueError("pack must contain at least one module string")

        self.series = len(self.modules[0])
        self.parallel = len(self.modules)
        if any(len(module_string) != self.series for module_string in self.modules):
            raise ValueError("all module strings in a pack must have equal length")

        self.config = f"{self.series}S{self.parallel}P"
        self.calculate_pack_properties()

    def _flatten_modules(self):
        return [module for module_string in self.modules for module in module_string]

    def calculate_pack_properties(self):
        modules = self._flatten_modules()
        self.weight_kg = sum(module.weight_kg for module in modules)
        self.volume_L = sum(module.volume_L for module in modules)
        self.footprint_m2 = sum(module.footprint_m2 for module in modules)
        self.nameplate_energy_kWh = sum(
            module.nameplate_energy_kWh for module in modules
        )
        self.purchase_price = sum(module.purchase_price for module in modules)
        self.number_of_modules = len(modules)
        self.number_of_cells = sum(module.number_of_cells for module in modules)
        self.remaining_energy_kWh = self._calculate_topology_aware_remaining_energy()
        self.percent_remaining_energy = (
            self.remaining_energy_kWh / self.nameplate_energy_kWh
        )

    def _calculate_topology_aware_remaining_energy(self):
        remaining_energy = 0.0
        for module_string in self.modules:
            if not module_string:
                continue
            weakest_module_energy = min(
                module.remaining_energy_kWh for module in module_string
            )
            remaining_energy += weakest_module_energy * len(module_string)
        return remaining_energy

    def calculate_pack_failure_impact(self):
        self.remaining_energy_kWh = self._calculate_topology_aware_remaining_energy()
        self.percent_remaining_energy = (
            self.remaining_energy_kWh / self.nameplate_energy_kWh
        )
        return self.remaining_energy_kWh

    def is_usable(self, min_remaining_energy_fraction=0.6):
        return self.percent_remaining_energy >= min_remaining_energy_fraction

    def properties(self):
        print("Pack Properties:")
        print(f"- Pack Mass: {self.weight_kg:.2f} kg")
        print(f"- Pack Volume: {self.volume_L:.1f} L")
        print(f"- Pack Footprint: {self.footprint_m2 * 1000:.1f} cm^2")
        print(f"- Approx. Remaining Energy: {self.remaining_energy_kWh:.2f} kWh")
        print(f"- Remaining Energy Fraction: {self.percent_remaining_energy:.2%}")
        print(f"- Number of Modules: {self.number_of_modules}")
        print(f"- Module Configuration: {self.config}")


class Batterymodule:
    def __init__(self, nameplate_energy_kWh=5, weight_kg=10, purchase_price=0,
                 height_mm=100, width_mm=200, length_mm=300,
                 percent_remaining_energy=0.7, seriescells=10, paralellcells=10,
                 cell_fault_rate=0.00001, forced_selling_price_per_kWh=44,
                 chemistry="NCA", rng_seed=None, cell_soh_std=0.0,
                 min_cell_soh=0.0, max_cell_soh=1.0):
        # Physical properties
        self.weight_kg = weight_kg
        self.height_mm = height_mm
        self.width_mm = width_mm
        self.length_mm = length_mm
        self.volume_L = (self.height_mm * self.width_mm * self.length_mm) / 1e6
        self.footprint_m2 = (self.length_mm / 1000) * (self.width_mm / 1000)

        # Performance properties
        self.nameplate_energy_kWh = nameplate_energy_kWh
        self.nominal_cell_soh = percent_remaining_energy
        self.percent_remaining_energy = percent_remaining_energy
        self.cell_soh_std = cell_soh_std
        self.min_cell_soh = min_cell_soh
        self.max_cell_soh = max_cell_soh
        self.energydensity_Wh_per_L = (
            self.nameplate_energy_kWh * 1000 / self.volume_L
        )
        self.specificenergy_Wh_per_kg = (
            self.nameplate_energy_kWh * 1000 / self.weight_kg
        )
        self.remaining_energy_kWh = (
            self.nameplate_energy_kWh * percent_remaining_energy
        )

        # Cell properties. The matrix is indexed as series groups, each containing
        # parallel cells. In an SxP module, series raises voltage and parallel raises
        # capacity. The weakest series group limits module-level capacity.
        self.seriescells = seriescells
        self.paralellcells = paralellcells
        self.number_of_cells = seriescells * paralellcells
        self.config = f"{self.seriescells}S{self.paralellcells}P"
        self.chemistry = chemistry
        self.cell_fault_rate = cell_fault_rate
        self.rng_seed = (
            DEFAULT_MODULE_RNG_SEED if rng_seed is None else int(rng_seed)
        )

        # Economic properties
        self.purchase_price = purchase_price
        self.forced_selling_price_per_kWh = forced_selling_price_per_kWh

        self.init_cells(
            chemistry=chemistry,
            cell_fault_rate=cell_fault_rate,
            rng_seed=rng_seed,
        )
        self.calculate_cell_failure_impact()

    def init_cells(self, chemistry, cell_fault_rate, rng_seed=None):
        seed = self.rng_seed if rng_seed is None else rng_seed
        rng = np.random.default_rng(seed)
        self.cells = []
        for _ in range(self.seriescells):
            series_group = []
            for _ in range(self.paralellcells):
                series_group.append(
                    cell(
                        chemistry=chemistry,
                        mean_soh=self.percent_remaining_energy,
                        soh_std=self.cell_soh_std,
                        min_soh=self.min_cell_soh,
                        max_soh=self.max_cell_soh,
                        cell_fault_rate=cell_fault_rate,
                        rng=rng,
                    )
                )
            self.cells.append(series_group)

    def reset_cell_states(self, rng_seed=None):
        seed = self.rng_seed if rng_seed is None else rng_seed
        rng = np.random.default_rng(seed)
        for series_group in self.cells:
            for module_cell in series_group:
                module_cell.sample_state(rng=rng)
        self.calculate_cell_failure_impact()

    def reset_cell_failures(self, rng_seed=None):
        self.reset_cell_states(rng_seed=rng_seed)

    @property
    def failed_cells_count(self):
        return sum(
            1 for series_group in self.cells for module_cell in series_group
            if module_cell.failed
        )

    @property
    def failed_series_groups_count(self):
        return sum(
            1 for series_group in self.cells
            if all(module_cell.effective_soh <= 0 for module_cell in series_group)
        )

    @property
    def failed_strings_count(self):
        return self.failed_series_groups_count

    @property
    def series_group_capacity_fractions(self):
        fractions = []
        for series_group in self.cells:
            effective_soh_sum = sum(
                module_cell.effective_soh for module_cell in series_group
            )
            fractions.append(effective_soh_sum / self.paralellcells)
        return fractions

    @property
    def capacity_fraction_from_cells(self):
        if not self.series_group_capacity_fractions:
            return 0.0
        return min(self.series_group_capacity_fractions)

    @property
    def usable_parallel_fraction(self):
        return self.capacity_fraction_from_cells / self.percent_remaining_energy

    def is_usable(self, min_remaining_energy_fraction=0.6):
        remaining_fraction = self.remaining_energy_kWh / self.nameplate_energy_kWh
        return remaining_fraction >= min_remaining_energy_fraction

    def reliability_summary(self, min_remaining_energy_fraction=0.6):
        remaining_fraction = self.remaining_energy_kWh / self.nameplate_energy_kWh
        group_fractions = self.series_group_capacity_fractions
        return {
            "failed_cells": self.failed_cells_count,
            "failed_series_groups": self.failed_series_groups_count,
            "min_series_group_capacity_fraction": min(group_fractions),
            "mean_series_group_capacity_fraction": float(np.mean(group_fractions)),
            "remaining_energy_kWh": self.remaining_energy_kWh,
            "remaining_energy_fraction": remaining_fraction,
            "is_usable": self.is_usable(min_remaining_energy_fraction),
            "min_remaining_energy_fraction": min_remaining_energy_fraction,
        }

    def properties(self):
        print("Module Properties:")
        print(f"- Module Mass: {self.weight_kg:.2f} kg")
        print(f"- Module Volume: {self.volume_L:.1f} L")
        print(f"- Module X: {self.height_mm / 1000 * 100:.1f} cm")
        print(f"- Module Y: {self.width_mm / 1000 * 100:.1f} cm")
        print(f"- Module Z: {self.length_mm / 1000 * 100:.1f} cm")
        print(f"- Module Footprint: {self.footprint_m2 * 1000:.1f} cm^2")
        print(f"- Approx. Remaining Energy: {self.remaining_energy_kWh:.2f} kWh")
        print(f"- Number of Cells: {self.number_of_cells}")
        print(f"- Module purchase price: ${self.purchase_price:.2f}")
        print(
            "- Forced Selling Price: "
            f"${self.forced_selling_price_per_kWh:.2f} per kWh"
        )
        print(f"- Chemistry: {self.chemistry}")
        print(f"- Cell Configuration: {self.config}")
        print(f"- Number of failed cells: {self.failed_cells_count}")
        print(f"- Number of failed series groups: {self.failed_series_groups_count}")

    def calculate_cell_failure_impact(self):
        self.remaining_energy_kWh = (
            self.nameplate_energy_kWh * self.capacity_fraction_from_cells
        )
        self.percent_remaining_energy = (
            self.remaining_energy_kWh / self.nameplate_energy_kWh
        )
        return self.remaining_energy_kWh


class cell:
    def __init__(self, chemistry, mean_soh=1.0, soh_std=0.0, min_soh=0.0,
                 max_soh=1.0, cycle_count=0, cell_fault_rate=0.001, rng=None):
        self.cycle_count = cycle_count
        self.chemistry = chemistry
        self.mean_soh = mean_soh
        self.soh_std = soh_std
        self.min_soh = min_soh
        self.max_soh = max_soh
        self.cell_fault_rate = cell_fault_rate
        self.sample_state(rng=rng)

    def properties(self):
        print("Cell Properties:")
        print(f"- Cycle Count: {self.cycle_count}")
        print(f"- Chemistry: {self.chemistry}")
        print(f"- Cell SoH: {self.soh:.2%}")
        print(f"- Cell Fault Rate: {self.cell_fault_rate:.5%}")
        print(f"- Failed: {self.failed}")

    @property
    def effective_soh(self):
        if self.failed:
            return 0.0
        return self.soh

    def sample_state(self, rng=None):
        if rng is None:
            rng = np.random.default_rng(DEFAULT_MODULE_RNG_SEED)
        if self.soh_std > 0:
            sampled_soh = rng.normal(self.mean_soh, self.soh_std)
        else:
            sampled_soh = self.mean_soh
        self.soh = float(np.clip(sampled_soh, self.min_soh, self.max_soh))
        self.failed = bool(rng.random() < self.cell_fault_rate)
        return self.failed

    def calculate_failed(self, rng=None):
        if rng is None:
            rng = np.random.default_rng(DEFAULT_MODULE_RNG_SEED)
        self.failed = bool(rng.random() < self.cell_fault_rate)
        return self.failed


if __name__ == "__main__":
    leafGen1 = Batterymodule(nameplate_energy_kWh=0.5, weight_kg=3.8,
                             height_mm=35.0, width_mm=223.0,
                             length_mm=303.0, percent_remaining_energy=0.67,
                             seriescells=2, paralellcells=2,
                             cell_fault_rate=0.00001,
                             forced_selling_price_per_kWh=44.0,
                             chemistry="LMO")

    teslaSGen1 = Batterymodule(nameplate_energy_kWh=5.3, weight_kg=25.6,
                               height_mm=79.0, width_mm=300.0,
                               length_mm=685.0, percent_remaining_energy=0.8,
                               seriescells=6, paralellcells=74,
                               cell_fault_rate=0.00001,
                               forced_selling_price_per_kWh=44.0,
                               chemistry="NCA")

    leafGen1Pack = pack(modules=[[leafGen1, leafGen1, leafGen1, leafGen1,
                                  leafGen1, leafGen1, leafGen1, leafGen1]])
    leafGen1Pack.properties()
    teslaSGen1.properties()
    modules = [[teslaSGen1 for _ in range(16)]]
    teslaSGen1Pack = pack(modules=modules)
    teslaSGen1Pack.properties()
