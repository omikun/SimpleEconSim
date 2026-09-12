"""
render_engine/gpu/shaders.py — High-performance multi-pass GLSL shaders for terrain generation.

Features:
- Pass 1: Continuous Elevation, Hex Conformation, Ridged Multifractals, Bathymetry & Valley Carving
- Pass 2: Finite-Difference Normals, Slope Derivation & Flat Water Normal Smoothing
- Pass 3: Lighting, Bathymetry, Inland Lakes & Rivers, 2D Volumetric Forest Canopy, and Multi-Scale Plains
"""

# Vertex shader for rendering a full-screen quad (shared across all passes)
QUAD_VERT = """#version 330 core
in vec2 in_vert;
in vec2 in_texcoord;
out vec2 v_uv;

void main() {
    v_uv = in_texcoord;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

# Pass 1 Fragment Shader: Continuous Elevation, Hex Conformation, and Valley/Lake Depression Carving
PASS1_ELEV_FRAG = """#version 330 core
in vec2 v_uv;
layout(location = 0) out vec4 out_elev_biome; // R=Elevation(H), G=LandProb, B=MountProb, A=ForestProb
layout(location = 1) out vec4 out_aux;        // R=SnowProb, G=SlopeHint, B=CarveDepth, A=1.0

uniform vec4 u_bbox;       // min_wx, min_wy, max_wx, max_wy
uniform vec2 u_center;     // cx_center, cy_center
uniform vec2 u_span;       // span_x, span_y
uniform float u_hex_size;  // 50.0
uniform float u_seed;
uniform sampler2D u_noise_tex;
uniform sampler2D u_biome_grid; // R=land, G=forest, B=mount/snow, A=hills
uniform sampler2D u_river_tex;  // R=water mask, G=flow/depth, B=carve, A=riparian
uniform vec4 u_grid_bounds;     // min_q, min_r, q_size, r_size

// Live tuning uniforms
uniform float u_mountain_roughness;
uniform float u_shelf_width_mult;
uniform float u_ocean_depth_mult;
uniform float u_river_depth_mult;
uniform float u_lake_depth_mult;

const float SQRT3 = 1.7320508075688772;

// Value noise with analytical derivatives & boundary modulo
vec3 noised(in vec2 p) {
    vec2 fl = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    vec2 du = 6.0 * f * (1.0 - f);

    vec2 i0 = mod(fl, 256.0);
    vec2 i1 = mod(fl + 1.0, 256.0);

    vec2 uv0 = (i0 + vec2(0.5)) / 256.0;
    vec2 uv1 = (i1 + vec2(0.5)) / 256.0;

    float a = texture(u_noise_tex, vec2(uv0.x, uv0.y)).r;
    float b = texture(u_noise_tex, vec2(uv1.x, uv0.y)).r;
    float c = texture(u_noise_tex, vec2(uv0.x, uv1.y)).r;
    float d = texture(u_noise_tex, vec2(uv1.x, uv1.y)).r;

    float k0 = a;
    float k1 = b - a;
    float k2 = c - a;
    float k3 = a - b - c + d;

    float val = k0 + k1 * u.x + k2 * u.y + k3 * u.x * u.y;
    vec2 deriv = du * vec2(k1 + k3 * u.y, k2 + k3 * u.x);
    return vec3(val, deriv);
}

// 7-Octave Inigo Quilez derivative erosion fBm
vec3 fbm_erosion(vec2 p) {
    vec2 px = p;
    float a = 0.0;
    float b = 1.0;
    vec2 d_accum = vec2(0.0);
    mat2 m2 = mat2(0.8, 0.6, -0.6, 0.8);

    for (int i = 0; i < 7; i++) {
        vec3 n = noised(px);
        d_accum += n.yz;
        float erosion = 1.0 + dot(d_accum, d_accum) * 0.75;
        a += b * n.x / erosion;
        b *= 0.50;
        px = 2.0 * (m2 * px);
    }
    return vec3((a - 0.85) * 0.70, d_accum);
}

// Axial hex coordinate lookup from world position
vec2 world_to_axial_frac(vec2 w, float hex_size) {
    float q = (SQRT3 / 3.0 * w.x - 1.0 / 3.0 * w.y) / hex_size;
    float r = (2.0 / 3.0 * w.y) / hex_size;
    return vec2(q, r);
}

// Cube rounding for pointy-top axial coordinates
ivec2 axial_round(vec2 frac_qr) {
    float x = frac_qr.x;
    float y = frac_qr.y;
    float z = -x - y;

    float rx = floor(x + 0.5);
    float ry = floor(y + 0.5);
    float rz = floor(z + 0.5);

    float dx = abs(rx - x);
    float dy = abs(ry - y);
    float dz = abs(rz - z);

    if (dx > dy && dx > dz) {
        rx = -ry - rz;
    } else if (dy > dz) {
        ry = -rx - rz;
    }
    return ivec2(int(rx), int(ry));
}

