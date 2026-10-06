/**
 * projection_3d.js — True 35mm Perspective Projection & 3D Frustum Camera Engine
 * Provides 100% feature parity with the desktop client's 3D perspective pipeline:
 * - 45° vertical FOV perspective projection matrix with 35mm lens characteristics
 * - Dynamic Civ-style zoom tilt: S-curve transition from 89° overview to 52° 3D tilt
 * - 6-Plane frustum clipping in homogeneous clip coordinates (-w <= x, y, z <= w)
 * - 3D ray unprojection for ray-terrain elevation surface picking
 */
(function (root) {
  'use strict';

  // ---------------- 4x4 Matrix Mathematics ----------------

  function mat4Create() {
    return new Float32Array([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1
    ]);
  }

  function mat4Multiply(a, b) {
    const out = new Float32Array(16);
    for (let row = 0; row < 4; row++) {
      for (let col = 0; col < 4; col++) {
        let sum = 0;
        for (let i = 0; i < 4; i++) {
          sum += a[row * 4 + i] * b[i * 4 + col];
        }
        out[row * 4 + col] = sum;
      }
    }
    return out;
  }

  function mat4Perspective(fovyRad, aspect, near, far) {
    const f = 1.0 / Math.tan(fovyRad / 2.0);
    const nf = 1.0 / (near - far);
    const out = new Float32Array(16);
    out[0] = f / aspect;
    out[5] = f;
    out[10] = (far + near) * nf;
    out[11] = (2.0 * far * near) * nf;
    out[14] = -1.0;
    out[15] = 0.0;
    return out;
  }

  function mat4LookAt(eye, target, up) {
    let zx = eye[0] - target[0];
    let zy = eye[1] - target[1];
    let zz = eye[2] - target[2];
    let zLen = Math.hypot(zx, zy, zz);
    if (zLen > 1e-6) { zx /= zLen; zy /= zLen; zz /= zLen; }

    let xx = up[1] * zz - up[2] * zy;
    let xy = up[2] * zx - up[0] * zz;
    let xz = up[0] * zy - up[1] * zx;
    let xLen = Math.hypot(xx, xy, xz);
    if (xLen > 1e-6) { xx /= xLen; xy /= xLen; xz /= xLen; }

    const yx = zy * xz - zz * xy;
    const yy = zz * xx - zx * xz;
    const yz = zx * xy - zy * xx;

    const out = new Float32Array(16);
    out[0] = xx; out[1] = xy; out[2] = xz;
    out[3] = -(xx * eye[0] + xy * eye[1] + xz * eye[2]);

    out[4] = yx; out[5] = yy; out[6] = yz;
    out[7] = -(yx * eye[0] + yy * eye[1] + yz * eye[2]);

    out[8] = zx; out[9] = zy; out[10] = zz;
    out[11] = -(zx * eye[0] + zy * eye[1] + zz * eye[2]);

    out[12] = 0; out[13] = 0; out[14] = 0; out[15] = 1;
    return out;
  }

  function mat4Invert(m) {
    const inv = new Float32Array(16);
    const m00 = m[0], m01 = m[1], m02 = m[2], m03 = m[3];
    const m10 = m[4], m11 = m[5], m12 = m[6], m13 = m[7];
    const m20 = m[8], m21 = m[9], m22 = m[10], m23 = m[11];
    const m30 = m[12], m31 = m[13], m32 = m[14], m33 = m[15];

    inv[0] = m11 * m22 * m33 - m11 * m23 * m32 - m21 * m12 * m33 + m21 * m13 * m32 + m31 * m12 * m23 - m31 * m13 * m22;
    inv[4] = -m10 * m22 * m33 + m10 * m23 * m32 + m20 * m12 * m33 - m20 * m13 * m32 - m30 * m12 * m23 + m30 * m13 * m22;
    inv[8] = m10 * m21 * m33 - m10 * m23 * m31 - m20 * m11 * m33 + m20 * m13 * m31 + m30 * m11 * m23 - m30 * m13 * m21;
    inv[12] = -m10 * m21 * m32 + m10 * m22 * m31 + m20 * m11 * m32 - m20 * m12 * m31 - m30 * m11 * m22 + m30 * m12 * m21;
    inv[1] = -m01 * m22 * m33 + m01 * m23 * m32 + m21 * m02 * m33 - m21 * m03 * m32 - m31 * m02 * m23 + m31 * m03 * m22;
    inv[5] = m00 * m22 * m33 - m00 * m23 * m32 - m20 * m02 * m33 + m20 * m03 * m32 + m30 * m02 * m23 - m30 * m03 * m22;
    inv[9] = -m00 * m21 * m33 + m00 * m23 * m31 + m20 * m01 * m33 - m20 * m03 * m31 - m30 * m01 * m23 + m30 * m03 * m21;
    inv[13] = m00 * m21 * m32 - m00 * m22 * m31 - m20 * m01 * m32 + m20 * m02 * m31 + m30 * m01 * m22 - m30 * m02 * m21;
    inv[2] = m01 * m12 * m33 - m01 * m13 * m32 - m11 * m02 * m33 + m11 * m03 * m32 + m31 * m02 * m13 - m31 * m03 * m12;
    inv[6] = -m00 * m12 * m33 + m00 * m13 * m32 + m10 * m02 * m33 - m10 * m03 * m32 - m30 * m02 * m13 + m30 * m03 * m12;
    inv[10] = m00 * m11 * m33 - m00 * m13 * m31 - m10 * m01 * m33 + m10 * m03 * m31 + m30 * m01 * m13 - m30 * m03 * m11;
    inv[14] = -m00 * m11 * m32 + m00 * m12 * m31 + m10 * m01 * m32 - m10 * m02 * m31 - m30 * m01 * m12 + m30 * m02 * m11;
    inv[3] = -m01 * m12 * m23 + m01 * m13 * m22 + m11 * m02 * m23 - m11 * m03 * m22 - m21 * m02 * m13 + m21 * m03 * m12;
    inv[7] = m00 * m12 * m23 - m00 * m13 * m22 - m10 * m02 * m23 + m10 * m03 * m22 + m20 * m02 * m13 - m20 * m03 * m12;
    inv[11] = -m00 * m11 * m23 + m00 * m13 * m21 + m10 * m01 * m23 - m10 * m03 * m21 - m20 * m01 * m13 + m20 * m03 * m11;
    inv[15] = m00 * m11 * m22 - m00 * m12 * m21 - m10 * m01 * m22 + m10 * m02 * m21 + m20 * m01 * m12 - m20 * m02 * m11;

    let det = m00 * inv[0] + m01 * inv[4] + m02 * inv[8] + m03 * inv[12];
    if (Math.abs(det) < 1e-8) return null;
    const invDet = 1.0 / det;
    for (let i = 0; i < 16; i++) inv[i] *= invDet;
    return inv;
  }

  // ---------------- Camera & MVP Computation ----------------

  /**
   * Replicates desktop S-curve interpolation between overview (89°) and close-up (52°).
   * @param {number} zoom
   * @returns {{pitch: number, yaw: number}}
   */
  function computePitchYaw(zoom) {
    const t = Math.max(0.0, Math.min(1.0, (zoom - 0.90) / (2.20 - 0.90)));
    const ts = t * t * (3.0 - 2.0 * t);
    const pitch = 89.0 - ts * (89.0 - 52.0);
    const yaw = 0.0 + ts * 9.0;
    return { pitch, yaw };
  }

  /**
   * Compute 35mm regular perspective MVP matrix matching desktop camera.py
   * @param {Object} cam
   * @param {number} vw Viewport width
   * @param {number} vh Viewport height
   * @returns {Float32Array} 4x4 MVP matrix
   */
  function getCameraMVP(cam, vw, vh) {
    const pitch = Number(cam.pitch !== undefined ? cam.pitch : 52.0);
    const yaw = Number(cam.yaw !== undefined ? cam.yaw : 9.0);
    const zoom = Math.max(0.2, Number(cam.zoom || 1.0));
    const tx = Number(cam.target_x !== undefined ? cam.target_x : 512.0);
    const ty = Number(cam.target_y !== undefined ? cam.target_y : 512.0);

    const target = [tx, ty, 0.0];
    const pRad = (pitch * Math.PI) / 180.0;
    const yRad = (yaw * Math.PI) / 180.0;

    let vx = Math.sin(yRad) * Math.cos(pRad);
    let vy = -Math.cos(yRad) * Math.cos(pRad);
    let vz = Math.sin(pRad);
    const vNorm = Math.hypot(vx, vy, vz) || 1.0;
    vx /= vNorm; vy /= vNorm; vz /= vNorm;

    const tPitch = Math.max(0.0, Math.min(1.0, (89.0 - pitch) / (89.0 - 52.0)));
    const baseDist = 1100.0 - tPitch * (1100.0 - 760.0);
    const dist = baseDist / zoom;
    const eye = [target[0] + vx * dist, target[1] + vy * dist, target[2] + vz * dist];

    const aspect = Math.max(0.1, vw / Math.max(1.0, vh));
    const fovyRad = (45.0 * Math.PI) / 180.0; // 35mm perspective

    const proj = mat4Perspective(fovyRad, aspect, 10.0, 25000.0);
    const view = mat4LookAt(eye, target, [0.0, 0.0, 1.0]);
    return mat4Multiply(proj, view);
  }

  // ---------------- Frustum Clipping & Projection ----------------

  /**
   * Project a 3D point (wx, wy, wz) into 2D screen pixels.
   * @param {Float32Array} mvp
   * @param {number} wx World X
   * @param {number} wy World Y
   * @param {number} wz World Z (elevation)
   * @param {number} vw Viewport Width
   * @param {number} vh Viewport Height
   * @returns {{x: number, y: number, valid: boolean}}
   */
  function projectPoint3D(mvp, wx, wy, wz, vw, vh) {
    const x = mvp[0] * wx + mvp[1] * wy + mvp[2] * wz + mvp[3];
    const y = mvp[4] * wx + mvp[5] * wy + mvp[6] * wz + mvp[7];
    const z = mvp[8] * wx + mvp[9] * wy + mvp[10] * wz + mvp[11];
    const w = mvp[12] * wx + mvp[13] * wy + mvp[14] * wz + mvp[15];

    if (w <= 1e-4) return { x: -9999, y: -9999, valid: false };

    const ndcX = x / w;
    const ndcY = y / w;

    const sx = Math.round((ndcX * 0.5 + 0.5) * vw);
    const sy = Math.round((1.0 - (ndcY * 0.5 + 0.5)) * vh);

    return { x: sx, y: sy, valid: true };
  }

  /**
   * Clip a 3D polygon to the 6 camera frustum planes in homogeneous coordinates
   * (-w <= x, y, z <= w) before perspective divide, matching desktop camera.py
   * @param {Float32Array} mvp
   * @param {Array<[number, number, number]>} pts3D Array of [x, y, z] points
   * @param {number} vw Viewport Width
   * @param {number} vh Viewport Height
   * @returns {Array<[number, number]>} Clipped screen polygon points
   */
  function projectPolygon3D(mvp, pts3D, vw, vh) {
    if (!pts3D || pts3D.length < 3) return [];

    let polygon = pts3D.map(([wx, wy, wz]) => [
      mvp[0] * wx + mvp[1] * wy + mvp[2] * wz + mvp[3],
      mvp[4] * wx + mvp[5] * wy + mvp[6] * wz + mvp[7],
      mvp[8] * wx + mvp[9] * wy + mvp[10] * wz + mvp[11],
      mvp[12] * wx + mvp[13] * wy + mvp[14] * wz + mvp[15]
    ]);

    // 6 Frustum planes: -w <= x <= w, -w <= y <= w, -w <= z <= w
    const planes = [
      { axis: 0, sign: 1 },  // Left:   x + w >= 0
      { axis: 0, sign: -1 }, // Right:  w - x >= 0
      { axis: 1, sign: 1 },  // Bottom: y + w >= 0
      { axis: 1, sign: -1 }, // Top:    w - y >= 0
      { axis: 2, sign: 1 },  // Near:   z + w >= 0
      { axis: 2, sign: -1 }  // Far:    w - z >= 0
    ];

    for (const { axis, sign } of planes) {
      if (polygon.length === 0) return [];
      const clipped = [];
      let prev = polygon[polygon.length - 1];
      let prevDist = prev[3] + sign * prev[axis];

      for (let i = 0; i < polygon.length; i++) {
        const cur = polygon[i];
        const curDist = cur[3] + sign * cur[axis];

        if ((prevDist >= 0.0) !== (curDist >= 0.0)) {
          const frac = prevDist / (prevDist - curDist + 1e-9);
          clipped.push([
            prev[0] + frac * (cur[0] - prev[0]),
            prev[1] + frac * (cur[1] - prev[1]),
            prev[2] + frac * (cur[2] - prev[2]),
            prev[3] + frac * (cur[3] - prev[3])
          ]);
        }

        if (curDist >= 0.0) {
          clipped.push(cur);
        }

        prev = cur;
        prevDist = curDist;
      }
      polygon = clipped;
    }

    if (polygon.length < 3) return [];

    const screenPoints = [];
    for (const pt of polygon) {
      const w = pt[3];
      if (w <= 1e-4) continue;
      const ndcX = pt[0] / w;
      const ndcY = pt[1] / w;
      const sx = Math.round((ndcX * 0.5 + 0.5) * vw);
      const sy = Math.round((1.0 - (ndcY * 0.5 + 0.5)) * vh);
      screenPoints.push([sx, sy]);
    }

    return screenPoints.length >= 3 ? screenPoints : [];
  }

  /**
   * Unproject screen pixel (sx, sy) to world near and far points for ray-terrain intersection.
   * @param {number} sx Screen X
   * @param {number} sy Screen Y
   * @param {Float32Array} mvp Matrix
   * @param {number} vw Viewport Width
   * @param {number} vh Viewport Height
   * @returns {{near: [number, number, number], far: [number, number, number], dir: [number, number, number]}|null}
   */
  function screenToWorldRay(sx, sy, mvp, vw, vh) {
    const invMVP = mat4Invert(mvp);
    if (!invMVP) return null;

    const ndcX = (sx / vw) * 2.0 - 1.0;
    const ndcY = 1.0 - (sy / vh) * 2.0;

    function unprojectPoint(nx, ny, nz) {
      const x = invMVP[0] * nx + invMVP[1] * ny + invMVP[2] * nz + invMVP[3];
      const y = invMVP[4] * nx + invMVP[5] * ny + invMVP[6] * nz + invMVP[7];
      const z = invMVP[8] * nx + invMVP[9] * ny + invMVP[10] * nz + invMVP[11];
      const w = invMVP[12] * nx + invMVP[13] * ny + invMVP[14] * nz + invMVP[15];
      const safeW = Math.abs(w) > 1e-6 ? w : 1.0;
      return [x / safeW, y / safeW, z / safeW];
    }

    const near = unprojectPoint(ndcX, ndcY, -1.0);
    const far = unprojectPoint(ndcX, ndcY, 1.0);

    const dx = far[0] - near[0];
    const dy = far[1] - near[1];
    const dz = far[2] - near[2];
    const len = Math.hypot(dx, dy, dz) || 1.0;

    return {
      origin: near,
      near,
      far,
      dir: [dx / len, dy / len, dz / len]
    };
  }

  /**
   * Intersect a 3D ray (origin, dir) with a horizontal world plane z = planeZ
   * @param {[number, number, number]} origin
   * @param {[number, number, number]} dir
   * @param {number} planeZ
   * @returns {{x: number, y: number, z: number}|null}
   */
  function intersectRayPlane(origin, dir, planeZ) {
    if (!origin || !dir || Math.abs(dir[2]) < 1e-6) return null;
    const t = (planeZ - origin[2]) / dir[2];
    if (t < 0) return null;
    return {
      x: origin[0] + dir[0] * t,
      y: origin[1] + dir[1] * t,
      z: planeZ
    };
  }

  const CoCProjection3D = Object.freeze({
    mat4Create,
    mat4Multiply,
    mat4Perspective,
    mat4LookAt,
    mat4Invert,
    computePitchYaw,
    getCameraMVP,
    projectPoint3D,
    projectPolygon3D,
    screenToWorldRay,
    intersectRayPlane
  });

  root.CoCProjection3D = CoCProjection3D;
  root.RegnumProjection3D = CoCProjection3D;
})(typeof globalThis !== 'undefined' ? globalThis : window);
