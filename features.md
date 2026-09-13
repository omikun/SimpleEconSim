# REGNUM Desktop Client Feature Inventory & Web Client Parity Matrix

This document enumerates all buttons, graphs, tables, tabs, and interactive dialogs present in the native desktop client (`worldview.py`, `worldview_ui.py`, `worldview_compare.py`, `worldview_gov_panel.py`, `worldview_build_panel.py`, `worldview_debt_panel.py`, `worldview_diplomacy_panel.py`, `worldview_science_panel.py`, `worldview_military_panel.py`, `worldview_cadastre.py`, `worldview_citizens.py`, `worldview_labor_ui.py`, `worldview_transfer_dialog.py`, `worldview_help.py`, `worldview_layers.py`, and `worldview_charts.py`).

Each item is categorized as:
- `[x]` **Implemented in Web Client**
- `[ ]` **Pending Implementation in Web Client**

---

## 1. Top Bar & Viewport Controls

### A. Simulation & Sovereign Header Buttons
1. `[x]` **Play / Pause Toggle Button (`▶ / ⏸`)**: Toggles real-time simulation turn loop.
2. `[x]` **Step Turn Button (`⏭`)**: Advances simulation exactly one turn.
3. `[x]` **Turn Counter Badge**: Displays current simulation turn.
4. `[x]` **Sovereign Switcher Dropdown**: Allows assuming control of any sovereign nation in the world.
5. `[x]` **Treasury Cash Display (`£`)**: Current sovereign treasury balance.
6. `[x]` **Treasury Grain Display (`🌾`)**: National strategic food reserve.
7. `[x]` **Population & Delta Display (`+Δ`)**: Total population with turn-over-turn net growth.
8. `[x]` **Real GDP Display (`£`)**: Aggregate national output.
9. `[x]` **Civil Unrest Badge**: Color-coded threat stage (`Calm`, `Agitation`, `Riot`, `Insurrection`, `Takeover`).
10. `[x]` **Gini Index Display**: Inequality coefficient across living citizens.
11. `[x]` **Trade Balance Display**: Net export/import surplus or deficit.
12. `[x]` **Cost of Living (CoL) Display**: Average consumer goods basket price.
13. `[ ]` **ISRB Benchmark Bond Yield Badge**: National sovereign credit rating and benchmark yield in the top bar.

### B. Viewport & Command Action Buttons
14. `[x]` **Help Modal Button (`[?] Help (H)`)**: Opens multi-page guide.
15. `[x]` **Compare Nations Button (`Compare (C)`)**: Opens economic accounts comparison suite.
16. `[ ]` **Diplomacy Button (`Diplomacy (D)`)**: Top-bar direct trigger to open diplomacy modal/drawer.
17. `[ ]` **Military Button (`Military (M)`)**: Top-bar direct trigger to open military modal/drawer.
18. `[ ]` **Pipeline Toggle Button (`Pipeline: GPU / CPU [U]`)**: Switches between continuous photorealistic terrain and flat vector biome rendering.
19. `[x]` **Zoom In Button (`+`)**: Magnifies hex viewport.
20. `[x]` **Zoom Out Button (`-`)**: Demagnifies hex viewport.
21. `[x]` **Zoom Reset Button (`R`)**: Recenters camera and fits world to viewport.
22. `[x]` **Mobile LAN QR Button (`📱`)**: Shows QR code modal for mobile access.

---

## 2. The 9 Thematic Map Layers (Drop-Up Selector & Keys 1–9)

23. `[x]` **Layer 1: Overview**: Topographic base terrain, settlements, borders, road trade arrows.
24. `[x]` **Layer 2: Physical & Height**: Topographic elevation gradient and biome labels.
25. `[x]` **Layer 3: Population & Unrest**: Demographic density and civil unrest threat heat.
26. `[x]` **Layer 4: Economy & Wealth**: Regional GDP, local market basket price, and bank deposits.
27. `[x]` **Layer 5: Production & Output**: Commodity output volume and factories.
28. `[x]` **Layer 6: Military & Defense**: Garrisons, combat strength, and fortresses.
29. `[x]` **Layer 7: Land Tenure (Enclosure)**: Customary commons vs enclosed private plots.
30. `[x]` **Layer 8: Exploitation & Strikes**: Surplus value rate (s/v) and active wildcat strikes.
31. `[x]` **Layer 9: Ecology & Rift**: Metabolic rift, soil fertility, smog, and toxic runoff.

---

## 3. Left Sovereign Dock Suites (6 Drawers)

