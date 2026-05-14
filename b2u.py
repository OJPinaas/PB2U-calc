from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from Batterycomponents import Batterymodule, pack
from reliability_model import component_reliability_summary

M_PER_FT = 0.3048
M_PER_MI = 1609.344
M2_PER_FT2 = M_PER_FT**2
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_MINUTE = 60.0



def _ft_to_m(value_ft: float) -> float:
    return value_ft * M_PER_FT


def _mi_to_m(value_mi: float) -> float:
    return value_mi * M_PER_MI


def _cost_per_mile_to_cost_per_m(value_per_mile: float) -> float:
    return value_per_mile / M_PER_MI


def _ft3_to_m3(value_ft3: float) -> float:
    return value_ft3 * (M_PER_FT**3)


def _flatten_pack_modules(component: pack) -> list[Batterymodule]:
    return [module for module_string in component.modules for module in module_string]


@dataclass(frozen=True)
class _ComponentData:
    nameplate_energy_kwh: float
    remaining_energy_fraction: float
    cell_fault_rate: float
    volume_m3: float
    mass_kg: float
    height_m: float
    width_m: float
    length_m: float
    footprint_m2: float
    cells_per_unit: int
    forced_selling_price_per_kwh: float
    purchase_price_per_unit: float
    component_kind: str
    module_count: int = 1

    @property
    def remaining_energy_kwh(self) -> float:
        return self.remaining_energy_fraction * self.nameplate_energy_kwh

    @property
    def number_of_cells(self) -> int:
        return self.cells_per_unit

    def to_public_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _component_data(component: Batterymodule | pack) -> _ComponentData:
    if isinstance(component, Batterymodule):
        return _module_data(component)
    if isinstance(component, pack):
        return _pack_data(component)
    raise TypeError(
        "component must be a Batterymodule or pack from Batterycomponents.py"
    )


def _module_data(module: Batterymodule) -> _ComponentData:
    height_m = float(module.height_mm) / 1000.0
    width_m = float(module.width_mm) / 1000.0
    length_m = float(module.length_mm) / 1000.0
    volume_m3 = height_m * width_m * length_m
    footprint_m2 = width_m * length_m
    remaining_energy_fraction = (
        float(module.remaining_energy_kWh) / float(module.nameplate_energy_kWh)
    )
    cell_fault_rate = module.cell_fault_rate
    return _ComponentData(
        nameplate_energy_kwh=float(module.nameplate_energy_kWh),
        remaining_energy_fraction=remaining_energy_fraction,
        cell_fault_rate=float(cell_fault_rate),
        volume_m3=volume_m3,
        mass_kg=float(module.weight_kg),
        height_m=height_m,
        width_m=width_m,
        length_m=length_m,
        footprint_m2=footprint_m2,
        cells_per_unit=int(module.number_of_cells),
        forced_selling_price_per_kwh=float(module.forced_selling_price_per_kWh),
        purchase_price_per_unit=float(module.purchase_price),
        component_kind="module",
        module_count=1,
    )


def _pack_data(component: pack) -> _ComponentData:
    modules = _flatten_pack_modules(component)
    if not modules:
        raise ValueError("pack contains no modules")

    first = modules[0]
    cell_fault_rate = first.cell_fault_rate
    heights_m = [float(module.height_mm) / 1000.0 for module in modules]
    widths_m = [float(module.width_mm) / 1000.0 for module in modules]
    lengths_m = [float(module.length_mm) / 1000.0 for module in modules]

    total_volume_m3 = sum(
        h * w * l for h, w, l in zip(heights_m, widths_m, lengths_m)
    )
    total_footprint_m2 = sum(w * l for w, l in zip(widths_m, lengths_m))

    return _ComponentData(
        nameplate_energy_kwh=float(component.nameplate_energy_kWh),
        remaining_energy_fraction=(
            float(component.remaining_energy_kWh)
            / float(component.nameplate_energy_kWh)
        ),
        cell_fault_rate=float(cell_fault_rate),
        volume_m3=total_volume_m3,
        mass_kg=float(component.weight_kg),
        height_m=max(heights_m),
        width_m=math.sqrt(total_footprint_m2),
        length_m=math.sqrt(total_footprint_m2),
        footprint_m2=total_footprint_m2,
        cells_per_unit=sum(int(module.number_of_cells) for module in modules),
        forced_selling_price_per_kwh=float(first.forced_selling_price_per_kWh),
        purchase_price_per_unit=sum(
            float(module.purchase_price) for module in modules
        ),
        component_kind="pack",
        module_count=len(modules),
    )


@dataclass(frozen=True)
class FacilityAssumptions:
    target_annual_throughput_kwh: float = 1_000_000.0
    work_days_per_year: int = 252
    working_hours_per_day: float = 8.0
    calendar_days_per_year: int = 365
    station_hours_per_day: float = 24.0
    design_utilization: float = 0.90


@dataclass(frozen=True)
class TransportProfile:
    name: str
    distance_m: float
    trip_time_s: float
    truck_type: str
    truck_purchase_cost: float
    truck_operating_cost_per_m: float
    cargo_volume_m3: float
    cargo_mass_kg: float


@dataclass(frozen=True)
class LaborAssumptions:
    """Labour and process-time assumptions.

    By default, process times are scaled from an NREL-style 5 kWh reference
    module rather than calculated as a fixed time plus an additional
    mass/energy term.  The reference step times below are interpreted as the
    complete process time for the reference module.

    ``process_time_model="nrel_scaled"`` uses:

    * mass scaling for receiving/inspection and final inspection/packing
    * nameplate-energy scaling for connection, electrical testing, and
      disconnection
    * optional minimum step times as lower bounds after scaling and learning

    ``process_time_model="fixed_plus_variable"`` keeps the older behaviour
    for comparison or sensitivity testing.
    """

    process_time_model: str = "nrel_scaled"
    reference_nameplate_energy_kwh: float = 5.0
    reference_specific_energy_wh_per_kg: float = 115.0
    reference_mass_kg: Optional[float] = None

    receiving_inspection_time_s: float = 20.0 * SECONDS_PER_MINUTE
    connection_initiation_time_s: float = 5.0 * SECONDS_PER_MINUTE
    electrical_testing_time_s: float = 4_300.0
    disconnect_time_s: float = 5.0 * SECONDS_PER_MINUTE
    final_inspection_time_s: float = 20.0 * SECONDS_PER_MINUTE
    # Optional pack-disassembly or de-moduleing labour assigned to each processed
    # unit.  The default is zero, so existing scenarios are unchanged.  The Leaf
    # pack-to-modules pathway uses this to represent buying complete packs, then
    # disassembling them before module-level testing and resale.
    disassembly_time_s_per_unit: float = 0.0
    charging_time_s: float = 45.0 * SECONDS_PER_MINUTE
    average_c_rate: float = 1.0
    charging_efficiency: float = 0.85

    minimum_inspection_time_s: float = 0.0
    minimum_connection_time_s: float = 0.0
    minimum_testing_time_s: float = 0.0
    minimum_disconnect_time_s: float = 0.0
    minimum_packing_time_s: float = 0.0

    inspection_time_per_kg_s: float = 12.0
    connection_time_per_kwh_s: float = 30.0
    testing_time_per_kwh_s: float = 60.0
    packing_time_per_kg_s: float = 10.0
    pallet_move_time_s: float = 15.0 * SECONDS_PER_MINUTE


@dataclass(frozen=True)
class LayoutAssumptions:
    width_depth_per_employee_m: float = _ft_to_m(3.0)
    forklift_width_m: float = 2.5
    hallway_width_m: float = _ft_to_m(5.0)
    pallet_width_m: float = 0.8
    pallet_length_m: float = 1.2
    pallet_height_m: float = 0.144
    rack_stack_height_m: float = _ft_to_m(10.0)
    rack_row_buffer_m: float = _ft_to_m(1.0)
    office_length_m: float = _ft_to_m(13.0)
    office_width_m: float = _ft_to_m(8.0)
    hallway_office_width_m: float = _ft_to_m(5.0)


@dataclass(frozen=True)
class ShippingAssumptions:
    pallet_width_m: float = 0.8
    pallet_length_m: float = 1.2
    pallet_height_m: float = 0.144
    pallet_tare_kg: float = 25.0
    pallet_max_payload_kg: float = 1_500.0
    pallet_area_utilization: float = 0.90
    max_loaded_pallet_height_m: float = 1.80
    container_type: str = "40ft"
    container_20ft_internal_length_m: float = 5.896
    container_20ft_internal_width_m: float = 2.350
    container_20ft_internal_height_m: float = 2.393
    container_20ft_volume_m3: float = 33.0
    container_20ft_payload_kg: float = 28_200.0
    container_20ft_euro_pallet_slots: int = 11
    container_40ft_internal_length_m: float = 12.032
    container_40ft_internal_width_m: float = 2.350
    container_40ft_internal_height_m: float = 2.393
    container_40ft_volume_m3: float = 67.0
    container_40ft_payload_kg: float = 28_800.0
    container_40ft_euro_pallet_slots: int = 25


