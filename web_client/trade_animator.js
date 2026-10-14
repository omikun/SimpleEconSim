/**
 * trade_animator.js — Decoupled 60fps Overland Trade Network & Flow Animator
 * Provides high-performance vector trade routing and smooth time-based commodity particle flows.
 */
(function (root) {
  'use strict';

  const hexGeo = root.CoCHexGeometry;
  const { axialToPixel } = hexGeo || {};

  function getTilePos(tile, hexRadius, projectFn) {
    if (!tile) return null;
    if (typeof projectFn === 'function') {
      const pt = projectFn(tile);
      if (pt && (pt.valid !== false)) return pt;
      return null;
    }
    if (tile.centroid && Array.isArray(tile.centroid)) {
      return { x: tile.centroid[0], y: tile.centroid[1] };
    }
    if (tile.q !== undefined && tile.r !== undefined && typeof axialToPixel === 'function') {
      return axialToPixel(tile.q, tile.r, hexRadius);
    }
    return null;
  }

  /**
   * Draw static overland trade route lines between connected territories.
   * @param {CanvasRenderingContext2D} ctx
   * @param {Object} tradeNetwork
   * @param {Map} tileByName
   * @param {number} hexRadius
   * @param {number} camZoom
   * @param {Function} [projectFn] Optional custom 3D projection function
   */
  function drawTradeRoutes(ctx, tradeNetwork, tileByName, hexRadius, camZoom, projectFn) {
    if (!tradeNetwork || !tradeNetwork.edges || tradeNetwork.edges.length === 0) return;

    ctx.save();
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.45)';
    ctx.lineWidth = Math.max(1.0, 1.6 / (camZoom || 1.0));

    ctx.beginPath();
    tradeNetwork.edges.forEach(edge => {
      const t1 = tileByName.get(edge.from);
      const t2 = tileByName.get(edge.to);
      if (t1 && t2) {
        const p1 = getTilePos(t1, hexRadius, projectFn);
        const p2 = getTilePos(t2, hexRadius, projectFn);
        if (p1 && p2) {
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
        }
      }
    });
    ctx.stroke();
    ctx.restore();
  }

  /**
   * Draw animated commodity trade flow particles along routes using wall-clock time.
   * @param {CanvasRenderingContext2D} ctx
   * @param {Object} tradeNetwork
   * @param {Map} tileByName
   * @param {number} hexRadius
   * @param {number} camZoom
   * @param {number} timestamp
   * @param {Function} [projectFn] Optional custom 3D projection function
   */
  function drawTradeFlowParticles(ctx, tradeNetwork, tileByName, hexRadius, camZoom, timestamp, projectFn) {
    if (!tradeNetwork || !tradeNetwork.flows || tradeNetwork.flows.length === 0) return;

    // Smooth 1.8-second continuous cycle
    const cycleDuration = 1800;
    const phase = (timestamp % cycleDuration) / cycleDuration;

    ctx.save();
    tradeNetwork.flows.forEach(flow => {
      const t1 = tileByName.get(flow.from);
      const t2 = tileByName.get(flow.to);
      if (!t1 || !t2) return;

      const p1 = getTilePos(t1, hexRadius, projectFn);
      const p2 = getTilePos(t2, hexRadius, projectFn);
      if (!p1 || !p2) return;

      const start = flow.forward ? p1 : p2;
      const end = flow.forward ? p2 : p1;

      // Primary particle
      const curX = start.x + (end.x - start.x) * phase;
      const curY = start.y + (end.y - start.y) * phase;
      const dotR = Math.max(2.0, Math.min(4.5, (flow.volume || 1.0) * 0.8)) / camZoom;

      // Glow halo
      ctx.beginPath();
      ctx.arc(curX, curY, dotR * 1.8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(56, 189, 248, 0.25)';
      ctx.fill();

      // Core particle
      ctx.beginPath();
      ctx.arc(curX, curY, dotR, 0, Math.PI * 2);
      ctx.fillStyle = '#38bdf8';
      ctx.fill();

      // Half-cycle offset secondary particle for denser routes
      if ((flow.volume || 0) > 2.0) {
        const phase2 = (phase + 0.5) % 1.0;
        const curX2 = start.x + (end.x - start.x) * phase2;
        const curY2 = start.y + (end.y - start.y) * phase2;

        ctx.beginPath();
        ctx.arc(curX2, curY2, dotR * 0.8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(56, 189, 248, 0.85)';
        ctx.fill();
      }
    });
    ctx.restore();
  }

  /**
   * Create an independent animation ticker that dispatches smooth 60fps render requests.
   * @param {Function} onTick
   * @returns {Object} { start, stop, isRunning }
   */
  function createAnimationTicker(onTick) {
    let animId = null;
    let running = false;

    function loop(time) {
      if (!running) return;
      onTick(time);
      animId = requestAnimationFrame(loop);
    }

    return {
      start() {
        if (running) return;
        running = true;
        animId = requestAnimationFrame(loop);
      },
      stop() {
        running = false;
        if (animId) {
          cancelAnimationFrame(animId);
          animId = null;
        }
      },
      isRunning() {
        return running;
      }
    };
  }

  const CoCTradeAnimator = Object.freeze({
    drawTradeRoutes,
    drawTradeFlowParticles,
    createAnimationTicker
  });
  root.CoCTradeAnimator = CoCTradeAnimator;
})(typeof globalThis !== 'undefined' ? globalThis : window);