void main() {
    vec2 world_pos = mix(u_bbox.xy, u_bbox.zw, v_uv);
    vec2 norm_pos = (world_pos - u_center) / u_span;

    // 1. Derivative erosion fBm
    vec3 erosion_res = fbm_erosion(norm_pos * 3.0);
    vec2 d_accum = erosion_res.yz;

    // 2. Hex conformation coordinate warp
    float warp_amp = u_hex_size * 0.12;
    vec2 W_warped = world_pos + d_accum * 0.20 * warp_amp;

    // Find nearest hex center
    vec2 qr_frac = world_to_axial_frac(W_warped, u_hex_size);
    ivec2 q_near = axial_round(qr_frac);

    // Sample neighboring hex weights
    float min_q = u_grid_bounds.x;
    float min_r = u_grid_bounds.y;
    float q_size = u_grid_bounds.z;
    float r_size = u_grid_bounds.w;

    float H_land_sum = 0.0;
    float H_forest_sum = 0.0;
    float H_mount_sum = 0.0;
    float H_snow_sum = 0.0;
    float H_hills_sum = 0.0;
    float W_total = 0.0;

    float R_blend = u_hex_size * 2.2;
    float R2 = R_blend * R_blend;

    ivec2 hex_dirs[7] = ivec2[](
        ivec2(0, 0), ivec2(1, 0), ivec2(-1, 0),
        ivec2(0, 1), ivec2(0, -1), ivec2(1, -1), ivec2(-1, 1)
    );

    for (int i = 0; i < 7; i++) {
        ivec2 qc = q_near + hex_dirs[i];
        if (float(qc.x) >= min_q && float(qc.x) < min_q + q_size &&
            float(qc.y) >= min_r && float(qc.y) < min_r + r_size) {

            vec2 tex_coord = vec2(
                (float(qc.x) - min_q + 0.5) / q_size,
                (float(qc.y) - min_r + 0.5) / r_size
            );
            vec4 biome_tex = texture(u_biome_grid, tex_coord);

            vec2 hex_center = vec2(
                u_hex_size * SQRT3 * (float(qc.x) + float(qc.y) / 2.0),
                u_hex_size * 1.5 * float(qc.y)
            );
            float dist_sq = dot(W_warped - hex_center, W_warped - hex_center);

            if (dist_sq < R2) {
                float w = pow(max(0.0, 1.0 - (dist_sq / R2)), 2.5);
                H_land_sum += w * biome_tex.r;
                H_forest_sum += w * biome_tex.g;
                H_mount_sum += w * min(1.0, biome_tex.b);
                H_snow_sum += w * max(0.0, biome_tex.b - 1.0);
                H_hills_sum += w * biome_tex.a;
                W_total += w;
            }
        }
    }

    float inv_w = 1.0 / (W_total + 1e-6);
    float H_land_prob = H_land_sum * inv_w;
    float H_forest_prob = H_forest_sum * inv_w;
    float H_mount_prob = H_mount_sum * inv_w;
    float H_snow_prob = H_snow_sum * inv_w;
    float H_hills_prob = H_hills_sum * inv_w;

    // Organic Domain Warping for Mountain Relief
    float warp_scale = 1.0 / (u_hex_size * 3.5);
    vec3 qw = noised(world_pos * warp_scale);
    vec3 rw = noised((world_pos + vec2(120.0, -80.0)) * warp_scale + qw.yz * 0.5);
    vec2 W_geo = world_pos + (qw.yz * 0.4 + rw.yz * 0.6) * (u_hex_size * 0.4);

    // Ridged Mountain Multi-Fractal (rugged crags and valleys)
    vec2 mount_p = W_geo / (u_hex_size * 2.2);
    float mount_relief = 0.0;
    float mount_amp = 1.0;
    float mount_freq = 1.0;
    vec2 m_d_accum = vec2(0.0);

    for (int o = 0; o < 6; o++) {
        vec3 n = noised(mount_p * mount_freq);
        float ridge = 1.0 - abs(2.0 * n.x - 1.0);
        ridge = ridge * ridge;
        m_d_accum += n.yz * mount_freq;
        float erosion = 1.0 + dot(m_d_accum, m_d_accum) * 0.35;
        mount_relief += mount_amp * (ridge / erosion);
        mount_amp *= 0.52;
        mount_freq *= 2.05;
    }
    mount_relief = max(0.0, (mount_relief - 0.45) * 1.35) * u_mountain_roughness;

    // Plains micro-relief
    vec2 plains_p = W_geo / (u_hex_size * 0.5);
    float plains_fbm = 0.0;
    float p_amp = 0.5;
    float p_freq = 1.0;
    for (int p_idx = 0; p_idx < 4; p_idx++) {
        vec3 p_val = noised(plains_p * p_freq);
        plains_fbm += p_amp * p_val.x;
        p_amp *= 0.5;
        p_freq *= 2.15;
    }
    float plains_details = (plains_fbm - 0.50) * 0.035;

    // Hills
    vec3 hill_noise = noised(W_geo / (u_hex_size * 1.8));
    float hill_ridge = H_hills_prob * (0.26 + 0.14 * hill_noise.x);

    // Alpine Mountain Spines
    float mount_mask = pow(clamp(H_mount_prob * 1.5 + H_snow_prob * 0.6, 0.0, 1.0), 0.85);
    float mountain_ridge = mount_mask * (0.16 + 0.88 * mount_relief);

    // Coastal shelf & bathymetry
    float shore_ref = 0.30;
    vec3 c_m1 = noised(world_pos / (u_hex_size * 3.6) + vec2(41.2, -17.8));
    vec3 c_m2 = noised(world_pos / (u_hex_size * 1.5) + vec2(-73.1, 62.4));
    float coast_morph = c_m1.x * 0.6 + c_m2.x * 0.4;

    float w_cliff = pow(clamp((coast_morph - 0.50) * 2.2, 0.0, 1.0), 1.3);
    float w_ramp = pow(clamp((0.50 - coast_morph) * 2.5, 0.0, 1.0), 1.2);
    float w_terrace = clamp(1.0 - w_cliff - w_ramp, 0.0, 1.0);

    float shelf_width_tiles = (w_cliff * 0.18 + w_terrace * 1.6 + w_ramp * 4.6) * u_shelf_width_mult;

    float sea_dist_tiles = max(0.0, (shore_ref - H_land_prob) * 6.5);
    float inland_dist_tiles = max(0.0, (H_land_prob - shore_ref) * 6.5);

    // Above-water shelf profile
    float cliff_coast_H = 0.15 * smoothstep(0.0, 0.20, inland_dist_tiles);
    float ramp_coast_H = 0.085 * pow(clamp(inland_dist_tiles / 1.8, 0.0, 1.0), 1.1);
    float terrace_coast_H = 0.035 * pow(clamp(inland_dist_tiles / 1.1, 0.0, 1.0), 0.4);
    float land_shelf_above = cliff_coast_H * w_cliff + ramp_coast_H * w_ramp + terrace_coast_H * w_terrace;

    // Sub-sea bathymetry profile
    float t_shelf = clamp(sea_dist_tiles / max(shelf_width_tiles, 0.05), 0.0, 1.0);
    float ramp_shelf_depth = 0.001 + 0.016 * pow(t_shelf, 1.05);
    float cliff_shelf_depth = 0.035 + 0.160 * pow(t_shelf, 2.40);
    float terrace_shelf_depth = 0.005 + 0.060 * pow(t_shelf, 1.30);
    float shelf_depth = (ramp_shelf_depth * w_ramp + cliff_shelf_depth * w_cliff + terrace_shelf_depth * w_terrace) * u_ocean_depth_mult;

    float plunge_rate = w_cliff * 0.14 + w_terrace * 0.95 + w_ramp * 3.60;
    float t_plunge = clamp((sea_dist_tiles - shelf_width_tiles) / max(plunge_rate, 0.06), 0.0, 1.0);
    float s_plunge = t_plunge * t_plunge * (3.0 - 2.0 * t_plunge);
    float ocean_depth = shelf_depth + (s_plunge * 0.35 + s_plunge * s_plunge * 0.28) * u_ocean_depth_mult;
    float seabed_H = -ocean_depth;

    float wsea_width = w_cliff * 0.012 + w_terrace * 0.024 + w_ramp * 0.035;
    float wsea = smoothstep(0.0, 1.0, clamp((shore_ref + 0.006 - H_land_prob) / max(wsea_width, 0.008), 0.0, 1.0));
    float land_shelf = mix(land_shelf_above, seabed_H, wsea);

    float base_ground_H = land_shelf + hill_ridge + mountain_ridge + plains_details * (1.0 - mount_mask);

    // Valley & Lake Carving from Hydrography Map
    vec3 riv_warp = noised(world_pos * 0.04);
    vec2 riv_uv = v_uv + riv_warp.yz * 0.005;
    vec4 river_data = texture(u_river_tex, riv_uv);
    float carve_amt = river_data.b * 0.032 * u_river_depth_mult;
    float carved_H = base_ground_H - carve_amt;

    // Flatten lake and river water basins so water is level
    if (river_data.r > 0.10 && H_land_prob >= 0.28) {
        float water_h = max(0.005, base_ground_H - carve_amt * 0.40);
        carved_H = mix(carved_H, water_h, smoothstep(0.10, 0.70, river_data.r));
    }

    float slope_hint = mount_mask + w_cliff * 0.5;

    out_elev_biome = vec4(carved_H, H_land_prob, H_mount_prob, H_forest_prob);
    out_aux = vec4(H_snow_prob, slope_hint, carve_amt, 1.0);
}
"""

# Pass 2 Fragment Shader: Surface Normals, Slope & Water Surface Smoothing
PASS2_NORMAL_FRAG = """#version 330 core
in vec2 v_uv;
out vec4 frag_normal; // N.x, N.y, N.z, slope

