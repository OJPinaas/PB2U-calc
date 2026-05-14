from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

import numpy as np

from Batterycomponents import Batterymodule, pack


@dataclass(frozen=True)
class ReliabilitySimulationResult:
    method: str
    samples: int
    seed: int | None
    min_remaining_energy_fraction: float
    cell_fault_rate: float
    cells_per_unit: int
    seriescells: int
    paralellcells: int
    usable_fraction: float
    rejected_fraction: float
    mean_failed_cells: float
    mean_failed_series_groups: float
    mean_failed_strings: float
    mean_remaining_energy_kwh: float
    mean_remaining_energy_fraction: float
    mean_sellable_energy_kwh_per_unit: float
    p05_remaining_energy_fraction: float
    p50_remaining_energy_fraction: float
    p95_remaining_energy_fraction: float

    def to_dict(self) -> Dict[str, float | int | str | None]:
        return asdict(self)


def _sample_cell_soh(
    rng: np.random.Generator,
    mean_soh: float,
    soh_std: float,
    min_soh: float,
    max_soh: float,
    shape: tuple[int, ...],
) -> np.ndarray:
    if soh_std > 0:
        sampled = rng.normal(mean_soh, soh_std, size=shape)
    else:
        sampled = np.full(shape, mean_soh, dtype=float)
    return np.clip(sampled, min_soh, max_soh)


