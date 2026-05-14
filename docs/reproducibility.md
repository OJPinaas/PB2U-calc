# Reproducibility

Run commands from the repository root.

## Environment

`battery-tea.yml` is the thesis development environment. It may include dependencies used for notebooks, exploratory analysis or adjacent battery modelling work. The separate `requirements.txt` file is a minimal dependency list inferred from the scripts and tests in this repository.

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

## Tests

```bash
python -m pytest -q
```

## Regenerate thesis outputs

```bash
python thesis_scenarios.py
python norway_sensitivity.py
python norway_throughput_scaling.py
python plot_norway_extended_analysis.py
```

The scripts write CSV outputs to `outputs/tables/` and figures to `outputs/figures/`.

## Expected generated files

Typical generated CSV files include:

- `outputs/tables/thesis_scenario_results.csv`
- `outputs/tables/norway_sensitivity_results.csv`
- `outputs/tables/norway_throughput_scaling_results.csv`
- `outputs/tables/norway_throughput_scaling_summary.csv`
- `outputs/tables/throughput_unit_requirements_1gwh.csv`

## Determinism

The thesis scenario factories and reliability simulations use fixed random seeds.
Repeated runs from the same code revision and dependency environment should
therefore reproduce the generated CSV outputs exactly. If new stochastic analyses
are added, give them explicit seed parameters and write those seeds to output
metadata.