uniform sampler2D u_elev_tex;
uniform sampler2D u_river_tex;
uniform sampler2D u_noise_tex;
uniform vec2 u_resolution;
uniform vec4 u_bbox;

vec3 noised(in vec2 p) {
    vec2 fl = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    vec2 du = 6.0 * f * (1.0 - f);
    vec2 uv0 = (mod(fl, 256.0) + vec2(0.5)) / 256.0;
    vec2 uv1 = (mod(fl + 1.0, 256.0) + vec2(0.5)) / 256.0;
    float a = texture(u_noise_tex, vec2(uv0.x, uv0.y)).r;
    float b = texture(u_noise_tex, vec2(uv1.x, uv0.y)).r;
    float c = texture(u_noise_tex, vec2(uv0.x, uv1.y)).r;
    float d = texture(u_noise_tex, vec2(uv1.x, uv1.y)).r;
    return vec3(a + (b - a) * u.x + (c - a) * u.y + (a - b - c + d) * u.x * u.y,
                du * vec2((b - a) + (a - b - c + d) * u.y, (c - a) + (a - b - c + d) * u.x));
}

void main() {
    vec2 eps = 1.0 / u_resolution;
    float H_r = texture(u_elev_tex, v_uv + vec2(eps.x, 0.0)).r;
    float H_l = texture(u_elev_tex, v_uv - vec2(eps.x, 0.0)).r;
    float H_u = texture(u_elev_tex, v_uv + vec2(0.0, eps.y)).r;
    float H_d = texture(u_elev_tex, v_uv - vec2(0.0, eps.y)).r;

    float dHx = (H_r - H_l) * 95.0;
    float dHy = (H_u - H_d) * 95.0;
    vec3 N = normalize(vec3(-dHx, -dHy, 1.0));

    // Flatten normals over calm inland lakes and slow rivers for mirror-like specular reflections
    vec2 world_pos = mix(u_bbox.xy, u_bbox.zw, v_uv);
    vec3 riv_warp = noised(world_pos * 0.04);
    vec2 riv_uv = v_uv + riv_warp.yz * 0.005;
    vec4 river_data = texture(u_river_tex, riv_uv);
    if (river_data.r > 0.05) {
        float flat_w = smoothstep(0.05, 0.50, river_data.r);
        N = normalize(mix(N, vec3(0.0, 0.0, 1.0), flat_w * 0.95));
    }

    float slope = 1.0 - N.z;
    frag_normal = vec4(N, slope);
}
"""

# Pass 3 Fragment Shader: Lighting, Bathymetry, Inland Lakes & Rivers, Volumetric Forest Canopy, and Multi-Scale Plains
PASS3_COMPOSITE_FRAG = """#version 330 core
in vec2 v_uv;
out vec4 frag_color;

