# Norwegian scenarios

`norway_scenarios.py` builds the Norwegian scenario set used in the thesis. The scenarios combine Norwegian monetary assumptions, battery presets and pathway definitions while preserving the currency-neutral core model.

## Currency and VAT

Norwegian cases use:

- `currency == "NOK"`
- monetary values excluding VAT
- `vat_rate = 0.25`
- `include_vat_in_profit = False`

VAT is recorded as scenario metadata and discussed as a market/pricing issue, but it is not included in NPV or profitability calculations.

## Conversion boundary

The core B2U calculation does not convert currencies. Where source assumptions are documented as USD reference values, `norway_scenarios.py` converts them to NOK before constructing the scenario. Rates and fractions, such as discount rate, tax rate and warranty fraction, are not converted.

## Battery and pathway factories

The main helper functions are:

- `make_leaf_gen1_module()`
- `make_leaf_gen1_module_from_pack_purchase()`
- `make_leaf_gen1_pack_from_pack_purchase()`
- `make_leaf_pack_triage_pathway()`
- `make_tesla_model_s_gen1_module()`
- `make_norway_scenario()`
- `iter_core_norway_cases()`
- `iter_all_norway_cases()`

The Leaf pathway helpers distinguish between complete-pack resale, pack-to-modules resale and pack-first triage. Component-level assumptions such as topology, SoH and cell fault rate live on the component objects. Facility, labour, economic, learning, tax, currency and transport assumptions live on `B2UScenario`.