### A. Unified Left Dock & Drawer Navigation
32. `[x]` **Dock Button Strip**: 6 vertical drawer toggle buttons (`🔨`, `🏛️`, `🤝`, `📜`, `🔬`, `⚔️`).
33. `[ ]` **Drawer Top Switcher Bar**: 6-tab icon switcher rendered across the top of any open drawer.
34. `[x]` **Drawer Close Button (`×`)**: Collapses open drawer.

### B. Suite 1: 🔨 Build Menu (`B`)
35. `[ ]` **Category Switcher: `[ Industry & Roads ]` vs `[ Ecology & Sanitation ]`**: Segmented category switcher.
36. `[x]` **Tier 1: Municipal Construction Recipes**: Granary, Textile Mill, Brickworks, Iron Smelter, Toolmaker, Furniture Workshop, Brewery, Bakery, Glassworks, Distillery, Paper Mill, Printing Press, Steam Pump, Locomotive Works.
37. `[ ]` **Tier 2: Provincial Infrastructure Recipes**: Paved Road, Canal, Highway.
38. `[ ]` **Tier 3: Sovereign National Recipes**: Railroad, Telegraph, Fortress, Naval Dockyard, Academy, Bank Headquarters.
39. `[ ]` **Ecology & Sanitation Recipes**: Night Soil Depot, Sewer System, Infirmary, Water Filtration, Sanitarium, Waste Incinerator.
40. `[ ]` **Live Progress Bar Gauges**: Buttons morph into visual turn-completion gauges for active construction projects.
41. `[ ]` **Fiscal Transfer & Shortfall Trigger**: Prompting funding dialog if local treasury has insufficient cash.

### C. Suite 2: 🏛️ Governance & Decrees (`G`)
42. `[ ]` **Scope Switcher: `[ City / Tile ]` vs `[ Province ]` vs `[ Nation ]` vs `[ Frontier ]`**: 4-tier governance switcher.
43. `[ ]` **Frontier: Sponsor Settlers ($100)**: Expeditions into wilderness.
44. `[ ]` **Frontier: Send Pioneer Aid ($40)**: Food subsidies to frontier settlers.
45. `[ ]` **City: Tax Adjusters (`[-2% Tax]`, `[+2% Tax]`)**: Fine-grained municipal tax tuning.
46. `[ ]` **City: Enact / Active UBI Decree**: 10-turn universal basic income mandate.
47. `[x]` **City: Disburse Food Relief ($50)**: Emergency granary grain distribution.
48. `[ ]` **City: Subsidize Farming ($100)**: Grants to agrarian producers.
49. `[ ]` **City: Deploy Safety Patrol ($60)**: Civic patrol reducing crime and minor unrest.
50. `[x]` **City: Enforce Police Curfew**: Emergency garrison curfew deployed during insurrections.
51. `[ ]` **City: Enclose Feudal Plot ($fee)**: Direct enclosure charter decree on selected tile.
52. `[ ]` **City: Chemical Agronomy Toggles (`Fertilizer: ON/OFF`, `Pesticides: ON/OFF`)**: Regulate modern inputs.
53. `[ ]` **Province: Pave Regional Highway ($120)**: Provincial logistics upgrade.
54. `[ ]` **Province: Regional Health Initiative ($150)**: Provincial public health campaign.
55. `[ ]` **Province: Provincial Equalization ($200)**: Inter-municipal fiscal rebalancing.
56. `[ ]` **Province: Standardize Routes ($100)**: Harmonize trade routes.
57. `[ ]` **Province: Harmonize Taxes (Uniform)**: Standardize tax rates across constituent cities.
58. `[ ]` **Province: Fund Soil Conservation ($150)**: Anti-erosion public works.
59. `[ ]` **Nation: Fund Science Prize ($300)**: Royal discovery incentive bounty.
60. `[ ]` **Nation: Mobilize Standing Army ($250)**: National military mobilization.
61. `[ ]` **Nation: Sovereign Equalization Grant ($250)**: National fiscal transfer to impoverished provinces.
62. `[ ]` **Nation: Statutory Income Tax Buttons (`10%`, `15%`, `25%`, `35%`)**: Quick rate presets.
63. `[ ]` **Nation: Customs Tariff Buttons (`0%`, `5%`, `10%`, `15%`)**: Protectionist tariff presets.
64. `[ ]` **Nation: Empire UBI Decree**: National-level basic income mandate.
65. `[ ]` **Nation: Open / Closed Borders Toggle**: Regulate foreign migration inflows.
66. `[ ]` **Nation: Statutory Workday Hours (`[-2h]`, `[+2h]`)**: Legal shift cap controls.
67. `[ ]` **Nation: Factory Safety Act**: Workplace health and machinery guards mandate.
68. `[x]` **Nation: Ten-Hour Act**: Statutory 10-hour labor ceiling.
69. `[ ]` **Nation: Truck Act**: Statutory ban on company scrip and truck store wages.

