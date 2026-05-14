import json

import b2u
from norway_scenarios import iter_core_norway_cases


for label, component, scenario in iter_core_norway_cases():
    result = b2u.run_b2u_scenario(component, scenario)
    output = result.to_dict()
    print(f"\n=== {label} ===")
    print(f"Currency: {output['scenario']['currency']['currency']}")
    print(f"Total NPV: {output['revenue_npv']['total_npv_usd']:.2f}")
    print(json.dumps(output["reliability"], indent=2))
