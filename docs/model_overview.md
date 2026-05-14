# Model overview

This repository contains a script-based Python implementation and extension of the NREL Battery Second Use (B2U) repurposing-cost calculator. The model combines battery component assumptions, facility throughput, labour, transport, capital costs, annual operating expenses, tax treatment, discounted cash flow and reliability/remaining-energy screening.

## Main modules

- `Batterycomponents.py` defines cell, module and pack objects. The thesis cases use Nissan Leaf pouch modules/packs and Tesla Model S 18650 modules.
- `b2u.py` contains the core facility-level techno-economic model. It builds transportation, handling, staffing, facility-size, capital-cost, annual-expense, revenue, NPV, unit-economics and throughput results.
- `reliability_model.py` estimates usable fraction and sellable energy using Monte Carlo cell-SoH/fault sampling for modules and packs.
- `max_purchase_price.py` solves for NPV break-even selling price and maximum allowable used-battery purchase price.
- `norway_scenarios.py` defines Norwegian scenario factories and battery presets.
- `thesis_scenarios.py`, `norway_sensitivity.py`, `norway_throughput_scaling.py` and `plot_norway_extended_analysis.py` generate the thesis outputs.

## Currency rule

The core model is currency-neutral. All monetary values passed into `b2u.py` are interpreted in `scenario.currency`. The core model does not perform automatic currency conversion.

For example, a USD reference scenario passes USD values to the model and labels the result as USD. A Norwegian scenario passes NOK values to the same fields and labels the result as NOK. Currency conversion for Norwegian assumptions happens during scenario construction, not in the core calculation engine.

## Result structure

`b2u.run_b2u_scenario(component, scenario)` returns a `B2UModelResult`. Calling `.to_dict()` returns nested dictionaries for:

- `module`
- `scenario`
- `currency`
- `throughput`
- `transportation`
- `handling`
- `staffing`
- `facility_size`
- `capital_costs`
- `employment_costs`
- `annual_expenses`
- `revenue_npv`
- `purchase_price`
- `unit_economics`
- `reliability`
- `yearly_operations`

The most important financial outputs are `revenue_npv["total_npv"]`, `unit_economics["annual_break_even_selling_price_per_kwh"]`, `unit_economics["cost_per_sellable_kwh"]`, and the solver outputs from `max_purchase_price.py`.
