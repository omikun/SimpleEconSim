// WebGL terrain mesh renderer using the same vertex buffers as the desktop GPU path.
(function (root) {
  'use strict';

  const VERTEX_SHADER = `#version 300 es
    in vec3 in_pos; in vec3 in_norm; in vec3 in_color; in float in_elev;
    uniform mat4 u_mvp;
    out vec3 v_pos; out vec3 v_norm; out vec3 v_color; out float v_elev;
    void main() {
      v_pos = in_pos; v_norm = normalize(in_norm); v_color = in_color; v_elev = in_elev;
      gl_Position = u_mvp * vec4(in_pos, 1.0);
    }`;

  const FRAGMENT_SHADER = `#version 300 es
    precision highp float;
    in vec3 v_pos; in vec3 v_norm; in vec3 v_color; in float v_elev;
    uniform bool u_water; uniform vec3 u_eye; uniform vec3 u_sun_dir;
    out vec4 frag_color;
    const float PI = 3.141592653589793;
    float oren_nayar(vec3 N, vec3 L, vec3 V, float roughness) {
      float nl = dot(N,L), nv = dot(N,V), s = max(0.0,nl);
      if (s <= 0.0) return 0.0;
      float sigma2 = roughness * roughness;
      float A = 1.0 - 0.5 * sigma2 / (sigma2 + 0.33);
      float B = 0.45 * sigma2 / (sigma2 + 0.09);
      vec3 lp = normalize(L - N * nl + vec3(1e-5));
      vec3 vp = normalize(V - N * nv + vec3(1e-5));
      float cosPhi = max(0.0,dot(lp,vp));
      float ti = acos(clamp(nl,0.0,0.999));
      float tr = acos(clamp(nv,0.001,0.999));
      float sinAlpha = (ti >= tr) ? sin(ti) : sin(tr);
      float tanBeta = clamp((ti >= tr) ? tan(tr) : tan(ti),0.0,5.0);
      return s * (A + B * cosPhi * sinAlpha * tanBeta);
    }
    float distributionGGX(vec3 N, vec3 H, float roughness) {
      float a = roughness * roughness, a2 = a * a;
      float nh = max(dot(N,H),0.0), nh2 = nh * nh;
      float d = nh2 * (a2 - 1.0) + 1.0;
      return a2 / max(PI * d * d, 1e-7);
    }
    float geometrySchlick(float nv, float roughness) {
      float r = roughness + 1.0, k = r*r/8.0;
      return nv / (nv*(1.0-k)+k);
    }
    float geometrySmith(vec3 N, vec3 V, vec3 L, float roughness) {
      return geometrySchlick(max(dot(N,V),0.0),roughness) * geometrySchlick(max(dot(N,L),0.0),roughness);
    }
    vec3 fresnelSchlick(float cosine, vec3 F0) {
      return F0 + (1.0-F0)*pow(clamp(1.0-cosine,0.0,1.0),5.0);
    }
    void main() {
      if (u_water) { frag_color = vec4(0.04, 0.18, 0.35, 1.0); return; }
      vec3 n = normalize(v_norm);
      float slope = 1.0 - max(0.0, n.z);
      vec3 base = v_color;
      if (slope > 0.45) {
        float strata = sin(v_pos.z * 1.8) * 0.5 + 0.5;
        base = mix(base, mix(vec3(0.48,0.44,0.40), vec3(0.38,0.34,0.30), strata), smoothstep(0.45,0.75,slope)*0.65);
      }
      float snow = smoothstep(0.70, 0.82, v_elev) * (1.0 - smoothstep(0.65,0.90,slope));
      base = mix(base, vec3(0.95,0.97,1.0), snow);
      vec3 L = normalize(u_sun_dir), V = normalize(u_eye-v_pos), H = normalize(L+V);
      float roughness = 0.92;
      float diffuse = oren_nayar(n,L,V,roughness);
      vec3 F0 = mix(vec3(0.04),base,0.1);
      vec3 F = fresnelSchlick(max(dot(H,V),0.0),F0);
      vec3 spec = distributionGGX(n,H,roughness) * geometrySmith(n,V,L,roughness) * F;
      spec /= max(4.0*max(dot(n,V),0.0)*max(dot(n,L),0.0),0.001);
      vec3 kd = vec3(1.0)-F;
      float fill = max(0.0,dot(n,normalize(vec3(0.45,-0.65,0.60)))) * 0.22;
      vec3 color = 0.45*vec3(0.55,0.62,0.72)*base;
      color += fill*vec3(0.70,0.80,0.90)*base;
      color += (kd*base*diffuse + spec*0.45)*1.15*vec3(1.0,0.96,0.88);
      frag_color = vec4(clamp(color,0.0,1.0),1.0);
    }`;

  function shader(gl, type, source) {
    const result = gl.createShader(type);
    gl.shaderSource(result, source);
    gl.compileShader(result);
    if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(result));
    return result;
  }

  function createProgram(gl) {
    const program = gl.createProgram();
    gl.attachShader(program, shader(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
    gl.attachShader(program, shader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    return program;
  }

  function createTerrainRenderer(onReady = () => {}) {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2', { alpha: false, antialias: true });
    if (!gl) return { draw: () => false, get ready() { return false; } };
    let program;
    let buffers = [];
    let counts = [];
    let ready = false;
    let failed = false;
    let started = false;
    let lastFrame = '';

    function loadMesh() {
      if (started) return;
      started = true;
      fetch('/api/terrain-mesh.bin').then(response => {
      if (!response.ok) throw new Error(`Terrain mesh request failed (${response.status})`);
      return response.arrayBuffer();
    }).then(data => {
      const view = new DataView(data);
      counts = Array.from({ length: 4 }, (_, i) => view.getUint32(i * 4, true) / 10);
      let offset = 16;
      const lengths = counts.map(count => count * 10);
      program = createProgram(gl);
      for (const length of lengths) {
        const vertices = new Float32Array(data, offset, length);
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
        buffers.push(buffer);
        offset += length * 4;
      }
      ready = true;
      onReady();
      }).catch(error => {
        failed = true;
        console.error('Desktop terrain mesh unavailable:', error);
        onReady();
      });
    }

    function draw(ctx, camera, width, height, getMvp) {
      loadMesh();
      if (!ready || failed) return false;
      const key = `${width}:${height}:${camera.pitch}:${camera.yaw}:${camera.zoom}:${camera.target_x}:${camera.target_y}`;
      if (key !== lastFrame) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
        gl.enable(gl.DEPTH_TEST);
        gl.depthFunc(gl.LEQUAL);
        gl.clearColor(0.04, 0.12, 0.24, 1);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        gl.useProgram(program);
        const matrix = getMvp(camera, width, height);
        const columnMajor = new Float32Array(16);
        for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
          columnMajor[col * 4 + row] = matrix[row * 4 + col];
        }
        gl.uniformMatrix4fv(gl.getUniformLocation(program, 'u_mvp'), false, columnMajor);
        const pitch = camera.pitch * Math.PI / 180, yaw = camera.yaw * Math.PI / 180;
        const direction = [Math.sin(yaw)*Math.cos(pitch), -Math.cos(yaw)*Math.cos(pitch), Math.sin(pitch)];
        const tPitch = Math.max(0, Math.min(1, (89 - camera.pitch) / 37));
        const distance = (1100 - tPitch * 340) / camera.zoom;
        const eye = [camera.target_x + direction[0]*distance, camera.target_y + direction[1]*distance, direction[2]*distance];
        gl.uniform3fv(gl.getUniformLocation(program, 'u_eye'), eye);
        const az = -45*Math.PI/180, el = 24*Math.PI/180;
        gl.uniform3fv(gl.getUniformLocation(program, 'u_sun_dir'), [Math.cos(el)*Math.cos(az), Math.cos(el)*Math.sin(az), Math.sin(el)]);
        const waterUniform = gl.getUniformLocation(program, 'u_water');
        const locations = ['in_pos', 'in_norm', 'in_color', 'in_elev'].map(name => gl.getAttribLocation(program, name));
        const stride = 10 * 4;
        const drawMesh = (index, water = false, blend = false) => {
          gl.bindBuffer(gl.ARRAY_BUFFER, buffers[index]);
          for (let i = 0; i < 4; i++) {
            const size = i === 3 ? 1 : 3;
            gl.enableVertexAttribArray(locations[i]);
            gl.vertexAttribPointer(locations[i], size, gl.FLOAT, false, stride, [0, 12, 24, 36][i]);
          }
          gl.uniform1i(waterUniform, water ? 1 : 0);
          if (blend) gl.enable(gl.BLEND);
          gl.drawArrays(gl.TRIANGLES, 0, counts[index]);
          if (blend) gl.disable(gl.BLEND);
        };

        // Desktop scene order: ocean, terrain, trees, rivers, then coastal surf.
        const ocean = new Float32Array([
          -1500,-1500,-0.35, 2524,-1500,-0.35, -1500,2524,-0.35,
          -1500,2524,-0.35, 2524,-1500,-0.35, 2524,2524,-0.35
        ]);
        const oceanBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, oceanBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, ocean, gl.STATIC_DRAW);
        gl.vertexAttribPointer(locations[0], 3, gl.FLOAT, false, 12, 0);
        gl.enableVertexAttribArray(locations[0]);
        gl.disableVertexAttribArray(locations[1]); gl.disableVertexAttribArray(locations[2]);
        gl.disableVertexAttribArray(locations[3]);
        gl.uniform1i(waterUniform, 1);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
        gl.enableVertexAttribArray(locations[1]); gl.enableVertexAttribArray(locations[2]);
        gl.enableVertexAttribArray(locations[3]);
        drawMesh(0);
        drawMesh(1);
        drawMesh(2, false, true);
        drawMesh(3, false, true);
        gl.deleteBuffer(oceanBuffer);
        lastFrame = key;
      }
      ctx.drawImage(canvas, 0, 0, width, height);
      return true;
    }

    return Object.freeze({ draw, get ready() { return ready; }, get failed() { return failed; } });
  }

  root.CoCTerrainRenderer = Object.freeze({ createTerrainRenderer });
})(typeof window !== 'undefined' ? window : globalThis);
