// vis_pyramid.js — Class Wealth Stratification Pyramid & Lorenz Curve Visualizer.
(function (root) {
  'use strict';

  function drawWealthPyramid(canvas, options = {}, dpr = 1) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth || 460;
    const h = canvas.clientHeight || 260;
    const scale = dpr || window.devicePixelRatio || 1;

    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    ctx.save();
    ctx.scale(scale, scale);
    ctx.clearRect(0, 0, w, h);

    // Dark background container
    ctx.fillStyle = '#141824';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#2b3347';
    ctx.strokeRect(0, 0, w, h);

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('🏛️ 4-Tier Class Wealth & Demographic Stratification Pyramid', 14, 18);

    const padX = 24;
    const padTop = 32;
    const padBottom = 20;
    const plotW = w - padX * 2;
    const plotH = h - padTop - padBottom;
    const cx = padX + plotW / 2;

    // 4 Demographic tiers: [name, pop_pct, wealth_pct, color]
    const tiers = [
      { name: 'Bourgeoisie & Gentry', pop: '2.5%', wealth: '64.2%', col: '#f59e0b', topRatio: 0.12, botRatio: 0.32 },
      { name: 'Petty Bourgeoisie & Artisans', pop: '14.5%', wealth: '21.4%', col: '#38bdf8', topRatio: 0.32, botRatio: 0.58 },
      { name: 'Proletariat & Customary Serfs', pop: '68.0%', wealth: '13.1%', col: '#ef4444', topRatio: 0.58, botRatio: 0.86 },
      { name: 'Destitute & Vagabonds', pop: '15.0%', wealth: '1.3%', col: '#a855f7', topRatio: 0.86, botRatio: 1.0 }
    ];

    const tierCount = tiers.length;
    const tierH = plotH / tierCount;

    tiers.forEach((t, i) => {
      const y0 = padTop + i * tierH;
      const y1 = y0 + tierH - 3;
      const topHalfW = (plotW / 2) * t.topRatio;
      const botHalfW = (plotW / 2) * t.botRatio;

      // Draw trapezoid
      ctx.beginPath();
      ctx.moveTo(cx - topHalfW, y0);
      ctx.lineTo(cx + topHalfW, y0);
      ctx.lineTo(cx + botHalfW, y1);
      ctx.lineTo(cx - botHalfW, y1);
      ctx.closePath();

      ctx.fillStyle = t.col + '33';
      ctx.fill();
      ctx.strokeStyle = t.col;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Tier label & metrics
      ctx.font = '10px -apple-system, sans-serif';
      ctx.fillStyle = '#f1f5f9';
      ctx.textAlign = 'center';
      ctx.fillText(t.name, cx, y0 + tierH * 0.45);

      // Left pop label
      ctx.textAlign = 'right';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(`👥 ${t.pop}`, Math.max(10, cx - botHalfW - 8), y0 + tierH * 0.5);

      // Right wealth label
      ctx.textAlign = 'left';
      ctx.fillStyle = t.col;
      ctx.fillText(`💰 ${t.wealth}`, Math.min(w - 10, cx + botHalfW + 8), y0 + tierH * 0.5);
    });

    ctx.restore();
  }

  function drawLorenzCurve(canvas, giniValue = 0.42, dpr = 1) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth || 460;
    const h = canvas.clientHeight || 260;
    const scale = dpr || window.devicePixelRatio || 1;

    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    ctx.save();
    ctx.scale(scale, scale);
    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = '#141824';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#2b3347';
    ctx.strokeRect(0, 0, w, h);

    const gini = Math.max(0.01, Math.min(0.99, Number(giniValue) || 0.42));

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`📊 Lorenz Curve (Gini Coefficient: ${gini.toFixed(2)})`, 14, 18);

    const padL = 40;
    const padR = 20;
    const padT = 32;
    const padB = 30;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // Grid axes
    ctx.strokeStyle = '#2b3347';
    ctx.lineWidth = 1;
    ctx.strokeRect(padL, padT, plotW, plotH);

    // 45-degree Line of Perfect Equality
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#64748b';
    ctx.moveTo(padL, padT + plotH);
    ctx.lineTo(padL + plotW, padT);
    ctx.stroke();
    ctx.setLineDash([]);

    // Actual Lorenz curve: L(p) = p^(1 + 2*Gini)
    const exponent = 1.0 + 2.4 * gini;
    const steps = 40;

    // Shaded inequality region
    ctx.beginPath();
    ctx.moveTo(padL, padT + plotH);
    for (let i = 0; i <= steps; i++) {
      const p = i / steps;
      const x = padL + p * plotW;
      const yDiag = padT + plotH - p * plotH;
      ctx.lineTo(x, yDiag);
    }
    for (let i = steps; i >= 0; i--) {
      const p = i / steps;
      const L = Math.pow(p, exponent);
      const x = padL + p * plotW;
      const yCurve = padT + plotH - L * plotH;
      ctx.lineTo(x, yCurve);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
    ctx.fill();

    // Lorenz curve line
    ctx.beginPath();
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2.5;
    for (let i = 0; i <= steps; i++) {
      const p = i / steps;
      const L = Math.pow(p, exponent);
      const x = padL + p * plotW;
      const y = padT + plotH - L * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Axis labels
    ctx.font = '9px -apple-system, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.textAlign = 'center';
    ctx.fillText('0%', padL, padT + plotH + 14);
    ctx.fillText('Cumulative Population %', padL + plotW / 2, padT + plotH + 18);
    ctx.fillText('100%', padL + plotW, padT + plotH + 14);

    ctx.textAlign = 'right';
    ctx.fillText('100% Wealth', padL - 6, padT + 8);
    ctx.fillText('0%', padL - 6, padT + plotH);

    // Gini Assessment Tag
    let rating = 'Moderate Concentration';
    let badgeColor = '#f59e0b';
    if (gini < 0.30) { rating = 'Egalitarian Distribution'; badgeColor = '#10b981'; }
    else if (gini > 0.55) { rating = 'Extreme Oligarchic Capture'; badgeColor = '#ef4444'; }

    ctx.textAlign = 'left';
    ctx.fillStyle = badgeColor;
    ctx.fillText(`● ${rating}`, padL + 12, padT + 18);

    ctx.restore();
  }

  const CoCVisPyramid = Object.freeze({ drawWealthPyramid, drawLorenzCurve });
  root.CoCVisPyramid = CoCVisPyramid;
})(typeof globalThis !== 'undefined' ? globalThis : window);