uniform sampler2D u_elev_tex;
uniform sampler2D u_aux_tex;
uniform sampler2D u_normal_tex;
uniform sampler2D u_river_tex;
uniform sampler2D u_noise_tex;

uniform vec4 u_bbox;
uniform float u_seed;
uniform vec3 u_sun_dir;
uniform float u_sun_intensity;
uniform float u_ambient_intensity;

// Live technical controls
uniform float u_forest_density;
uniform float u_canopy_roughness;
uniform float u_tree_scale;
uniform float u_plains_grain;
uniform float u_soil_patchiness;
uniform float u_grass_warmth;
uniform float u_lake_depth_mult;

vec3 noised(in vec2 p) {
    vec2 fl = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    vec2 du = 6.0 * f * (1.0 - f);

    vec2 i0 = mod(fl, 256.0);
    vec2 i1 = mod(fl + 1.0, 256.0);

    vec2 uv0 = (i0 + vec2(0.5)) / 256.0;
    vec2 uv1 = (i1 + vec2(0.5)) / 256.0;

    float a = texture(u_noise_tex, vec2(uv0.x, uv0.y)).r;
    float b = texture(u_noise_tex, vec2(uv1.x, uv0.y)).r;
    float c = texture(u_noise_tex, vec2(uv0.x, uv1.y)).r;
    float d = texture(u_noise_tex, vec2(uv1.x, uv1.y)).r;

    float k0 = a;
    float k1 = b - a;
    float k2 = c - a;
    float k3 = a - b - c + d;

    float val = k0 + k1 * u.x + k2 * u.y + k3 * u.x * u.y;
    vec2 deriv = du * vec2(k1 + k3 * u.y, k2 + k3 * u.x);
    return vec3(val, deriv);
}

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453123);
}

