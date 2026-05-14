# Output files

The repository is designed to regenerate analysis outputs rather than store every generated file under version control.

## `data/thesis_scenario_results.csv`

Produced by `python thesis_scenarios.py`. Contains the main scenario summary table used in the thesis, including:

- case name and case type
- currency
- NPV
- current and maximum purchase price
- annual and NPV break-even selling price
- revenue/cost per sellable kWh
- usable fraction and mean sellable energy

## `data/norway_sensitivity_results.csv`

Produced by `python norway_sensitivity.py`. Contains one-at-a-time sensitivity outputs for Norwegian Leaf and Tesla cases.

## `data/norway_throughput_scaling_results.csv`

Produced by `python norway_throughput_scaling.py`. Contains throughput-scaling outputs for selected target annual processing levels and pathways.

## `Figures/norway_extended/`

Produced by `python plot_norway_extended_analysis.py`. Contains generated thesis figures based on the CSV outputs.
