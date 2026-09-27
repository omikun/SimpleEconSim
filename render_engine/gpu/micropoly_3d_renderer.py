"""
render_engine/gpu/micropoly_3d_renderer.py — Real-time ModernGL 3D GPU Perspective Renderer.

Features:
- True 3D perspective projection with 35mm lens (FOV ~45°).
- Constant view angle from overview to close-up (pitch ~52°, yaw ~9°), moving camera closer on zoom.
- Directional 3D shadow mapping with PCF (Percentage Closer Filtering) 3x3 kernel.
- 3D faceted micropoly terrain mesh with Oren-Nayar diffuse, GGX specular, rock strata, and snow peaks.
- 3D low-poly faceted trees placed on forest biomes with shadow reception.
- 3D hydro river ribbons carved through canyons with downstream ripple animation.
- Option A coastal waves & breakers with 2D SDF shoreline refraction, beach swash, and Voronoi seafoam lace.
- Sub-millisecond FBO rendering and seamless Pygame surface integration.
"""

import math
import os
import json
import numpy as np
import pygame

try:
    import moderngl
    MODERNGL_AVAILABLE = True
except ImportError:
    moderngl = None
    MODERNGL_AVAILABLE = False


# ── Matrix Math Helpers ────────────────────────────────────────────────────────