float hash1(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

// Procedural Voronoi crown cell stamps for individual tree heads, highlights & shadows
void evaluate_canopy_crowns(vec2 p, vec2 sun_dir_2d, float tree_scale,
                            out float out_cov, out float out_hi, out float out_sh, out float out_tex) {
    float cc = max(3.0, tree_scale * 5.0);
    vec2 u = p / cc;
    vec2 nu = floor(u);
    vec2 fu = fract(u);

    float wsum = 0.0001;
    float tone_ws = 0.0;
    float relief_ws = 0.0;
    float cov_max = 0.0;
    float hi_max = 0.0;
    float sh_max = 0.0;

    for (int gv = -1; gv <= 1; gv++) {
        for (int gu = -1; gu <= 1; gu++) {
            vec2 g = vec2(float(gu), float(gv));
            vec2 cell = nu + g;
            vec2 o = hash2(cell + vec2(1.0, 2.0));
            float hr = hash1(cell + vec2(3.0, 4.0));
            float hv = hash1(cell + vec2(5.0, 6.0));

            vec2 r = (g - fu + o) * cc;
            float rad = cc * (0.70 + 0.55 * hr);
            float d = length(r);
            float qn = d / max(rad, 0.001);

            if (qn < 1.35) {
                float prof = max(0.0, 1.0 - qn * qn);
                float tone = (hv < 0.42) ? -0.55 : ((hv < 0.80) ? 0.05 : 0.55);
                float sunlit = -dot(r, sun_dir_2d) / max(d, 0.001);

                wsum += prof;
                tone_ws += prof * tone;
                relief_ws += prof * sunlit;
                cov_max = max(cov_max, prof);
                hi_max = max(hi_max, clamp(sunlit, 0.0, 1.0) * prof);

                float ring = smoothstep(1.0, 1.35, qn) * (1.0 - smoothstep(1.35, 1.85, qn));
                if (sunlit < -0.10) {
                    sh_max = max(sh_max, ring * (-sunlit));
                }
            }
        }
    }

    float tone_blend = tone_ws / wsum;
    float relief_blend = relief_ws / wsum;
    out_cov = cov_max;
    out_hi = hi_max;
    out_sh = sh_max;
    out_tex = clamp(0.55 * tone_blend + 0.50 * (cov_max - 0.62) + 0.22 * relief_blend, -0.80, 0.60);
}

// Domain-warped Voronoi agricultural soil parcels (~36 px)
void evaluate_parcels(vec2 p, out float out_edge, out float out_dry) {
    vec2 pc = p / 36.0;
    vec2 nu = floor(pc);
    vec2 fu = fract(pc);

    float f1 = 1e9;
    float f2 = 1e9;
    float parcel_id = 0.0;

    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 cell = nu + g;
            vec2 o = hash2(cell + vec2(3.7, 8.1));
            vec2 feat = g + 0.15 + 0.70 * o;
            vec2 diff = fu - feat;
            float d2 = dot(diff, diff);

            if (d2 < f1) {
                f2 = f1;
                f1 = d2;
                parcel_id = hash1(cell + vec2(19.3, 4.2));
            } else if (d2 < f2) {
                f2 = d2;
            }
        }
    }

    out_edge = clamp((sqrt(f2) - sqrt(f1)) / 0.14, 0.0, 1.0);
    out_dry = clamp((parcel_id - 0.58) / 0.22, 0.0, 1.0) * out_edge;
}

// Ridged noise agricultural track filaments / hedge lines
float evaluate_filaments(vec2 p) {
    float fr_s = 1.0 / 62.5;
    vec3 fa0 = noised(p * fr_s * 0.40 + vec2(5.0, -2.0));
    vec3 fa1 = noised(p * fr_s * 0.90 + vec2(51.0, -7.0));
    float fa_v = fa0.x * 0.7 + fa1.x * 0.3;
    float ridgeA = 1.0 - abs(2.0 * fa_v - 1.0);

    vec3 fb0 = noised(p * fr_s * 1.60 + vec2(-8.0, 11.0));
    vec3 fb1 = noised(p * fr_s * 3.20 + vec2(17.0, -4.0));
    float fb_v = fb0.x * 0.7 + fb1.x * 0.3;
    float ridgeB = 1.0 - abs(2.0 * fb_v - 1.0);

    float fil_dark = max(smoothstep(0.88, 0.972, ridgeA), smoothstep(0.90, 0.978, ridgeB));
    vec3 sp = noised(p / 250.0 + vec2(30.0, -14.0));
    return fil_dark * clamp((sp.x - 0.42) / 0.28, 0.0, 1.0);
}