### D. Suite 3: 🤝 Diplomacy & Treaties (`D`)
70. `[ ]` **Target Foreign Nation Switcher Tabs**: Select which foreign power to negotiate with.
71. `[x]` **Bilateral Relation Meter**: Score from -100 to +100.
72. `[x]` **Active Treaties Status Indicators**: Trade Pact, Non-Aggression Pact, Defensive Alliance, At War.
73. `[x]` **Propose / Cancel Trade Pact**: Bilateral commercial agreement.
74. `[x]` **Propose / Cancel Non-Aggression Pact**: Mutual non-aggression agreement.
75. `[x]` **Form / Break Defensive Alliance**: Mutual defense covenant.
76. `[x]` **Declare War / Sign Peace Treaty**: Sovereign military declarations.
77. `[ ]` **Send Foreign Aid Gift ($100)**: +0.15 relations improvement dispatch.
78. `[ ]` **Diplomatic Incident & Betrayal Memory Table**: History of treaties signed, broken, and casus belli.

### E. Suite 4: 📜 Sovereign Debt & ISRB (`S`)
79. `[ ]` **Scope Switcher: `[ Domestic & ISRB ]` vs `[ Foreign Reserves & Bonds ]`**: Debt desk modes.
80. `[x]` **ISRB Credit Rating Badge (`AAA` to `D`) & Benchmark Yield**: Real-time credit assessment.
81. `[ ]` **ISRB Board Member Status & Rating Modifiers**: Institutional breakdown of sovereign rating.
82. `[ ]` **Lobby Upgrade ($200)**: Direct rating lobbying campaign.
83. `[ ]` **Audit Rival ($350)**: Request ISRB downgrading audit of a geopolitical rival.
84. `[ ]` **Board Seat ($600)**: Acquire permanent seat on the International Sovereign Rating Board.
85. `[x]` **Maturity Term Selector (`20t`, `50t`, `100t`)**: Configure bond duration.
86. `[ ]` **Tranche Preset Buttons (`$500`, `$1,000`)**: Standardized offering tranches.
87. `[x]` **Announce Bond Offering Action**: Authoritative debt issuance.
88. `[x]` **Outstanding Debt & Coupon Servicing Card**: Active debt burden and servicing costs.
89. `[ ]` **Foreign Sovereign Bond Portfolio Table**: Holdings of foreign sovereign paper and coupon dividends.
90. `[ ]` **Purchase Foreign Bond Tranche Buttons**: Acquire foreign reserves.

### F. Suite 5: 🔬 Science & Tech Tree (`T`)
91. `[ ]` **Strategic Resource Endowments Ribbon**: Displays national deposits (Iron, Coal, Timber, Petroleum, Rare Minerals).
92. `[ ]` **Era Selector: `Era I: Feudal`, `Era II: Renaissance`, `Era III: Industrial`, `Era IV: Modern`**: Filter technologies by epoch.
93. `[x]` **Technological Discovery Catalog**: Complete technology tree.
94. `[x]` **Tech Status Badges**: `MASTERED`, `DIFFUSING`, `ROYAL PRIZE ACTIVE`, `BLOCKED`, `PRESSURE`.
95. `[x]` **Pledge Royal Science Prize ($300)**: Direct bounty allocation for breakthroughs.

### G. Suite 6: ⚔️ Military Operations (`M`)
96. `[ ]` **Defense Readiness & Army Upkeep Card**: Total national soldiers and per-turn maintenance cost.
97. `[x]` **Stationed Tile Garrison Readout**: Local defending garrison size.
98. `[ ]` **Standing Armies Roster Table**: Regiment ID, Commander, Soldiers count, Morale, Equipment, Veteran XP, Combat Power.
99. `[x]` **Recruit Garrison Division (15 soldiers, $15)**: Municipal defensive recruitment.
100. `[ ]` **Mobilize Expeditionary Corps ($250)**: Raise field army corps.

---

## 4. Right Inspection & Analytics Panel

### A. Fiscal & Government Card
101. `[x]` **Municipal Treasury & Bank Deposits**: Combined liquid funds on selected tile.
102. `[x]` **Government Debt & Net Cashflow (`+£/t` / `-£/t`)**: Fiscal burn rate.
103. `[x]` **Active Construction Project Gauge**: Recipe name, progress turns, and percentage bar.
104. `[x]` **Ecological Vitality Readout**: Soil fertility %, nutrition density %, smog particulate index.