def mat4_perspective(fovy_rad: float, aspect: float, near: float, far: float) -> np.ndarray:
    tan_half = math.tan(fovy_rad / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 1.0 / (aspect * tan_half)
    m[1, 1] = 1.0 / tan_half
    m[2, 2] = -(far + near) / (far - near)
    m[2, 3] = -(2.0 * far * near) / (far - near)
    m[3, 2] = -1.0
    m[3, 3] = 0.0
    return m


def mat4_ortho(left: float, right: float, bottom: float, top: float, near: float, far: float) -> np.ndarray:
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


def mat4_lookat(eye, target, up) -> np.ndarray:
    eye = np.array(eye, dtype=np.float32)
    target = np.array(target, dtype=np.float32)
    up = np.array(up, dtype=np.float32)

    z = eye - target
    z_len = np.linalg.norm(z)
    z = z / (z_len if z_len > 1e-6 else 1.0)

    x = np.cross(up, z)
    x_len = np.linalg.norm(x)
    x = x / (x_len if x_len > 1e-6 else 1.0)

    y = np.cross(z, x)

    m = np.eye(4, dtype=np.float32)
    m[0, :3] = x
    m[1, :3] = y
    m[2, :3] = z
    m[0, 3] = -float(np.dot(x, eye))
    m[1, 3] = -float(np.dot(y, eye))
    m[2, 3] = -float(np.dot(z, eye))
    return m


# ── GLSL Shaders ──────────────────────────────────────────────────────────────

SHADOW_VS = """#version 330 core
layout(location = 0) in vec3 in_pos;
uniform mat4 u_light_vp;
void main() {
    gl_Position = u_light_vp * vec4(in_pos, 1.0);
}
"""

SHADOW_FS = """#version 330 core
void main() {}
"""

MESH_VS = """#version 330 core
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_norm;
layout(location = 2) in vec3 in_color;
layout(location = 3) in float in_elev;

uniform mat4 u_proj;
uniform mat4 u_view;
uniform mat4 u_shadow_matrix;
uniform vec3 u_sun_dir;

out vec3 v_norm;
out vec3 v_world_norm;
out vec3 v_world_pos;
out vec3 v_color;
out float v_elev;
out vec4 v_shadow_coord;
out vec3 v_sun_dir;
out vec3 v_fill_dir;

void main() {
    v_world_pos = in_pos;
    v_world_norm = normalize(in_norm);
    v_color = in_color;
    v_elev = in_elev;
    v_shadow_coord = u_shadow_matrix * vec4(in_pos, 1.0);

    mat3 normal_matrix = mat3(u_view);
    v_norm = normalize(normal_matrix * in_norm);
    v_sun_dir = normalize(normal_matrix * u_sun_dir);
    v_fill_dir = normalize(normal_matrix * vec3(0.45, -0.65, 0.60));

    gl_Position = u_proj * u_view * vec4(in_pos, 1.0);
}
"""

MESH_FS = """#version 330 core
in vec3 v_norm;
in vec3 v_world_norm;
in vec3 v_world_pos;
in vec3 v_color;
in float v_elev;
in vec4 v_shadow_coord;
in vec3 v_sun_dir;
in vec3 v_fill_dir;

uniform float u_sun_intensity;
uniform float u_ambient_intensity;
uniform float u_mountain_roughness;
uniform float u_snow_threshold;
uniform int u_shadow_mode;
uniform float u_shadow_darkness;
uniform vec3 u_sun_world_dir;
uniform sampler2D u_shadow_map;
uniform float u_shadow_size;

uniform float u_micropoly_strata;
uniform float u_micropoly_parcels;
uniform float u_micropoly_grain;
uniform float u_micropoly_blend;

out vec4 frag_color;

const float PI = 3.141592653589793;

const vec2 POISSON_DISK[16] = vec2[](
    vec2(-0.326212, -0.405810),
    vec2(-0.840144, -0.073580),
    vec2(-0.695914,  0.457137),
    vec2(-0.203345,  0.620716),
    vec2( 0.962340, -0.194983),
    vec2( 0.473434, -0.480026),
    vec2( 0.519456,  0.767022),
    vec2( 0.185461, -0.893124),
    vec2( 0.507431,  0.064425),
    vec2( 0.896420,  0.412458),
    vec2(-0.321940, -0.932615),
    vec2(-0.791559, -0.597710),
    vec2(-0.111818, -0.161108),
    vec2( 0.282828,  0.312918),
    vec2(-0.413812,  0.183719),
    vec2( 0.211412, -0.251918)
);

float compute_shadow_map(vec4 light_space_pos, vec3 N, vec3 L) {
    vec3 proj = light_space_pos.xyz / light_space_pos.w;
    if (proj.z > 1.0 || proj.x < 0.0 || proj.x > 1.0 || proj.y < 0.0 || proj.y > 1.0) {
        return 1.0;
    }
    float NdotL = max(0.0, dot(N, L));
    // Tight slope-scaled bias to avoid acne while allowing crisp contact
    float bias = max(0.0016 * (1.0 - NdotL), 0.0004);
    float current_depth = proj.z - bias;

    // Contact Hardening: measure distance from blocker to receiver
    float blocker_depth = texture(u_shadow_map, proj.xy).r;
    float blocker_dist = max(0.0, current_depth - blocker_depth);

    // Near contact (tree base, cliff foot): penumbra is tiny (0.35 texels) -> sharp!
    // Distant caster (canopy, mountain peak): penumbra expands naturally (up to 2.4 texels)
    float penumbra = clamp(blocker_dist * 140.0, 0.35, 2.4);
    vec2 texel_step = (penumbra / max(1024.0, u_shadow_size)) * vec2(1.0);

    float shadow = 0.0;
    for (int i = 0; i < 16; ++i) {
        float sample_depth = texture(u_shadow_map, proj.xy + POISSON_DISK[i] * texel_step).r;
        shadow += (sample_depth >= current_depth) ? 1.0 : 0.0;
    }
    return shadow / 16.0;
}

float oren_nayar_diffuse(vec3 N, vec3 L, vec3 V, float roughness) {
    float NdotL = dot(N, L);
    float NdotV = dot(N, V);
    float s = max(0.0, NdotL);
    if (s <= 0.0) return 0.0;

    float sigma2 = roughness * roughness;
    float A = 1.0 - 0.5 * (sigma2 / (sigma2 + 0.33));
    float B = 0.45 * (sigma2 / (sigma2 + 0.09));

    vec3 L_proj = normalize(L - N * NdotL + vec3(1e-5));
    vec3 V_proj = normalize(V - N * NdotV + vec3(1e-5));
    float cos_phi = max(0.0, dot(L_proj, V_proj));

    float theta_i = acos(clamp(NdotL, 0.0, 0.999));
    float theta_r = acos(clamp(NdotV, 0.001, 0.999));

    float sin_alpha = (theta_i >= theta_r) ? sin(theta_i) : sin(theta_r);
    float tan_beta  = (theta_i >= theta_r) ? tan(theta_r) : tan(theta_i);
    tan_beta = clamp(tan_beta, 0.0, 5.0);

    return s * (A + B * cos_phi * sin_alpha * tan_beta);
}

float distribution_ggx(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float NdotH2 = NdotH * NdotH;
    float denom = (NdotH2 * (a2 - 1.0) + 1.0);
    denom = PI * denom * denom;
    return a2 / max(denom, 0.0000001);
}

float geometry_schlick_ggx(float NdotV, float roughness) {
    float r = (roughness + 1.0);
    float k = (r * r) / 8.0;
    return NdotV / (NdotV * (1.0 - k) + k);
}

float geometry_smith(vec3 N, vec3 V, vec3 L, float roughness) {
    float NdotV = max(dot(N, V), 0.0);
    float NdotL = max(dot(N, L), 0.0);
    return geometry_schlick_ggx(NdotV, roughness) * geometry_schlick_ggx(NdotL, roughness);
}

vec3 fresnel_schlick(float cos_theta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cos_theta, 0.0, 1.0), 5.0);
}

void main() {
    vec3 N = normalize(v_norm);
    vec3 L = normalize(v_sun_dir);
    vec3 V = vec3(0.0, 0.0, 1.0);
    vec3 H = normalize(L + V);

    vec3 base_color = v_color;
    float is_water = step(v_elev, 0.0);

    if (is_water < 0.5) {
        float slope = 1.0 - max(0.0, v_world_norm.z);
        if (slope > 0.45 && u_micropoly_strata > 0.5) {
            float strata = sin(v_world_pos.z * 1.8) * 0.5 + 0.5;
            vec3 rock_tint = mix(vec3(0.48, 0.44, 0.40), vec3(0.38, 0.34, 0.30), strata);
            base_color = mix(base_color, rock_tint, smoothstep(0.45, 0.75, slope) * 0.65);
        }
        if (v_elev > u_snow_threshold) {
            float snow_factor = smoothstep(u_snow_threshold, u_snow_threshold + 0.12, v_elev);
            vec3 snow_color = vec3(0.95, 0.97, 1.0);
            base_color = mix(base_color, snow_color, snow_factor * (1.0 - smoothstep(0.65, 0.90, slope)));
        }
    }

    float roughness = mix(0.55, 0.92, u_mountain_roughness);
    if (is_water > 0.5) roughness = 0.18;

    float diff = oren_nayar_diffuse(N, L, V, roughness);
    vec3 F0 = mix(vec3(0.04), base_color, 0.1);
    if (is_water > 0.5) F0 = vec3(0.02);

    float NDF = distribution_ggx(N, H, roughness);
    float G = geometry_smith(N, V, L, roughness);
    vec3 F = fresnel_schlick(max(dot(H, V), 0.0), F0);
    vec3 kD = (vec3(1.0) - F);
    vec3 spec = (NDF * G * F) / max(4.0 * max(dot(N, V), 0.0) * max(dot(N, L), 0.0), 0.001);

    float cast_shadow = 1.0;
    if (u_shadow_mode == 1) {
        cast_shadow = compute_shadow_map(v_shadow_coord, v_world_norm, normalize(u_sun_world_dir));
    }
    float shadow = (u_shadow_mode == 0) ? 1.0 : mix(1.0, cast_shadow, clamp(u_shadow_darkness, 0.0, 1.0));

    vec3 ambient = u_ambient_intensity * vec3(0.55, 0.62, 0.72) * base_color;
    float fill_diff = max(0.0, dot(N, normalize(v_fill_dir))) * 0.22;
    vec3 fill_light = fill_diff * vec3(0.70, 0.80, 0.90) * base_color;

    vec3 direct = (kD * base_color * diff + spec * 0.45) * u_sun_intensity * vec3(1.0, 0.96, 0.88) * shadow;
    vec3 final_color = ambient + fill_light + direct;

    frag_color = vec4(clamp(final_color, 0.0, 1.0), 1.0);
}
"""

OCEAN_VS = """#version 330 core
layout(location = 0) in vec3 in_pos;
uniform mat4 u_proj;
uniform mat4 u_view;
out vec3 v_world_pos;
void main() {
    v_world_pos = in_pos;
    gl_Position = u_proj * u_view * vec4(in_pos, 1.0);
}
"""

OCEAN_FS = """#version 330 core
in vec3 v_world_pos;
uniform float u_time;
uniform float u_wave_intensity;
uniform float u_wave_speed;
uniform float u_wave_period;
uniform vec3 u_sun_world_dir;
out vec4 frag_color;

void main() {
    float speed = max(0.05, u_wave_speed);
    float period = max(0.2, u_wave_period);
    float t = u_time * speed;

    vec2 uv1 = v_world_pos.xy * (0.052 / period);
    vec2 dN1 = vec2(
        cos(uv1.x * 0.8 + uv1.y * 0.6 - t * 1.8) * 0.8,
        sin(uv1.x * 0.6 - uv1.y * 0.8 + t * 1.5) * 0.8
    ) * 0.025;

    vec2 uv2 = v_world_pos.xy * (0.18 / period);
    vec2 dN2 = vec2(
        cos(uv2.x * 1.2 - uv2.y * 0.7 - t * 2.6) * 1.2,
        sin(uv2.x * 0.7 + uv2.y * 1.2 - t * 2.3) * 1.2
    ) * 0.015;

    vec2 dN = (dN1 + dN2) * u_wave_intensity;
    vec3 N = normalize(vec3(dN, 1.0));
    vec3 L = normalize(u_sun_world_dir);
    vec3 V = normalize(vec3(0.0, 0.45, 0.89));
    vec3 H = normalize(L + V);

    float NdotV = max(0.0, dot(N, V));
    float fresnel = 0.04 + 0.96 * pow(1.0 - NdotV, 5.0);
    float sun_spec = pow(max(0.0, dot(N, H)), 48.0) * 1.20;

    vec3 deep_ocean = vec3(0.04, 0.18, 0.35);
    vec3 sky_refl = vec3(0.35, 0.60, 0.82);

    vec3 water_color = mix(deep_ocean, sky_refl, fresnel);
    water_color += vec3(1.0, 0.96, 0.85) * sun_spec;

    frag_color = vec4(water_color, 1.0);
}
"""

RIVER_VS = """#version 330 core
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec3 in_color;
layout(location = 3) in float in_flow;

uniform mat4 u_proj;
uniform mat4 u_view;
uniform mat4 u_shadow_matrix;
uniform float u_time;
uniform vec3 u_sun_dir;

out vec3 v_color;
out vec3 v_normal;
out float v_flow;
out vec3 v_sun_dir;
out vec4 v_shadow_coord;
out vec3 v_world_pos;

void main() {
    float ripple = sin(u_time * 4.2 - in_flow * 3.5) * 0.04;
    vec3 p_world = vec3(in_pos.x, in_pos.y, in_pos.z + ripple);

    v_world_pos = p_world;
    v_color = in_color;
    v_normal = normalize(mat3(u_view) * in_normal);
    v_flow = in_flow;
    v_sun_dir = normalize(mat3(u_view) * u_sun_dir);
    v_shadow_coord = u_shadow_matrix * vec4(p_world, 1.0);

    gl_Position = u_proj * u_view * vec4(p_world, 1.0);
}
"""

RIVER_FS = """#version 330 core
in vec3 v_color;
in vec3 v_normal;
in float v_flow;
in vec3 v_sun_dir;
in vec4 v_shadow_coord;
in vec3 v_world_pos;

uniform sampler2D u_shadow_map;
uniform float u_shadow_size;
uniform int u_shadow_mode;
uniform float u_shadow_darkness;
uniform vec3 u_sun_world_dir;

out vec4 frag_color;

const vec2 POISSON_DISK[16] = vec2[](
    vec2(-0.326212, -0.405810),
    vec2(-0.840144, -0.073580),
    vec2(-0.695914,  0.457137),
    vec2(-0.203345,  0.620716),
    vec2( 0.962340, -0.194983),
    vec2( 0.473434, -0.480026),
    vec2( 0.519456,  0.767022),
    vec2( 0.185461, -0.893124),
    vec2( 0.507431,  0.064425),
    vec2( 0.896420,  0.412458),
    vec2(-0.321940, -0.932615),
    vec2(-0.791559, -0.597710),
    vec2(-0.111818, -0.161108),
    vec2( 0.282828,  0.312918),
    vec2(-0.413812,  0.183719),
    vec2( 0.211412, -0.251918)
);

float compute_shadow_map(vec4 light_space_pos, vec3 N, vec3 L) {
    vec3 proj = light_space_pos.xyz / light_space_pos.w;
    if (proj.z > 1.0 || proj.x < 0.0 || proj.x > 1.0 || proj.y < 0.0 || proj.y > 1.0) {
        return 1.0;
    }
    float NdotL = max(0.0, dot(N, L));
    float bias = max(0.0016 * (1.0 - NdotL), 0.0004);
    float current_depth = proj.z - bias;

    float blocker_depth = texture(u_shadow_map, proj.xy).r;
    float blocker_dist = max(0.0, current_depth - blocker_depth);

    float penumbra = clamp(blocker_dist * 140.0, 0.35, 2.4);
    vec2 texel_step = (penumbra / max(1024.0, u_shadow_size)) * vec2(1.0);

    float shadow = 0.0;
    for (int i = 0; i < 16; ++i) {
        float sample_depth = texture(u_shadow_map, proj.xy + POISSON_DISK[i] * texel_step).r;
        shadow += (sample_depth >= current_depth) ? 1.0 : 0.0;
    }
    return shadow / 16.0;
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(v_sun_dir);
    vec3 V = vec3(0.0, 0.0, 1.0);
    vec3 H = normalize(L + V);

    float diff = max(0.0, dot(N, L));
    float specular = pow(max(0.0, dot(N, H)), 48.0);

    float cast_shadow = 1.0;
    if (u_shadow_mode == 1) {
        cast_shadow = compute_shadow_map(v_shadow_coord, vec3(0.0, 0.0, 1.0), normalize(u_sun_world_dir));
    }
    float shadow = mix(1.0, cast_shadow, clamp(u_shadow_darkness, 0.0, 1.0));

    vec3 col = v_color * (0.45 + 0.55 * diff * shadow);
    col += vec3(0.90, 0.96, 1.0) * (specular * 0.65 * shadow);
    frag_color = vec4(clamp(col, 0.0, 1.0), 0.95);
}
"""

SURF_VS = """#version 330 core
layout(location = 0) in vec3 in_pos;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec3 in_color;
layout(location = 3) in float in_dist;

uniform mat4 u_proj;
uniform mat4 u_view;
uniform float u_time;
uniform float u_wave_intensity;
uniform float u_wave_speed;
uniform float u_wave_period;
uniform float u_wave_desync;

out vec3 v_world_pos;
out vec3 v_world_norm;
out vec3 v_color;
out float v_dist;
out float v_wave_crest;
out float v_phase;

void main() {
    float z_offset = 0.0;
    vec2 horiz_offset = vec2(0.0);
    float wave_phase = 0.0;
    float crest_val = 0.0;

    vec2 swell_dir = normalize(vec2(-0.707, 0.707));
    float exposure = dot(in_normal.xy, swell_dir);
    float coast_exposure = mix(1.0, clamp(exposure * 0.85 + 0.40, 0.05, 1.0), u_wave_desync);

    float along_shore = dot(in_pos.xy, vec2(-in_normal.y, in_normal.x));
    float sector_id = floor(along_shore * 0.012);
    float sector_phase = sin(sector_id * 14.123) * 6.2831;
    float local_desync = (sin(along_shore * 0.018) * 2.2 + cos(along_shore * 0.042) * 1.1) * u_wave_desync;

    float t = u_time * (0.85 * u_wave_speed);
    float group_phase = t * 0.25 + sector_phase + along_shore * 0.008;
    float wave_packet = pow(clamp(sin(group_phase), 0.0, 1.0), 1.5);
    float k_shelf = 5.2 / max(0.2, u_wave_period);

    float wave_phase1 = t * 2.0 - in_dist * k_shelf + local_desync;
    float wave_phase2 = t * 1.25 - in_dist * (k_shelf * 0.60) + sector_phase * 0.5;
    wave_phase = mix(wave_phase1, wave_phase2, 0.30);

    float s1 = sin(wave_phase1);
    float s2 = sin(wave_phase2);
    float composite = clamp(s1 * 0.70 + s2 * 0.30, 0.0, 1.0);

    float shoaling = (1.0 + 1.2 * exp(-pow((in_dist - 0.22) * 4.5, 2.0))) * coast_exposure * (0.35 + 0.65 * wave_packet);
    float sharp_crest = pow(composite, 2.8) * shoaling;

    z_offset = 0.30 + (sharp_crest * 0.40) * (0.25 * u_wave_intensity);
    horiz_offset = -in_normal.xy * (cos(wave_phase) * 0.008 * u_wave_intensity * shoaling);
    crest_val = sharp_crest;

    vec3 p_world = vec3(in_pos.xy + horiz_offset, max(0.20, in_pos.z + z_offset));
    v_world_pos = p_world;
    v_world_norm = in_normal;
    v_color = in_color;
    v_dist = in_dist;
    v_wave_crest = crest_val;
    v_phase = wave_phase;

    gl_Position = u_proj * u_view * vec4(p_world, 1.0);
}
"""

SURF_FS = """#version 330 core
in vec3 v_color;
in float v_dist;
in vec3 v_world_pos;
in vec3 v_world_norm;
in float v_wave_crest;
in float v_phase;

uniform float u_time;
uniform float u_wave_intensity;
uniform float u_wave_speed;
uniform float u_wave_period;
uniform float u_foam_coverage;
uniform float u_wave_desync;
uniform vec3 u_sun_world_dir;

out vec4 frag_color;

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453123);
}

float voronoi(vec2 x) {
    vec2 n = floor(x);
    vec2 f = fract(x);
    float m_dist = 1.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = hash2(n + g);
            vec2 r = g + o - f;
            float d = dot(r, r);
            m_dist = min(m_dist, d);
        }
    }
    return sqrt(m_dist);
}

void main() {
    vec3 N = vec3(0.0, 0.0, 1.0);
    vec3 L = normalize(u_sun_world_dir);
    vec3 V = normalize(vec3(0.0, 0.45, 0.89));
    vec3 H = normalize(L + V);
    float sun_spec = pow(max(0.0, dot(N, H)), 32.0) * 0.85;

    float along_shore = dot(v_world_pos.xy, vec2(-v_world_norm.y, v_world_norm.x));
    float local_desync = (sin(along_shore * 0.018) * 2.2 + cos(along_shore * 0.042) * 1.1) * u_wave_desync;
    float t = u_time * (0.85 * u_wave_speed);

    vec2 swell_dir = normalize(vec2(-0.707, 0.707));
    float exposure = dot(v_world_norm.xy, swell_dir);
    float coast_exposure = mix(1.0, clamp(exposure * 0.85 + 0.40, 0.05, 1.0), u_wave_desync);

    float outer_fade = 1.0 - smoothstep(0.40, 0.92, v_dist);

    float breaker = smoothstep(0.40, 0.88, v_wave_crest) * smoothstep(0.65, 0.08, v_dist) * u_wave_intensity * u_foam_coverage;

    float swash_cycle = sin(t * 1.1 + local_desync * 0.4);
    float swash_lead = smoothstep(0.16, 0.01, v_dist - swash_cycle * 0.04);
    float swash_foam = swash_lead * (0.60 + 0.40 * max(0.0, swash_cycle)) * coast_exposure * u_foam_coverage;

    vec2 lace_uv = v_world_pos.xy * 0.20 + vec2(t * 0.03, -t * 0.02);
    float v1 = voronoi(lace_uv);
    float v2 = voronoi(lace_uv * 1.7 + vec2(3.1, 7.4));
    float lace_pattern = (1.0 - smoothstep(0.03, 0.16, v1)) * smoothstep(0.14, 0.75, v2);
    float lace_residue = lace_pattern * smoothstep(0.03, 0.20, v_dist) * smoothstep(0.48, 0.14, v_dist) * breaker * 0.70;

    float total_foam = clamp(breaker * 0.95 + swash_foam * 0.85 + lace_residue * 0.60, 0.0, 1.0);

    vec3 shallow_sand_water = vec3(0.20, 0.75, 0.86);
    vec3 mid_aquamarine = vec3(0.11, 0.58, 0.78);
    vec3 ocean_match = vec3(0.06, 0.24, 0.45);

    vec3 sea = mix(shallow_sand_water, mid_aquamarine, smoothstep(0.02, 0.30, v_dist));
    sea = mix(sea, ocean_match, smoothstep(0.30, 0.85, v_dist));

    vec3 water_color = mix(sea, vec3(1.0, 1.0, 1.0), total_foam);
    water_color += vec3(1.0, 0.98, 0.92) * (sun_spec * (1.0 - total_foam * 0.50));
    float alpha = clamp(0.75 + total_foam * 0.25 - v_dist * 0.15, 0.0, 0.98) * outer_fade;

    frag_color = vec4(water_color, alpha);
}
"""


# ── Renderer Class ─────────────────────────────────────────────────────────────

class Micropoly3DRenderer:
    """High-performance ModernGL 3D GPU Perspective Renderer for REGNUM."""

    def __init__(self):
        if not MODERNGL_AVAILABLE:
            raise RuntimeError("ModernGL is required for GPU 3D terrain rendering.")

        self.ctx = moderngl.create_context(standalone=True)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)

        # Compile Shader Programs
        self.shadow_prog = self.ctx.program(vertex_shader=SHADOW_VS, fragment_shader=SHADOW_FS)
        self.mesh_prog = self.ctx.program(vertex_shader=MESH_VS, fragment_shader=MESH_FS)
        self.ocean_prog = self.ctx.program(vertex_shader=OCEAN_VS, fragment_shader=OCEAN_FS)
        self.river_prog = self.ctx.program(vertex_shader=RIVER_VS, fragment_shader=RIVER_FS)
        self.surf_prog = self.ctx.program(vertex_shader=SURF_VS, fragment_shader=SURF_FS)

        # Shadow Mapping Resources (4096 high resolution for crisp contact-hardening shadows)
        self.shadow_size = 4096
        self.shadow_tex = self.ctx.depth_texture((self.shadow_size, self.shadow_size))
        self.shadow_fbo = self.ctx.framebuffer(depth_attachment=self.shadow_tex)
        self._last_shadow_key = None

        # Offscreen Main Color Framebuffer
        self.fbo = None
        self.fbo_size = (0, 0)

        # VAOs and VBOs
        self.mesh_vao = None
        self.mesh_shadow_vao = None
        self.mesh_vbo = None
        self.mesh_count = 0

        self.tree_vao = None
        self.tree_shadow_vao = None
        self.tree_vbo = None
        self.tree_count = 0

        self.river_vao = None
        self.river_vbo = None
        self.river_count = 0

        self.surf_vao = None
        self.surf_vbo = None
        self.surf_count = 0

        self.ocean_vao = None
        self.ocean_vbo = None

        self._init_ocean_plane()

        # Cached slot state
        self.slot_state = {}
        self.shadow_matrix = np.eye(4, dtype=np.float32)
        self.sun_world_dir = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    def _init_ocean_plane(self):
        # Full water quad covering world bounds [-1500, 2524] at z = -0.35
        ocean_pts = np.array([
            -1500.0, -1500.0, -0.35,
             2524.0, -1500.0, -0.35,
            -1500.0,  2524.0, -0.35,
            -1500.0,  2524.0, -0.35,
             2524.0, -1500.0, -0.35,
             2524.0,  2524.0, -0.35,
        ], dtype=np.float32)
        self.ocean_vbo = self.ctx.buffer(ocean_pts.tobytes())
        self.ocean_vao = self.ctx.vertex_array(self.ocean_prog, [(self.ocean_vbo, '3f', 'in_pos')])

    def setup_scene(self, gen, slot_state: dict):
        """Build GPU vertex buffers and render the static shadow map."""
        self.slot_state = slot_state

        from mapgen_web import (
            get_cached_micropolys,
            build_micropoly_trees,
            build_coastal_surf_ribbon,
            build_hydro_river_ribbons
        )
        from scipy.spatial import cKDTree

        graph_key = (
            int(slot_state.get('seed', 777)),
            slot_state.get('shape', 'radial'),
            int(slot_state.get('points', 1000)),
            int(slot_state.get('rivers', 25)),
            round(float(slot_state.get('sharpness', 1.9)), 2),
            0.0, 0.0, 0.0, 0.0,
            round(float(slot_state.get('canyon_depth', 2.7)), 2),
            round(float(slot_state.get('valley_width', 1.4)), 2)
        )

        triangles, actual_count = get_cached_micropolys(
            gen,
            graph_key,
            int(slot_state.get('polys', 16000)),
            float(slot_state.get('roughness', 3.0)),
            float(slot_state.get('jitter', 0.22)),
            float(slot_state.get('alpha', 0.0)),
            float(slot_state.get('height_scale', 48.0)),
            float(slot_state.get('smooth', 0.7)),
            quad_fold=slot_state.get('quad_fold', True),
            ridge_noise=float(slot_state.get('ridge_noise', 0.35)),
            erosion_strength=float(slot_state.get('erosion_strength', 0.3)),
            erosion_droplets=int(slot_state.get('erosion_droplets', 15000)),
        )

        # 1. Terrain Mesh Buffer [x, y, z, nx, ny, nz, r, g, b, elev] (stride 10 floats = 40 bytes)
        mesh_verts = []
        for t in triangles:
            p0, p1, p2, col, elev, is_riv, poly_idx, norm = t
            r, g, b = col[0] / 255.0, col[1] / 255.0, col[2] / 255.0
            nx, ny, nz = float(norm[0]), float(norm[1]), float(norm[2])
            el = float(elev)
            mesh_verts.extend([float(p0[0]), float(p0[1]), float(p0[2]), nx, ny, nz, r, g, b, el])
            mesh_verts.extend([float(p1[0]), float(p1[1]), float(p1[2]), nx, ny, nz, r, g, b, el])
            mesh_verts.extend([float(p2[0]), float(p2[1]), float(p2[2]), nx, ny, nz, r, g, b, el])

        mesh_data = np.array(mesh_verts, dtype=np.float32)
        self.mesh_count = len(mesh_data) // 10
        self.mesh_vbo = self.ctx.buffer(mesh_data.tobytes())
        self.mesh_vao = self.ctx.vertex_array(
            self.mesh_prog,
            [(self.mesh_vbo, '3f 3f 3f 1f', 'in_pos', 'in_norm', 'in_color', 'in_elev')]
        )
        self.mesh_shadow_vao = self.ctx.vertex_array(
            self.shadow_prog,
            [(self.mesh_vbo, '3f 28x', 'in_pos')]
        )

        # 2. Elevation KD-Tree for Trees and Rivers
        mesh_pts = np.asarray([v for t in triangles for v in (t[0], t[1], t[2])], dtype=np.float32)
        mesh_tree = cKDTree(mesh_pts[:, :2])

        def sample_elevation(pts_xy):
            dists, idxs = mesh_tree.query(pts_xy, k=min(3, len(mesh_pts)))
            if dists.ndim == 1:
                z = mesh_pts[idxs.flatten(), 2]
            else:
                w = 1.0 / np.maximum(dists, 1e-4)
                w /= np.sum(w, axis=1, keepdims=True)
                z = np.sum(mesh_pts[idxs, 2] * w, axis=1)
            return np.maximum(0.0, z) + 0.08

        self.sample_elevation_func = sample_elevation

        # 3. Low-Poly 3D Trees Buffer
        tree_arr = build_micropoly_trees(
            gen, sample_elevation,
            height_scale=float(slot_state.get('height_scale', 48.0)),
            tree_density=float(slot_state.get('tree_density', 1.28))
        )
        if len(tree_arr) > 0:
            self.tree_count = len(tree_arr) // 10
            self.tree_vbo = self.ctx.buffer(tree_arr.tobytes())
            self.tree_vao = self.ctx.vertex_array(
                self.mesh_prog,
                [(self.tree_vbo, '3f 3f 3f 1f', 'in_pos', 'in_norm', 'in_color', 'in_elev')]
            )
            self.tree_shadow_vao = self.ctx.vertex_array(
                self.shadow_prog,
                [(self.tree_vbo, '3f 28x', 'in_pos')]
            )
        else:
            self.tree_count = 0
            self.tree_vao = None

        # 4. 3D Hydro River Ribbons Buffer
        river_arr = build_hydro_river_ribbons(
            gen, sample_mesh_elevation=sample_elevation,
            height_scale=float(slot_state.get('height_scale', 48.0)),
            river_width_mult=float(slot_state.get('river_width', 1.0)),
            river_count=int(slot_state.get('rivers', 25))
        )
        if len(river_arr) > 0:
            self.river_count = len(river_arr) // 10
            self.river_vbo = self.ctx.buffer(river_arr.tobytes())
            self.river_vao = self.ctx.vertex_array(
                self.river_prog,
                [(self.river_vbo, '3f 3f 3f 1f', 'in_pos', 'in_normal', 'in_color', 'in_flow')]
            )
        else:
            self.river_count = 0
            self.river_vao = None

        # 5. Option A Coastal Waves & Breakers Buffer
        surf_arr = build_coastal_surf_ribbon(
            gen, ribbon_width=32.0 * float(slot_state.get('wave_intensity', 1.4))
        )
        if len(surf_arr) > 0:
            self.surf_count = len(surf_arr) // 10
            self.surf_vbo = self.ctx.buffer(surf_arr.tobytes())
            self.surf_vao = self.ctx.vertex_array(
                self.surf_prog,
                [(self.surf_vbo, '3f 3f 3f 1f', 'in_pos', 'in_normal', 'in_color', 'in_dist')]
            )
        else:
            self.surf_count = 0
            self.surf_vao = None

        # 6. Render Directional Shadow Map Pass
        self._render_shadow_map()

    def _render_shadow_map(self, cam=None):
        """Render the 3D shadow map from the sun light source with view-dependent bounds."""
        az_deg = float(self.slot_state.get('sun_azimuth', -45.0))
        el_deg = max(5.0, min(88.0, float(self.slot_state.get('sun_elevation', 24.0))))

        az_rad = math.radians(az_deg)
        el_rad = math.radians(el_deg)
        sx = math.cos(el_rad) * math.cos(az_rad)
        sy = math.cos(el_rad) * math.sin(az_rad)
        sz = math.sin(el_rad)
        slen = math.hypot(math.hypot(sx, sy), sz)
        self.sun_world_dir = np.array([sx / slen, sy / slen, sz / slen], dtype=np.float32)

        # View-dependent focus: tight orthographic shadow box around visible area
        if cam is not None:
            tx = float(cam.get('target_x', 512.0))
            ty = float(cam.get('target_y', 512.0))
            zoom = max(0.5, float(cam.get('zoom', 1.0)))
            center = np.array([tx, ty, 0.0], dtype=np.float32)
            half_ext = max(180.0, min(820.0, 750.0 / zoom + 50.0))
        else:
            center = np.array([512.0, 512.0, 0.0], dtype=np.float32)
            half_ext = 800.0

        light_pos = center + self.sun_world_dir * 1800.0
        light_view = mat4_lookat(light_pos, center, (0.0, 0.0, 1.0))
        light_proj = mat4_ortho(-half_ext, half_ext, -half_ext, half_ext, 10.0, 3600.0)

        light_vp = light_proj @ light_view

        # Bias matrix mapping NDC [-1, 1] to Texture Coordinates [0, 1]
        bias_matrix = np.array([
            [0.5, 0.0, 0.0, 0.5],
            [0.0, 0.5, 0.0, 0.5],
            [0.0, 0.0, 0.5, 0.5],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)

        self.shadow_matrix = bias_matrix @ light_vp

        # Render depth pass to shadow FBO
        self.shadow_fbo.use()
        self.ctx.viewport = (0, 0, self.shadow_size, self.shadow_size)
        self.ctx.clear(depth=1.0)

        self.shadow_prog['u_light_vp'].write(light_vp.T.tobytes())

        if self.mesh_shadow_vao and self.mesh_count > 0:
            self.mesh_shadow_vao.render(moderngl.TRIANGLES, self.mesh_count)

        if self.tree_shadow_vao and self.tree_count > 0:
            self.tree_shadow_vao.render(moderngl.TRIANGLES, self.tree_count)

    def get_camera_matrices(self, viewport_w: int, viewport_h: int, cam: dict):
        """Compute 35mm regular perspective projection and lookAt view matrix with constant tilt."""
        pitch = float(cam.get('pitch', 52.0))
        yaw = float(cam.get('yaw', 9.0))
        zoom = max(0.2, float(cam.get('zoom', 1.0)))

        # 35mm focal length on standard full-frame 36x24mm sensor corresponds to ~45° vertical FOV
        fovy_rad = math.radians(45.0)
        aspect = max(0.1, viewport_w / max(1.0, float(viewport_h)))
        proj = mat4_perspective(fovy_rad, aspect, 10.0, 25000.0)

        # Target center point on ground
        tx = float(cam.get('target_x', 512.0))
        ty = float(cam.get('target_y', 512.0))
        target = np.array([tx, ty, 0.0], dtype=np.float32)

        # Constant viewing direction vector
        p_rad = math.radians(pitch)
        y_rad = math.radians(yaw)
        v_dir = np.array([
            math.sin(y_rad) * math.cos(p_rad),
            -math.cos(y_rad) * math.cos(p_rad),
            math.sin(p_rad)
        ], dtype=np.float32)
        v_dir /= np.linalg.norm(v_dir)

        # Base overview distance (~760 world units) fits the whole 1024x1024 island comfortably
        d_base = 760.0
        dist = d_base / zoom
        eye = target + v_dir * dist

        view = mat4_lookat(eye, target, (0.0, 0.0, 1.0))
        return proj, view, eye, target, v_dir

    def render(self, viewport_w: int, viewport_h: int, cam: dict, sim_time: float = 0.0) -> pygame.Surface:
        """Render complete 3D scene from GPU to a Pygame Surface."""
        viewport_w = max(64, int(viewport_w))
        viewport_h = max(64, int(viewport_h))

        # Reallocate main offscreen framebuffer if resized
        if self.fbo is None or self.fbo_size != (viewport_w, viewport_h):
            self.fbo = self.ctx.simple_framebuffer((viewport_w, viewport_h))
            self.fbo_size = (viewport_w, viewport_h)

        # Dynamically update view-dependent shadow map when camera pans or zooms
        tx_snap = round(float(cam.get('target_x', 512.0)), 0)
        ty_snap = round(float(cam.get('target_y', 512.0)), 0)
        zoom_snap = round(float(cam.get('zoom', 1.0)), 2)
        view_shadow_key = (tx_snap, ty_snap, zoom_snap)
        if getattr(self, '_last_shadow_key', None) != view_shadow_key:
            self._render_shadow_map(cam=cam)
            self._last_shadow_key = view_shadow_key

        proj, view, eye, target, v_dir = self.get_camera_matrices(viewport_w, viewport_h, cam)

        self.fbo.use()
        self.ctx.viewport = (0, 0, viewport_w, viewport_h)
        # Deep navy ocean backdrop
        self.ctx.clear(0.04, 0.12, 0.24, 1.0, depth=1.0)

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.depth_func = '<='

        # Bind shadow depth map to texture unit 1
        self.shadow_tex.use(location=1)

        def _set(prog, name, val):
            if name in prog:
                if isinstance(val, (int, float)):
                    prog[name].value = val
                elif isinstance(val, np.ndarray):
                    if val.ndim == 2:
                        prog[name].write(val.T.tobytes())
                    else:
                        prog[name].write(val.tobytes())
                elif isinstance(val, (bytes, bytearray)):
                    prog[name].write(val)

        # 1. Ocean Plane
        _set(self.ocean_prog, 'u_proj', proj)
        _set(self.ocean_prog, 'u_view', view)
        _set(self.ocean_prog, 'u_time', sim_time)
        _set(self.ocean_prog, 'u_wave_intensity', float(self.slot_state.get('wave_intensity', 1.4)))
        _set(self.ocean_prog, 'u_wave_speed', float(self.slot_state.get('wave_speed', 0.65)))
        _set(self.ocean_prog, 'u_wave_period', float(self.slot_state.get('wave_period', 1.2)))
        _set(self.ocean_prog, 'u_sun_world_dir', self.sun_world_dir)
        self.ocean_vao.render(moderngl.TRIANGLES, 6)

        # 2. Terrain Micropoly Mesh (Opaque)
        _set(self.mesh_prog, 'u_proj', proj)
        _set(self.mesh_prog, 'u_view', view)
        _set(self.mesh_prog, 'u_shadow_matrix', self.shadow_matrix)
        _set(self.mesh_prog, 'u_sun_dir', self.sun_world_dir)
        _set(self.mesh_prog, 'u_sun_world_dir', self.sun_world_dir)
        _set(self.mesh_prog, 'u_sun_intensity', float(self.slot_state.get('sun_intensity', 1.15)))
        _set(self.mesh_prog, 'u_ambient_intensity', float(self.slot_state.get('ambient_intensity', 0.45)))
        _set(self.mesh_prog, 'u_mountain_roughness', float(self.slot_state.get('mountain_roughness', 1.0)))
        _set(self.mesh_prog, 'u_snow_threshold', float(self.slot_state.get('snow_altitude', 0.70)))
        _set(self.mesh_prog, 'u_shadow_mode', 1 if self.slot_state.get('shadows', True) else 0)
        _set(self.mesh_prog, 'u_shadow_darkness', float(self.slot_state.get('shadow_darkness', 1.0)))
        _set(self.mesh_prog, 'u_shadow_map', 1)
        _set(self.mesh_prog, 'u_shadow_size', float(self.shadow_size))
        _set(self.mesh_prog, 'u_micropoly_strata', 1.0 if self.slot_state.get('micropoly_strata', True) else 0.0)
        _set(self.mesh_prog, 'u_micropoly_parcels', 1.0 if self.slot_state.get('micropoly_parcels', True) else 0.0)
        _set(self.mesh_prog, 'u_micropoly_grain', 1.0 if self.slot_state.get('micropoly_grain', True) else 0.0)
        _set(self.mesh_prog, 'u_micropoly_blend', float(self.slot_state.get('micropoly_blend', 0.0)))

        if self.mesh_vao and self.mesh_count > 0:
            self.mesh_vao.render(moderngl.TRIANGLES, self.mesh_count)

        # 3. Low-Poly 3D Trees (Opaque)
        if self.tree_vao and self.tree_count > 0 and self.slot_state.get('micropoly_trees', True):
            self.tree_vao.render(moderngl.TRIANGLES, self.tree_count)

        # 4. Translucent Passes (Rivers and Coastal Waves)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        self.ctx.enable(moderngl.DEPTH_TEST)

        # 4a. 3D Hydro Rivers
        if self.river_vao and self.river_count > 0 and self.slot_state.get('rivers', 25) > 0:
            _set(self.river_prog, 'u_proj', proj)
            _set(self.river_prog, 'u_view', view)
            _set(self.river_prog, 'u_shadow_matrix', self.shadow_matrix)
            _set(self.river_prog, 'u_sun_dir', self.sun_world_dir)
            _set(self.river_prog, 'u_sun_world_dir', self.sun_world_dir)
            _set(self.river_prog, 'u_time', sim_time)
            _set(self.river_prog, 'u_shadow_mode', 1 if self.slot_state.get('shadows', True) else 0)
            _set(self.river_prog, 'u_shadow_darkness', float(self.slot_state.get('shadow_darkness', 1.0)))
            _set(self.river_prog, 'u_shadow_map', 1)
            _set(self.river_prog, 'u_shadow_size', float(self.shadow_size))
            self.river_vao.render(moderngl.TRIANGLES, self.river_count)

        # 4b. Option A Coastal Waves & Breakers
        if self.surf_vao and self.surf_count > 0 and self.slot_state.get('micropoly_waves', True):
            _set(self.surf_prog, 'u_proj', proj)
            _set(self.surf_prog, 'u_view', view)
            _set(self.surf_prog, 'u_time', sim_time)
            _set(self.surf_prog, 'u_wave_intensity', float(self.slot_state.get('wave_intensity', 1.4)))
            _set(self.surf_prog, 'u_wave_speed', float(self.slot_state.get('wave_speed', 0.65)))
            _set(self.surf_prog, 'u_wave_period', float(self.slot_state.get('wave_period', 1.2)))
            _set(self.surf_prog, 'u_foam_coverage', float(self.slot_state.get('foam_coverage', 0.85)))
            _set(self.surf_prog, 'u_wave_desync', float(self.slot_state.get('wave_desync', 0.60)))
            _set(self.surf_prog, 'u_sun_world_dir', self.sun_world_dir)
            self.surf_vao.render(moderngl.TRIANGLES, self.surf_count)

        self.ctx.disable(moderngl.BLEND)

        # Read back rendered pixels into Pygame Surface (flipped vertically to convert OpenGL bottom-up FBO to Pygame top-down)
        raw = self.fbo.read(components=3)
        surf = pygame.image.frombuffer(raw, (viewport_w, viewport_h), 'RGB')
        return pygame.transform.flip(surf, False, True)


# Singleton instance
_GPU_3D_RENDERER = None

def get_micropoly_3d_renderer() -> Micropoly3DRenderer:
    global _GPU_3D_RENDERER
    if _GPU_3D_RENDERER is None:
        _GPU_3D_RENDERER = Micropoly3DRenderer()
    return _GPU_3D_RENDERER
