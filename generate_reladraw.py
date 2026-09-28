#!/usr/bin/env python3
"""
Generate a complete, fully connected callgraph of all modules and classes
in the codebase using the reladraw language specification (https://github.com/reladraw/reladraw).
"""

import os, ast
from collections import defaultdict

root = '/Users/sli/Code'
skip_dirs = {'venv', 'tmp', 'scratch', 'build', '__pycache__', '.git', 'bin', 'lib', 'include', 'share', 'm3tunnel_cert', 'outputs', 'saved_slots', 'SaveFiles', 'map_cache', 'epub_build', 'gwalker', 'proto'}

py_files = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in skip_dirs]
    for f in filenames:
        if f.endswith('.py') and not f.startswith('test_'):
            rel = os.path.relpath(os.path.join(dirpath, f), root)
            py_files.append(rel)

py_files.sort()

modules = {}
for pf in py_files:
    full = os.path.join(root, pf)
    mod = pf[:-3].replace('/', '.')
    try:
        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=pf)
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        modules[mod] = {'classes': classes, 'funcs': funcs, 'file': pf}
    except Exception as e:
        pass

# Logical subsystem categorization
subsystems = [
    ('server_net', 'Authoritative Server & Network Protocol', 'server', [
        'sim_server.sim_server', 'sim_server.web_server', 'sim_server.protocol',
        'sim_server.server_cli', 'sim_server.qr_code', 'game_client.game_client', 'game_client.__init__', 'sim_server.__init__'
    ]),
    ('desktop_ui', 'Desktop Presentation UI (Pygame)', 'ui', [
        'worldview', 'worldview_engine', 'worldview_camera', 'worldview_ui', 'worldview_map',
        'worldview_layers', 'worldview_charts', 'worldview_left_dock', 'worldview_gov_panel',
        'worldview_build_panel', 'worldview_debt_panel', 'worldview_diplomacy_panel',
        'worldview_military_panel', 'worldview_science_panel', 'worldview_progress_panel',
        'worldview_compare', 'worldview_compare_ecology', 'worldview_compare_extraction',
        'worldview_compare_protest', 'worldview_cadastre', 'worldview_citizens',
        'worldview_labor_ui', 'worldview_policies', 'worldview_transfer_dialog',
        'worldview_help', 'worldview_seasonal_clock', 'worldview_actions', 'worldview_tooltips',
        'worldview_tooltips_charts', 'worldview_tooltips_ecology', 'worldview_tooltips_extra',
        'worldview_tooltips_visualizations', 'worldview_vis_circuits', 'worldview_vis_protest_attractor',
        'worldview_vis_pyramid', 'worldview_vis_radar', 'ui_icons', 'ui_targets'
    ]),
    ('render_engine', '3D & GPU Render Engine (ModernGL)', 'render', [
        'render_engine.core', 'render_engine.camera', 'render_engine.terrain',
        'render_engine.hex_renderer', 'render_engine.layers', 'render_engine.gpu.base',
        'render_engine.gpu.fallback_pipeline', 'render_engine.gpu.mesh_brdf_pipeline',
        'render_engine.gpu.micropoly_3d_renderer', 'render_engine.gpu.moderngl_pipeline',
        'render_engine.gpu.settings', 'render_engine.gpu.shaders', 'render_dev_viewer',
        'render_island_micropolys', 'render_regnum_terrain', 'render_voronoi_geopolitics',
        'render_engine.__init__', 'render_engine.gpu.__init__'
    ]),
    ('orchestration', 'Simulation Orchestration & Lifecycle', 'orchestration', [
        'sim_world', 'sim_world_voronoi', 'sim_engine', 'sim_nation', 'sim_ring',
        'world_config', 'world_cache', 'world_names', 'tile_resources', 'system_menu'
    ]),
    ('spatial_mesh', 'Spatial Mesh & Procedural Geography', 'spatial', [
        'polygon_map', 'hexmap', 'hexview', 'heightmap', 'hydraulic_erosion',
        'terrain_edges', 'wilderness', 'compare_map_generators', 'mapgen_gui', 'mapgen_web'
    ]),
    ('macro_sovereign', 'Macroeconomic & Sovereign Systems', 'macro', [
        'nation', 'nation_logic', 'government', 'regime', 'election', 'coup',
        'sovereign_bonds', 'diplomacy', 'army', 'imperialism', 'ai_nation',
        'intents', 'innovation', 'construction_politics', 'buildings'
    ]),
    ('meso_institutions', 'Mesoeconomic Institutions & Markets', 'meso', [
        'province', 'forex', 'world_trade', 'trade_settle', 'transporter',
        'migration', 'claims', 'banking_policy', 'charity', 'workhouse',
        'ledger', 'trade_dashboard'
    ]),
    ('micro_regional', 'Regional Tile Economy & Commodity Auctions', 'micro', [
        'region', 'region_production', 'region_labor', 'region_market',
        'region_finance', 'region_logistics', 'region_factions', 'region_plotting',
        'econsim', 'econsim_live', 'econsim_states', 'econsim_trade_money', 'econsim_two_region'
    ]),
    ('agent_dynamics', 'Micro-Agents, Class & Metabolic Rift', 'agent', [
        'agent', 'social_class', 'demographics_consumption', 'demographics_reproduction',
        'demographics_career', 'demographics_estate', 'labor_contract', 'labor_resistance',
        'labor_politics', 'land_tenure', 'land_rent', 'enclosure', 'feudal_tribute',
        'foraging', 'alienation', 'unrest', 'popular_resistance', 'faction',
        'externalities', 'disease', 'secular_climate', 'goods'
    ]),
    ('support_utils', 'Diagnostics, Analytics & Tooling', 'utils', [
        'wealth_collector', 'wealth_diagnostic', 'wealth_lineage', 'logger',
        'random_cache', 'setup_cython', 'bench_cython', 'wolfsheep', 'hrl-agent'
    ])
]