### B. Right Panel Main Tabs
105. `[x]` **Tab 1: 📊 Charts**: Time-series charting suite.
106. `[x]` **Tab 2: 🗺️ Cadastre**: Land tenure and parcel deed registry.
107. `[x]` **Tab 3: 👥 Citizens**: Social classes and resident census.
108. `[ ]` **Tab 4: ⚖️ Policies**: In-dock right sidebar governance controls matching `worldview_policies.py`.
109. `[x]` **Tab 5: 🏥 Workhouse**: Pauper registry and relief capacity.
110. `[x]` **Tab 6: 📰 Chronicle / News**: Historical event ticker.
111. `[ ]` **Conserved Audit Footer**: Real-time monetary and physical conservation validator (`Conserved: 0 LEAK / 0 SHIFT`).

### C. Right Panel Graphs (10 Economic + 6 Ecological + 4 Labor = 20 Charts)
112. `[ ]` **Chart Mode Switcher: `[ Economic Charts ]` vs `[ Ecological & Epidemic Charts ]`**: Segmented switcher.
113. `[x]` **Graph 1: Prices**: Food, Wood, Furniture price logs.
114. `[x]` **Graph 2: Pop / Hunger**: Total population vs starving citizens.
115. `[ ]` **Graph 3: Production**: Physical production output volumes across goods.
116. `[ ]` **Graph 4: Trade Flow (Paired Bars)**: Inter-regional exports vs imports.
117. `[ ]` **Graph 5: Gov Income (Stacked Bars)**: Municipal revenue breakdown (Taxes, Tariffs, Inheritance).
118. `[ ]` **Graph 6: Gini Inequality & Migration**: Wealth Gini curve vs net outward migration pressure.
119. `[ ]` **Graph 7: Commodity Inventories**: Physical stock in warehouses.
120. `[ ]` **Graph 8: Protest Energy & Commons Tenure**: Protest energy vs customary commons ratio.
121. `[x]` **Graph 9: Real GDP Output**: Moving average of real economic output.
122. `[ ]` **Graph 10: Demand Ratios**: Market supply-demand pressure ratios.
123. `[ ]` **Graph 11: Soil & Nutrition**: Soil fertility % vs crop nutritional density.
124. `[ ]` **Graph 12: Pollution Rift**: Smog particulate, water effluent, and chemical toxin curves.
125. `[ ]` **Graph 13: Epidemic Cases**: Malnutrition, cholera, smog bronchitis, and toxic illness counts.
126. `[ ]` **Graph 14: Healthcare Outlays (Paired Bars)**: Private out-of-pocket medical bills vs public hospital subsidies.
127. `[ ]` **Graph 15: Untreated Illness & Fatalities**: Impoverished untreated patients and epidemic mortality.
128. `[ ]` **Graph 16: Physiological Health Attrition**: Working-class physical wear-and-tear degradation.
129. `[ ]` **Graph 17: Shift Hours & Exploitation Rate (s/v)**: Average shift hours, legal workday ceiling, and surplus value rate.
130. `[ ]` **Graph 18: 4D Alienation & Attrition**: Psychological alienation index, bodily attrition, and vice spending.
131. `[ ]` **Graph 19: Class Consciousness & Pacification**: Proletarian consciousness vs mass spectacle entertainment vs protest.
132. `[ ]` **Graph 20: Workplace Resistance**: Active wildcat strikers, sabotaged machines, and operating capital stock.

### D. Right Panel Tables & Cadastre Controls
133. `[x]` **Parish Land Summary Card**: Breakdown of Commons %, Feudal %, Enclosed %, Arable % vs Pasture %.
134. `[x]` **Surveyed Parcels List / Table**: Table of surveyed plots on selected parish.
135. `[ ]` **Parcel Scroll Buttons (`▲ Scroll Up`, `▼ Scroll Down`)**: Scroll through extensive parish plot registries.
136. `[ ]` **Parcel Action Button: `Enclose ($fee)`**: Enclose feudal plot directly from cadastre.
137. `[ ]` **Parcel Action Button: `To Pasture` / `To Arable`**: Toggle land use between wool sheep and grain crops.
138. `[ ]` **Parcel Action Button: `Restore Commons`**: Revert enclosed parcel to customary usufruct commons.
139. `[ ]` **Statutory Foreclosure Countdown Badge**: Warning badge showing turns remaining before enclosure debt foreclosure.
140. `[ ]` **Citizens Sub-Tab Switcher: `[ Class & Tenure ]` vs `[ Labor & Alienation ]`**: Citizen dashboard modes.
141. `[x]` **Living Resident Census Table**: Table listing individual citizens with ID, Age, Career, Wage, Cash, Hunger, Happiness, and Faction.
142. `[x]` **Pauper Workhouse Census Table**: Paupers registered, relief capacity, intake rate.
143. `[x]` **Spot Commodity Market Price Ticker Table**: Prices and inventory for all 8 traded goods.