void main() {
    vec4 elev_data = texture(u_elev_tex, v_uv);
    float H = elev_data.r;
    float land_prob = elev_data.g;
    float mount_prob = elev_data.b;
    float forest_prob = elev_data.a;

    vec4 aux_data = texture(u_aux_tex, v_uv);
    float snow_prob = aux_data.r;
    float slope_hint = aux_data.g;

    vec4 norm_data = texture(u_normal_tex, v_uv);
    vec3 N = norm_data.xyz;
    float slope = norm_data.w;

    vec2 world_pos = mix(u_bbox.xy, u_bbox.zw, v_uv);
    vec3 riv_warp = noised(world_pos * 0.04);
    vec2 riv_uv = v_uv + riv_warp.yz * 0.005;
    vec4 river_data = texture(u_river_tex, riv_uv);

    // Directional Sun lighting & ambient sky lighting
    vec3 L = normalize(u_sun_dir);
    float NdotL = max(0.0, dot(N, L));
    float diffuse = pow(NdotL, 1.05) * u_sun_intensity;
    float sky_light = (N.z * 0.60 + 0.40) * u_ambient_intensity;
    float total_light = diffuse + sky_light;

    // Photorealistic Color Palettes
    vec3 deep_ocean        = vec3(0.05, 0.14, 0.32);  // Sapphire navy
    vec3 mid_ocean         = vec3(0.10, 0.26, 0.44);  // Maritime blue
    vec3 shallow_shelf     = vec3(0.15, 0.44, 0.55);  // Azure shelf
    vec3 coastal_turquoise = vec3(0.25, 0.62, 0.65);  // Tropical turquoise

    vec3 wet_sand          = vec3(0.72, 0.66, 0.50);  // Wet shoreline sand
    vec3 gold_sand         = vec3(0.88, 0.82, 0.60);  // Dry golden sand
    vec3 dune_sand         = vec3(0.94, 0.89, 0.72);  // Sunlit coastal dunes

    vec3 grass_sage        = vec3(0.40, 0.46, 0.34);  // Desaturated cool sage
    vec3 grass_mid         = vec3(0.37, 0.45, 0.27);  // Neutral meadow olive
    vec3 grass_dry         = vec3(0.55, 0.52, 0.30);  // Warm straw

    vec3 riparian_turf     = vec3(0.17, 0.40, 0.15);  // Lush riverbank turf
    vec3 woodland_floor    = vec3(0.13, 0.22, 0.11);  // Dark forest litter underlay

    vec3 canopy_deep       = vec3(0.06, 0.14, 0.08);  // Deep pine green
    vec3 canopy_core       = vec3(0.13, 0.27, 0.12);  // Rich cedar emerald
    vec3 canopy_olive      = vec3(0.30, 0.38, 0.17);  // Sunlit golden crown

    vec3 hills_col         = vec3(0.46, 0.43, 0.30);  // Highland scrub
    vec3 rock_slate        = vec3(0.38, 0.37, 0.41);  // Dark mountain slate
    vec3 rock_granite      = vec3(0.52, 0.51, 0.55);  // Sunlit granite
    vec3 rock_scree        = vec3(0.44, 0.42, 0.40);  // Alpine talus / scree
    vec3 cliff_dark        = vec3(0.26, 0.25, 0.28);  // Shadowed rock crevice

    vec3 snow_base         = vec3(0.92, 0.95, 0.98);  // Alpine snow
    vec3 snow_summit       = vec3(1.00, 1.00, 1.00);  // Glacial summit

    vec3 lake_deep         = vec3(0.10, 0.28, 0.54);  // Deep alpine tarn
    vec3 lake_shallow      = vec3(0.22, 0.52, 0.68);  // Shallow stream azure
    vec3 estuary_col       = vec3(0.15, 0.33, 0.40);  // River mouth brackish water

    vec3 final_color;

    if (H < 0.0) {
        // --- 1. Ocean Bathymetry & Coastal Waves ---
        float depth = -H;
        float t_shallow = clamp(depth / 0.055, 0.0, 1.0);
        float t_mid = clamp((depth - 0.055) / 0.15, 0.0, 1.0);
        float t_deep = clamp((depth - 0.18) / 0.16, 0.0, 1.0);

        vec3 c_shelf = mix(coastal_turquoise, shallow_shelf, t_shallow);
        vec3 c_water = mix(c_shelf, mid_ocean, t_mid);
        vec3 w_col   = mix(c_water, deep_ocean, t_deep);

        // Water surface ripples
        vec3 wave_n = noised(world_pos * 0.08 + vec2(u_seed * 0.1, 0.0));
        vec3 half_vec = normalize(vec3(u_sun_dir.xy, u_sun_dir.z + 1.0));
        vec3 wave_norm = normalize(vec3(-wave_n.yz * 0.15, 1.0));

        float w_NdotL = clamp(dot(wave_norm, L), 0.0, 1.0);
        float w_diffuse = 0.65 + 0.35 * pow(w_NdotL, 1.2);

        float w_NdotH = clamp(dot(wave_norm, half_vec), 0.0, 1.0);
        float specular = (pow(w_NdotH, 36.0) * 0.18 + pow(w_NdotH, 90.0) * 0.30) * u_sun_intensity;

        final_color = w_col * w_diffuse + vec3(specular);

        // Shore surf foam
        float dist_to_shore = max(0.0, (0.30 - land_prob) * 6.5);
        if (dist_to_shore < 0.14 && depth > 0.001) {
            float foam_mask = pow(clamp((0.14 - dist_to_shore) / 0.14, 0.0, 1.0), 1.5);
            vec3 surf_n = noised(world_pos * 0.25);
            if (surf_n.x > 0.45) {
                final_color = mix(final_color, vec3(0.95, 0.97, 0.98), foam_mask * 0.75);
            }
        }
    } else {
        // --- 2. Multi-Scale Procedural Plains & Ground Cover ---
        // (A) High-frequency value grain (3-13 px)
        vec3 grain_n1 = noised(world_pos / 6.0);
        vec3 grain_n2 = noised(world_pos / 3.0);
        float grain = (grain_n1.x * 0.65 + grain_n2.x * 0.35 - 0.50) * 2.0 * u_plains_grain;

        // (B) Sub-hex clump mottle (9-20 px)
        vec3 clump_n = noised(world_pos / 16.0);
        float clump = (clump_n.x - 0.50) * 2.0;

        // (C) Domain-warped agricultural soil parcels (~36 px)
        float parcel_edge, parcel_dry;
        evaluate_parcels(world_pos, parcel_edge, parcel_dry);
        parcel_dry *= u_soil_patchiness;

        // (D) Thin linear tracks / furrows
        float fil_dark = evaluate_filaments(world_pos);

        // (E) Hill band dry/desaturate transition
        float hillw = smoothstep(0.15, 0.75, aux_data.g);

        // Modulate local dryness and saturation
        float dryness = clamp(0.50 + 0.16 * parcel_dry + 0.05 * clump + 0.05 * grain + 0.22 * hillw + (u_grass_warmth - 1.0) * 0.25, 0.15, 0.88);
        float sat_mod = clamp(0.50 - 0.12 * parcel_dry + 0.14 * clump + 0.14 * grain - 0.24 * hillw, 0.0, 1.0);
        float value_mott = clamp(1.0 - 0.045 * parcel_dry + 0.11 * clump + 0.26 * grain - 0.20 * fil_dark - 0.09 * hillw, 0.65, 1.35);

        // Tri-tone grass blending: sage -> mid meadow -> warm straw
        vec3 plains_col = (dryness < 0.50) ? mix(grass_sage, grass_mid, dryness / 0.50) : mix(grass_mid, grass_dry, (dryness - 0.50) / 0.50);
        float luma = dot(plains_col, vec3(0.299, 0.587, 0.114));
        plains_col = luma + (plains_col - luma) * (0.82 + 0.40 * sat_mod);
        plains_col *= value_mott;

        // Green-leads-blue guard so grass never reads as shallow turquoise
        plains_col.b = min(plains_col.b, plains_col.g * 0.86);
        plains_col.r = max(plains_col.r, plains_col.b * 0.95);

        vec3 ground_c = plains_col;

        // (F) Riparian moisture & lush turf margin along rivers & lakes
        if (river_data.a > 0.05) {
            float rip_blend = clamp(river_data.a * 0.88, 0.0, 1.0);
            ground_c = mix(ground_c, riparian_turf, rip_blend);
        }

        // (G) Prominent Sandy Beach & Dunes
        if (H < 0.075) {
            float t_beach = clamp(H / 0.065, 0.0, 1.0);
            vec3 beach_col = mix(wet_sand, gold_sand, t_beach);
            if (H > 0.040) {
                beach_col = mix(beach_col, dune_sand, (H - 0.040) / 0.035);
            }
            float beach_mask = 1.0 - smoothstep(0.015, 0.065, H);
            ground_c = mix(ground_c, beach_col, beach_mask);
        }

        // (H) Mountain rock & cliff strata
        float m_weight = clamp(mount_prob * 1.5 + clamp((H - 0.22) / 0.25, 0.0, 1.0), 0.0, 1.0);
        vec3 m_rock = mix(rock_slate, rock_granite, clamp((H - 0.35) / 0.35, 0.0, 1.0));
        if (slope < 0.12) {
            m_rock = rock_scree;
        }
        ground_c = mix(ground_c, m_rock, m_weight);

        // Steep cliff exposure
        if (slope > 0.14) {
            float cliff_factor = clamp((slope - 0.14) / 0.18, 0.0, 1.0) * (mount_prob * 1.5 + 0.3);
            ground_c = mix(ground_c, cliff_dark, clamp(cliff_factor, 0.0, 0.85));
        }

        // (I) Glacial Snow Summits
        float snow_mask = smoothstep(0.25, 0.65, snow_prob) * smoothstep(0.50, 0.80, H);
        vec3 snow_col = mix(snow_base, snow_summit, clamp((H - 0.75) / 0.20, 0.0, 1.0));
        ground_c = mix(ground_c, snow_col, snow_mask);

        // --- 3. 2D Volumetric Forest Canopy Layer ---
        float tree_s = max(0.5, u_tree_scale);
        float crown_cov, crown_hi, crown_sh, crown_tex;
        evaluate_canopy_crowns(world_pos, u_sun_dir.xy, tree_s, crown_cov, crown_hi, crown_sh, crown_tex);

        // Multi-octave boundary noise for bays and crenellated canopy edges
        vec3 cbn1 = noised(world_pos / 150.0);
        vec3 cbn2 = noised(world_pos / 40.0);
        vec3 cfn = noised(world_pos / 12.0);
        float edge_noise = (cbn1.x * 0.6 + cbn2.x * 0.3 + cfn.x * 0.1 - 0.5) * 2.0 * u_canopy_roughness;

        // Interior clearings
        vec3 clear_n = noised(world_pos / 90.0);
        float clearing = smoothstep(0.52, 0.80, clear_n.x);

        // Treeline & slope falloff
        float elev_treeline = clamp(1.0 - (H - 0.20) / 0.16, 0.0, 1.0);
        float mount_treeline = clamp(1.0 - mount_prob * 2.2, 0.0, 1.0);
        float slope_treeline = clamp(1.0 - (slope - 0.14) / 0.34, 0.0, 1.0);
        float treeline_factor = elev_treeline * mount_treeline * slope_treeline;

        // Continuous canopy density
        float f_edge = (forest_prob + 0.35 * edge_noise + 0.07 * (crown_cov - 0.55)) * u_forest_density;
        float canopy_density = smoothstep(0.28, 0.50, f_edge) * (1.0 - 0.85 * clearing) * treeline_factor;

        // Forest floor AO darkening under canopy
        ground_c = mix(ground_c, ground_c * 0.70, smoothstep(0.1, 0.7, canopy_density));

        // Canopy surface color: deep pine -> cedar emerald -> sunlit olive
        vec3 canopy_rgb = mix(canopy_deep, canopy_core, 0.5 + 0.5 * crown_tex);
        canopy_rgb = mix(canopy_rgb, canopy_olive, 0.55 * crown_hi);
        canopy_rgb *= (1.0 - 0.34 * crown_sh);

        // Composite canopy over terrain
        float canopy_alpha = smoothstep(0.14, 0.42, canopy_density) + 0.35 * crown_cov * smoothstep(0.04, 0.22, canopy_density);
        ground_c = mix(ground_c, canopy_rgb, clamp(canopy_alpha, 0.0, 1.0));

        // Apply 3D solar hillshading
        final_color = ground_c * total_light;

        // --- 4. Flat Inland Rivers & Alpine Tarn Lakes ---
        if (river_data.r > 0.05) {
            float r_alpha = smoothstep(0.05, 0.55, river_data.r);
            float lake_depth = clamp(river_data.g * u_lake_depth_mult, 0.0, 1.0);
            vec3 inland_col = mix(lake_shallow, lake_deep, lake_depth);

            // Estuary brackish tint near coast
            if (H < 0.02) {
                inland_col = mix(inland_col, estuary_col, 0.60);
            }

            // Flat water sun reflection
            vec3 half_v = normalize(vec3(u_sun_dir.xy, u_sun_dir.z + 1.0));
            float spec_flat = pow(max(0.0, dot(N, half_v)), 32.0) * 0.35 * u_sun_intensity;

            vec3 inland_lit = inland_col * (total_light * 0.65 + 0.35) + vec3(spec_flat);
            final_color = mix(final_color, inland_lit, r_alpha);
        }
    }

    frag_color = vec4(final_color, 1.0);
}
"""

# Retain single-pass TERRAIN_FRAG for backward compatibility
TERRAIN_FRAG = PASS3_COMPOSITE_FRAG
