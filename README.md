# PB2U-calc

Python research code for a master’s thesis on the techno-economic viability of repurposing retired electric-vehicle batteries for second-life stationary energy-storage applications.

The repository contains an independent Python implementation and extension of the National Renewable Energy Laboratory Battery Second Use (B2U) repurposing-cost calculator. It adds Norwegian scenario assumptions, Nissan Leaf and Tesla Model S case definitions, reliability/state-of-health logic, resale-pathway comparisons, break-even-price calculations, one-at-a-time sensitivity analysis, and throughput-scaling scripts.

This is not an official NREL tool. The original NREL B2U spreadsheet user agreement is included as [`NREL user agreement.md`](NREL%20user%20agreement.md).

## Repository structure

| Path | Purpose |
| --- | --- |
| `b2u.py` | Core B2U facility, cost, throughput, NPV and unit-economics model. |
| `Batterycomponents.py` | Battery cell, module and pack component definitions. |
| `reliability_model.py` | Monte Carlo reliability and remaining-energy calculations. |
| `norway_scenarios.py` | Norwegian scenario factory functions and Leaf/Tesla presets. |
| `thesis_scenarios.py` | Main thesis case definitions and CSV export workflow. |
| `norway_sensitivity.py` | One-at-a-time sensitivity runs for Norwegian cases. |
| `norway_throughput_scaling.py` | Throughput-scaling analysis. |
| `plot_norway_extended_analysis.py` | Figure generation from exported CSV files. |
| `max_purchase_price.py` | Solvers for NPV break-even selling price and maximum purchase price. |
| `tests/` | Regression and smoke tests. |
| `docs/` | Additional documentation. |

## Monetary convention

All monetary inputs and outputs are interpreted in the scenario currency. The core model does not perform currency conversion; scenario factories are responsible for providing values in the intended currency. Norwegian cases are NOK values excluding VAT.

See [`docs/model_overview.md`](docs/model_overview.md), [`docs/norway_scenarios.md`](docs/norway_scenarios.md), [`docs/reproducibility.md`](docs/reproducibility.md), and [`docs/outputs.md`](docs/outputs.md) for details.

## Installation

The code is written as a lightweight script-based research repository rather than as an installed Python package. From the repository root, use either the thesis conda environment or the minimal pip environment. `battery-tea.yml` is left as the thesis development environment; `requirements.txt` is only a lightweight dependency list inferred from the repository imports.

Minimal pip setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Conda setup:

```bash
conda env create -f battery-tea.yml
conda activate battery-tea
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run tests

```bash
python -m pytest -q
```

## Reproduce main outputs

Generate main thesis scenario outputs:

```bash
python thesis_scenarios.py
```

Generate one-at-a-time sensitivity results:

```bash
python norway_sensitivity.py
```

Generate throughput-scaling results:

```bash
python norway_throughput_scaling.py
```

Generate figures from the CSV outputs:

```bash
python plot_norway_extended_analysis.py
```

The scripts write generated files under `outputs/`: CSV tables in `outputs/tables/` and figures in `outputs/figures/`. The directory is treated as generated output unless explicitly archived.

## Limitations

The model is a screening-oriented techno-economic model, not a full operational simulation or electrochemical ageing model. It does not validate results against a specific commercial repurposing facility, laboratory data set, or observed market-clearing price series. Scenario outputs should therefore be interpreted as conditional on the stated input assumptions.

## License and attribution

No reuse license is specified in this repository. Do not assume permission for reuse beyond normal academic review unless a license is added.

If you cite or reuse the thesis code, cite the associated master’s thesis and make clear that this is an independent Python implementation/extension of the B2U calculator, not an official NREL release.