---

## 5. Modals & Dialogs

### A. Modal 1: 📊 Cross-Nation & Provincial Economic Comparison Suite (`C`)
144. `[ ]` **Compare Suite 6-Tab Switcher**: Tabs 1..6.
145. `[x]` **Tab 1 Table: Macro Accounts & Sovereign Leaderboard**: Table with Nation, Population, Treasury, GDP, Unrest Stage, Gini, Trade Balance, ISRB Rating.
146. `[ ]` **Tab 1 Turn Delta Tracking**: (+/-) per-turn deltas color-coded in green/red for all macro metrics.
147. `[ ]` **Tab 2 Table: Goods Market & Provincial Industrial Economy**: Table of Food, Wood, Furniture prices, output, stocks, and trade values across all provinces.
148. `[ ]` **Tab 3 Table: Sovereign Monetary Accounts & Banking**: National NEER, central bank FX reserves, provincial branch bank deposits.
149. `[ ]` **Tab 3 Table: Bilateral FX Matrix**: Currency exchange rates and currency reserves matrix.
150. `[ ]` **Tab 4 Table: Class Wealth Extraction & Attrition**: Feudal tribute, Ground rent, Surplus value s/v, Taxes by Muni/Prov/Nation, Bodily health degradation, 4D Alienation.
151. `[ ]` **Tab 4 Scope Drilldown: `[ By Country ]`, `[ By Province ]`, `[ By City / Tile ]`**: Multi-level hierarchical table view.
152. `[ ]` **Tab 5 Table: Protest Energy & Grievance Sources**: Table breakdown of protest energy by grievance cause (Overwork, Enclosure, Hunger, Strikes, Taxes/Repression, Inequality).
153. `[ ]` **Tab 5 Stacked Proportional Grievance Bars**: 100% stacked horizontal bars showing grievance distribution.
154. `[ ]` **Tab 5 Scope Drilldown: `[ By Country ]`, `[ By Province ]`, `[ By City / Tile ]`**: Hierarchical protest table.
155. `[ ]` **Tab 6 Table: Environmental Degradation & Public Health**: Soil depletion, nutrition density, smog/water/chemical pollution, infection counts (malnutrition, cholera, bronchitis, toxic chemical), private vs public healthcare bills.
156. `[ ]` **Tab 6 Scope Drilldown: `[ By Country ]`, `[ By Province ]`, `[ By City / Tile ]`**: Hierarchical environmental health table.

### B. Modal 2: 🏛️ Full Sovereign Command Suite Modal (`A`)
157. `[ ]` **Full-Screen Sovereign Command Center**: Fullscreen modal matching `worldview_actions.py` combining diplomacy, military, construction, innovation, and bonds with AI advisory.

### C. Modal 3: 💸 Inter-Governmental Fiscal Transfer & Bailout Dialog
158. `[ ]` **Shortfall Resolution Dialog**: Modal appearing when commissioning infrastructure or policy with insufficient local cash on hand:
    - Button 1: Provincial Equalization Grant.
    - Button 2: Sovereign Treasury Infrastructure Bailout.
    - Button 3: Municipal Bank Deficit Loan.

### D. Modal 4: 📖 3-Page System Manual & World Registry (`?`)
159. `[ ]` **3-Page Paginated Navigation Tabs**:
    - Page 1: Simulation Controls, Camera, Map Info Layers, Badges & Terrain Glyphs.
    - Page 2: 3-Tab Economic Accounts & Financial Glossary.
    - Page 3: Procedural World Seeds & Sovereign Nations Registry.
160. `[x]` **Controls & Quick Hotkey Guide**: Keyboard shortcuts guide.

---

## Summary of Feature Parity

| Category | Total Features | Implemented | Pending |
| :--- | :---: | :---: | :---: |
| 1. Top Bar & Viewport Controls | 22 | 16 | 6 |
| 2. The 9 Thematic Map Layers | 9 | 9 | 0 |
| 3. Left Sovereign Dock Suites (6 Drawers) | 77 | 26 | 51 |
| 4. Right Inspection & Analytics Panel | 35 | 16 | 19 |
| 5. Modals & Dialogs | 17 | 4 | 13 |
| **TOTAL** | **160** | **71** | **89** |

---

*Updated automatically during implementation of full feature parity.*
