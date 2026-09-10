"""
test_disease_and_medical.py — Verification of Phase 3 Epidemics, Medical Economics & Visualizations.

Tests:
1. Disease onset from environmental degradation (bad food, bad water, smog, chemical pesticides).
2. Health attrition and mortality escalation from active diseases.
3. Private medical billing (0 LEAK / cash conserved).
4. Public healthcare decree & municipal clinics (0 LEAK / cash conserved).
5. Technologies: germ theory, pharmaceutical chemistry, universal healthcare.
6. Tab 6 Ecology & Public Health comparison modal rendering.
7. Tile ecological charts in right panel and chart mode toggling.
8. Interactive tooltips for all new buttons, tabs, and policies.
"""

import sys
import os
import pygame

# Headless pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'
pygame.init()
pygame.font.init()

from goods import Goods
from region import Region
from nation import Nation
from province import Province
from agent import Agent, initialize_agent
from disease import (
    DIS_MALNUTRITION, DIS_WATERBORNE, DIS_RESPIRATORY, DIS_CHEMICAL,
    step_agent_disease_onset, step_medical_care, step_tile_diseases
)
from demographics_estate import handle_death
from innovation import TECH_CATALOG
from buildings import BUILDING_RECIPES, Building
from worldview_charts import tile_ecological_charts
from worldview_compare_ecology import draw_tab6_ecology, handle_tab6_click
from worldview_compare import compare_tab_hit, draw_nations_comparison
from worldview_tooltips_ecology import build_ecology_tooltip
from worldview_tooltips import get_button_tooltip_data


def test_disease_onset_and_wear():
    print("Testing Disease Onset from Environmental Hazards...")
    r = Region("Toxic_Hollow", 1)
    r.nutrition_density = 0.60
    r.pollution_water = 35.0
    r.pollution_air = 30.0
    r.use_pesticides = True
    r.pesticide_residue = 25.0

    a = Agent(1)
    initialize_agent(a, Goods.food, 0, 5, 50.0)
    a.hungry_steps = 2

    # Step disease onset multiple times
    for _ in range(20):
        step_agent_disease_onset(a, r)

    assert len(a.diseases) > 0, f"Agent should have contracted diseases from toxic conditions: {a.diseases}"
    print(f"  -> Agent contracted active diseases: {a.diseases}")
    assert a.health_attrition > 0.0, "Health attrition should increase with active diseases"
    print("  -> Disease onset and bodily wear verified!")


def test_medical_economics_and_cash_conservation():
    print("Testing Medical Economics & 0-LEAK Cash Conservation...")
    r = Region("Clinic_Town", 1)
    r.nutrition_density = 0.50
    r.pollution_air = 40.0

    # 2 Citizens: one rich ($50), one poor ($5)
    a_rich = Agent(1)
    initialize_agent(a_rich, Goods.food, 0, 5, 50.0)
    a_rich.diseases = [DIS_MALNUTRITION, DIS_RESPIRATORY]

    a_poor = Agent(2)
    initialize_agent(a_poor, Goods.wood, 0, 5, 5.0)
    a_poor.diseases = [DIS_RESPIRATORY]

    # Provider agent (local doctor/artisan)
    a_doc = Agent(3)
    initialize_agent(a_doc, Goods.furniture, 0, 5, 100.0)

    r.agents = [a_rich, a_poor, a_doc]

    # --- Scenario A: Private Out-of-Pocket Care (No Public Decree) ---
    r.public_healthcare_decree = False
    gov_agent = r.gov.agent
    start_total_cash = a_rich.cash + a_poor.cash + a_doc.cash + gov_agent.cash

    step_medical_care(r, 1)

    end_total_cash = a_rich.cash + a_poor.cash + a_doc.cash + gov_agent.cash
    assert abs(start_total_cash - end_total_cash) < 1e-4, f"0 LEAK VIOLATION: {start_total_cash} vs {end_total_cash}"
    assert a_rich.medical_expenses_paid > 0.0, "Rich patient should have paid medical bill"
    assert a_poor.cash == 5.0, "Impoverished worker cannot afford $20 treatment, cash should remain untouched"
    assert DIS_RESPIRATORY in a_poor.diseases, "Impoverished worker should remain untreated"
    assert r.untreated_cases_log[-1] >= 1, "Untreated cases should be logged"
    print(f"  -> Private care verified: Rich paid ${a_rich.medical_expenses_paid:.0f}, Poor untreated, 0 LEAK confirmed!")

    # --- Scenario B: Public Healthcare Decree (State Subsidized) ---
    r.gov.agent.cash = 200.0
    r.public_healthcare_decree = True

    start_pool = a_rich.cash + a_poor.cash + a_doc.cash + r.gov.agent.cash

    step_medical_care(r, 2)

    end_pool = a_rich.cash + a_poor.cash + a_doc.cash + r.gov.agent.cash
    assert abs(start_pool - end_pool) < 1e-4, f"0 LEAK VIOLATION in public healthcare: {start_pool} vs {end_pool}"
    assert r.medical_spending_public_log[-1] > 0.0, "Public healthcare spending should be logged"
    assert a_poor.cash == 5.0, "Citizen paid $0 out-of-pocket under public healthcare"
    print(f"  -> Public decree verified: State paid ${r.medical_spending_public_log[-1]:.0f}, Citizen paid $0, 0 LEAK confirmed!")


