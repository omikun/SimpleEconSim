// Pointy-top axial hex geometry shared by map rendering and pointer hit testing.
(function (root) {
  'use strict';

  const SQRT3 = Math.sqrt(3.0);

  function axialToPixel(q, r, size) {
    return {
      x: size * (SQRT3 * q + (SQRT3 / 2.0) * r),
      y: size * (1.5 * r)
    };
  }

  function axialRound(q, r) {
    const s = -q - r;
    let rq = Math.round(q);
    let rr = Math.round(r);
    const rs = Math.round(s);
    const dq = Math.abs(rq - q);
    const dr = Math.abs(rr - r);
    const ds = Math.abs(rs - s);
    if (dq > dr && dq > ds) rq = -rr - rs;
    else if (dr > ds) rr = -rq - rs;
    return { q: rq, r: rr };
  }

  function pixelToAxial(px, py, size) {
    const q = ((SQRT3 / 3.0) * px - (1.0 / 3.0) * py) / size;
    const r = ((2.0 / 3.0) * py) / size;
    return axialRound(q, r);
  }

  function drawHexPolygon(ctx, cx, cy, radius) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 180.0) * (60 * i - 30);
      const x = cx + radius * Math.cos(angle);
      const y = cy + radius * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  root.RegnumHexGeometry = Object.freeze({ axialToPixel, pixelToAxial, axialRound, drawHexPolygon });
})(typeof globalThis !== 'undefined' ? globalThis : window);
