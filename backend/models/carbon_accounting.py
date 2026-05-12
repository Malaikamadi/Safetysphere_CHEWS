"""
Carbon Accounting Model
========================
Facility-level greenhouse gas inventory estimation.
Estimates CO2e emissions for healthcare facilities, schools, and community buildings.
Supports Scope 1 (direct), Scope 2 (electricity), Scope 3 (supply chain) emissions.
"""

from __future__ import annotations
from typing import NamedTuple


class CarbonResult(NamedTuple):
    total_co2e_kg: float
    scope1_kg: float
    scope2_kg: float
    scope3_kg: float
    intensity_per_sqm: float
    benchmark_comparison: str
    reduction_potential_pct: float
    factors: list[str]
    recommendations: list[str]


# Emission factors (kg CO2e per unit) — adapted for low-resource settings
FUEL_FACTORS = {
    "diesel": 2.68,      # kg CO2e per liter
    "petrol": 2.31,       # kg CO2e per liter
    "lpg": 1.51,          # kg CO2e per liter
    "kerosene": 2.54,     # kg CO2e per liter
    "charcoal": 3.30,     # kg CO2e per kg
    "wood": 1.80,         # kg CO2e per kg (if not sustainable)
}

# Grid electricity emission factors by region (kg CO2e per kWh)
GRID_FACTORS = {
    "sierra_leone": 0.65,
    "west_africa": 0.55,
    "sub_saharan_africa": 0.50,
    "global_average": 0.45,
    "solar_only": 0.05,
}

# Scope 3 multipliers (supply chain as fraction of Scope 1+2)
SUPPLY_CHAIN_MULTIPLIERS = {
    "hospital": 1.8,     # large supply chains
    "health_center": 1.2,
    "clinic": 0.8,
    "school": 0.6,
    "community_center": 0.4,
}

# Benchmarks (kg CO2e per sqm per year)
BENCHMARKS = {
    "hospital": {"good": 80, "average": 150, "poor": 250},
    "health_center": {"good": 40, "average": 80, "poor": 140},
    "clinic": {"good": 25, "average": 50, "poor": 90},
    "school": {"good": 20, "average": 45, "poor": 80},
}


def predict(
    facility_type="health_center",
    floor_area_sqm=200.0,
    diesel_liters_month=0.0,
    petrol_liters_month=0.0,
    lpg_liters_month=0.0,
    kerosene_liters_month=0.0,
    charcoal_kg_month=0.0,
    wood_kg_month=0.0,
    electricity_kwh_month=0.0,
    grid_region="sierra_leone",
    has_solar=False,
    solar_kwh_month=0.0,
    generator_hours_month=0.0,
    generator_fuel="diesel",
    generator_consumption_lph=3.0,
) -> CarbonResult:
    """Estimate monthly CO2e emissions for a facility."""
    # --- Scope 1: Direct emissions (fuel combustion) ---
    scope1 = (
        diesel_liters_month * FUEL_FACTORS["diesel"] +
        petrol_liters_month * FUEL_FACTORS["petrol"] +
        lpg_liters_month * FUEL_FACTORS["lpg"] +
        kerosene_liters_month * FUEL_FACTORS["kerosene"] +
        charcoal_kg_month * FUEL_FACTORS["charcoal"] +
        wood_kg_month * FUEL_FACTORS["wood"]
    )
    # Generator emissions
    gen_fuel_liters = generator_hours_month * generator_consumption_lph
    scope1 += gen_fuel_liters * FUEL_FACTORS.get(generator_fuel, FUEL_FACTORS["diesel"])

    # --- Scope 2: Indirect (electricity) ---
    grid_factor = GRID_FACTORS.get(grid_region, GRID_FACTORS["global_average"])
    scope2 = electricity_kwh_month * grid_factor
    if has_solar:
        scope2 -= solar_kwh_month * (grid_factor - GRID_FACTORS["solar_only"])
        scope2 = max(0, scope2)

    # --- Scope 3: Supply chain estimate ---
    multiplier = SUPPLY_CHAIN_MULTIPLIERS.get(facility_type, 0.8)
    scope3 = (scope1 + scope2) * multiplier * 0.3

    total = scope1 + scope2 + scope3
    intensity = total / max(floor_area_sqm, 1)

    # Benchmark comparison
    bench = BENCHMARKS.get(facility_type, BENCHMARKS["health_center"])
    annual_intensity = intensity * 12
    if annual_intensity <= bench["good"]: comparison = "Below average — good performance"
    elif annual_intensity <= bench["average"]: comparison = "Average for facility type"
    else: comparison = "Above average — reduction recommended"

    # Reduction potential
    reduction = 0.0
    factors = []
    recs = []

    if generator_hours_month > 100:
        reduction += 20
        factors.append(f"Heavy generator use ({generator_hours_month:.0f} hrs/month) — major emission source")
        recs.append("Invest in solar+battery to reduce generator dependence")
    if charcoal_kg_month > 50:
        reduction += 15
        factors.append(f"Charcoal use ({charcoal_kg_month:.0f} kg/month) — high-emission fuel")
        recs.append("Transition from charcoal to LPG or improved cookstoves")
    if not has_solar and electricity_kwh_month > 200:
        reduction += 25
        recs.append("Install solar panels to offset grid electricity emissions")
    if kerosene_liters_month > 20:
        reduction += 10
        recs.append("Replace kerosene lighting with solar lanterns")
    if not factors:
        factors = ["Emissions are within acceptable ranges for facility type"]
    if not recs:
        recs = ["Continue current practices", "Monitor energy consumption monthly"]

    return CarbonResult(
        total_co2e_kg=round(total, 1),
        scope1_kg=round(scope1, 1),
        scope2_kg=round(scope2, 1),
        scope3_kg=round(scope3, 1),
        intensity_per_sqm=round(intensity, 2),
        benchmark_comparison=comparison,
        reduction_potential_pct=min(60, round(reduction, 1)),
        factors=factors,
        recommendations=recs,
    )
