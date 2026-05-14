import json
from dataclasses import replace

import b2u
from Batterycomponents import Batterymodule


tesla = Batterymodule(
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
    cell_soh_std=0.03,
    min_cell_soh=0.50,
    max_cell_soh=0.95,
    forced_selling_price_per_kWh=55.0,
    chemistry="NCA",
)

base = b2u.B2UScenario(name="base")

monte_carlo_yield = replace(
    base,
    name="monte_carlo_yield",
    reliability=b2u.ReliabilityAssumptions(
        enabled=True,
        samples=10_000,
        seed=42,
        min_remaining_energy_fraction=0.60,
        use_remaining_energy_for_revenue=False,
    ),
)

monte_carlo_remaining_energy = replace(
    base,
    name="monte_carlo_remaining_energy",
    reliability=b2u.ReliabilityAssumptions(
        enabled=True,
        samples=10_000,
        seed=42,
        min_remaining_energy_fraction=0.60,
        use_remaining_energy_for_revenue=True,
    ),
)

for scenario in [base, monte_carlo_yield, monte_carlo_remaining_energy]:
    result = b2u.run_b2u_scenario(tesla, scenario)
    output = result.to_dict()
    print(f"\n=== {scenario.name} ===")
    print(json.dumps(output["reliability"], indent=2))
    print(f"Total NPV: {output['revenue_npv']['total_npv_usd']:.2f}")