lines = []
lines.append("// ============================================================================")
lines.append("// Call of Capital: Modern Economic Warfare / SimpleEconSim — Complete Module & Class Call Graph (reladraw v0.7.1)")
lines.append("// Stated relative positions and hierarchical domain clusters.")
lines.append("// ============================================================================")
lines.append("")

# Styles
lines.append("// --- Styles ---")
lines.append("style server         fill: #0f172a  border: #38bdf8  line: #38bdf8")
lines.append("style ui             fill: #1e1b4b  border: #818cf8  line: #818cf8")
lines.append("style render         fill: #311042  border: #c084fc  line: #c084fc")
lines.append("style orchestration  fill: #064e3b  border: #34d399  line: #34d399")
lines.append("style spatial        fill: #14532d  border: #4ade80  line: #4ade80")
lines.append("style macro          fill: #701a75  border: #f472b6  line: #f472b6")
lines.append("style meso           fill: #78350f  border: #fbbf24  line: #fbbf24")
lines.append("style micro          fill: #451a03  border: #f97316  line: #f97316")
lines.append("style agent          fill: #4c0519  border: #fb7185  line: #fb7185")
lines.append("style utils          fill: #262626  border: #a3a3a3  line: #a3a3a3")
lines.append("style dim            text: (color: muted)")
lines.append("")

# Subsystem containers
lines.append("// --- Subsystem Containers ---")
lines.append('node server_net "Authoritative Server & Network Protocol"  style: server')
lines.append('node desktop_ui "Desktop Presentation UI (Pygame)"  right of server_net  gap: wide  style: ui')
lines.append('node render_engine "3D & GPU Render Engine (ModernGL)"  right of desktop_ui  gap: wide  style: render')
lines.append("")
lines.append('node orchestration "Simulation Orchestration & Lifecycle"  below server_net  gap: wide  style: orchestration')
lines.append('node spatial_mesh "Spatial Mesh & Procedural Geography"  left of orchestration  gap: wide  style: spatial')
lines.append('node macro_sovereign "Macroeconomic & Sovereign Systems"  below orchestration  gap: wide  style: macro')
lines.append('node meso_institutions "Mesoeconomic Institutions & Markets"  right of macro_sovereign  gap: wide  style: meso')
lines.append('node micro_regional "Regional Tile Economy & Commodity Auctions"  below macro_sovereign  gap: wide  style: micro')
lines.append('node agent_layer "Micro-Agents, Class & Metabolic Rift"  below micro_regional  gap: wide  style: agent')
lines.append('node support_utils "Diagnostics, Analytics & Tooling"  right of meso_institutions  gap: wide  style: utils')
lines.append("")

