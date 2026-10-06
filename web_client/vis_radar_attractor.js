// vis_radar_attractor.js — 4D Alienation Spider Chart & Rebellion Attractor 2D Phase-Space Visualizer.
(function (root) {
  'use strict';

  function drawAlienationRadar(canvas, data = {}, dpr = 1) {
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

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('🕸️ 4-Dimensional Alienation Radar (Marxian Entfremdung)', 14, 18);

    const cx = w / 2;
    const cy = h / 2 + 10;
    const radius = Math.min(w, h) * 0.36;

    const axes = [
      { name: '1. Product Ownership', angle: -Math.PI / 2 },
      { name: '2. Labor Process Control', angle: 0 },
      { name: '3. Metabolic Nature Rift', angle: Math.PI / 2 },
      { name: '4. Species-Being Essence', angle: Math.PI }
    ];

    // Concentric grid webs
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    [0.25, 0.50, 0.75, 1.0].forEach(rRatio => {
      ctx.beginPath();
      axes.forEach((ax, idx) => {
        const x = cx + Math.cos(ax.angle) * radius * rRatio;
        const y = cy + Math.sin(ax.angle) * radius * rRatio;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.stroke();
    });

    // Radial spokes & labels
    ctx.font = '10px -apple-system, sans-serif';
    axes.forEach(ax => {
      const x = cx + Math.cos(ax.angle) * radius;
      const y = cy + Math.sin(ax.angle) * radius;
      ctx.beginPath();
      ctx.strokeStyle = '#334155';
      ctx.moveTo(cx, cy);
      ctx.lineTo(x, y);
      ctx.stroke();

      // Label
      const lx = cx + Math.cos(ax.angle) * (radius + 16);
      const ly = cy + Math.sin(ax.angle) * (radius + 14);
      ctx.fillStyle = '#94a3b8';
      ctx.textAlign = Math.abs(Math.cos(ax.angle)) < 0.2 ? 'center' : (Math.cos(ax.angle) > 0 ? 'left' : 'right');
      ctx.fillText(ax.name, lx, ly);
    });

    // Plot Profiles: Proletariat vs Customary Serf vs Bourgeoisie
    const profiles = [
      { name: 'Wage Proletariat', values: [0.85, 0.78, 0.72, 0.88], color: '#ef4444' },
      { name: 'Customary Serf', values: [0.45, 0.35, 0.20, 0.30], color: '#10b981' },
      { name: 'Ruling Elite', values: [0.10, 0.08, 0.15, 0.12], color: '#f59e0b' }
    ];

    profiles.forEach(prof => {
      ctx.beginPath();
      prof.values.forEach((val, idx) => {
        const ax = axes[idx];
        const rVal = radius * val;
        const x = cx + Math.cos(ax.angle) * rVal;
        const y = cy + Math.sin(ax.angle) * rVal;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.fillStyle = prof.color + '33';
      ctx.fill();
      ctx.strokeStyle = prof.color;
      ctx.lineWidth = 1.8;
      ctx.stroke();
    });

    // Legend
    let legX = 14;
    ctx.font = '10px -apple-system, sans-serif';
    profiles.forEach(prof => {
      ctx.fillStyle = prof.color;
      ctx.fillRect(legX, h - 16, 10, 10);
      ctx.fillStyle = '#cbd5e1';
      ctx.textAlign = 'left';
      ctx.fillText(prof.name, legX + 14, h - 8);
      legX += ctx.measureText(prof.name).width + 28;
    });

    ctx.restore();
  }

  function drawRebellionAttractor(canvas, shiftHours = 12.0, consciousness = 0.55, dpr = 1) {
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

    // Title
    ctx.fillStyle = '#f1f5f9';
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('⚡ The Rebellion Attractor: 2D Phase-Space Dynamic Plot', 14, 18);

    const padL = 44;
    const padR = 20;
    const padT = 32;
    const padB = 32;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // Grid box
    ctx.strokeStyle = '#2b3347';
    ctx.strokeRect(padL, padT, plotW, plotH);

    // Axes range: X = 8h to 16h (shift length); Y = 0.0 to 1.0 (consciousness)
    const minH = 8.0, maxH = 16.0;

    // Danger Zone / Hazard Attractor where shift > 10.0h and consciousness > 0.40
    const hzX = padL + ((10.0 - minH) / (maxH - minH)) * plotW;
    const hzY = padT + (1.0 - 1.0) * plotH;
    const hzW = padL + plotW - hzX;
    const hzH = (1.0 - 0.40) * plotH;

    ctx.fillStyle = 'rgba(239, 68, 68, 0.16)';
    ctx.fillRect(hzX, hzY, hzW, hzH);
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.strokeRect(hzX, hzY, hzW, hzH);
    ctx.setLineDash([]);

    ctx.fillStyle = '#ef4444';
    ctx.font = 'bold 9px -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('🔥 STRIKE & SABOTAGE ATTRACTOR ZONE', padL + plotW - 6, padT + 14);

    // Trajectory vector simulation line
    ctx.beginPath();
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    const traj = [
      [8.5, 0.15], [9.2, 0.22], [10.5, 0.32], [11.8, 0.44], [shiftHours, consciousness]
    ];
    traj.forEach(([sh, co], idx) => {
      const px = padL + ((sh - minH) / (maxH - minH)) * plotW;
      const py = padT + (1.0 - co) * plotH;
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // Current State Point with Pulse Halo
    const curX = padL + ((shiftHours - minH) / (maxH - minH)) * plotW;
    const curY = padT + (1.0 - consciousness) * plotH;

    const inDanger = shiftHours > 10.0 && consciousness > 0.40;
    const ptCol = inDanger ? '#ef4444' : '#38bdf8';

    ctx.beginPath();
    ctx.arc(curX, curY, 8, 0, Math.PI * 2);
    ctx.fillStyle = inDanger ? 'rgba(239, 68, 68, 0.3)' : 'rgba(56, 189, 248, 0.3)';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(curX, curY, 4, 0, Math.PI * 2);
    ctx.fillStyle = ptCol;
    ctx.fill();

    // Labels
    ctx.font = '9px -apple-system, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.textAlign = 'center';
    ctx.fillText('8h', padL, padT + plotH + 14);
    ctx.fillText('10h (Ten-Hour Cap)', padL + (2 / 8) * plotW, padT + plotH + 14);
    ctx.fillText('16h Workday Shift Length', padL + plotW / 2, padT + plotH + 24);
    ctx.fillText('16h', padL + plotW, padT + plotH + 14);

    ctx.textAlign = 'right';
    ctx.fillText('1.00 Consciousness', padL - 6, padT + 8);
    ctx.fillText('0.00', padL - 6, padT + plotH);

    ctx.restore();
  }

  const CoCVisRadarAttractor = Object.freeze({ drawAlienationRadar, drawRebellionAttractor });
  root.CoCVisRadarAttractor = CoCVisRadarAttractor;
  root.RegnumVisRadarAttractor = CoCVisRadarAttractor;
})(typeof globalThis !== 'undefined' ? globalThis : window);
