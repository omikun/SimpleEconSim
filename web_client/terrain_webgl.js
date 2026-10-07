// WebGL terrain mesh renderer using the same vertex buffers as the desktop GPU path.
(function (root) {
  'use strict';

  const VERTEX_SHADER = `#version 300 es
    in vec3 in_pos; in vec3 in_norm; in vec3 in_color; in float in_elev;
    uniform mat4 u_mvp; uniform mat4 u_view; uniform mat4 u_shadow_matrix;
    uniform vec3 u_sun_dir;
    out vec3 v_norm; out vec3 v_world_norm; out vec3 v_world_pos;
    out vec3 v_color; out float v_elev; out vec4 v_shadow_coord;
    out vec3 v_sun_dir; out vec3 v_fill_dir;
    void main() {
      v_world_pos = in_pos; v_world_norm = normalize(in_norm);
      v_color = in_color; v_elev = in_elev;
      v_shadow_coord = u_shadow_matrix * vec4(in_pos, 1.0);
      mat3 normal_matrix = mat3(u_view);
      v_norm = normalize(normal_matrix * in_norm);
      v_sun_dir = normalize(normal_matrix * u_sun_dir);
      v_fill_dir = normalize(normal_matrix * vec3(0.45, -0.65, 0.60));
      gl_Position = u_mvp * vec4(in_pos, 1.0);
    }`;

  const FRAGMENT_SHADER = `#version 300 es
    precision highp float;
    in vec3 v_norm; in vec3 v_world_norm; in vec3 v_world_pos;
    in vec3 v_color; in float v_elev; in vec4 v_shadow_coord;
    in vec3 v_sun_dir; in vec3 v_fill_dir;
    uniform float u_sun_intensity; uniform float u_ambient_intensity;
    uniform float u_mountain_roughness; uniform float u_snow_threshold;
    uniform int u_shadow_mode; uniform float u_shadow_darkness;
    uniform vec3 u_sun_world_dir; uniform sampler2D u_shadow_map;
    uniform float u_shadow_size; uniform bool u_micropoly_strata;
    out vec4 frag_color;
    const float PI = 3.141592653589793;
    const vec2 POISSON_DISK[16] = vec2[](
      vec2(-0.326212,-0.405810), vec2(-0.840144,-0.073580),
      vec2(-0.695914,0.457137), vec2(-0.203345,0.620716),
      vec2(0.962340,-0.194983), vec2(0.473434,-0.480026),
      vec2(0.519456,0.767022), vec2(0.185461,-0.893124),
      vec2(0.507431,0.064425), vec2(0.896420,0.412458),
      vec2(-0.321940,-0.932615), vec2(-0.791559,-0.597710),
      vec2(-0.111818,-0.161108), vec2(0.282828,0.312918),
      vec2(-0.413812,0.183719), vec2(0.211412,-0.251918));
    float computeShadow(vec4 coord, vec3 N, vec3 L) {
      vec3 p = coord.xyz / coord.w;
      if (p.z > 1.0 || p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) return 1.0;
      float bias = max(0.0016 * (1.0 - max(dot(N,L),0.0)), 0.0004);
      float depth = p.z - bias;
      float blocker = texture(u_shadow_map,p.xy).r;
      float penumbra = clamp(max(0.0,depth-blocker)*140.0,0.35,2.4);
      vec2 stepUV = vec2(penumbra/max(1024.0,u_shadow_size));
      float shadow = 0.0;
      for (int i=0;i<16;i++) shadow += texture(u_shadow_map,p.xy+POISSON_DISK[i]*stepUV).r >= depth ? 1.0 : 0.0;
      return shadow/16.0;
    }
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
      vec3 N = normalize(v_norm), L = normalize(v_sun_dir), V = vec3(0.0,0.0,1.0);
      vec3 H = normalize(L+V), base = v_color;
      float slope = 1.0-max(0.0,v_world_norm.z);
      if (v_elev > 0.0 && slope > 0.45 && u_micropoly_strata) {
        float strata = sin(v_world_pos.z*1.8)*0.5+0.5;
        vec3 rock = mix(vec3(0.48,0.44,0.40),vec3(0.38,0.34,0.30),strata);
        base = mix(base,rock,smoothstep(0.45,0.75,slope)*0.65);
      }
      float snow = smoothstep(u_snow_threshold,u_snow_threshold+0.12,v_elev)*(1.0-smoothstep(0.65,0.90,slope));
      if (v_elev > 0.0) base = mix(base,vec3(0.95,0.97,1.0),snow);
      float roughness = mix(0.55,0.92,u_mountain_roughness);
      if (v_elev <= 0.0) roughness = 0.18;
      float diffuse = oren_nayar(N,L,V,roughness);
      vec3 F0 = mix(vec3(0.04),base,0.1);
      if (v_elev <= 0.0) F0 = vec3(0.02);
      vec3 F = fresnelSchlick(max(dot(H,V),0.0),F0);
      vec3 spec = distributionGGX(N,H,roughness) * geometrySmith(N,V,L,roughness) * F;
      spec /= max(4.0*max(dot(N,V),0.0)*max(dot(N,L),0.0),0.001);
      vec3 kd = vec3(1.0)-F;
      float fill = max(0.0,dot(N,normalize(v_fill_dir))) * 0.22;
      float castShadow = u_shadow_mode == 1 ? computeShadow(v_shadow_coord,v_world_norm,normalize(u_sun_world_dir)) : 1.0;
      float shadow = mix(1.0,castShadow,clamp(u_shadow_darkness,0.0,1.0));
      vec3 color = u_ambient_intensity*vec3(0.55,0.62,0.72)*base;
      color += fill*vec3(0.70,0.80,0.90)*base;
      color += (kd*base*diffuse + spec*0.45)*u_sun_intensity*vec3(1.0,0.96,0.88)*shadow;
      frag_color = vec4(clamp(color,0.0,1.0),1.0);
    }`;

  const SHADOW_VERTEX_SHADER = `#version 300 es
    in vec3 in_pos; uniform mat4 u_light_vp;
    void main() { gl_Position = u_light_vp * vec4(in_pos,1.0); }`;
  const SHADOW_FRAGMENT_SHADER = `#version 300 es
    precision highp float; void main() {}`;

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

  function createShadowProgram(gl) {
    const program = gl.createProgram();
    gl.attachShader(program, shader(gl, gl.VERTEX_SHADER, SHADOW_VERTEX_SHADER));
    gl.attachShader(program, shader(gl, gl.FRAGMENT_SHADER, SHADOW_FRAGMENT_SHADER));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    return program;
  }

  function columnMajor(matrix) {
    const result = new Float32Array(16);
    for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
      result[col * 4 + row] = matrix[row * 4 + col];
    }
    return result;
  }

  function ortho(left, right, bottom, top, near, far) {
    return new Float32Array([
      2/(right-left),0,0,-(right+left)/(right-left),
      0,2/(top-bottom),0,-(top+bottom)/(top-bottom),
      0,0,-2/(far-near),-(far+near)/(far-near),
      0,0,0,1
    ]);
  }

  function cameraView(camera) {
    const p = camera.pitch * Math.PI / 180, y = camera.yaw * Math.PI / 180;
    const t = Math.max(0, Math.min(1, (89 - camera.pitch) / 37));
    const distance = (1100 - t * 340) / camera.zoom;
    const eye = [
      camera.target_x + Math.sin(y)*Math.cos(p)*distance,
      camera.target_y - Math.cos(y)*Math.cos(p)*distance,
      Math.sin(p)*distance
    ];
    return root.CoCProjection3D.mat4LookAt(eye,[camera.target_x,camera.target_y,0],[0,0,1]);
  }

  function createTerrainRenderer(onReady = () => {}) {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2', { alpha: false, antialias: true });
    if (!gl) return Object.freeze({
      draw: () => false,
      get ready() { return false; },
      get status() { return 'error'; },
      get error() { return 'Safari could not create a WebGL 2 context'; }
    });
    let program;
    let shadowProgram;
    let effects;
    let buffers = [];
    let counts = [];
    let flags = 0;
    let settings = [];
    let terrainVertices = null;
    let terrainBuckets = new Map();
    let terrainTriangleBuckets = new Map();
    const elevationCache = new Map();
    const sampleCellSize = 24;
    let shadowTexture;
    let shadowFramebuffer;
    let shadowSize = 2048;
    let shadowEnabled = false;
    let ready = false;
    let failed = false;
    let started = false;
    let contextLost = false;
    let loadGeneration = 0;
    let retryDelay = 500;
    let retryTimer = null;
    let status = 'loading';
    let errorMessage = '';
    let lastFrame = '';
    let lastShadowKey = '';

    canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      contextLost = true;
      loadGeneration++;
      clearTimeout(retryTimer);
      ready = false;
      started = true;
      status = 'context-lost';
      errorMessage = 'Safari lost the graphics context';
      onReady();
    });
    canvas.addEventListener('webglcontextrestored', () => {
      contextLost = false;
      started = false;
      failed = false;
      buffers = [];
      lastFrame = '';
      lastShadowKey = '';
      status = 'loading';
      loadMesh();
    });

    function loadMesh() {
      if (started || failed || contextLost) return;
      started = true;
      const attempt = ++loadGeneration;
      let meshDownloaded = false;
      fetch('/api/terrain-mesh.bin').then(response => {
      if (!response.ok) {
        const error = new Error(`Terrain mesh request failed (${response.status})`);
        error.retryable = response.status >= 500;
        throw error;
      }
      return response.arrayBuffer();
    }).then(data => {
      if (attempt !== loadGeneration || contextLost) return;
      meshDownloaded = true;
      const view = new DataView(data);
      counts = Array.from({ length: 4 }, (_, i) => view.getUint32(i * 4, true) / 10);
      flags = view.getUint32(16, true);
      settings = Array.from({ length: 12 }, (_, i) => view.getFloat32(20 + i * 4, true));
      let offset = 68;
      const lengths = counts.map(count => count * 10);
      terrainVertices = new Float32Array(new Float32Array(data, offset, lengths[0]));
      terrainBuckets.clear();
      terrainTriangleBuckets.clear();
      elevationCache.clear();
      for (let vertex = 0; vertex < lengths[0]; vertex += 10) {
        const x = terrainVertices[vertex], y = terrainVertices[vertex + 1];
        const key = `${Math.floor(x / sampleCellSize)},${Math.floor(y / sampleCellSize)}`;
        if (!terrainBuckets.has(key)) terrainBuckets.set(key, []);
        terrainBuckets.get(key).push(vertex);
      }
      for (let triangle = 0; triangle < lengths[0]; triangle += 30) {
        const ax = terrainVertices[triangle], ay = terrainVertices[triangle + 1];
        const bx = terrainVertices[triangle + 10], by = terrainVertices[triangle + 11];
        const cx = terrainVertices[triangle + 20], cy = terrainVertices[triangle + 21];
        const minX = Math.floor(Math.min(ax, bx, cx) / sampleCellSize);
        const maxX = Math.floor(Math.max(ax, bx, cx) / sampleCellSize);
        const minY = Math.floor(Math.min(ay, by, cy) / sampleCellSize);
        const maxY = Math.floor(Math.max(ay, by, cy) / sampleCellSize);
        for (let cellY = minY; cellY <= maxY; cellY++) {
          for (let cellX = minX; cellX <= maxX; cellX++) {
            const key = `${cellX},${cellY}`;
            if (!terrainTriangleBuckets.has(key)) terrainTriangleBuckets.set(key, []);
            terrainTriangleBuckets.get(key).push(triangle);
          }
        }
      }
      program = createProgram(gl);
      shadowProgram = createShadowProgram(gl);
      effects = root.CoCTerrainEffects.create(gl);
      const touchDevice = window.matchMedia('(pointer: coarse)').matches;
      shadowSize = Math.min(touchDevice ? 1024 : 4096, gl.getParameter(gl.MAX_TEXTURE_SIZE));
      shadowTexture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, shadowTexture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.DEPTH_COMPONENT24, shadowSize, shadowSize, 0, gl.DEPTH_COMPONENT, gl.UNSIGNED_INT, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      shadowFramebuffer = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, shadowFramebuffer);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.TEXTURE_2D, shadowTexture, 0);
      gl.drawBuffers([gl.NONE]);
      gl.readBuffer(gl.NONE);
      shadowEnabled = Boolean(flags & 2) && gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      for (const length of lengths) {
        const vertices = new Float32Array(data, offset, length);
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
        buffers.push(buffer);
        offset += length * 4;
      }
      if (gl.isContextLost()) return;
      ready = true;
      retryDelay = 500;
      status = 'ready';
      errorMessage = '';
      onReady();
      }).catch(error => {
        if (attempt !== loadGeneration || contextLost) return;
        const retryable = !meshDownloaded && (error instanceof TypeError || error.retryable);
        failed = !retryable;
        status = retryable ? 'retrying' : 'error';
        errorMessage = error.message || String(error);
        console.error('Desktop terrain mesh unavailable:', error);
        onReady();
        if (retryable) {
          const delay = retryDelay;
          retryDelay = Math.min(retryDelay * 2, 10000);
          retryTimer = setTimeout(() => {
            started = false;
            loadMesh();
          }, delay);
        } else {
          started = false;
        }
      });
    }

    function draw(ctx, camera, width, height, getMvp) {
      loadMesh();
      if (!ready || failed || contextLost) return false;
      try {
      const animated = counts[2] > 0 || counts[3] > 0;
      const simTime = performance.now() / 1000;
      const animationFrame = animated ? Math.floor(simTime * 12) : 0;
      const key = `${width}:${height}:${camera.pitch}:${camera.yaw}:${camera.zoom}:${camera.target_x}:${camera.target_y}:${animationFrame}`;
      if (key !== lastFrame) {
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
        }
        const projection = getMvp(camera, width, height);
        const viewMatrix = cameraView(camera);
        const sunAz = settings[0] * Math.PI / 180;
        const sunEl = Math.max(5, Math.min(88, settings[1])) * Math.PI / 180;
        const sun = [Math.cos(sunEl)*Math.cos(sunAz), Math.cos(sunEl)*Math.sin(sunAz), Math.sin(sunEl)];
        const shadowCenter = [camera.target_x,camera.target_y,0];
        const halfExtent = Math.max(180,Math.min(820,750/camera.zoom+50));
        const lightPos = shadowCenter.map((value,i) => value+sun[i]*1800);
        const lightView = root.CoCProjection3D.mat4LookAt(lightPos,shadowCenter,[0,0,1]);
        const lightProj = ortho(-halfExtent,halfExtent,-halfExtent,halfExtent,10,3600);
        const lightVp = root.CoCProjection3D.mat4Multiply(lightProj,lightView);
        const bias = new Float32Array([0.5,0,0,0.5, 0,0.5,0,0.5, 0,0,0.5,0.5, 0,0,0,1]);
        const shadowMatrix = root.CoCProjection3D.mat4Multiply(bias,lightVp);

        const shadowKey = `${camera.target_x}:${camera.target_y}:${camera.zoom}`;
        if (shadowEnabled && shadowKey !== lastShadowKey) {
          gl.bindFramebuffer(gl.FRAMEBUFFER,shadowFramebuffer);
          gl.viewport(0,0,shadowSize,shadowSize);
          gl.clear(gl.DEPTH_BUFFER_BIT);
          gl.enable(gl.DEPTH_TEST);
          gl.depthFunc(gl.LEQUAL);
          gl.useProgram(shadowProgram);
          gl.uniformMatrix4fv(gl.getUniformLocation(shadowProgram,'u_light_vp'),false,columnMajor(lightVp));
          const shadowPos = gl.getAttribLocation(shadowProgram,'in_pos');
          for (const index of [0,1]) {
            if (!buffers[index] || !counts[index]) continue;
            gl.bindBuffer(gl.ARRAY_BUFFER,buffers[index]);
            gl.enableVertexAttribArray(shadowPos);
            gl.vertexAttribPointer(shadowPos,3,gl.FLOAT,false,40,0);
            gl.drawArrays(gl.TRIANGLES,0,counts[index]);
          }
          lastShadowKey = shadowKey;
        }

        gl.bindFramebuffer(gl.FRAMEBUFFER,null);
        gl.viewport(0, 0, width, height);
        gl.enable(gl.DEPTH_TEST);
        gl.depthFunc(gl.LEQUAL);
        gl.disable(gl.BLEND);
        gl.clearColor(0.04, 0.12, 0.24, 1);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

        const setMatrix = (target, name, matrix) => {
          gl.uniformMatrix4fv(gl.getUniformLocation(target, name), false, columnMajor(matrix));
        };
        const setRibbonAttributes = (target, buffer) => {
          gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
          const stride = 40;
          const attributes = ['in_pos', 'in_normal', 'in_color', 'in_measure'];
          const offsets = [0, 12, 24, 36];
          attributes.forEach((name, index) => {
            const location = gl.getAttribLocation(target, name);
            if (location < 0) return;
            gl.enableVertexAttribArray(location);
            gl.vertexAttribPointer(location, index === 3 ? 1 : 3, gl.FLOAT, false, stride, offsets[index]);
          });
        };

        // Keep the ocean and shoreline effect passes in the same order as desktop.
        const oceanProgram = effects.oceanProgram;
        gl.useProgram(oceanProgram);
        setMatrix(oceanProgram, 'u_mvp', projection);
        gl.uniform1f(gl.getUniformLocation(oceanProgram, 'u_time'), simTime);
        gl.uniform1f(gl.getUniformLocation(oceanProgram, 'u_wave_intensity'), settings[7]);
        gl.uniform1f(gl.getUniformLocation(oceanProgram, 'u_wave_speed'), settings[8]);
        gl.uniform1f(gl.getUniformLocation(oceanProgram, 'u_wave_period'), settings[9]);
        gl.uniform3fv(gl.getUniformLocation(oceanProgram, 'u_sun_world_dir'), sun);
        const oceanPosition = gl.getAttribLocation(oceanProgram, 'in_pos');
        gl.bindBuffer(gl.ARRAY_BUFFER, effects.ocean);
        gl.enableVertexAttribArray(oceanPosition);
        gl.vertexAttribPointer(oceanPosition, 3, gl.FLOAT, false, 12, 0);
        gl.drawArrays(gl.TRIANGLES, 0, 6);

        gl.useProgram(program);
        gl.uniformMatrix4fv(gl.getUniformLocation(program,'u_mvp'),false,columnMajor(projection));
        gl.uniformMatrix4fv(gl.getUniformLocation(program,'u_view'),false,columnMajor(viewMatrix));
        gl.uniformMatrix4fv(gl.getUniformLocation(program,'u_shadow_matrix'),false,columnMajor(shadowMatrix));
        gl.uniform3fv(gl.getUniformLocation(program,'u_sun_dir'),sun);
        gl.uniform3fv(gl.getUniformLocation(program,'u_sun_world_dir'),sun);
        gl.uniform1f(gl.getUniformLocation(program,'u_sun_intensity'),settings[2]);
        gl.uniform1f(gl.getUniformLocation(program,'u_ambient_intensity'),settings[3]);
        gl.uniform1f(gl.getUniformLocation(program,'u_mountain_roughness'),settings[4]);
        gl.uniform1f(gl.getUniformLocation(program,'u_snow_threshold'),settings[5]);
        gl.uniform1i(gl.getUniformLocation(program,'u_shadow_mode'),shadowEnabled?1:0);
        gl.uniform1f(gl.getUniformLocation(program,'u_shadow_darkness'),settings[6]);
        gl.uniform1i(gl.getUniformLocation(program,'u_micropoly_strata'),(flags&1)?1:0);
        gl.uniform1f(gl.getUniformLocation(program,'u_shadow_size'),shadowSize);
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D,shadowTexture);
        gl.uniform1i(gl.getUniformLocation(program,'u_shadow_map'),1);
        const locations = ['in_pos', 'in_norm', 'in_color', 'in_elev'].map(name => gl.getAttribLocation(program, name));
        const stride = 10 * 4;
        const drawMesh = (index) => {
          gl.bindBuffer(gl.ARRAY_BUFFER, buffers[index]);
          for (let i = 0; i < 4; i++) {
            const size = i === 3 ? 1 : 3;
            gl.enableVertexAttribArray(locations[i]);
            gl.vertexAttribPointer(locations[i], size, gl.FLOAT, false, stride, [0, 12, 24, 36][i]);
          }
          gl.drawArrays(gl.TRIANGLES, 0, counts[index]);
        };

        drawMesh(0);
        drawMesh(1);

        if (counts[2] > 0 || counts[3] > 0) {
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          if (counts[2] > 0) {
            const riverProgram = effects.riverProgram;
            gl.useProgram(riverProgram);
            setMatrix(riverProgram, 'u_mvp', projection);
            gl.uniform1f(gl.getUniformLocation(riverProgram, 'u_time'), simTime);
            setRibbonAttributes(riverProgram, buffers[2]);
            gl.drawArrays(gl.TRIANGLES, 0, counts[2]);
          }
          if (counts[3] > 0 && (flags & 4)) {
            const ribbonProgram = effects.ribbonProgram;
            gl.useProgram(ribbonProgram);
            setMatrix(ribbonProgram, 'u_mvp', projection);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_time'), simTime);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_wave_intensity'), settings[7]);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_wave_speed'), settings[8]);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_wave_period'), settings[9]);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_foam_coverage'), settings[10]);
            gl.uniform1f(gl.getUniformLocation(ribbonProgram, 'u_wave_desync'), settings[11]);
            gl.uniform3fv(gl.getUniformLocation(ribbonProgram, 'u_sun_world_dir'), sun);
            setRibbonAttributes(ribbonProgram, buffers[3]);
            gl.drawArrays(gl.TRIANGLES, 0, counts[3]);
          }
          gl.disable(gl.BLEND);
        }
        if (gl.isContextLost()) return false;
        const glError = gl.getError();
        if (glError === gl.OUT_OF_MEMORY) throw new Error('Safari ran out of graphics memory');
        if (glError !== gl.NO_ERROR) throw new Error(`WebGL error 0x${glError.toString(16)}`);
        lastFrame = key;
      }
      ctx.drawImage(canvas, 0, 0, width, height);
      if (animated) setTimeout(onReady, 80);
      return true;
      } catch (error) {
        ready = false;
        failed = true;
        status = 'error';
        errorMessage = error.message || String(error);
        console.error('Desktop terrain draw failed:', error);
        onReady();
        return false;
      }
    }

    function sampleElevation(x, y) {
      if (!terrainVertices) return 0.08;
      const cacheKey = `${x.toFixed(2)},${y.toFixed(2)}`;
      if (elevationCache.has(cacheKey)) return elevationCache.get(cacheKey);
      const cellX = Math.floor(x / sampleCellSize), cellY = Math.floor(y / sampleCellSize);
      const checkedTriangles = new Set();
      for (let radius = 0; radius <= 2; radius++) {
        for (let cy = cellY - radius; cy <= cellY + radius; cy++) {
          for (let cx = cellX - radius; cx <= cellX + radius; cx++) {
            if (radius && cx !== cellX - radius && cx !== cellX + radius && cy !== cellY - radius && cy !== cellY + radius) continue;
            for (const triangle of terrainTriangleBuckets.get(`${cx},${cy}`) || []) {
              if (checkedTriangles.has(triangle)) continue;
              checkedTriangles.add(triangle);
              const ax = terrainVertices[triangle], ay = terrainVertices[triangle + 1];
              const bx = terrainVertices[triangle + 10], by = terrainVertices[triangle + 11];
              const cxv = terrainVertices[triangle + 20], cyv = terrainVertices[triangle + 21];
              const denom = (by - cyv) * (ax - cxv) + (cxv - bx) * (ay - cyv);
              if (Math.abs(denom) < 1e-8) continue;
              const wa = ((by - cyv) * (x - cxv) + (cxv - bx) * (y - cyv)) / denom;
              const wb = ((cyv - ay) * (x - cxv) + (ax - cxv) * (y - cyv)) / denom;
              const wc = 1 - wa - wb;
              if (wa < -1e-5 || wb < -1e-5 || wc < -1e-5) continue;
              const elevation = Math.max(0,
                wa * terrainVertices[triangle + 2] +
                wb * terrainVertices[triangle + 12] +
                wc * terrainVertices[triangle + 22]
              ) + 0.08;
              elevationCache.set(cacheKey, elevation);
              return elevation;
            }
          }
        }
      }
      const nearest = [];
      const visited = new Set();
      for (let radius = 0; radius <= 5; radius++) {
        for (let cy = cellY - radius; cy <= cellY + radius; cy++) {
          for (let cx = cellX - radius; cx <= cellX + radius; cx++) {
            if (radius && cx !== cellX - radius && cx !== cellX + radius && cy !== cellY - radius && cy !== cellY + radius) continue;
            const key = `${cx},${cy}`;
            if (visited.has(key)) continue;
            visited.add(key);
            const bucket = terrainBuckets.get(key);
            if (!bucket) continue;
            for (const vertex of bucket) {
              const dx = terrainVertices[vertex] - x, dy = terrainVertices[vertex + 1] - y;
              const distance = Math.hypot(dx, dy);
              nearest.push({ vertex, distance });
            }
          }
        }
        nearest.sort((a, b) => a.distance - b.distance);
        nearest.length = Math.min(3, nearest.length);
        const lowerBound = Math.min(
          x - (cellX - radius) * sampleCellSize,
          (cellX + radius + 1) * sampleCellSize - x,
          y - (cellY - radius) * sampleCellSize,
          (cellY + radius + 1) * sampleCellSize - y
        );
        if (nearest.length === 3 && nearest[2].distance <= lowerBound) break;
      }
      if (!nearest.length) return 0.08;
      let weightedHeight = 0, totalWeight = 0;
      for (const point of nearest) {
        const weight = 1 / Math.max(point.distance, 1e-4);
        weightedHeight += terrainVertices[point.vertex + 2] * weight;
        totalWeight += weight;
      }
      const elevation = Math.max(0, weightedHeight / totalWeight) + 0.08;
      elevationCache.set(cacheKey, elevation);
      return elevation;
    }

    return Object.freeze({
      draw, sampleElevation,
      get ready() { return ready; },
      get failed() { return failed; },
      get status() { return status; },
      get error() { return errorMessage; }
    });
  }

  root.CoCTerrainRenderer = Object.freeze({ createTerrainRenderer });
})(typeof window !== 'undefined' ? window : globalThis);