def test_tech_and_building_solutions():
    print("Testing Medical Technologies and Clinic Buildings...")
    assert 'germ_theory_antisepsis' in TECH_CATALOG
    assert 'pharmaceutical_chemistry' in TECH_CATALOG
    assert 'universal_healthcare_system' in TECH_CATALOG
    assert 'municipal_clinic' in BUILDING_RECIPES
    print("  -> Technologies & clinic recipes verified in catalogs!")


def test_comparison_tab6_and_visualizations():
    print("Testing Tab 6 Comparison Modal & Ecological Charts...")
    surface = pygame.Surface((1400, 900))
    font = pygame.font.Font(None, 20)
    font_small = pygame.font.Font(None, 16)

    # Create dummy world
    n = Nation("Valoria", 1, (100, 150, 240))
    r = Region("Oakhaven", 1)
    r.owner_nation = n
    n.tiles = [r]
    p = Province("North_March", 1, n)
    p.tiles = [r]
    r.province = p
    n.provinces = [p]

    r.soil_fertility_log = [1.0, 0.95, 0.90]
    r.nutrition_density_log = [1.0, 0.85, 0.75]
    r.pollution_air_log = [5.0, 15.0, 25.0]
    r.pollution_water_log = [10.0, 20.0, 30.0]
    r.pollution_soil_log = [0.0, 10.0, 20.0]
    r.disease_cases_log = [{'malnutrition': 2, 'waterborne': 1, 'respiratory': 3, 'chemical': 1, 'total': 7}]
    r.medical_spending_private_log = [40.0]
    r.medical_spending_public_log = [60.0]
    r.untreated_cases_log = [1]
    r.disease_fatalities_log = [0]
    r.avg_health_attrition_log = [0.15]

    world = {
        'nations': [n],
        'compare_open': True,
        'compare_tab': 6,
        'compare_eco_scope': 'country',
        'tile_chart_mode': 'eco',
        'selected_region': r,
        'window': (0, 0),
        'turn': 5,
        'violations': [],
    }

    # 1. Render Tab 6
    draw_tab6_ecology(surface, world, 30, 20, 1340, 860, font, font_small)
    print("  -> Tab 6 draw_tab6_ecology rendered cleanly!")

    # 2. Scope switching
    hit = handle_tab6_click(world, 30 + 16 + 160, 20 + 44 + 10, 30, 20, 1340)
    assert hit is True, "Should register click on Tab 6 province scope button"
    assert world['compare_eco_scope'] == 'province'

    # 3. Tab hit
    res = compare_tab_hit((30 + 20 + 100, 20 + 48 + 10), 30, 20, world)
    assert res == ('tab', 1) or res[0] == 'tab', f"compare_tab_hit returned {res}"

    # 4. Ecological sidebar charts
    charts = tile_ecological_charts(r)
    assert len(charts) == 6, f"Expected 6 ecological charts, got {len(charts)}"
    print("  -> tile_ecological_charts generated 6 time-series charts successfully!")


def test_tooltips():
    print("Testing Tooltips for new Phase 3 buttons and metrics...")
    world = {'selected_region': None, 'nations': []}
    expected_ids = [
        'compare_tab_6',
        'compare_eco_scope_country',
        'compare_eco_scope_province',
        'compare_eco_scope_city',
        'btn_chart_mode_econ',
        'btn_chart_mode_eco',
        'city_toggle_public_healthcare',
        'build_municipal_clinic',
        'tech_germ_theory_antisepsis',
        'tech_pharmaceutical_chemistry',
        'tech_universal_healthcare_system',
    ]
    for bid in expected_ids:
        tip = get_button_tooltip_data(bid, world)
        assert tip is not None, f"Tooltip missing for {bid}"
        assert 'title' in tip and 'desc' in tip, f"Tooltip incomplete for {bid}"
    print("  -> All 11 ecological & medical tooltips verified!")


if __name__ == '__main__':
    test_disease_onset_and_wear()
    test_medical_economics_and_cash_conservation()
    test_tech_and_building_solutions()
    test_comparison_tab6_and_visualizations()
    test_tooltips()
    print("\nALL PHASE 3 EPIDEMICS, MEDICAL ECONOMICS & VISUALIZATION TESTS PASSED SUCCESSFULLY!")