@dataclass(frozen=True)
class CurrencyAssumptions:
    """Metadata for interpreting monetary model inputs and outputs.

    The model is currency-neutral: it does not convert monetary values during
    calculation.  ``currency`` documents the unit of account used in the
    scenario.  ``nok_per_usd`` is optional metadata for Norwegian scenario
    construction and reporting; it is not used by the B2U calculation.
    """

    currency: str = "USD"
    nok_per_usd: Optional[float] = None
    monetary_values_are_ex_vat: bool = True
    vat_rate: float = 0.0
    include_vat_in_profit: bool = False


@dataclass(frozen=True)
class RoadFreightAssumptions:
    """Optional scenario-level freight-cost overrides.

    Values are interpreted in the same currency as the rest of the scenario.
    Leave fields as ``None`` to use the default transport profile values.
    """

    truck_operating_cost_per_m: Optional[float] = None
    truck_purchase_cost: Optional[float] = None
    truck_type: Optional[str] = None


@dataclass(frozen=True)
class CapitalCostAssumptions:
    test_channel_cost_per_station: float = 20_000.0
    can_hardware_cost_per_station: float = 160.0
    computer_cost: float = 3_000.0
    conveyor_cost_per_m2: float = 50.0 / M2_PER_FT2
    storage_rack_cost: float = 100.0
    forklift_cost: float = 7_000.0
    workstation_cost: float = 500.0
    office_and_other_cost: float = 100_000.0
    shipping_container_cost: float = 500.0


@dataclass(frozen=True)
class WageAssumptions:
    technician_wage_per_year: float = 37_860.0
    forklift_operator_wage_per_year: float = 32_660.0
    truck_driver_wage_per_year: float = 33_490.0
    supervisor_wage_per_year: float = 58_150.0
    chief_executive_wage_per_year: float = 178_400.0
    electrical_engineer_wage_per_year: float = 93_380.0
    sales_manager_wage_per_year: float = 85_610.0
    admin_assistant_wage_per_year: float = 34_000.0
    security_guard_wage_per_year: float = 27_550.0
    hr_manager_wage_per_year: float = 100_800.0
    operations_manager_wage_per_year: float = 116_090.0
    janitor_wage_per_year: float = 25_140.0
    non_wage_compensation_fraction: float = 0.302


@dataclass(frozen=True)
class EconomicAssumptions:
    forced_selling_price_per_kwh: Optional[float] = None
    discount_rate: float = 0.15
    federal_tax_rate: float = 0.393
    state_tax_rate: float = 0.0
    electricity_testing_cost_per_kwh: float = 0.104
    hvac_lighting_cost_per_m2_year: float = 2.27 / M2_PER_FT2
    rent_per_m2_year: float = 9.7 / M2_PER_FT2
    other_direct_cost_fraction_of_wages: float = 0.02
    insurance_fraction_of_direct_costs: float = 0.03
    ga_fraction_of_direct_costs: float = 0.05
    warranty_fraction_of_revenue: float = 0.05
    rnd_fraction_of_direct_costs: float = 0.03


@dataclass(frozen=True)
class LearningAssumptions:
    analysis_years: int = 5
    initial_utilization: float = 0.70
    max_utilization: float = 0.92
    utilization_improvement_per_year: float = 0.05
    handling_time_improvement_per_year: float = 0.04
    testing_time_improvement_per_year: float = 0.03
    packing_time_improvement_per_year: float = 0.03
    forklift_time_improvement_per_year: float = 0.02


@dataclass(frozen=True)
class ReliabilityAssumptions:
    enabled: bool = False
    samples: int = 10_000
    seed: int | None = 42
    min_remaining_energy_fraction: float = 0.60
    use_remaining_energy_for_revenue: bool = False
    # Optional precomputed reliability summary used for operational pathway
    # sensitivities where one incoming unit may produce a mixed output stream.
    # The hybrid Leaf triage case uses this to represent complete packs sold as
    # packs when they pass pack-level screening and module recovery when they do
    # not.
    summary_override: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class B2UScenario:
    name: str = "ad_hoc"
    facility: FacilityAssumptions = FacilityAssumptions()
    labor: LaborAssumptions = LaborAssumptions()
    layout: LayoutAssumptions = LayoutAssumptions()
    capital: CapitalCostAssumptions = CapitalCostAssumptions()
    wages: WageAssumptions = WageAssumptions()
    economics: EconomicAssumptions = EconomicAssumptions()
    learning: LearningAssumptions = LearningAssumptions()
    shipping: ShippingAssumptions = ShippingAssumptions()
    reliability: ReliabilityAssumptions = ReliabilityAssumptions()
    currency: CurrencyAssumptions = CurrencyAssumptions()
    road_freight: RoadFreightAssumptions = RoadFreightAssumptions()
    collection_scale: str = "Regional"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "facility": asdict(self.facility),
            "labor": asdict(self.labor),
            "layout": asdict(self.layout),
            "capital": asdict(self.capital),
            "wages": asdict(self.wages),
            "economics": asdict(self.economics),
            "learning": asdict(self.learning),
            "shipping": asdict(self.shipping),
            "reliability": asdict(self.reliability),
            "currency": asdict(self.currency),
            "road_freight": asdict(self.road_freight),
            "collection_scale": self.collection_scale,
        }


@dataclass(frozen=True)
class ThroughputResult:
    target_annual_throughput_kwh: float
    target_units_per_year: int
    installed_capacity_units_per_year: int
    actual_units_per_year: int
    actual_units_per_day: int
    actual_annual_throughput_kwh: float
    utilization: float
    bottleneck_step: str


@dataclass(frozen=True)
class TransportationResult:
    collection_scale: str
    truck_type: str
    truck_purchase_cost: float
    truck_operating_cost_per_m: float
    cargo_volume_m3: float
    cargo_mass_kg: float
    truck_unit_capacity: int
    trips_per_year: int
    total_collection_time_s: float
    number_of_trucks_and_drivers: int
    total_distance_m_per_year: float
    units_per_shipping_pallet: int
    shipping_pallets_per_container: int
    units_per_container: int
    loaded_pallet_height_m: float
    loaded_pallet_mass_kg: float
    container_type: str
    container_internal_volume_m3: float
    container_payload_kg: float
    shipping_containers: int
    shipping_container_cost: float


@dataclass(frozen=True)
class HandlingResult:
    process_times: Dict[str, float]
    annual_electricity_testing_kwh: float
    units_per_technician_per_year: float
    receiving_pallets_per_day: int
    forklift_operator_time_s_per_day: float


@dataclass(frozen=True)
class StaffingResult:
    technicians: int
    forklift_operators: int
    truck_drivers: int
    supervisors: int
    sales_managers: int
    electrical_engineers: int
    operations_managers: int
    chief_executives: int
    administrative_assistants: int
    human_resources_personnel: int
    security_guards: int
    janitors: int
    employees_onsite: int


@dataclass(frozen=True)
class FacilitySizeResult:
    inspection_stations: int
    electrical_test_stations: int
    packing_stations: int
    station_width_m: float
    station_length_m: float
    station_footprint_m2: float
    conveyor_width_m: float
    conveyor_length_m: float
    total_floor_width_m: float
    inspection_test_packing_area_m2: float
    units_per_pallet: int
    pallets_per_rack: int
    units_per_rack: int
    racks_per_row: int
    receiving_racks: int
    rows_receiving: int
    total_racks: int
    floor_length_racks_m: float
    docks_and_storage_area_m2: float
    office_count: int
    restroom_area_m2: float
    breakroom_area_m2: float
    workshop_area_m2: float
    offices_area_total_m2: float
    total_facility_area_m2: float


@dataclass(frozen=True)
class CapitalCostResult:
    total_test_equipment_cost: float
    total_materials_handling_cost: float
    office_and_other_cost: float
    total_capital_cost: float
    line_items: Dict[str, float]


@dataclass(frozen=True)
class EmploymentCostResult:
    total_wages: float
    non_wage_compensation_cost: float
    total_employment_cost: float
    line_items: Dict[str, float]


@dataclass(frozen=True)
class AnnualExpenseResult:
    annual_revenue: float
    total_direct_costs: float
    total_indirect_costs: float
    total_annual_expenses: float
    line_items: Dict[str, float]


@dataclass(frozen=True)
class RevenueNPVResult:
    selling_price_per_unit: float
    yield_on_units: float
    annual_revenue: float
    cashflows: list[Dict[str, float]]
    total_npv: float


@dataclass(frozen=True)
class PurchasePriceResult:
    purchase_price_per_kwh_nameplate: float
    effective_repurposing_cost_per_kwh_nameplate: float


@dataclass(frozen=True)
class UnitEconomicsResult:
    sellable_energy_kwh_per_year: float
    processed_nameplate_kwh_per_year: float
    revenue_per_sellable_kwh: float
    cost_per_sellable_kwh: float
    direct_cost_per_sellable_kwh: float
    purchase_cost_per_sellable_kwh: float
    break_even_selling_price_per_kwh: float
    annual_break_even_selling_price_per_kwh: float
    break_even_purchase_price_per_unit: float
    break_even_purchase_price_per_kwh_nameplate: float
    annual_profit_before_tax: float
    annual_profit_after_tax: float
    annual_profit_before_discounting: float


