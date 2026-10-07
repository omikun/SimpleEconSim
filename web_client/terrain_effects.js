// Animated water, river, and shoreline passes shared by the web terrain renderer.
(function (root) {
  'use strict';

  const OCEAN_VERTEX = `#version 300 es
    in vec3 in_pos; uniform mat4 u_mvp; out vec3 v_world_pos;
    void main() { v_world_pos = in_pos; gl_Position = u_mvp * vec4(in_pos, 1.0); }`;
  const OCEAN_FRAGMENT = `#version 300 es
    precision highp float;
    in vec3 v_world_pos;
    uniform float u_time, u_wave_intensity, u_wave_speed, u_wave_period;
    uniform vec3 u_sun_world_dir;
    out vec4 frag_color;
    void main() {
      float t = u_time * max(0.05, u_wave_speed);
      float period = max(0.2, u_wave_period);
      vec2 uv1 = v_world_pos.xy * (0.052 / period);
      vec2 uv2 = v_world_pos.xy * (0.18 / period);
      vec2 d1 = vec2(cos(uv1.x*.8+uv1.y*.6-t*1.8)*.8, sin(uv1.x*.6-uv1.y*.8+t*1.5)*.8)*.025;
      vec2 d2 = vec2(cos(uv2.x*1.2-uv2.y*.7-t*2.6)*1.2, sin(uv2.x*.7+uv2.y*1.2-t*2.3)*1.2)*.015;
      vec3 N = normalize(vec3((d1+d2)*u_wave_intensity, 1.0));
      vec3 L = normalize(u_sun_world_dir), V = normalize(vec3(0.0,.45,.89));
      float fresnel = .04 + .96*pow(1.0-max(0.0,dot(N,V)),5.0);
      float spec = pow(max(0.0,dot(N,normalize(L+V))),48.0)*1.2;
      vec3 water = mix(vec3(.04,.18,.35),vec3(.35,.60,.82),fresnel);
      frag_color = vec4(water+vec3(1.0,.96,.85)*spec,1.0);
    }`;

  const RIBBON_VERTEX = `#version 300 es
    in vec3 in_pos, in_normal, in_color; in float in_measure;
    uniform mat4 u_mvp; uniform float u_time, u_wave_intensity, u_wave_speed, u_wave_period, u_wave_desync;
    out vec3 v_world_pos, v_world_norm, v_color; out float v_dist, v_crest;
    void main() {
      float along = dot(in_pos.xy, vec2(-in_normal.y, in_normal.x));
      float sector = sin(floor(along*.012)*14.123)*6.2831;
      float desync = (sin(along*.018)*2.2 + cos(along*.042)*1.1)*u_wave_desync;
      float t = u_time*(.85*u_wave_speed), k = 5.2/max(.2,u_wave_period);
      float p1 = t*2.0-in_measure*k+desync, p2 = t*1.25-in_measure*(k*.60)+sector*.5;
      float packet = pow(clamp(sin(t*.25+sector+along*.008),0.0,1.0),1.5);
      float exposure = mix(1.0,clamp(dot(in_normal.xy,normalize(vec2(-.707,.707)))*.85+.40,.05,1.0),u_wave_desync);
      float shoal = (1.0+1.2*exp(-pow((in_measure-.22)*4.5,2.0)))*exposure*(.35+.65*packet);
      float crest = pow(clamp(sin(p1)*.70+sin(p2)*.30,0.0,1.0),2.8)*shoal;
      vec2 drift = -in_normal.xy*(cos(mix(p1,p2,.30))*.008*u_wave_intensity*shoal);
      vec3 pos = vec3(in_pos.xy+drift,max(.20,in_pos.z+.30+crest*.10*u_wave_intensity));
      v_world_pos=pos; v_world_norm=in_normal; v_color=in_color; v_dist=in_measure; v_crest=crest;
      gl_Position=u_mvp*vec4(pos,1.0);
    }`;

  const RIBBON_FRAGMENT = `#version 300 es
    precision highp float;
    in vec3 v_world_pos,v_world_norm,v_color; in float v_dist,v_crest;
    uniform float u_time,u_wave_intensity,u_wave_speed,u_foam_coverage,u_wave_desync;
    uniform vec3 u_sun_world_dir; out vec4 frag_color;
    vec2 hash2(vec2 p){p=vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3)));return fract(sin(p)*43758.5453);}
    float voronoi(vec2 x){vec2 n=floor(x),f=fract(x);float d=1.0;for(int j=-1;j<=1;j++)for(int i=-1;i<=1;i++){vec2 g=vec2(float(i),float(j));vec2 r=g+hash2(n+g)-f;d=min(d,dot(r,r));}return sqrt(d);}
    void main(){
      float along=dot(v_world_pos.xy,vec2(-v_world_norm.y,v_world_norm.x));
      float desync=(sin(along*.018)*2.2+cos(along*.042)*1.1)*u_wave_desync,t=u_time*(.85*u_wave_speed);
      float exposure=mix(1.0,clamp(dot(v_world_norm.xy,normalize(vec2(-.707,.707)))*.85+.40,.05,1.0),u_wave_desync);
      float crest=smoothstep(.40,.88,v_crest)*smoothstep(.65,.08,v_dist)*u_wave_intensity*u_foam_coverage;
      float cycle=sin(t*1.1+desync*.4), swash=smoothstep(.16,.01,v_dist-cycle*.04)*(.60+.40*max(0.0,cycle))*exposure*u_foam_coverage;
      vec2 uv=v_world_pos.xy*.20+vec2(t*.03,-t*.02);
      float lace=(1.0-smoothstep(.03,.16,voronoi(uv)))*smoothstep(.14,.75,voronoi(uv*1.7+vec2(3.1,7.4)));
      lace*=smoothstep(.03,.20,v_dist)*smoothstep(.48,.14,v_dist)*crest*.70;
      float foam=clamp(crest*.95+swash*.85+lace*.60,0.0,1.0);
      vec3 sea=mix(vec3(.20,.75,.86),vec3(.11,.58,.78),smoothstep(.02,.30,v_dist));
      sea=mix(sea,vec3(.06,.24,.45),smoothstep(.30,.85,v_dist));
      vec3 N=vec3(0,0,1),L=normalize(u_sun_world_dir),V=normalize(vec3(0,.45,.89));
      float glint=pow(max(0.0,dot(N,normalize(L+V))),32.0)*.85;
      vec3 color=mix(sea,vec3(1),foam)+vec3(1,.98,.92)*glint*(1.0-foam*.5);
      float alpha=clamp(.75+foam*.25-v_dist*.15,0.0,.98)*(1.0-smoothstep(.40,.92,v_dist));
      frag_color=vec4(color,alpha);
    }`;

  const RIVER_VERTEX = `#version 300 es
    in vec3 in_pos,in_normal,in_color; in float in_measure;
    uniform mat4 u_mvp; uniform float u_time;
    out vec3 v_color,v_normal; out float v_flow;
    void main(){vec3 p=in_pos;p.z+=sin(u_time*4.2-in_measure*3.5)*.04;v_color=in_color;v_normal=in_normal;v_flow=in_measure;gl_Position=u_mvp*vec4(p,1.0);}`;
  const RIVER_FRAGMENT = `#version 300 es
    precision highp float; in vec3 v_color,v_normal; in float v_flow; uniform float u_time; out vec4 frag_color;
    void main(){float glint=pow(max(0.0,dot(normalize(v_normal),normalize(vec3(.2,.4,1.0)))),24.0);vec3 c=v_color*(.75+.25*sin(u_time*4.0-v_flow*4.0))+vec3(.4,.75,1.0)*glint*.3;frag_color=vec4(c,.95);}`;

  function createProgram(gl, vertexSource, fragmentSource) {
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source); gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
      return shader;
    };
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    return program;
  }

  root.CoCTerrainEffects = Object.freeze({
    create(gl) {
      const oceanProgram = createProgram(gl, OCEAN_VERTEX, OCEAN_FRAGMENT);
      const ribbonProgram = createProgram(gl, RIBBON_VERTEX, RIBBON_FRAGMENT);
      const riverProgram = createProgram(gl, RIVER_VERTEX, RIVER_FRAGMENT);
      const ocean = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, ocean);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
        -1500,-1500,-.35, 2524,-1500,-.35, -1500,2524,-.35,
        -1500,2524,-.35, 2524,-1500,-.35, 2524,2524,-.35
      ]), gl.STATIC_DRAW);
      return Object.freeze({ oceanProgram, ribbonProgram, riverProgram, ocean });
    }
  });
})(typeof window !== 'undefined' ? window : globalThis);
