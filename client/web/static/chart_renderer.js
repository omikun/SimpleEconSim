// Chart catalog and canvas drawing for the web client's historical metrics panel.
(function (root) {
  'use strict';

  const chartCatalog = Object.freeze({
    economic: [
      { id: 'gdp', name: 'Real GDP' }, { id: 'treasury', name: 'Treasury' },
      { id: 'food_price', name: 'Food Price' }, { id: 'pop', name: 'Pop/Hunger' },
      { id: 'production', name: 'Production' }, { id: 'trade', name: 'Trade Flow' },
      { id: 'gov_income', name: 'Gov Revenue' }, { id: 'gini', name: 'Gini Inequality' },
      { id: 'inventories', name: 'Commodity Stocks' }, { id: 'unrest', name: 'Protest Energy' }
    ],
    ecological: [
      { id: 'soil', name: 'Soil & Nutrition' }, { id: 'smog', name: 'Smog Particulate' },
      { id: 'effluent', name: 'Water Effluent' }, { id: 'epidemics', name: 'Epidemic Cases' },
      { id: 'health_outlays', name: 'Healthcare Outlays' }, { id: 'illness_deaths', name: 'Illness Fatalities' }
    ],
    labor: [
      { id: 'shift_hours', name: 'Shift Hours & (s/v)' }, { id: 'alienation', name: '4D Alienation' },
      { id: 'consciousness', name: 'Class Consciousness' }, { id: 'strikes', name: 'Wildcat Strikes' }
    ]
  });

  const metricColors = {
    gdp: '#38bdf8', treasury: '#f59e0b', food_price: '#10b981', pop: '#a855f7',
    unrest: '#ef4444', soil: '#10b981', smog: '#94a3b8', alienation: '#f43f5e'
  };

  function getChartCatalog() {
    return chartCatalog;
  }

  function drawHistoricalChart(canvas, values, metric, dpr = 1) {
    const ctx = canvas.getContext('2d');
    const width = canvas.clientWidth || 380;
    const height = canvas.clientHeight || 220;
    const scale = dpr || 1;
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    ctx.save();
    ctx.scale(scale, scale);
    ctx.clearRect(0, 0, width, height);

    const series = Array.isArray(values) && values.length >= 2 ? values : [50, 54, 52, 57, 56];
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
    ctx.restore();
    return `${String(metric).toUpperCase()}: Historical Trend over Turns (Min ${minVal.toFixed(1)} | Max ${maxVal.toFixed(1)})`;
  }

  root.RegnumCharts = Object.freeze({ getChartCatalog, drawHistoricalChart });
})(typeof globalThis !== 'undefined' ? globalThis : window);