@dataclass(frozen=True)
class B2UModelResult:
    module: Dict[str, Any]
    scenario: Dict[str, Any]
    currency: Dict[str, Any]
    throughput: ThroughputResult
    transportation: TransportationResult
    handling: HandlingResult
    staffing: StaffingResult
    facility_size: FacilitySizeResult
    capital_costs: CapitalCostResult
    employment_costs: EmploymentCostResult
    annual_expenses: AnnualExpenseResult
    revenue_npv: RevenueNPVResult
    purchase_price: PurchasePriceResult
    unit_economics: UnitEconomicsResult
    reliability: Dict[str, Any]
    yearly_operations: list[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary using currency-neutral monetary keys.

        Monetary values are expressed in ``currency["currency"]``. No
        currency-specific aliases such as ``total_npv_nok`` are added in the
        v1.0 API; consumers should read the explicit currency metadata instead.
        """
        return {
            "module": self.module,
            "scenario": self.scenario,
            "currency": self.currency,
            "throughput": asdict(self.throughput),
            "transportation": asdict(self.transportation),
            "handling": asdict(self.handling),
            "staffing": asdict(self.staffing),
            "facility_size": asdict(self.facility_size),
            "capital_costs": asdict(self.capital_costs),
            "employment_costs": asdict(self.employment_costs),
            "annual_expenses": asdict(self.annual_expenses),
            "revenue_npv": asdict(self.revenue_npv),
            "purchase_price": asdict(self.purchase_price),
            "unit_economics": asdict(self.unit_economics),
            "reliability": self.reliability,
            "yearly_operations": self.yearly_operations,
        }


TRANSPORT_PROFILES: Dict[str, TransportProfile] = {
    "Local": TransportProfile(
        name="Local",
        distance_m=_mi_to_m(30.0),
        trip_time_s=2.0 * SECONDS_PER_HOUR,
        truck_type="24\' Box Truck",
        truck_purchase_cost=62_000.0,
        truck_operating_cost_per_m=_cost_per_mile_to_cost_per_m(0.4),
        cargo_volume_m3=_ft3_to_m3(10.0 * 10.0 * 24.0),
        cargo_mass_kg=6500.0 / 2.2,
    ),
    "Regional": TransportProfile(
        name="Regional",
        distance_m=_mi_to_m(320.0),
        trip_time_s=8.0 * SECONDS_PER_HOUR,
        truck_type="Class 8 with 48\' trailer",
        truck_purchase_cost=141_000.0,
        truck_operating_cost_per_m=_cost_per_mile_to_cost_per_m(0.5),
        cargo_volume_m3=_ft3_to_m3(0.8 * 10.0 * 48.0 * 10.0),
        cargo_mass_kg=50000.0 / 2.2,
    ),
    "National": TransportProfile(
        name="National",
        distance_m=_mi_to_m(2400.0),
        trip_time_s=44.0 * SECONDS_PER_HOUR,
        truck_type="Class 8 with 48\' trailer",
        truck_purchase_cost=141_000.0,
        truck_operating_cost_per_m=_cost_per_mile_to_cost_per_m(0.5),
        cargo_volume_m3=_ft3_to_m3(0.8 * 10.0 * 48.0 * 10.0),
        cargo_mass_kg=50000.0 / 2.2,
    ),
}


def _default_reliability_summary(data: _ComponentData) -> Dict[str, Any]:
    usable_fraction = (1.0 - data.cell_fault_rate) ** data.number_of_cells
    return {
        "method": "analytical_formula",
        "samples": 0,
        "seed": None,
        "min_remaining_energy_fraction": None,
        "cell_fault_rate": data.cell_fault_rate,
        "cells_per_unit": data.number_of_cells,
        "usable_fraction": usable_fraction,
        "rejected_fraction": 1.0 - usable_fraction,
        "mean_sellable_energy_kwh_per_unit": (
            data.nameplate_energy_kwh * usable_fraction
        ),
        "mean_remaining_energy_kwh": data.remaining_energy_kwh,
        "mean_remaining_energy_fraction": data.remaining_energy_fraction,
    }


def _build_reliability_summary(
    component: Batterymodule | pack,
    data: _ComponentData,
    assumptions: ReliabilityAssumptions,
) -> Dict[str, Any]:
    if assumptions.summary_override is not None:
        return dict(assumptions.summary_override)

    if not assumptions.enabled:
        return _default_reliability_summary(data)

    return component_reliability_summary(
        component=component,
        samples=assumptions.samples,
        min_remaining_energy_fraction=assumptions.min_remaining_energy_fraction,
        seed=assumptions.seed,
        use_remaining_energy_for_revenue=(
            assumptions.use_remaining_energy_for_revenue
        ),
    )


def _selling_price_per_kwh(
    data: _ComponentData,
    economics: EconomicAssumptions,
) -> float:
    if economics.forced_selling_price_per_kwh is None:
        return data.forced_selling_price_per_kwh
    return economics.forced_selling_price_per_kwh


def _utilization_for_year(learning: LearningAssumptions, year: int) -> float:
    raw_utilization = (
        learning.initial_utilization
        + (year - 1) * learning.utilization_improvement_per_year
    )
    return min(learning.max_utilization, raw_utilization)


def _apply_learning(base_time_s: float, improvement_rate: float, year: int) -> float:
    if year <= 1:
        return base_time_s
    return base_time_s * ((1.0 - improvement_rate) ** (year - 1))


def _units_per_pallet(
    data: _ComponentData,
    layout: LayoutAssumptions,
) -> int:
    pallet_area = layout.pallet_width_m * layout.pallet_length_m
    return max(1, math.floor(pallet_area / (1.2 * data.footprint_m2)))


def _pallets_per_rack(
    data: _ComponentData,
    layout: LayoutAssumptions,
) -> int:
    clearance_m = _ft_to_m(0.5)
    loaded_height_m = layout.pallet_height_m + data.height_m + clearance_m
    return max(1, math.floor(layout.rack_stack_height_m / loaded_height_m))


def _reference_mass_kg(labor: LaborAssumptions) -> float:
    if labor.reference_mass_kg is not None:
        if labor.reference_mass_kg <= 0:
            raise ValueError("reference_mass_kg must be positive")
        return labor.reference_mass_kg
    if labor.reference_nameplate_energy_kwh <= 0:
        raise ValueError("reference_nameplate_energy_kwh must be positive")
    if labor.reference_specific_energy_wh_per_kg <= 0:
        raise ValueError("reference_specific_energy_wh_per_kg must be positive")
    return (
        labor.reference_nameplate_energy_kwh
        * 1000.0
        / labor.reference_specific_energy_wh_per_kg
    )


def _learned_with_minimum(
    raw_time_s: float,
    minimum_time_s: float,
    improvement_rate: float,
    year: int,
) -> float:
    learned_time_s = _apply_learning(raw_time_s, improvement_rate, year)
    return max(minimum_time_s, learned_time_s)


def _scaled_process_times(
    data: _ComponentData,
    labor: LaborAssumptions,
    learning: LearningAssumptions,
    year: int,
) -> Dict[str, float]:
    reference_energy_kwh = labor.reference_nameplate_energy_kwh
    if reference_energy_kwh <= 0:
        raise ValueError("reference_nameplate_energy_kwh must be positive")

    reference_mass_kg = _reference_mass_kg(labor)
    mass_scale = data.mass_kg / reference_mass_kg
    energy_scale = data.nameplate_energy_kwh / reference_energy_kwh

    inspection_time = _learned_with_minimum(
        labor.receiving_inspection_time_s * mass_scale,
        labor.minimum_inspection_time_s,
        learning.handling_time_improvement_per_year,
        year,
    )
    connection_time = _learned_with_minimum(
        labor.connection_initiation_time_s * energy_scale,
        labor.minimum_connection_time_s,
        learning.handling_time_improvement_per_year,
        year,
    )
    testing_time = _learned_with_minimum(
        labor.electrical_testing_time_s * energy_scale,
        labor.minimum_testing_time_s,
        learning.testing_time_improvement_per_year,
        year,
    )
    disconnect_time = _learned_with_minimum(
        labor.disconnect_time_s * energy_scale,
        labor.minimum_disconnect_time_s,
        learning.handling_time_improvement_per_year,
        year,
    )
    packing_time = _learned_with_minimum(
        labor.final_inspection_time_s * mass_scale,
        labor.minimum_packing_time_s,
        learning.packing_time_improvement_per_year,
        year,
    )
    disassembly_time = _apply_learning(
        labor.disassembly_time_s_per_unit,
        learning.handling_time_improvement_per_year,
        year,
    )

    return {
        "inspection_time": inspection_time,
        "connection_time": connection_time,
        "testing_time": testing_time,
        "disconnect_time": disconnect_time,
        "packing_time": packing_time,
        "disassembly_time": disassembly_time,
    }


def _fixed_plus_variable_process_times(
    data: _ComponentData,
    labor: LaborAssumptions,
    learning: LearningAssumptions,
    year: int,
) -> Dict[str, float]:
    inspection_time = _apply_learning(
        labor.receiving_inspection_time_s
        + labor.inspection_time_per_kg_s * data.mass_kg,
        learning.handling_time_improvement_per_year,
        year,
    )
    connection_time = _apply_learning(
        labor.connection_initiation_time_s
        + labor.connection_time_per_kwh_s * data.nameplate_energy_kwh,
        learning.handling_time_improvement_per_year,
        year,
    )
    testing_time = _apply_learning(
        labor.electrical_testing_time_s
        + labor.testing_time_per_kwh_s * data.nameplate_energy_kwh,
        learning.testing_time_improvement_per_year,
        year,
    )
    disconnect_time = _apply_learning(
        labor.disconnect_time_s,
        learning.handling_time_improvement_per_year,
        year,
    )
    packing_time = _apply_learning(
        labor.final_inspection_time_s + labor.packing_time_per_kg_s * data.mass_kg,
        learning.packing_time_improvement_per_year,
        year,
    )
    disassembly_time = _apply_learning(
        labor.disassembly_time_s_per_unit,
        learning.handling_time_improvement_per_year,
        year,
    )

    return {
        "inspection_time": inspection_time,
        "connection_time": connection_time,
        "testing_time": testing_time,
        "disconnect_time": disconnect_time,
        "packing_time": packing_time,
        "disassembly_time": disassembly_time,
    }


def _process_times(
    data: _ComponentData,
    labor: LaborAssumptions,
    learning: LearningAssumptions,
    year: int,
) -> Dict[str, float]:
    if labor.process_time_model == "nrel_scaled":
        step_times = _scaled_process_times(data, labor, learning, year)
    elif labor.process_time_model == "fixed_plus_variable":
        step_times = _fixed_plus_variable_process_times(
            data, labor, learning, year
        )
    else:
        raise ValueError(
            "process_time_model must be 'nrel_scaled' or 'fixed_plus_variable'"
        )

    inspection_time = step_times["inspection_time"]
    connection_time = step_times["connection_time"]
    testing_time = step_times["testing_time"]
    disconnect_time = step_times["disconnect_time"]
    packing_time = step_times["packing_time"]
    disassembly_time = step_times.get("disassembly_time", 0.0)

    electricity_per_unit = (
        (labor.charging_time_s / SECONDS_PER_HOUR)
        * labor.average_c_rate
        * data.remaining_energy_kwh
        / labor.charging_efficiency
    )

    pallet_move_time = _apply_learning(
        labor.pallet_move_time_s,
        learning.forklift_time_improvement_per_year,
        year,
    )

    test_stage_time = connection_time + testing_time + disconnect_time
    technician_touch_time = (
        disassembly_time + inspection_time + test_stage_time + packing_time
    )

    return {
        "process_time_model": labor.process_time_model,
        "reference_nameplate_energy_kwh": labor.reference_nameplate_energy_kwh,
        "reference_mass_kg": _reference_mass_kg(labor),
        "disassembly_time_per_unit_s": disassembly_time,
        "inspection_time_per_unit_s": inspection_time,
        "connection_time_per_unit_s": connection_time,
        "testing_time_per_unit_s": testing_time,
        "disconnect_time_per_unit_s": disconnect_time,
        "test_stage_time_per_unit_s": test_stage_time,
        "packing_time_per_unit_s": packing_time,
        "technician_touch_time_per_unit_s": technician_touch_time,
        "electricity_testing_kwh_per_unit": electricity_per_unit,
        "pallet_move_time_s": pallet_move_time,
    }


def _capacity_from_stations(
    station_count: int,
    process_time_per_unit_s: float,
    facility: FacilityAssumptions,
    utilization: float,
) -> int:
    annual_station_seconds = (
        station_count
        * facility.station_hours_per_day
        * facility.calendar_days_per_year
        * SECONDS_PER_HOUR
        * utilization
    )
    return math.floor(annual_station_seconds / process_time_per_unit_s)


def _target_units_per_year(
    data: _ComponentData,
    facility: FacilityAssumptions,
) -> int:
    return math.floor(
        facility.target_annual_throughput_kwh / data.nameplate_energy_kwh
    )


def _year_operation_state(
    data: _ComponentData,
    scenario: B2UScenario,
    facility_size: FacilitySizeResult,
    year: int,
) -> Dict[str, Any]:
    utilization = _utilization_for_year(scenario.learning, year)
    process_times = _process_times(data, scenario.labor, scenario.learning, year)

    inspection_capacity = _capacity_from_stations(
        facility_size.inspection_stations,
        process_times["inspection_time_per_unit_s"],
        scenario.facility,
        utilization,
    )
    testing_capacity = _capacity_from_stations(
        facility_size.electrical_test_stations,
        process_times["test_stage_time_per_unit_s"],
        scenario.facility,
        utilization,
    )
    packing_capacity = _capacity_from_stations(
        facility_size.packing_stations,
        process_times["packing_time_per_unit_s"],
        scenario.facility,
        utilization,
    )

    step_capacities = {
        "inspection": inspection_capacity,
        "testing": testing_capacity,
        "packing": packing_capacity,
    }
    bottleneck_step = min(step_capacities, key=step_capacities.get)
    installed_capacity_units_per_year = step_capacities[bottleneck_step]

    target_units = _target_units_per_year(data, scenario.facility)
    actual_units_per_year = min(target_units, installed_capacity_units_per_year)
    actual_units_per_day = math.floor(
        actual_units_per_year / scenario.facility.calendar_days_per_year
    )
    actual_annual_throughput_kwh = actual_units_per_year * data.nameplate_energy_kwh

    units_per_technician_per_year = (
        scenario.facility.work_days_per_year
        * scenario.facility.working_hours_per_day
        * SECONDS_PER_HOUR
        / process_times["technician_touch_time_per_unit_s"]
    )
    receiving_pallets_per_day = math.ceil(
        actual_units_per_day / facility_size.units_per_pallet
    )
    forklift_operator_time_s_per_day = (
        receiving_pallets_per_day * process_times["pallet_move_time_s"] * 2.0
    )
    annual_electricity_testing_kwh = (
        process_times["electricity_testing_kwh_per_unit"] * actual_units_per_year
    )

    return {
        "utilization": utilization,
        "installed_capacity_units_per_year": installed_capacity_units_per_year,
        "actual_units_per_year": actual_units_per_year,
        "actual_units_per_day": actual_units_per_day,
        "actual_annual_throughput_kwh": actual_annual_throughput_kwh,
        "bottleneck_step": bottleneck_step,
        "inspection_capacity_units_per_year": inspection_capacity,
        "testing_capacity_units_per_year": testing_capacity,
        "packing_capacity_units_per_year": packing_capacity,
        "process_times": process_times,
        "units_per_technician_per_year": units_per_technician_per_year,
        "receiving_pallets_per_day": receiving_pallets_per_day,
        "forklift_operator_time_s_per_day": forklift_operator_time_s_per_day,
        "annual_electricity_testing_kwh": annual_electricity_testing_kwh,
    }


def _build_staffing(
    scenario: B2UScenario,
    actual_annual_throughput_kwh: float,
    actual_units_per_year: int,
    units_per_technician_per_year: float,
    forklift_operator_time_s_per_day: float,
    truck_drivers: int,
) -> StaffingResult:
    technicians = max(
        1, math.ceil(actual_units_per_year / units_per_technician_per_year)
    )
    forklift_operators = max(
        1,
        math.ceil(
            (
                forklift_operator_time_s_per_day
                / SECONDS_PER_HOUR
                * scenario.facility.calendar_days_per_year
            )
            / (
                scenario.facility.working_hours_per_day
                * scenario.facility.work_days_per_year
            )
        ),
    )
    supervisors = max(
        1, math.ceil((technicians + forklift_operators + truck_drivers) / 10.0)
    )
    sales_managers = max(1, math.ceil(actual_annual_throughput_kwh / 100000.0))
    electrical_engineers = max(1, math.ceil(actual_annual_throughput_kwh / 100000.0))
    operations_managers = 1 if (
        technicians
        + forklift_operators
        + truck_drivers
        + supervisors
        + sales_managers
        + electrical_engineers
    ) > 20 else 0
    chief_executives = 1
    admin_scope = (
        technicians
        + forklift_operators
        + truck_drivers
        + supervisors
        + sales_managers
        + electrical_engineers
        + operations_managers
        + chief_executives
    )
    administrative_assistants = max(1, math.ceil(admin_scope / 30.0))
    human_resources_personnel = math.floor(admin_scope / 30.0)
    security_guards = 0
    janitors = 0
    employees_onsite = math.ceil(
        (
            sales_managers
            + chief_executives
            + administrative_assistants
            + human_resources_personnel
        )
        + 0.23
        * (
            electrical_engineers
            + operations_managers
            + technicians
            + forklift_operators
            + supervisors
        )
    )
    return StaffingResult(
        technicians=technicians,
        forklift_operators=forklift_operators,
        truck_drivers=truck_drivers,
        supervisors=supervisors,
        sales_managers=sales_managers,
        electrical_engineers=electrical_engineers,
        operations_managers=operations_managers,
        chief_executives=chief_executives,
        administrative_assistants=administrative_assistants,
        human_resources_personnel=human_resources_personnel,
        security_guards=security_guards,
        janitors=janitors,
        employees_onsite=employees_onsite,
    )


def _build_employment_costs(
    staffing: StaffingResult,
    wages: WageAssumptions,
) -> EmploymentCostResult:
    line_items = {
        "technicians": staffing.technicians * wages.technician_wage_per_year,
        "forklift_operators": (
            staffing.forklift_operators * wages.forklift_operator_wage_per_year
        ),
        "truck_drivers": staffing.truck_drivers * wages.truck_driver_wage_per_year,
        "supervisors": staffing.supervisors * wages.supervisor_wage_per_year,
        "chief_executives": (
            staffing.chief_executives * wages.chief_executive_wage_per_year
        ),
        "electrical_engineers": (
            staffing.electrical_engineers * wages.electrical_engineer_wage_per_year
        ),
        "sales_managers": staffing.sales_managers * wages.sales_manager_wage_per_year,
        "admin_assistants": (
            staffing.administrative_assistants * wages.admin_assistant_wage_per_year
        ),
        "security_guards": (
            staffing.security_guards * wages.security_guard_wage_per_year
        ),
        "hr_personnel": (
            staffing.human_resources_personnel * wages.hr_manager_wage_per_year
        ),
        "operations_managers": (
            staffing.operations_managers * wages.operations_manager_wage_per_year
        ),
        "janitors": staffing.janitors * wages.janitor_wage_per_year,
    }
    total_wages = sum(line_items.values())
    non_wage_compensation = wages.non_wage_compensation_fraction * total_wages
    return EmploymentCostResult(
        total_wages=total_wages,
        non_wage_compensation_cost=non_wage_compensation,
        total_employment_cost=total_wages + non_wage_compensation,
        line_items=line_items,
    )


def _build_facility_size(
    data: _ComponentData,
    scenario: B2UScenario,
) -> FacilitySizeResult:
    target_units_per_year = _target_units_per_year(data, scenario.facility)
    base_times = _process_times(data, scenario.labor, scenario.learning, year=1)
    design_seconds = (
        scenario.facility.station_hours_per_day
        * scenario.facility.calendar_days_per_year
        * SECONDS_PER_HOUR
        * scenario.facility.design_utilization
    )
    inspection_stations = math.ceil(
        target_units_per_year
        * base_times["inspection_time_per_unit_s"]
        / design_seconds
    )
    electrical_test_stations = math.ceil(
        target_units_per_year
        * base_times["test_stage_time_per_unit_s"]
        / design_seconds
    )
    packing_stations = math.ceil(
        target_units_per_year
        * base_times["packing_time_per_unit_s"]
        / design_seconds
    )

    station_width_m = max(_ft_to_m(2.0), data.width_m + _ft_to_m(1.0))
    station_length_m = max(
        scenario.layout.width_depth_per_employee_m,
        data.length_m + _ft_to_m(1.0),
    )
    station_footprint_m2 = station_width_m * station_length_m
    conveyor_width_m = station_length_m
    station_pair_count = math.ceil(
        (inspection_stations + electrical_test_stations + packing_stations) / 2.0
    )
    conveyor_length_m = station_pair_count * (
        station_width_m + scenario.layout.width_depth_per_employee_m
    )
    total_floor_width_m = (
        conveyor_width_m
        + 2.0 * station_length_m
        + 2.0 * scenario.layout.hallway_width_m
        + scenario.layout.forklift_width_m
    )
    inspection_test_packing_area_m2 = total_floor_width_m * conveyor_length_m

    units_per_pallet = _units_per_pallet(data, scenario.layout)
    pallets_per_rack = _pallets_per_rack(data, scenario.layout)
    units_per_rack = units_per_pallet * pallets_per_rack
    racks_per_row = max(
        1,
        math.floor(
            (
                total_floor_width_m
                - scenario.layout.forklift_width_m
                - 2.0 * scenario.layout.hallway_width_m
            )
            / (scenario.layout.pallet_width_m + scenario.layout.rack_row_buffer_m)
        ),
    )
    target_units_per_day = math.floor(
        target_units_per_year / scenario.facility.calendar_days_per_year
    )
    receiving_racks = math.ceil(target_units_per_day / units_per_rack)
    rows_receiving = math.ceil(receiving_racks / racks_per_row)
    total_racks = receiving_racks * 2
    floor_length_racks_m = rows_receiving * 2.0 * (
        scenario.layout.pallet_length_m + _ft_to_m(3.0)
    )
    docks_and_storage_area_m2 = floor_length_racks_m * total_floor_width_m

    utilization = _utilization_for_year(scenario.learning, 1)
    units_per_technician_per_year = (
        scenario.facility.work_days_per_year
        * scenario.facility.working_hours_per_day
        * SECONDS_PER_HOUR
        / base_times["technician_touch_time_per_unit_s"]
    )
    inspection_capacity = _capacity_from_stations(
        inspection_stations,
        base_times["inspection_time_per_unit_s"],
        scenario.facility,
        utilization,
    )
    testing_capacity = _capacity_from_stations(
        electrical_test_stations,
        base_times["test_stage_time_per_unit_s"],
        scenario.facility,
        utilization,
    )
    packing_capacity = _capacity_from_stations(
        packing_stations,
        base_times["packing_time_per_unit_s"],
        scenario.facility,
        utilization,
    )
    year_one_units = min(
        target_units_per_year,
        min(inspection_capacity, testing_capacity, packing_capacity),
    )
    year_one_units_day = math.floor(
        year_one_units / scenario.facility.calendar_days_per_year
    )
    year_one_pallets_day = math.ceil(year_one_units_day / units_per_pallet)
    year_one_forklift_time = (
        year_one_pallets_day * base_times["pallet_move_time_s"] * 2.0
    )
    year_one_transport = _build_transportation(
        data,
        year_one_units,
        scenario.collection_scale,
        scenario.shipping,
        scenario.capital.shipping_container_cost,
        scenario.road_freight,
    )
    year_one_staffing = _build_staffing(
        scenario,
        year_one_units * data.nameplate_energy_kwh,
        year_one_units,
        units_per_technician_per_year,
        year_one_forklift_time,
        year_one_transport.number_of_trucks_and_drivers,
    )

    office_count = (
        year_one_staffing.sales_managers
        + year_one_staffing.electrical_engineers
        + year_one_staffing.operations_managers
        + year_one_staffing.chief_executives
        + year_one_staffing.administrative_assistants
        + year_one_staffing.human_resources_personnel
    )
    total_width_offices_m = scenario.layout.office_width_m * office_count
    restroom_area_m2 = max(
        scenario.layout.office_length_m * _ft_to_m(6.0) * 2.0,
        0.5 * year_one_staffing.employees_onsite * M2_PER_FT2,
    )
    restroom_total_width_m = restroom_area_m2 / scenario.layout.office_length_m
    hallway_total_length_m = restroom_total_width_m + total_width_offices_m
    breakroom_area_m2 = year_one_staffing.employees_onsite * 4.0 * M2_PER_FT2
    workshop_area_m2 = year_one_staffing.electrical_engineers * 64.0 * M2_PER_FT2
    offices_area_total_m2 = (
        workshop_area_m2
        + breakroom_area_m2
        + restroom_area_m2
        + total_width_offices_m * scenario.layout.office_length_m
        + scenario.layout.hallway_office_width_m * hallway_total_length_m
    )
    total_facility_area_m2 = (
        inspection_test_packing_area_m2
        + docks_and_storage_area_m2
        + offices_area_total_m2
    )

    return FacilitySizeResult(
        inspection_stations=inspection_stations,
        electrical_test_stations=electrical_test_stations,
        packing_stations=packing_stations,
        station_width_m=station_width_m,
        station_length_m=station_length_m,
        station_footprint_m2=station_footprint_m2,
        conveyor_width_m=conveyor_width_m,
        conveyor_length_m=conveyor_length_m,
        total_floor_width_m=total_floor_width_m,
        inspection_test_packing_area_m2=inspection_test_packing_area_m2,
        units_per_pallet=units_per_pallet,
        pallets_per_rack=pallets_per_rack,
        units_per_rack=units_per_rack,
        racks_per_row=racks_per_row,
        receiving_racks=receiving_racks,
        rows_receiving=rows_receiving,
        total_racks=total_racks,
        floor_length_racks_m=floor_length_racks_m,
        docks_and_storage_area_m2=docks_and_storage_area_m2,
        office_count=office_count,
        restroom_area_m2=restroom_area_m2,
        breakroom_area_m2=breakroom_area_m2,
        workshop_area_m2=workshop_area_m2,
        offices_area_total_m2=offices_area_total_m2,
        total_facility_area_m2=total_facility_area_m2,
    )


def _container_spec(shipping: ShippingAssumptions) -> Dict[str, float | int | str]:
    if shipping.container_type == "20ft":
        return {
            "container_type": "20ft",
            "internal_length_m": shipping.container_20ft_internal_length_m,
            "internal_width_m": shipping.container_20ft_internal_width_m,
            "internal_height_m": shipping.container_20ft_internal_height_m,
            "volume_m3": shipping.container_20ft_volume_m3,
            "payload_kg": shipping.container_20ft_payload_kg,
            "euro_pallet_slots": shipping.container_20ft_euro_pallet_slots,
        }
    if shipping.container_type == "40ft":
        return {
            "container_type": "40ft",
            "internal_length_m": shipping.container_40ft_internal_length_m,
            "internal_width_m": shipping.container_40ft_internal_width_m,
            "internal_height_m": shipping.container_40ft_internal_height_m,
            "volume_m3": shipping.container_40ft_volume_m3,
            "payload_kg": shipping.container_40ft_payload_kg,
            "euro_pallet_slots": shipping.container_40ft_euro_pallet_slots,
        }
    raise ValueError("container_type must be '20ft' or '40ft'")


def _shipping_packaging(
    data: _ComponentData,
    shipping: ShippingAssumptions,
) -> Dict[str, float | int | str]:
    container = _container_spec(shipping)
    pallet_area_m2 = shipping.pallet_length_m * shipping.pallet_width_m
    units_per_layer = max(
        1,
        math.floor(
            pallet_area_m2
            * shipping.pallet_area_utilization
            / data.footprint_m2
        ),
    )
    max_loaded_height_m = min(
        shipping.max_loaded_pallet_height_m,
        float(container["internal_height_m"]),
    )
    usable_load_height_m = max_loaded_height_m - shipping.pallet_height_m
    max_layers = max(1, math.floor(usable_load_height_m / data.height_m))
    units_by_geometry = units_per_layer * max_layers
    units_by_mass = math.floor(shipping.pallet_max_payload_kg / data.mass_kg)
    units_per_pallet = min(units_by_geometry, units_by_mass)

    if units_per_pallet < 1:
        raise ValueError("Component cannot be loaded on one europallet")

    layers_used = math.ceil(units_per_pallet / units_per_layer)
    loaded_pallet_height_m = shipping.pallet_height_m + layers_used * data.height_m
    loaded_pallet_mass_kg = shipping.pallet_tare_kg + units_per_pallet * data.mass_kg
    loaded_pallet_volume_m3 = pallet_area_m2 * loaded_pallet_height_m
    pallets_by_slots = int(container["euro_pallet_slots"])
    pallets_by_payload = math.floor(
        float(container["payload_kg"]) / loaded_pallet_mass_kg
    )
    pallets_by_volume = math.floor(
        float(container["volume_m3"]) / loaded_pallet_volume_m3
    )
    pallets_per_container = min(
        pallets_by_slots,
        pallets_by_payload,
        pallets_by_volume,
    )

    if pallets_per_container < 1:
        raise ValueError("Loaded europallet does not fit the selected container")

    return {
        "units_per_shipping_pallet": units_per_pallet,
        "loaded_pallet_height_m": loaded_pallet_height_m,
        "loaded_pallet_mass_kg": loaded_pallet_mass_kg,
        "shipping_pallets_per_container": pallets_per_container,
        "units_per_container": units_per_pallet * pallets_per_container,
        "container_type": str(container["container_type"]),
        "container_internal_volume_m3": float(container["volume_m3"]),
        "container_payload_kg": float(container["payload_kg"]),
    }


def _build_transportation(
    data: _ComponentData,
    actual_units_per_year: int,
    collection_scale: str,
    shipping: ShippingAssumptions,
    shipping_container_cost: float,
    road_freight: RoadFreightAssumptions = RoadFreightAssumptions(),
) -> TransportationResult:
    profile = TRANSPORT_PROFILES[collection_scale]
    truck_type = road_freight.truck_type or profile.truck_type
    truck_purchase_cost = (
        profile.truck_purchase_cost
        if road_freight.truck_purchase_cost is None
        else road_freight.truck_purchase_cost
    )
    truck_operating_cost_per_m = (
        profile.truck_operating_cost_per_m
        if road_freight.truck_operating_cost_per_m is None
        else road_freight.truck_operating_cost_per_m
    )
    unit_capacity_by_mass = profile.cargo_mass_kg / data.mass_kg
    unit_capacity_by_volume = profile.cargo_volume_m3 / data.volume_m3
    truck_unit_capacity = max(
        1,
        math.floor(min(unit_capacity_by_mass, unit_capacity_by_volume)),
    )
    trips_per_year = math.ceil(actual_units_per_year / truck_unit_capacity)
    total_collection_time_s = trips_per_year * profile.trip_time_s
    number_of_trucks = math.ceil(
        total_collection_time_s / (252 * 8 * SECONDS_PER_HOUR)
    )
    total_distance_m_per_year = profile.distance_m * trips_per_year
    packaging = _shipping_packaging(data, shipping)
    concurrent_units = number_of_trucks * truck_unit_capacity
    shipping_containers = math.ceil(
        concurrent_units / int(packaging["units_per_container"])
    )
    return TransportationResult(
        collection_scale=collection_scale,
        truck_type=truck_type,
        truck_purchase_cost=truck_purchase_cost,
        truck_operating_cost_per_m=truck_operating_cost_per_m,
        cargo_volume_m3=profile.cargo_volume_m3,
        cargo_mass_kg=profile.cargo_mass_kg,
        truck_unit_capacity=truck_unit_capacity,
        trips_per_year=trips_per_year,
        total_collection_time_s=total_collection_time_s,
        number_of_trucks_and_drivers=number_of_trucks,
        total_distance_m_per_year=total_distance_m_per_year,
        units_per_shipping_pallet=int(packaging["units_per_shipping_pallet"]),
        shipping_pallets_per_container=int(
            packaging["shipping_pallets_per_container"]
        ),
        units_per_container=int(packaging["units_per_container"]),
        loaded_pallet_height_m=float(packaging["loaded_pallet_height_m"]),
        loaded_pallet_mass_kg=float(packaging["loaded_pallet_mass_kg"]),
        container_type=str(packaging["container_type"]),
        container_internal_volume_m3=float(
            packaging["container_internal_volume_m3"]
        ),
        container_payload_kg=float(packaging["container_payload_kg"]),
        shipping_containers=shipping_containers,
        shipping_container_cost=shipping_container_cost,
    )


def _build_handling(
    actual_units_per_day: int,
    units_per_pallet: int,
    operation_state: Dict[str, Any],
) -> HandlingResult:
    receiving_pallets_per_day = math.ceil(actual_units_per_day / units_per_pallet)
    return HandlingResult(
        process_times=operation_state["process_times"],
        annual_electricity_testing_kwh=operation_state["annual_electricity_testing_kwh"],
        units_per_technician_per_year=operation_state[
            "units_per_technician_per_year"
        ],
        receiving_pallets_per_day=receiving_pallets_per_day,
        forklift_operator_time_s_per_day=operation_state[
            "forklift_operator_time_s_per_day"
        ],
    )


def _build_capital_costs(
    data: _ComponentData,
    actual_units_per_year: int,
    transportation: TransportationResult,
    handling: HandlingResult,
    facility_size: FacilitySizeResult,
    capital: CapitalCostAssumptions,
) -> CapitalCostResult:
    qty_test_channels = facility_size.electrical_test_stations
    item_test_channels = qty_test_channels * capital.test_channel_cost_per_station
    qty_can_hardware = facility_size.electrical_test_stations
    item_can_hardware = qty_can_hardware * capital.can_hardware_cost_per_station
    qty_computers = math.ceil(facility_size.electrical_test_stations / 4.0)
    item_computers = qty_computers * capital.computer_cost
    total_test_equipment = item_test_channels + item_can_hardware + item_computers

    qty_conveyors_m2 = facility_size.conveyor_width_m * facility_size.conveyor_length_m
    item_conveyors = qty_conveyors_m2 * capital.conveyor_cost_per_m2
    qty_upfront_purchases = actual_units_per_year / 12.0
    item_upfront_purchases = qty_upfront_purchases * data.purchase_price_per_unit
    item_storage_racks = facility_size.total_racks * capital.storage_rack_cost
    forklift_count = max(
        1,
        math.ceil((handling.forklift_operator_time_s_per_day / SECONDS_PER_HOUR) / 24.0),
    )
    item_forklift = forklift_count * capital.forklift_cost
    item_md_truck = (
        transportation.number_of_trucks_and_drivers
        * transportation.truck_purchase_cost
    )
    item_shipping_containers = (
        transportation.shipping_containers * capital.shipping_container_cost
    )
    qty_work_stations = (
        facility_size.inspection_stations
        + facility_size.electrical_test_stations
        + facility_size.packing_stations
    )
    item_work_stations = qty_work_stations * capital.workstation_cost
    total_materials_handling = (
        item_conveyors
        + item_upfront_purchases
        + item_storage_racks
        + item_forklift
        + item_md_truck
        + item_shipping_containers
        + item_work_stations
    )
    total_capital_cost = (
        total_test_equipment
        + total_materials_handling
        + capital.office_and_other_cost
    )
    line_items = {
        "battery_test_channels": item_test_channels,
        "can_hardware": item_can_hardware,
        "computers": item_computers,
        "conveyors": item_conveyors,
        "upfront_battery_purchases": item_upfront_purchases,
        "storage_racks": item_storage_racks,
        "forklifts": item_forklift,
        "md_trucks": item_md_truck,
        "shipping_containers": item_shipping_containers,
        "workstations": item_work_stations,
    }
    return CapitalCostResult(
        total_test_equipment_cost=total_test_equipment,
        total_materials_handling_cost=total_materials_handling,
        office_and_other_cost=capital.office_and_other_cost,
        total_capital_cost=total_capital_cost,
        line_items=line_items,
    )


def _build_annual_expenses(
    data: _ComponentData,
    actual_units_per_year: int,
    transportation: TransportationResult,
    facility_size: FacilitySizeResult,
    employment_costs: EmploymentCostResult,
    annual_revenue: float,
    annual_electricity_testing_kwh: float,
    economics: EconomicAssumptions,
) -> AnnualExpenseResult:
    battery_units_cost = actual_units_per_year * data.purchase_price_per_unit
    labor_cost = employment_costs.total_employment_cost
    rent_cost = facility_size.total_facility_area_m2 * economics.rent_per_m2_year
    electricity_testing_cost = (
        annual_electricity_testing_kwh * economics.electricity_testing_cost_per_kwh
    )
    hvac_lighting_cost = (
        facility_size.total_facility_area_m2 * economics.hvac_lighting_cost_per_m2_year
    )
    transportation_cost = (
        transportation.total_distance_m_per_year
        * transportation.truck_operating_cost_per_m
    )
    other_direct_cost = (
        economics.other_direct_cost_fraction_of_wages
        * employment_costs.total_wages
    )
    total_direct_costs = (
        battery_units_cost
        + labor_cost
        + rent_cost
        + electricity_testing_cost
        + hvac_lighting_cost
        + transportation_cost
        + other_direct_cost
    )
    insurance_cost = economics.insurance_fraction_of_direct_costs * total_direct_costs
    ga_cost = economics.ga_fraction_of_direct_costs * total_direct_costs
    warranty_cost = economics.warranty_fraction_of_revenue * annual_revenue
    rnd_cost = economics.rnd_fraction_of_direct_costs * total_direct_costs
    total_indirect_costs = insurance_cost + ga_cost + warranty_cost + rnd_cost
    total_annual_expenses = total_direct_costs + total_indirect_costs
    line_items = {
        "battery_units": battery_units_cost,
        "labor": labor_cost,
        "rent": rent_cost,
        "electricity_testing": electricity_testing_cost,
        "electricity_hvac_lighting": hvac_lighting_cost,
        "transportation": transportation_cost,
        "other_direct": other_direct_cost,
        "insurance": insurance_cost,
        "ga": ga_cost,
        "warranty": warranty_cost,
        "rnd": rnd_cost,
    }
    return AnnualExpenseResult(
        annual_revenue=annual_revenue,
        total_direct_costs=total_direct_costs,
        total_indirect_costs=total_indirect_costs,
        total_annual_expenses=total_annual_expenses,
        line_items=line_items,
    )


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return float("nan")
    return numerator / denominator


def _build_unit_economics(
    data: _ComponentData,
    actual_units_per_year: int,
    reliability_summary: Dict[str, Any],
    annual_expenses: AnnualExpenseResult,
    annual_revenue: float,
    economics: EconomicAssumptions,
) -> UnitEconomicsResult:
    """Build per-kWh and break-even economics in scenario currency."""
    sellable_energy_kwh = (
        reliability_summary["mean_sellable_energy_kwh_per_unit"]
        * actual_units_per_year
    )
    processed_nameplate_kwh = data.nameplate_energy_kwh * actual_units_per_year
    purchase_cost = data.purchase_price_per_unit * actual_units_per_year
    direct_without_purchase = annual_expenses.total_direct_costs - purchase_cost
    indirect_fraction_on_direct = (
        economics.insurance_fraction_of_direct_costs
        + economics.ga_fraction_of_direct_costs
        + economics.rnd_fraction_of_direct_costs
    )
    warranty_fraction = economics.warranty_fraction_of_revenue

    target_purchase_cost = (
        annual_revenue * (1.0 - warranty_fraction)
        - (1.0 + indirect_fraction_on_direct) * direct_without_purchase
    ) / (1.0 + indirect_fraction_on_direct)
    break_even_purchase_price_per_unit = _safe_divide(
        target_purchase_cost, actual_units_per_year
    )

    profit_before_tax = annual_revenue - annual_expenses.total_annual_expenses
    # Tax is paid only in profitable years.  The model deliberately does not
    # monetize losses or carry tax losses forward to later years; this is a
    # conservative project-boundary simplification.
    taxes = max(
        0.0,
        profit_before_tax
        * (economics.federal_tax_rate + economics.state_tax_rate),
    )
    profit_after_tax = profit_before_tax - taxes

    # Annual break-even selling price: solve for price where revenue = expenses,
    # treating warranty as a fraction of break-even revenue (not actual revenue).
    # This avoids the circular dependency where warranty cost depends on the
    # input selling price.
    # Formula: p = non_warranty_expenses / ((1 - warranty_fraction) * sellable_kwh)
    warranty_cost = annual_expenses.line_items.get("warranty", 0.0)
    non_warranty_expenses = annual_expenses.total_annual_expenses - warranty_cost
    if sellable_energy_kwh <= 0 or warranty_fraction >= 1.0:
        annual_break_even_price = float("nan")
    else:
        annual_break_even_price = non_warranty_expenses / (
            (1.0 - warranty_fraction) * sellable_energy_kwh
        )

    return UnitEconomicsResult(
        sellable_energy_kwh_per_year=sellable_energy_kwh,
        processed_nameplate_kwh_per_year=processed_nameplate_kwh,
        revenue_per_sellable_kwh=_safe_divide(
            annual_revenue, sellable_energy_kwh
        ),
        cost_per_sellable_kwh=_safe_divide(
            annual_expenses.total_annual_expenses, sellable_energy_kwh
        ),
        direct_cost_per_sellable_kwh=_safe_divide(
            annual_expenses.total_direct_costs, sellable_energy_kwh
        ),
        purchase_cost_per_sellable_kwh=_safe_divide(
            purchase_cost, sellable_energy_kwh
        ),
        # Keep this non-circular annual break-even price separate from the NPV
        # break-even price solved in ``max_purchase_price.py``.
        break_even_selling_price_per_kwh=annual_break_even_price,
        annual_break_even_selling_price_per_kwh=annual_break_even_price,
        break_even_purchase_price_per_unit=break_even_purchase_price_per_unit,
        break_even_purchase_price_per_kwh_nameplate=_safe_divide(
            break_even_purchase_price_per_unit, data.nameplate_energy_kwh
        ),
        annual_profit_before_tax=profit_before_tax,
        annual_profit_after_tax=profit_after_tax,
        annual_profit_before_discounting=profit_after_tax,
    )


def _build_purchase_price(
    data: _ComponentData,
    economics: EconomicAssumptions,
) -> PurchasePriceResult:
    selling_price_per_unit = (
        _selling_price_per_kwh(data, economics) * data.nameplate_energy_kwh
    )
    purchase_price = (
        data.purchase_price_per_unit / data.nameplate_energy_kwh
    )
    repurposing_cost = (
        selling_price_per_unit - data.purchase_price_per_unit
    ) / data.nameplate_energy_kwh
    return PurchasePriceResult(
        purchase_price_per_kwh_nameplate=purchase_price,
        effective_repurposing_cost_per_kwh_nameplate=repurposing_cost,
    )


def _build_year_operation(
    data: _ComponentData,
    scenario: B2UScenario,
    facility_size: FacilitySizeResult,
    reliability_summary: Dict[str, Any],
    year: int,
) -> Dict[str, Any]:
    state = _year_operation_state(data, scenario, facility_size, year)
    transportation = _build_transportation(
        data,
        state["actual_units_per_year"],
        scenario.collection_scale,
        scenario.shipping,
        scenario.capital.shipping_container_cost,
        scenario.road_freight,
    )
    staffing = _build_staffing(
        scenario,
        state["actual_annual_throughput_kwh"],
        state["actual_units_per_year"],
        state["units_per_technician_per_year"],
        state["forklift_operator_time_s_per_day"],
        transportation.number_of_trucks_and_drivers,
    )
    employment_costs = _build_employment_costs(staffing, scenario.wages)
    annual_revenue = (
        _selling_price_per_kwh(data, scenario.economics)
        * reliability_summary["mean_sellable_energy_kwh_per_unit"]
        * state["actual_units_per_year"]
    )
    annual_expenses = _build_annual_expenses(
        data,
        state["actual_units_per_year"],
        transportation,
        facility_size,
        employment_costs,
        annual_revenue,
        state["annual_electricity_testing_kwh"],
        scenario.economics,
    )
    profit_before_tax = annual_revenue - annual_expenses.total_annual_expenses
    # Tax is paid only in profitable years.  Loss carryforward is excluded from
    # the default TEA model to avoid firm-level tax assumptions outside the
    # project boundary.
    taxes = max(
        0.0,
        profit_before_tax
        * (scenario.economics.federal_tax_rate + scenario.economics.state_tax_rate),
    )
    profit_after_tax = profit_before_tax - taxes
    annual_npv = profit_after_tax / (
        (1.0 + scenario.economics.discount_rate) ** year
    )
    return {
        "year": year,
        "utilization": state["utilization"],
        "inspection_capacity_units_per_year": state[
            "inspection_capacity_units_per_year"
        ],
        "testing_capacity_units_per_year": state["testing_capacity_units_per_year"],
        "packing_capacity_units_per_year": state["packing_capacity_units_per_year"],
        "installed_capacity_units_per_year": state[
            "installed_capacity_units_per_year"
        ],
        "actual_units_per_year": state["actual_units_per_year"],
        "actual_throughput_kwh": state["actual_annual_throughput_kwh"],
        "bottleneck_step": state["bottleneck_step"],
        "technicians": staffing.technicians,
        "forklift_operators": staffing.forklift_operators,
        "annual_revenue": annual_revenue,
        "total_annual_expenses": annual_expenses.total_annual_expenses,
        "annual_npv": annual_npv,
        "transportation": transportation,
        "handling": _build_handling(
            state["actual_units_per_day"],
            facility_size.units_per_pallet,
            state,
        ),
        "staffing": staffing,
        "employment_costs": employment_costs,
        "annual_expenses": annual_expenses,
        "annual_profit_after_tax": profit_after_tax,
        "taxes": taxes,
    }


def run_b2u_scenario(
    component: Batterymodule | pack,
    scenario: B2UScenario,
) -> B2UModelResult:
    data = _component_data(component)
    reliability = _build_reliability_summary(
        component,
        data,
        scenario.reliability,
    )
    facility_size = _build_facility_size(data, scenario)
    year_ops = [
        _build_year_operation(data, scenario, facility_size, reliability, year)
        for year in range(1, scenario.learning.analysis_years + 1)
    ]

    first_year = year_ops[0]
    transportation = first_year["transportation"]
    handling = first_year["handling"]
    staffing = first_year["staffing"]
    employment_costs = first_year["employment_costs"]
    annual_expenses = first_year["annual_expenses"]

    capital_costs = _build_capital_costs(
        data,
        first_year["actual_units_per_year"],
        transportation,
        handling,
        facility_size,
        scenario.capital,
    )

    selling_price_per_unit = (
        _selling_price_per_kwh(data, scenario.economics) * data.nameplate_energy_kwh
    )
    yield_on_units = float(reliability["usable_fraction"])

    top_level_throughput = ThroughputResult(
        target_annual_throughput_kwh=scenario.facility.target_annual_throughput_kwh,
        target_units_per_year=_target_units_per_year(data, scenario.facility),
        installed_capacity_units_per_year=first_year[
            "installed_capacity_units_per_year"
        ],
        actual_units_per_year=first_year["actual_units_per_year"],
        actual_units_per_day=math.floor(
            first_year["actual_units_per_year"]
            / scenario.facility.calendar_days_per_year
        ),
        actual_annual_throughput_kwh=first_year["actual_throughput_kwh"],
        utilization=first_year["utilization"],
        bottleneck_step=first_year["bottleneck_step"],
    )

    cashflows = [
        {
            "year": 0.0,
            "utilization": 0.0,
            "actual_units_per_year": 0.0,
            "actual_throughput_kwh": 0.0,
            "bottleneck_step": "capital",
            "expenses": capital_costs.total_capital_cost,
            "taxes": 0.0,
            "revenue": 0.0,
            "profit_after_tax": -capital_costs.total_capital_cost,
            "annual_npv": -capital_costs.total_capital_cost,
        }
    ]
    for year_state in year_ops:
        year = year_state["year"]
        annual_expense = year_state["annual_expenses"]
        cashflows.append(
            {
                "year": float(year),
                "utilization": year_state["utilization"],
                "actual_units_per_year": float(year_state["actual_units_per_year"]),
                "actual_throughput_kwh": year_state["actual_throughput_kwh"],
                "bottleneck_step": year_state["bottleneck_step"],
                "expenses": annual_expense.total_annual_expenses,
                "taxes": year_state["taxes"],
                "revenue": year_state["annual_revenue"],
                "profit_after_tax": year_state[
                    "annual_profit_after_tax"
                ],
                "annual_npv": year_state["annual_npv"],
            }
        )

    total_npv = sum(item["annual_npv"] for item in cashflows)
    revenue_npv = RevenueNPVResult(
        selling_price_per_unit=selling_price_per_unit,
        yield_on_units=yield_on_units,
        annual_revenue=first_year["annual_revenue"],
        cashflows=cashflows,
        total_npv=total_npv,
    )

    purchase_price = _build_purchase_price(data, scenario.economics)
    unit_economics = _build_unit_economics(
        data=data,
        actual_units_per_year=first_year["actual_units_per_year"],
        reliability_summary=reliability,
        annual_expenses=annual_expenses,
        annual_revenue=first_year["annual_revenue"],
        economics=scenario.economics,
    )
    yearly_operations = [
        {
            "year": op["year"],
            "utilization": op["utilization"],
            "inspection_capacity_units_per_year": op[
                "inspection_capacity_units_per_year"
            ],
            "testing_capacity_units_per_year": op["testing_capacity_units_per_year"],
            "packing_capacity_units_per_year": op["packing_capacity_units_per_year"],
            "installed_capacity_units_per_year": op[
                "installed_capacity_units_per_year"
            ],
            "actual_units_per_year": op["actual_units_per_year"],
            "actual_throughput_kwh": op["actual_throughput_kwh"],
            "bottleneck_step": op["bottleneck_step"],
            "technicians": op["staffing"].technicians,
            "forklift_operators": op["staffing"].forklift_operators,
            "annual_revenue": op["annual_revenue"],
            "total_annual_expenses": op[
                "annual_expenses"
            ].total_annual_expenses,
            "annual_npv": op["annual_npv"],
        }
        for op in year_ops
    ]

    return B2UModelResult(
        module=data.to_public_dict(),
        scenario=scenario.to_dict(),
        currency=asdict(scenario.currency),
        throughput=top_level_throughput,
        transportation=transportation,
        handling=handling,
        staffing=staffing,
        facility_size=facility_size,
        capital_costs=capital_costs,
        employment_costs=employment_costs,
        annual_expenses=annual_expenses,
        revenue_npv=revenue_npv,
        purchase_price=purchase_price,
        unit_economics=unit_economics,
        reliability=reliability,
        yearly_operations=yearly_operations,
    )


def run_b2u_model(
    component: Batterymodule | pack,
    *,
    scenario: Optional[B2UScenario] = None,
    facility: FacilityAssumptions = FacilityAssumptions(),
    labor: LaborAssumptions = LaborAssumptions(),
    layout: LayoutAssumptions = LayoutAssumptions(),
    capital: CapitalCostAssumptions = CapitalCostAssumptions(),
    wages: WageAssumptions = WageAssumptions(),
    economics: EconomicAssumptions = EconomicAssumptions(),
    learning: LearningAssumptions = LearningAssumptions(),
    shipping: ShippingAssumptions = ShippingAssumptions(),
    reliability: ReliabilityAssumptions = ReliabilityAssumptions(),
    currency: CurrencyAssumptions = CurrencyAssumptions(),
    road_freight: RoadFreightAssumptions = RoadFreightAssumptions(),
    collection_scale: str = "Regional",
) -> B2UModelResult:
    if scenario is None:
        scenario = B2UScenario(
            name="ad_hoc",
            facility=facility,
            labor=labor,
            layout=layout,
            capital=capital,
            wages=wages,
            economics=economics,
            learning=learning,
            shipping=shipping,
            reliability=reliability,
            currency=currency,
            road_freight=road_freight,
            collection_scale=collection_scale,
        )
    return run_b2u_scenario(component, scenario)


__all__ = [
    "FacilityAssumptions",
    "TransportProfile",
    "LaborAssumptions",
    "LayoutAssumptions",
    "ShippingAssumptions",
    "CurrencyAssumptions",
    "RoadFreightAssumptions",
    "CapitalCostAssumptions",
    "WageAssumptions",
    "EconomicAssumptions",
    "LearningAssumptions",
    "ReliabilityAssumptions",
    "B2UScenario",
    "ThroughputResult",
    "TransportationResult",
    "HandlingResult",
    "StaffingResult",
    "FacilitySizeResult",
    "CapitalCostResult",
    "EmploymentCostResult",
    "AnnualExpenseResult",
    "RevenueNPVResult",
    "PurchasePriceResult",
    "UnitEconomicsResult",
    "B2UModelResult",
    "TRANSPORT_PROFILES",
    "run_b2u_scenario",
    "run_b2u_model",
]
