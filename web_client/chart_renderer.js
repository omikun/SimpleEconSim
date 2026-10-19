// Chart catalog and canvas drawing for the web client's historical metrics panel.
(function (root) {
  'use strict';

  const chartCatalog = Object.freeze({
    economic: [
      { id: 'gdp', name: 'Nominal GDP' }, { id: 'treasury', name: 'Treasury' },
      { id: 'food_price', name: 'Food Price' },
      { id: 'wood_price', name: 'Wood Price (Tile)' },
      { id: 'furniture_price', name: 'Furniture Price (Tile)' },
      { id: 'pop', name: 'Pop/Hunger' },
      { id: 'production', name: 'Food Production' },
      { id: 'wood_production', name: 'Wood Production' },
      { id: 'furniture_production', name: 'Furniture Production' },
      { id: 'food_demand_ratio', name: 'Food Demand / Supply' },
      { id: 'wood_demand_ratio', name: 'Wood Demand / Supply' },
      { id: 'furniture_demand_ratio', name: 'Furniture Demand / Supply' },
      { id: 'trade', name: 'Net Trade Value' },
      { id: 'trade_exports', name: 'Export Receipts' },
      { id: 'trade_imports', name: 'Import Purchases' },
      { id: 'gov_income', name: 'Government Revenue' }, { id: 'gini', name: 'Food Cash Inequality' },
      { id: 'inventories', name: 'Food Stocks' },
      { id: 'wood_inventories', name: 'Wood Stocks' },
      { id: 'furniture_inventories', name: 'Furniture Stocks' },
      { id: 'unrest', name: 'Protest Energy' }
    ],
    market: [
      { id: 'market_price', name: 'Reference Price' },
      { id: 'market_production', name: 'Production' },
      { id: 'market_demand_ratio', name: 'Demand / Supply' },
      { id: 'market_inventory', name: 'Producer Stocks' }
    ],
    ecological: [
      { id: 'soil', name: 'Soil Fertility' }, { id: 'nutrition', name: 'Nutrition Density' },
      { id: 'smog', name: 'Smog Particulate' },
      { id: 'effluent', name: 'Water Effluent' },
      { id: 'soil_pollution', name: 'Soil Toxicity' },
      { id: 'malnutrition_cases', name: 'Malnutrition Cases' },
      { id: 'waterborne_cases', name: 'Waterborne Cases' },
      { id: 'respiratory_cases', name: 'Respiratory Cases' },
      { id: 'chemical_cases', name: 'Chemical Exposure Cases' },
      { id: 'health_outlays', name: 'Healthcare Outlays' }, { id: 'illness_deaths', name: 'Illness Fatalities' },
      { id: 'bodily_wear', name: 'Average Bodily Wear' }
    ],
    labor: [
      { id: 'shift_hours', name: 'Average Shift Hours' },
      { id: 'exploitation', name: 'Rate of Exploitation (s/v)' },
      { id: 'alienation', name: 'Average Alienation' },
      { id: 'consciousness', name: 'Average Class Consciousness' },
      { id: 'strikes', name: 'Active Strikers' },
      { id: 'workplace_accidents', name: 'Workplace Accidents' },
      { id: 'entertainment', name: 'Pacification Investment' },
      { id: 'machinery_sabotaged', name: 'Machinery Sabotaged' },
      { id: 'broken_machinery', name: 'Broken Machinery' }
    ],
    citizens: [
      { id: 'class_serf', name: 'Commoners' },
      { id: 'class_tenant', name: 'Tenants' },
      { id: 'class_worker', name: 'Wage Workers' },
      { id: 'class_dispossessed', name: 'Dispossessed' },
      { id: 'class_gentry', name: 'Gentry' },
      { id: 'class_artisan', name: 'Artisans and Industrialists' },
      { id: 'food_foraged', name: 'Foraged Food' },
      { id: 'food_purchased', name: 'Purchased Food' },
      { id: 'commons_access', name: 'Effective Commons Access' },
      { id: 'rent_collected', name: 'Rent Collected' },
      { id: 'rent_arrears', name: 'Rent Arrears' }
    ]
  });

  const metricColors = {
    gdp: '#38bdf8', treasury: '#f59e0b', food_price: '#10b981', pop: '#a855f7',
    unrest: '#ef4444', soil: '#10b981', smog: '#94a3b8', alienation: '#f43f5e'
  };

  const traceBindings = Object.freeze({
    gdp: Object.freeze({ metricId: 'economy.gdp_nominal', historyKey: 'gdp',
      tilePath: ['economic', 'gdp'], label: 'Nominal GDP' }),
    treasury: Object.freeze({ metricId: 'finance.treasury', historyKey: 'treasury',
      label: 'Treasury' }),
    food_price: Object.freeze({ metricId: 'goods.national_food_price',
      historyKey: 'food_price', tilePath: ['economic', 'prices', 'food'],
      tileMetricId: 'goods.price', good: 'food', priceChart: true,
      label: 'Food price' }),
    wood_price: Object.freeze({ metricId: 'goods.price', good: 'wood',
      tilePath: ['economic', 'prices', 'wood'], priceChart: true,
      label: 'Wood price' }),
    furniture_price: Object.freeze({ metricId: 'goods.price', good: 'furniture',
      tilePath: ['economic', 'prices', 'furniture'], priceChart: true,
      label: 'Furniture price' }),
    pop: Object.freeze({ metricId: 'people.population', historyKey: 'pop',
      tilePath: ['economic', 'pop_hunger', 'pop'], label: 'Population' }),
    unrest: Object.freeze({ metricId: 'politics.protest_energy', historyKey: 'unrest',
      tilePath: ['economic', 'protest_commons', 'protest'],
      label: 'Protest energy' }),
    production: Object.freeze({ metricId: 'goods.production',
      tilePath: ['economic', 'production', 'food'], good: 'food',
      label: 'Food production' }),
    wood_production: Object.freeze({ metricId: 'goods.production',
      tilePath: ['economic', 'production', 'wood'], good: 'wood',
      label: 'Wood production' }),
    furniture_production: Object.freeze({ metricId: 'goods.production',
      tilePath: ['economic', 'production', 'furniture'], good: 'furniture',
      label: 'Furniture production' }),
    food_demand_ratio: Object.freeze({ metricId: 'goods.demand_ratio',
      tilePath: ['economic', 'demand_ratio', 'food'], good: 'food',
      label: 'Food demand / supply ratio' }),
    wood_demand_ratio: Object.freeze({ metricId: 'goods.demand_ratio',
      tilePath: ['economic', 'demand_ratio', 'wood'], good: 'wood',
      label: 'Wood demand / supply ratio' }),
    furniture_demand_ratio: Object.freeze({ metricId: 'goods.demand_ratio',
      tilePath: ['economic', 'demand_ratio', 'furniture'], good: 'furniture',
      label: 'Furniture demand / supply ratio' }),
    trade: Object.freeze({ metricId: 'trade.net_value',
      tilePath: ['economic', 'trade_flow', 'balance'],
      label: 'Net trade value in tile currency' }),
    trade_exports: Object.freeze({ metricId: 'trade.export_value',
      tilePath: ['economic', 'trade_flow', 'export'],
      label: 'Export receipts converted to tile currency' }),
    trade_imports: Object.freeze({ metricId: 'trade.import_value',
      tilePath: ['economic', 'trade_flow', 'import'],
      label: 'Import purchases in tile currency' }),
    inventories: Object.freeze({ metricId: 'goods.producer_inventory',
      tilePath: ['economic', 'inventories', 'food'], good: 'food',
      label: 'Food producer inventory' }),
    wood_inventories: Object.freeze({ metricId: 'goods.producer_inventory',
      tilePath: ['economic', 'inventories', 'wood'], good: 'wood',
      label: 'Wood producer inventory' }),
    furniture_inventories: Object.freeze({ metricId: 'goods.producer_inventory',
      tilePath: ['economic', 'inventories', 'furniture'], good: 'furniture',
      label: 'Furniture producer inventory' }),
    gini: Object.freeze({ metricId: 'economy.gini',
      tilePath: ['economic', 'gini_migration', 'gini'], good: 'food',
      chartScale: 100, displayUnit: '%', label: 'Food producer cash inequality' }),
    soil: Object.freeze({ metricId: 'ecology.soil_fertility',
      tilePath: ['ecological', 'soil_nutrition', 'soil'], chartScale: 100,
      displayUnit: '%', label: 'Soil fertility' }),
    nutrition: Object.freeze({ metricId: 'ecology.nutrition_density',
      tilePath: ['ecological', 'soil_nutrition', 'nutrition'], chartScale: 100,
      displayUnit: '%', label: 'Nutrition density' }),
    smog: Object.freeze({ metricId: 'ecology.pollution_air',
      tilePath: ['ecological', 'pollution', 'smog'], label: 'Air pollution' }),
    effluent: Object.freeze({ metricId: 'ecology.pollution_water',
      tilePath: ['ecological', 'pollution', 'water'], label: 'Water pollution' }),
    soil_pollution: Object.freeze({ metricId: 'ecology.pollution_soil',
      tilePath: ['ecological', 'pollution', 'soil'], label: 'Soil toxicity' }),
    bodily_wear: Object.freeze({ metricId: 'health.average_bodily_wear',
      tilePath: ['ecological', 'health_attrition'], chartScale: 100,
      label: 'Average accumulated bodily wear' }),
    illness_deaths: Object.freeze({ metricId: 'health.fatalities',
      tilePath: ['ecological', 'untreated_fatalities', 'fatalities'],
      label: 'Disease fatalities' }),
    malnutrition_cases: Object.freeze({ metricId: 'health.disease_cases',
      tilePath: ['ecological', 'epidemics', 'malnutrition'], disease: 'malnutrition',
      label: 'Malnutrition cases' }),
    waterborne_cases: Object.freeze({ metricId: 'health.disease_cases',
      tilePath: ['ecological', 'epidemics', 'cholera'], disease: 'waterborne',
      label: 'Waterborne cases' }),
    respiratory_cases: Object.freeze({ metricId: 'health.disease_cases',
      tilePath: ['ecological', 'epidemics', 'bronchitis'], disease: 'respiratory',
      label: 'Respiratory cases' }),
    chemical_cases: Object.freeze({ metricId: 'health.disease_cases',
      tilePath: ['ecological', 'epidemics', 'toxic'], disease: 'chemical',
      label: 'Chemical exposure cases' }),
    health_outlays: Object.freeze({ metricId: 'health.medical_spending',
      seriesPaths: [['ecological', 'healthcare_outlay', 'private'],
        ['ecological', 'healthcare_outlay', 'public']],
      label: 'Healthcare outlays' }),
    gov_income: Object.freeze({ metricId: 'finance.government_income',
      seriesPaths: [['economic', 'gov_income', 'tax'],
        ['economic', 'gov_income', 'tariff'],
        ['economic', 'gov_income', 'inheritance']],
      label: 'Government revenue (tile or shared province)' }),
    shift_hours: Object.freeze({ metricId: 'labor.average_shift_hours',
      tilePath: ['labor', 'shifts_exploitation', 'shifts'],
      label: 'Average shift hours' }),
    exploitation: Object.freeze({ metricId: 'labor.exploitation_rate',
      tilePath: ['labor', 'shifts_exploitation', 'sv_rate'],
      chartScale: 100, displayUnit: '%', label: 'Rate of exploitation (s/v)' }),
    alienation: Object.freeze({ metricId: 'labor.average_alienation',
      tilePath: ['labor', 'alienation_health', 'alienation'],
      chartScale: 100, displayUnit: '%', label: 'Average alienation' }),
    consciousness: Object.freeze({ metricId: 'labor.average_class_consciousness',
      tilePath: ['labor', 'consciousness_pacification', 'consciousness'],
      chartScale: 100, displayUnit: '%', label: 'Average class consciousness' }),
    strikes: Object.freeze({ metricId: 'labor.strikers',
      tilePath: ['labor', 'workplace_resistance', 'strikers'],
      label: 'Active strikers' }),
    workplace_accidents: Object.freeze({ metricId: 'labor.workplace_accidents',
      tilePath: ['labor', 'workplace_conditions', 'accidents'],
      label: 'Workplace accidents' }),
    entertainment: Object.freeze({ metricId: 'society.entertainment_level',
      tilePath: ['labor', 'workplace_conditions', 'entertainment'],
      chartScale: 100, displayUnit: '%', label: 'Pacification investment level' }),
    machinery_sabotaged: Object.freeze({ metricId: 'labor.machinery_sabotaged',
      tilePath: ['labor', 'workplace_conditions', 'sabotage'],
      label: 'Machinery sabotaged this turn' }),
    broken_machinery: Object.freeze({ metricId: 'labor.broken_machinery',
      tilePath: ['labor', 'workplace_conditions', 'broken'],
      label: 'Broken machinery stock' }),
    class_serf: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'serf'], classGroup: 'serf',
      label: 'Commoners' }),
    class_tenant: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'tenant'], classGroup: 'tenant',
      label: 'Tenants' }),
    class_worker: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'worker'], classGroup: 'worker',
      label: 'Wage workers' }),
    class_dispossessed: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'dispossessed'], classGroup: 'dispossessed',
      label: 'Dispossessed' }),
    class_gentry: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'gentry'], classGroup: 'gentry',
      label: 'Gentry' }),
    class_artisan: Object.freeze({ metricId: 'society.class_population',
      tilePath: ['citizens', 'classes', 'artisan'], classGroup: 'artisan',
      label: 'Artisans and industrialists' }),
    food_foraged: Object.freeze({ metricId: 'food.foraged',
      tilePath: ['citizens', 'food_source', 'foraged'],
      label: 'Foraged food units' }),
    food_purchased: Object.freeze({ metricId: 'food.purchased',
      tilePath: ['citizens', 'food_source', 'market'],
      label: 'Purchased food units' }),
    commons_access: Object.freeze({ metricId: 'land.commons_access',
      tilePath: ['citizens', 'commons_rent', 'commons'], chartScale: 100,
      displayUnit: '%', label: 'Effective commons access' }),
    rent_collected: Object.freeze({ metricId: 'finance.rent_collected',
      tilePath: ['citizens', 'commons_rent', 'rent'], label: 'Rent collected' }),
    rent_arrears: Object.freeze({ metricId: 'finance.rent_arrears',
      tilePath: ['citizens', 'commons_rent', 'arrears'], label: 'Rent arrears' }),
    market_price: Object.freeze({ metricId: 'goods.price',
      tileMetricId: 'goods.price', priceChart: true, dynamicGood: true,
      pathPrefix: ['economic', 'prices'], labelSuffix: 'price' }),
    market_production: Object.freeze({ metricId: 'goods.production',
      dynamicGood: true, pathPrefix: ['economic', 'production'],
      labelSuffix: 'production' }),
    market_demand_ratio: Object.freeze({ metricId: 'goods.demand_ratio',
      dynamicGood: true, pathPrefix: ['economic', 'demand_ratio'],
      labelSuffix: 'demand / supply ratio' }),
    market_inventory: Object.freeze({ metricId: 'goods.producer_inventory',
      dynamicGood: true, pathPrefix: ['economic', 'inventories'],
      labelSuffix: 'producer stocks' })
  });

  function getChartCatalog() {
    return chartCatalog;
  }

  function getTraceBinding(metric, selectedGood) {
    const binding = traceBindings[metric];
    return binding ? {
      ...binding,
      tilePath: binding.dynamicGood
        ? [...binding.pathPrefix, String(selectedGood || '').toLowerCase()]
        : binding.tilePath && [...binding.tilePath],
      good: binding.dynamicGood ? String(selectedGood || '').toLowerCase()
        : binding.good,
      label: binding.dynamicGood
        ? `${String(selectedGood || 'Good').replaceAll('_', ' ')} ${binding.labelSuffix}`
        : binding.label,
      seriesPaths: binding.seriesPaths && binding.seriesPaths.map(path => [...path])
    } : null;
  }

  function getTileSeries(charts, binding) {
    const read = path => path.reduce((value, key) => value?.[key], charts);
    if (Array.isArray(binding?.tilePath)) {
      const series = read(binding.tilePath);
      return Array.isArray(series) ? series : [];
    }
    const arrays = (binding?.seriesPaths || []).map(read).filter(Array.isArray);
    if (!arrays.length) return [];
    const length = Math.min(...arrays.map(series => series.length));
    return Array.from({ length }, (_unused, index) => arrays.reduce(
      (sum, series) => sum + Number(series[series.length - length + index] || 0), 0));
  }

  function drawHistoricalChart(canvas, values, metric, dpr = 1, options = {}) {
    const metricLabel = options.label || metric;
    const ctx = canvas.getContext('2d');
    const width = canvas.clientWidth || 380;
    const height = canvas.clientHeight || 220;
    const scale = dpr || 1;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    ctx.save();
    ctx.scale(scale, scale);
    ctx.clearRect(0, 0, width, height);

    if (canvas._cocChartPointSelect && typeof canvas.removeEventListener === 'function') {
      canvas.removeEventListener('click', canvas._cocChartPointSelect);
      canvas._cocChartPointSelect = null;
    }

    const hasSeries = Array.isArray(values) && values.length > 0;
    if (!hasSeries) {
      if (canvas.style) canvas.style.cursor = '';
      ctx.fillStyle = '#94a3b8';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data series available', width / 2, height / 2);
      ctx.restore();
      return `${String(metricLabel).toUpperCase()}: No data series available`;
    }
    const series = values;
    const padL = 44;
    const padR = 14;
    const padT = 18;
    const padB = 24;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    let minVal = Math.min(...series);
    let maxVal = Math.max(...series);
    if (minVal === maxVal) { minVal -= 1; maxVal += 1; }
    const valSpan = maxVal - minVal;

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const y = padT + (plotH / 4) * i;
      const value = maxVal - (valSpan / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(width - padR, y);
      ctx.stroke();
      ctx.fillText(value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(value < 10 ? 1 : 0), padL - 6, y + 3);
    }

    const strokeColor = metricColors[metric] || '#38bdf8';
    const point = (value, index) => ({
      x: padL + (plotW / Math.max(1, series.length - 1)) * index,
      y: padT + plotH - ((value - minVal) / valSpan) * plotH
    });
    ctx.beginPath();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 2.5;
    series.forEach((value, index) => {
      const { x, y } = point(value, index);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = strokeColor;
    series.forEach((value, index) => {
      const { x, y } = point(value, index);
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
    if (hasSeries && typeof options.onPointSelect === 'function'
        && typeof canvas.addEventListener === 'function') {
      const selectPoint = event => {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        let nearest = -1;
        let nearestDistance = Infinity;
        series.forEach((value, index) => {
          const plotted = point(value, index);
          const distance = Math.hypot(plotted.x - x, plotted.y - y);
          if (distance < nearestDistance) {
            nearest = index;
            nearestDistance = distance;
          }
        });
        if (nearest >= 0 && nearestDistance <= 14) {
          const turns = Array.isArray(options.turns) ? options.turns : [];
          options.onPointSelect({
            index: nearest,
            value: series[nearest],
            turn: turns[nearest] ?? null,
            metric
          });
        }
      };
      canvas._cocChartPointSelect = selectPoint;
      canvas.addEventListener('click', selectPoint);
      if (canvas.style) canvas.style.cursor = 'crosshair';
    } else if (canvas.style) {
      canvas.style.cursor = '';
    }
    ctx.restore();
    return `${String(metricLabel).toUpperCase()}: Historical Trend over Turns (Min ${minVal.toFixed(1)} | Max ${maxVal.toFixed(1)})`;
  }

  const CoCCharts = Object.freeze({
    getChartCatalog, getTraceBinding, getTileSeries, drawHistoricalChart
  });
  root.CoCCharts = CoCCharts;
})(typeof globalThis !== 'undefined' ? globalThis : window);