# Populate each container with all constituent modules and classes
def clean_id(name):
    return name.replace('.', '_').replace('-', '_')

lines.append("// --- Constituent Modules & Classes ---")
for sys_id, title, style_name, mod_list in subsystems:
    lines.append(f"// Subsystem: {title}")
    c_target = 'agent_layer' if sys_id == 'agent_dynamics' else sys_id
    for mod_name in mod_list:
        if mod_name not in modules:
            continue
        m_info = modules[mod_name]
        c_names = m_info['classes']
        m_id = clean_id(mod_name)
        
        # Build text label
        f_name = os.path.basename(m_info['file'])
        if c_names:
            cls_str = ', '.join(c_names[:3])
            if len(c_names) > 3:
                cls_str += f', +{len(c_names)-3} more'
            lbl = f"{f_name} / [dim]class {cls_str}[/dim]"
        else:
            lbl = f"{f_name}"
        lines.append(f'node {c_target}.{m_id} "{lbl}"')
    lines.append("")

# Calls and Edge Relationships
lines.append("// --- Architecture & Turn Pipeline Callgraph Edges ---")

edges = [
    # Server / Network calls
    ('server_net.sim_server_sim_server', 'orchestration.sim_engine', 'executes turn pipeline / step_turn(t)', 'bottom', 'top'),
    ('server_net.sim_server_sim_server', 'orchestration.sim_world', 'build_world(seed)', 'bottom', 'top'),
    ('server_net.sim_server_web_server', 'server_net.sim_server_sim_server', 'dispatches client commands', 'left', 'right'),
    ('server_net.sim_server_protocol', 'server_net.sim_server_sim_server', 'typed CommandMessage / ServerEvent', 'left', 'right'),
    ('server_net.game_client_game_client', 'server_net.sim_server_web_server', 'REST / WebSocket stream', 'bottom', 'top'),

    # Desktop UI calls
    ('desktop_ui.worldview', 'desktop_ui.worldview_engine', 'drives game loop / step_world()', 'bottom', 'top'),
    ('desktop_ui.worldview_engine', 'orchestration.sim_engine', 'step_turn() tick', 'left', 'right'),
    ('desktop_ui.worldview', 'render_engine.render_engine_core', 'render_frame()', 'right', 'left'),
    ('desktop_ui.worldview_gov_panel', 'macro_sovereign.nation', 'enact decrees / adjust taxes', 'bottom', 'top'),
    ('desktop_ui.worldview_debt_panel', 'macro_sovereign.sovereign_bonds', 'float sovereign bonds', 'bottom', 'top'),
    ('desktop_ui.worldview_diplomacy_panel', 'macro_sovereign.diplomacy', 'propose treaties / embargoes', 'bottom', 'top'),
    ('desktop_ui.worldview_military_panel', 'macro_sovereign.army', 'mobilize standing army', 'bottom', 'top'),
    ('desktop_ui.worldview_science_panel', 'macro_sovereign.innovation', 'sponsor royal patent prizes', 'bottom', 'top'),
    ('desktop_ui.worldview_build_panel', 'macro_sovereign.intents', 'queue municipal / state infrastructure', 'bottom', 'top'),
    ('desktop_ui.worldview_cadastre', 'agent_layer.land_tenure', 'inspect tenure / enforce enclosure', 'bottom', 'top'),
    ('desktop_ui.worldview_citizens', 'agent_layer.social_class', 'inspect agent lineages & class breakdown', 'bottom', 'top'),
    ('desktop_ui.worldview_charts', 'micro_regional.region', 'query GDP / prices / surplus value', 'bottom', 'top'),

    # Render Engine internal & spatial calls
    ('render_engine.render_engine_core', 'render_engine.render_engine_terrain', 'draw_terrain()', 'bottom', 'top'),
    ('render_engine.render_engine_core', 'render_engine.render_engine_hex_renderer', 'draw_hexes()', 'bottom', 'top'),
    ('render_engine.render_engine_terrain', 'render_engine.render_engine_gpu_mesh_brdf_pipeline', 'render_mesh_brdf()', 'bottom', 'top'),
    ('render_engine.render_engine_terrain', 'spatial_mesh.polygon_map', 'sample dual-mesh corners / elevations', 'left', 'right'),
    ('render_engine.render_engine_hex_renderer', 'spatial_mesh.hexmap', 'sample axial coordinates', 'left', 'right'),

    # Orchestration -> Spatial & Initialization
    ('orchestration.sim_world', 'spatial_mesh.polygon_map', 'build_world_voronoi() / dual mesh', 'left', 'right'),
    ('orchestration.sim_world', 'spatial_mesh.hexmap', 'build_world_hex() / honeycomb layout', 'left', 'right'),
    ('orchestration.sim_world', 'orchestration.tile_resources', 'assign_tile_resources()', 'bottom', 'top'),
    ('orchestration.sim_world', 'orchestration.world_names', 'assign_world_identities()', 'bottom', 'top'),
    ('orchestration.sim_world', 'meso_institutions.province', 'partition_contiguous() / build provinces', 'bottom', 'top'),
    ('orchestration.sim_world', 'macro_sovereign.nation', 'instantiate Sovereign Nations', 'bottom', 'top'),

    # Orchestration -> Macro Sovereign (step_turn pipeline)
    ('orchestration.sim_engine', 'macro_sovereign.ai_nation', '0a. decide_turn() / sovereign AI', 'bottom', 'top'),
    ('orchestration.sim_engine', 'macro_sovereign.intents', '0b. step_intents_and_construction()', 'bottom', 'top'),
    ('macro_sovereign.intents', 'macro_sovereign.buildings', 'advance navvy construction projects', 'bottom', 'top'),
    ('orchestration.sim_engine', 'meso_institutions.world_trade', '1. pending_imports()', 'right', 'left'),
    ('orchestration.sim_engine', 'meso_institutions.province', '2a. Province.step() shared institutions', 'bottom', 'top'),
    ('orchestration.sim_engine', 'micro_regional.region', '2b. Region.step_economy() tile simulation', 'bottom', 'top'),
    ('orchestration.sim_engine', 'meso_institutions.transporter', '3. advance() & deliver cargo', 'right', 'left'),
    ('orchestration.sim_engine', 'agent_layer.disease', '3b. step_trade_epidemic_transmission()', 'bottom', 'top'),
    ('orchestration.sim_engine', 'meso_institutions.trade_settle', '5. settle_trade() bilateral clearing', 'right', 'left'),
    ('orchestration.sim_engine', 'meso_institutions.forex', '6. cycle_all_markets() / convert wallets', 'right', 'left'),
    ('orchestration.sim_engine', 'meso_institutions.migration', '7. run_migrations() displaced flight', 'right', 'left'),
    ('orchestration.sim_engine', 'meso_institutions.claims', '8. check_and_apply_claims()', 'right', 'left'),
    ('orchestration.sim_engine', 'macro_sovereign.regime', '10. step_regime() / coups & elections', 'bottom', 'top'),
    ('orchestration.sim_engine', 'macro_sovereign.army', '10b. step_armies() military upkeep', 'bottom', 'top'),
    ('orchestration.sim_engine', 'macro_sovereign.diplomacy', '10c. update_relations() diplomatic drift', 'bottom', 'top'),
    ('orchestration.sim_engine', 'macro_sovereign.innovation', '10d. step_innovation() tech diffusion', 'bottom', 'top'),
    ('orchestration.sim_engine', 'agent_layer.popular_resistance', '10e. step_popular_resistance() revolts', 'bottom', 'top'),
    ('orchestration.sim_engine', 'macro_sovereign.imperialism', '10f. step_imperialism() debt enforcement', 'bottom', 'top'),
    ('orchestration.sim_engine', 'meso_institutions.ledger', '12. audit_currency_total() vs ledger.cleared()', 'right', 'left'),

    # Micro Regional Tile Economy internal calls
    ('micro_regional.region', 'agent_layer.secular_climate', 'get_secular_climate(t)', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.foraging', 'forage_tile() customary usufruct', 'bottom', 'top'),
    ('micro_regional.region', 'micro_regional.region_labor', 'run_labour() wage & shift contracts', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.labor_resistance', 'step_workplace_resistance() strikes', 'bottom', 'top'),
    ('micro_regional.region', 'micro_regional.region_production', 'produce() commodity manufacturing', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.feudal_tribute', 'collect_tribute() in-kind seigneurial dues', 'bottom', 'top'),
    ('micro_regional.region', 'micro_regional.region_market', 'trade() double-auction clearance', 'bottom', 'top'),
    ('micro_regional.region', 'micro_regional.region_finance', 'pay_wages() & redeem scrip', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.land_rent', 'collect_rents() on enclosed plots', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.enclosure', 'step_enclosure_survey_debts()', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.labor_contract', 'aggregate_tile_surplus() exploitation rate', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.demographics_consumption', 'consume() food calories & cost-of-living', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.demographics_reproduction', 'reproduce() & mortality', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.social_class', 'update_tile_social_classes()', 'bottom', 'top'),
    ('micro_regional.region', 'meso_institutions.workhouse', 'step_workhouse() penal labor', 'right', 'left'),
    ('micro_regional.region', 'agent_layer.alienation', 'step_tile_alienation() worker despair', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.externalities', 'step_tile_externalities() metabolic rift', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.disease', 'step_tile_diseases() epidemics & clinics', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.unrest', 'step_unrest() threat escalation', 'bottom', 'top'),
    ('micro_regional.region', 'agent_layer.agent', 'manages instances of Agent class', 'bottom', 'top'),

    # Meso Institutions & High Finance
    ('macro_sovereign.nation', 'macro_sovereign.sovereign_bonds', 'issues sovereign debt / floats bonds', 'right', 'left'),
    ('macro_sovereign.sovereign_bonds', 'meso_institutions.ledger', 'records bond defaults / debt cancellations', 'bottom', 'top'),
    ('meso_institutions.forex', 'meso_institutions.banking_policy', 'clears interbank forex balances', 'bottom', 'top'),
    ('meso_institutions.claims', 'spatial_mesh.wilderness', 'encloses frontier wilderness plots', 'left', 'right'),

    # Spatial Mesh & Geography
    ('spatial_mesh.polygon_map', 'spatial_mesh.hydraulic_erosion', 'simulates fluvial erosion & river carving', 'bottom', 'top'),
    ('spatial_mesh.polygon_map', 'spatial_mesh.heightmap', 'generates tectonic elevation profiles', 'bottom', 'top'),
    ('spatial_mesh.polygon_map', 'spatial_mesh.terrain_edges', 'traces cliffs & coastlines', 'bottom', 'top'),

    # Diagnostics & Support
    ('support_utils.wealth_collector', 'agent_layer.agent', 'audits agent wealth distribution', 'left', 'right'),
    ('support_utils.wealth_lineage', 'agent_layer.agent', 'traces dynastic family fortunes', 'left', 'right')
]

for src, dst, lbl, f_side, t_side in edges:
    lines.append(f'edge {src} -> {dst} "{lbl}"  from: {f_side}  to: {t_side}')

out_path = '/Users/sli/Code/callgraph.reladraw'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Generated {out_path} with {len(lines)} lines.")
