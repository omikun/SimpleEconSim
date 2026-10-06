/**
 * voronoi_geometry.js — Irregular Voronoi Polygon Geometry, Hit-Testing & Vector Rendering
 * Provides high-performance 2D/3D polygon utilities for Mapgen2 Voronoi cell geopolitics:
 * - Point-in-polygon ray-casting test for irregular multi-sided territories
 * - Axis-aligned bounding box (AABB) spatial rejection filter
 * - Geometric centroid and area computation
 * - Optimized Canvas2D polygon boundary path generation
 */
(function (root) {
  'use strict';

  /**
   * Ray-casting algorithm to test whether point (px, py) is strictly inside a polygon.
   * @param {number} px
   * @param {number} py
   * @param {Array<[number, number]>} vertices
   * @returns {boolean}
   */
  function pointInPolygon(px, py, vertices) {
    if (!vertices || vertices.length < 3) return false;
    let inside = false;
    const n = vertices.length;

    for (let i = 0, j = n - 1; i < n; j = i++) {
      const xi = vertices[i][0], yi = vertices[i][1];
      const xj = vertices[j][0], yj = vertices[j][1];

      const intersect = ((yi > py) !== (yj > py)) &&
        (px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-9) + xi);

      if (intersect) inside = !inside;
    }
    return inside;
  }

  /**
   * Compute Axis-Aligned Bounding Box (AABB) for quick spatial rejection.
   * @param {Array<[number, number]>} vertices
   * @returns {{minX: number, minY: number, maxX: number, maxY: number}}
   */
  function polygonBBox(vertices) {
    if (!vertices || vertices.length === 0) {
      return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
    }
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    for (let i = 0; i < vertices.length; i++) {
      const x = vertices[i][0];
      const y = vertices[i][1];
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    return { minX, minY, maxX, maxY };
  }

  /**
   * Compute the geometric centroid of a 2D polygon.
   * @param {Array<[number, number]>} vertices
   * @returns {[number, number]} [cx, cy]
   */
  function polygonCentroid(vertices) {
    if (!vertices || vertices.length === 0) return [0, 0];
    if (vertices.length === 1) return [vertices[0][0], vertices[0][1]];
    if (vertices.length === 2) {
      return [(vertices[0][0] + vertices[1][0]) / 2, (vertices[0][1] + vertices[1][1]) / 2];
    }

    let area = 0.0;
    let cx = 0.0;
    let cy = 0.0;
    const n = vertices.length;

    for (let i = 0, j = n - 1; i < n; j = i++) {
      const p1 = vertices[j];
      const p2 = vertices[i];
      const f = p1[0] * p2[1] - p2[0] * p1[1];
      area += f;
      cx += (p1[0] + p2[0]) * f;
      cy += (p1[1] + p2[1]) * f;
    }

    area *= 0.5;
    if (Math.abs(area) < 1e-6) {
      // Fallback to vertex average
      let sx = 0, sy = 0;
      for (const v of vertices) { sx += v[0]; sy += v[1]; }
      return [sx / n, sy / n];
    }

    cx /= (6.0 * area);
    cy /= (6.0 * area);
    return [cx, cy];
  }

  /**
   * Render a closed polygon path on a Canvas2D rendering context.
   * @param {CanvasRenderingContext2D} ctx
   * @param {Array<[number, number]>} screenPoints
   */
  function drawPolygonPath(ctx, screenPoints) {
    if (!ctx || !screenPoints || screenPoints.length < 3) return;
    ctx.beginPath();
    ctx.moveTo(screenPoints[0][0], screenPoints[0][1]);
    for (let i = 1; i < screenPoints.length; i++) {
      ctx.lineTo(screenPoints[i][0], screenPoints[i][1]);
    }
    ctx.closePath();
  }

  const CoCVoronoiGeometry = Object.freeze({
    pointInPolygon,
    polygonBBox,
    polygonCentroid,
    drawPolygonPath
  });

  root.CoCVoronoiGeometry = CoCVoronoiGeometry;
  root.RegnumVoronoiGeometry = CoCVoronoiGeometry;
})(typeof globalThis !== 'undefined' ? globalThis : window);
