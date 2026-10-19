// Chart catalog and canvas drawing for the web client's historical metrics panel.
(function (root) {
  'use strict';

  const chartCatalog = Object.freeze({
    economic: [
      { id: 'gdp', name: 'Nominal GDP' }, { id: 'treasury', name: 'Treasury' },
      { id: 'food_price', name: 'Food Price' }, { id: 'pop', name: 'Pop/Hunger' },
      { id: 'production', name: 'Food Production' }, { id: 'trade', name: 'Trade Flow' },
      { id: 'gov_income', name: 'Gov Revenue' }, { id: 'gini', name: 'Food Cash Inequality' },
      { id: 'inventories', name: 'Food Stocks' }, { id: 'unrest', name: 'Protest Energy' }
    ],
    ecological: [
      { id: 'soil', name: 'Soil Fertility' }, { id: 'nutrition', name: 'Nutrition Density' },
      { id: 'smog', name: 'Smog Particulate' },
      { id: 'effluent', name: 'Water Effluent' },
      { id: 'malnutrition_cases', name: 'Malnutrition Cases' },
      { id: 'waterborne_cases', name: 'Waterborne Cases' },
      { id: 'respiratory_cases', name: 'Respiratory Cases' },
      { id: 'chemical_cases', name: 'Chemical Exposure Cases' },
      { id: 'health_outlays', name: 'Healthcare Outlays' }, { id: 'illness_deaths', name: 'Illness Fatalities' }
    ],
    labor: [
      { id: 'shift_hours', name: 'Average Shift Hours' },
      { id: 'exploitation', name: 'Rate of Exploitation (s/v)' },
      { id: 'alienation', name: 'Average Alienation' },
      { id: 'consciousness', name: 'Average Class Consciousness' },
      { id: 'strikes', name: 'Active Strikers' }
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
      label: 'Food price' }),
    pop: Object.freeze({ metricId: 'people.population', historyKey: 'pop',
      tilePath: ['economic', 'pop_hunger', 'pop'], label: 'Population' }),
    unrest: Object.freeze({ metricId: 'politics.protest_energy', historyKey: 'unrest',
      tilePath: ['economic', 'protest_commons', 'protest'],
      label: 'Protest energy' }),
    production: Object.freeze({ metricId: 'goods.production',
      tilePath: ['economic', 'production', 'food'], good: 'food',
      label: 'Food production' }),
    inventories: Object.freeze({ metricId: 'goods.producer_inventory',
      tilePath: ['economic', 'inventories', 'food'], good: 'food',
      label: 'Food producer inventory' }),
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
      label: 'Active strikers' })
  });

  function getChartCatalog() {
    return chartCatalog;
  }

  function getTraceBinding(metric) {
    const binding = traceBindings[metric];
    return binding ? {
      ...binding,
      tilePath: binding.tilePath && [...binding.tilePath],
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
      return `${String(metric).toUpperCase()}: No data series available`;
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
    return `${String(metric).toUpperCase()}: Historical Trend over Turns (Min ${minVal.toFixed(1)} | Max ${maxVal.toFixed(1)})`;
  }

  const CoCCharts = Object.freeze({
    getChartCatalog, getTraceBinding, getTileSeries, drawHistoricalChart
  });
  root.CoCCharts = CoCCharts;
})(typeof globalThis !== 'undefined' ? globalThis : window);