def _simulate_module_remaining_energy(
    module: Batterymodule,
    samples: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    series = int(module.seriescells)
    parallel = int(module.paralellcells)
    shape = (samples, series, parallel)

    cell_soh = _sample_cell_soh(
        rng=rng,
        mean_soh=float(module.nominal_cell_soh),
        soh_std=float(module.cell_soh_std),
        min_soh=float(module.min_cell_soh),
        max_soh=float(module.max_cell_soh),
        shape=shape,
    )
    failed = rng.random(size=shape) < float(module.cell_fault_rate)
    effective_soh = np.where(failed, 0.0, cell_soh)

    series_group_capacity_fraction = np.sum(effective_soh, axis=2) / parallel
    module_remaining_fraction = np.min(series_group_capacity_fraction, axis=1)
    module_remaining_energy = module_remaining_fraction * float(
        module.nameplate_energy_kWh
    )
    failed_cells = np.sum(failed, axis=(1, 2))
    failed_series_groups = np.sum(
        np.sum(effective_soh, axis=2) <= 0.0,
        axis=1,
    )
    return module_remaining_energy, failed_cells, failed_series_groups


def simulate_module_population(
    module: Batterymodule,
    samples: int = 10_000,
    min_remaining_energy_fraction: float = 0.60,
    seed: int | None = 42,
    use_remaining_energy_for_revenue: bool = False,
) -> ReliabilitySimulationResult:
    if samples < 1:
        raise ValueError("samples must be at least 1")

    rng = np.random.default_rng(seed)
    remaining_energy, failed_cells, failed_series_groups = (
        _simulate_module_remaining_energy(module, samples, rng)
    )
    remaining_fraction = remaining_energy / float(module.nameplate_energy_kWh)
    usable = remaining_fraction >= min_remaining_energy_fraction

    if use_remaining_energy_for_revenue:
        sellable_energy = np.where(usable, remaining_energy, 0.0)
    else:
        sellable_energy = np.where(usable, module.nameplate_energy_kWh, 0.0)

    usable_fraction = float(np.mean(usable))
    percentiles = np.percentile(remaining_fraction, [5, 50, 95])

    return ReliabilitySimulationResult(
        method="monte_carlo_cell_soh",
        samples=samples,
        seed=seed,
        min_remaining_energy_fraction=min_remaining_energy_fraction,
        cell_fault_rate=float(module.cell_fault_rate),
        cells_per_unit=int(module.number_of_cells),
        seriescells=int(module.seriescells),
        paralellcells=int(module.paralellcells),
        usable_fraction=usable_fraction,
        rejected_fraction=1.0 - usable_fraction,
        mean_failed_cells=float(np.mean(failed_cells)),
        mean_failed_series_groups=float(np.mean(failed_series_groups)),
        mean_failed_strings=float(np.mean(failed_series_groups)),
        mean_remaining_energy_kwh=float(np.mean(remaining_energy)),
        mean_remaining_energy_fraction=float(np.mean(remaining_fraction)),
        mean_sellable_energy_kwh_per_unit=float(np.mean(sellable_energy)),
        p05_remaining_energy_fraction=float(percentiles[0]),
        p50_remaining_energy_fraction=float(percentiles[1]),
        p95_remaining_energy_fraction=float(percentiles[2]),
    )


def analytical_module_reliability(
    module: Batterymodule,
    min_remaining_energy_fraction: float = 0.60,
    use_remaining_energy_for_revenue: bool = False,
) -> ReliabilitySimulationResult:
    # Exact analytical handling of both continuous cell-SoH variation and binary
    # cell failures is not useful here. This function therefore reports the current
    # deterministic module state. Monte Carlo is used for stochastic population
    # estimates.
    remaining_energy = float(module.remaining_energy_kWh)
    remaining_fraction = remaining_energy / float(module.nameplate_energy_kWh)
    usable_fraction = 1.0 if remaining_fraction >= min_remaining_energy_fraction else 0.0
    if use_remaining_energy_for_revenue:
        sellable_energy = remaining_energy if usable_fraction else 0.0
    else:
        sellable_energy = float(module.nameplate_energy_kWh) * usable_fraction

    return ReliabilitySimulationResult(
        method="current_module_state",
        samples=0,
        seed=None,
        min_remaining_energy_fraction=min_remaining_energy_fraction,
        cell_fault_rate=float(module.cell_fault_rate),
        cells_per_unit=int(module.number_of_cells),
        seriescells=int(module.seriescells),
        paralellcells=int(module.paralellcells),
        usable_fraction=usable_fraction,
        rejected_fraction=1.0 - usable_fraction,
        mean_failed_cells=float(module.failed_cells_count),
        mean_failed_series_groups=float(module.failed_series_groups_count),
        mean_failed_strings=float(module.failed_series_groups_count),
        mean_remaining_energy_kwh=remaining_energy,
        mean_remaining_energy_fraction=remaining_fraction,
        mean_sellable_energy_kwh_per_unit=sellable_energy,
        p05_remaining_energy_fraction=float("nan"),
        p50_remaining_energy_fraction=float("nan"),
        p95_remaining_energy_fraction=float("nan"),
    )


def _simulate_pack_population(
    component: pack,
    samples: int,
    seed: int | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    pack_remaining_energy = np.zeros(samples, dtype=float)
    pack_failed_cells = np.zeros(samples, dtype=float)
    pack_failed_series_groups = np.zeros(samples, dtype=float)

    for module_string in component.modules:
        string_module_energies = []
        for module in module_string:
            remaining_energy, failed_cells, failed_series_groups = (
                _simulate_module_remaining_energy(module, samples, rng)
            )
            string_module_energies.append(remaining_energy)
            pack_failed_cells += failed_cells
            pack_failed_series_groups += failed_series_groups

        string_module_energies = np.asarray(string_module_energies)
        weakest_module_energy = np.min(string_module_energies, axis=0)
        pack_remaining_energy += weakest_module_energy * len(module_string)

    return pack_remaining_energy, pack_failed_cells, pack_failed_series_groups


def simulate_pack_population(
    component: pack,
    samples: int = 10_000,
    min_remaining_energy_fraction: float = 0.60,
    seed: int | None = 42,
    use_remaining_energy_for_revenue: bool = False,
) -> Dict[str, float | int | str | None]:
    if samples < 1:
        raise ValueError("samples must be at least 1")

    remaining_energy, failed_cells, failed_series_groups = _simulate_pack_population(
        component=component,
        samples=samples,
        seed=seed,
    )
    nameplate = float(component.nameplate_energy_kWh)
    remaining_fraction = remaining_energy / nameplate
    usable = remaining_fraction >= min_remaining_energy_fraction

    if use_remaining_energy_for_revenue:
        sellable_energy = np.where(usable, remaining_energy, 0.0)
    else:
        sellable_energy = np.where(usable, nameplate, 0.0)

    percentiles = np.percentile(remaining_fraction, [5, 50, 95])

    modules = [module for string in component.modules for module in string]
    return {
        "method": "monte_carlo_pack_cell_soh",
        "samples": samples,
        "seed": seed,
        "min_remaining_energy_fraction": min_remaining_energy_fraction,
        "cell_fault_rate": float(modules[0].cell_fault_rate),
        "cells_per_unit": sum(int(module.number_of_cells) for module in modules),
        "seriescells": component.series,
        "paralellcells": component.parallel,
        "usable_fraction": float(np.mean(usable)),
        "rejected_fraction": 1.0 - float(np.mean(usable)),
        "mean_failed_cells": float(np.mean(failed_cells)),
        "mean_failed_series_groups": float(np.mean(failed_series_groups)),
        "mean_failed_strings": float(np.mean(failed_series_groups)),
        "mean_remaining_energy_kwh": float(np.mean(remaining_energy)),
        "mean_remaining_energy_fraction": float(np.mean(remaining_fraction)),
        "mean_sellable_energy_kwh_per_unit": float(np.mean(sellable_energy)),
        "p05_remaining_energy_fraction": float(percentiles[0]),
        "p50_remaining_energy_fraction": float(percentiles[1]),
        "p95_remaining_energy_fraction": float(percentiles[2]),
    }


def component_reliability_summary(
    component: Batterymodule | pack,
    samples: int = 10_000,
    min_remaining_energy_fraction: float = 0.60,
    seed: int | None = 42,
    use_remaining_energy_for_revenue: bool = False,
) -> Dict[str, float | int | str | None]:
    if isinstance(component, Batterymodule):
        return simulate_module_population(
            module=component,
            samples=samples,
            min_remaining_energy_fraction=min_remaining_energy_fraction,
            seed=seed,
            use_remaining_energy_for_revenue=use_remaining_energy_for_revenue,
        ).to_dict()

    if isinstance(component, pack):
        return simulate_pack_population(
            component=component,
            samples=samples,
            min_remaining_energy_fraction=min_remaining_energy_fraction,
            seed=seed,
            use_remaining_energy_for_revenue=use_remaining_energy_for_revenue,
        )

    raise TypeError("component must be a Batterymodule or pack")
