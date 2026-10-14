// vis_circuits.js — Marxian Circuit of Capital Sankey Flow (M -> C -> P -> C' -> M') & TRPF Profit Fall Visualizer.
(function (root) {
  'use strict';

  function drawCircuitSankey(canvas, data = {}, dpr = 1) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth || 700;
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

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText("🔄 Marxian Circuit of Capital (M → C {c, v} → P → C' → M') Sankey Flow", 14, 18);

    const padL = 30;
    const padR = 30;
    const padT = 36;
    const padB = 24;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // 5 Stages columns: M (Money), C (Commodities), P (Production), C' (Expanded), M' (Realized)
    const stages = [
      { id: 'M', label: 'M (Money Capital)', x: padL, color: '#f59e0b', desc: 'Liquid Vault Cash' },
      { id: 'C', label: 'C (Inputs: c + v)', x: padL + plotW * 0.25, color: '#38bdf8', desc: 'Raw Goods & Wages' },
      { id: 'P', label: 'P (Living Labor)', x: padL + plotW * 0.50, color: '#a855f7', desc: 'Surplus Extraction' },
      { id: 'C_prime', label: "C' (Output Goods)", x: padL + plotW * 0.75, color: '#10b981', desc: 'Wares + Surplus Value' },
      { id: 'M_prime', label: "M' (Gross Revenue)", x: padL + plotW, color: '#f59e0b', desc: 'Auction Realization' }
    ];

    // Draw connecting flow bands
    for (let i = 0; i < stages.length - 1; i++) {
      const s1 = stages[i];
      const s2 = stages[i + 1];

      const cy1 = padT + plotH / 2;
      const cy2 = padT + plotH / 2;
      const bandH1 = 40;
      const bandH2 = 40 + (i >= 2 ? 14 : 0); // Expansion from surplus value

      ctx.beginPath();
      ctx.moveTo(s1.x, cy1 - bandH1 / 2);
      ctx.bezierCurveTo(
        s1.x + (s2.x - s1.x) * 0.5, cy1 - bandH1 / 2,
        s1.x + (s2.x - s1.x) * 0.5, cy2 - bandH2 / 2,
        s2.x, cy2 - bandH2 / 2
      );
      ctx.lineTo(s2.x, cy2 + bandH2 / 2);
      ctx.bezierCurveTo(
        s1.x + (s2.x - s1.x) * 0.5, cy2 + bandH2 / 2,
        s1.x + (s2.x - s1.x) * 0.5, cy1 + bandH1 / 2,
        s1.x, cy1 + bandH1 / 2
      );
      ctx.closePath();

      const grad = ctx.createLinearGradient(s1.x, 0, s2.x, 0);
      grad.addColorStop(0, s1.color + '44');
      grad.addColorStop(1, s2.color + '44');
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.strokeStyle = s1.color + '88';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Draw Stage Pillars
    stages.forEach(st => {
      const cy = padT + plotH / 2;
      const pW = 12;
      const pH = 56;

      ctx.fillStyle = st.color;
      ctx.fillRect(st.x - pW / 2, cy - pH / 2, pW, pH);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1;
      ctx.strokeRect(st.x - pW / 2, cy - pH / 2, pW, pH);

      // Label top
      ctx.font = 'bold 10px -apple-system, sans-serif';
      ctx.fillStyle = '#f1f5f9';
      ctx.textAlign = 'center';
      ctx.fillText(st.label, st.x, cy - pH / 2 - 8);

      // Desc bottom
      ctx.font = '9px -apple-system, sans-serif';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(st.desc, st.x, cy + pH / 2 + 14);
    });

    ctx.restore();
  }

  function drawTRPFCurve(canvas, cvRatio = 2.4, dpr = 1) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth || 320;
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

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('📉 Tendency of Rate of Profit to Fall (TRPF)', 14, 18);

    const padL = 40;
    const padR = 20;
    const padT = 32;
    const padB = 30;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // Grid box
    ctx.strokeStyle = '#2b3347';
    ctx.strokeRect(padL, padT, plotW, plotH);

    // Curve: r = (s/v) / (c/v + 1)
    const sv = 0.85; // Rate of surplus value
    const steps = 40;
    ctx.beginPath();
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 2.5;

    for (let i = 0; i <= steps; i++) {
      const cv = 0.2 + (i / steps) * 4.8; // c/v from 0.2 to 5.0
      const r = sv / (cv + 1.0);
      const px = padL + ((cv - 0.2) / 4.8) * plotW;
      const py = padT + (1.0 - r / 0.8) * plotH;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // Current operating point
    const curCV = Math.max(0.2, Math.min(5.0, Number(cvRatio) || 2.4));
    const curR = sv / (curCV + 1.0);
    const cx = padL + ((curCV - 0.2) / 4.8) * plotW;
    const cy = padT + (1.0 - curR / 0.8) * plotH;

    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#f59e0b';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Axis labels
    ctx.font = '9px -apple-system, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.textAlign = 'center';
    ctx.fillText('Organic Composition (c/v)', padL + plotW / 2, padT + plotH + 18);
    ctx.textAlign = 'right';
    ctx.fillText('Profit Rate r%', padL - 6, padT + 12);

    ctx.restore();
  }

  const CoCVisCircuits = Object.freeze({ drawCircuitSankey, drawTRPFCurve });
  root.CoCVisCircuits = CoCVisCircuits;
})(typeof globalThis !== 'undefined' ? globalThis : window);
