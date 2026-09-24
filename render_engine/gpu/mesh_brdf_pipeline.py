"""
render_engine/gpu/mesh_brdf_pipeline.py — ModernGL Hardware Rasterizer for CPU Mapgen Meshes.

Renders high-detail 3D polygonal and micropoly meshes directly from CPU mapgen (build_island_mesh)
with full physics-based BRDF (Oren-Nayar diffuse, Cook-Torrance GGX specular, dynamic directional sun,
hemispherical ambient lighting, slope cliff scree, and alpine snow caps) on the GPU.
"""

import math
import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pygame

try:
    import moderngl
    MODERNGL_AVAILABLE = True
except ImportError:
    moderngl = None
    MODERNGL_AVAILABLE = False


# ---------------------------------------------------------------------------
# ModernGL Shaders for 3D Terrain Mesh BRDF Rendering
# ---------------------------------------------------------------------------

MESH_BRDF_VERT = """#version 330 core
in vec3 in_pos;
in vec3 in_norm;
in vec3 in_color;
in float in_elev;

uniform vec2 u_resolution; // (width, height)
uniform float u_max_z;      // max z for depth scaling
uniform float u_rot_pitch;  // in degrees (0 to 80)
uniform float u_rot_yaw;    // in degrees (-180 to 180)

out vec3 v_world_pos;
out vec3 v_norm;
out vec3 v_color;
out float v_elev;

void main() {
    v_world_pos = in_pos;
    v_color = in_color;
    v_elev = in_elev;

    vec2 center = u_resolution * 0.5;
    float R = max(center.x, center.y);

    // Centered coordinates: +X East, +Y North, +Z Up
    vec3 p = vec3(in_pos.x - center.x, center.y - in_pos.y, in_pos.z);
    vec3 n = vec3(in_norm.x, -in_norm.y, in_norm.z);

    float yaw_rad = radians(u_rot_yaw);
    float cos_y = cos(yaw_rad);
    float sin_y = sin(yaw_rad);

    // 1. Yaw rotation around vertical Z axis
    vec3 p_yaw = vec3(
        p.x * cos_y - p.y * sin_y,
        p.x * sin_y + p.y * cos_y,
        p.z
    );
    vec3 n_yaw = vec3(
        n.x * cos_y - n.y * sin_y,
        n.x * sin_y + n.y * cos_y,
        n.z
    );

    float pitch_rad = radians(u_rot_pitch);
    float cos_p = cos(pitch_rad);
    float sin_p = sin(pitch_rad);

    // 2. Camera Tilt looking North from South:
    // Screen Y: ground foreshortening + elevation rising upward (+Z * sin_p)
    // Eye Z: South is closer (-p_yaw.y * sin_p) + peaks closer (+p_yaw.z * cos_p)
    vec3 p_rot = vec3(
        p_yaw.x,
        p_yaw.y * cos_p + p_yaw.z * sin_p,
        -p_yaw.y * sin_p + p_yaw.z * cos_p
    );
    vec3 n_rot = vec3(
        n_yaw.x,
        n_yaw.y * cos_p + n_yaw.z * sin_p,
        -n_yaw.y * sin_p + n_yaw.z * cos_p
    );

    // Pass eye-space rotated normal to fragment shader
    v_norm = normalize(n_rot);

    // 3. Projected NDC coordinates [-1, 1]
    float scale_factor = (abs(u_rot_pitch) > 0.1 || abs(u_rot_yaw) > 0.1) ? 0.88 : 1.0;
    float x_ndc = (p_rot.x / R) * scale_factor;
    float y_ndc = (p_rot.y / R) * scale_factor;

    // Depth buffer: higher elevation / closer to viewer produces smaller depth
    float depth_span = max(1.0, u_max_z * 2.0 + R * 2.5);
    float z_ndc = clamp(-p_rot.z / depth_span, -0.99, 0.99);

    gl_Position = vec4(x_ndc, y_ndc, z_ndc, 1.0);
}
"""

MESH_BRDF_FRAG = """#version 330 core
in vec3 v_world_pos;
in vec3 v_norm;
in vec3 v_color;
in float v_elev;

uniform vec3 u_sun_dir;
uniform float u_sun_intensity;
uniform float u_ambient_intensity;
uniform float u_mountain_roughness;
uniform float u_snow_threshold;

out vec4 frag_color;

const float PI = 3.141592653589793;

// Oren-Nayar diffuse approximation for natural rough microfacets (rocks, earth, terrain)
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

    float theta_i = acos(clamp(NdotL, -1.0, 1.0));
    float theta_r = acos(clamp(NdotV, -1.0, 1.0));

    float sin_alpha = (theta_i >= theta_r) ? sin(theta_i) : sin(theta_r);
    float tan_beta  = (theta_i >= theta_r) ? tan(theta_r) : tan(theta_i);

    return s * (A + B * cos_phi * sin_alpha * max(0.0, tan_beta));
}

// Cook-Torrance GGX Specular
float distribution_ggx(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float NdotH2 = NdotH * NdotH;
    float denom = (NdotH2 * (a2 - 1.0) + 1.0);
    return a2 / max(PI * denom * denom, 1e-5);
}

float geometry_schlick_ggx(float NdotV, float roughness) {
    float r = (roughness + 1.0);
    float k = (r * r) / 8.0;
    return NdotV / max(NdotV * (1.0 - k) + k, 1e-5);
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
    if (N.z < 0.0) N = -N; // Ensure outward pointing normal

    vec3 L = normalize(u_sun_dir);
    vec3 V = vec3(0.0, 0.0, 1.0); // Top-down orthographic camera
    vec3 H = normalize(L + V);

    // 1. Base Albedo with dynamic slope scree & alpine snow
    vec3 albedo = v_color;

    // Dynamic steep cliff rock scree (granite/basalt) on mountain slopes
    float slope = 1.0 - N.z;
    float rock_weight = smoothstep(0.28, 0.58, slope) * smoothstep(0.22, 0.55, v_elev);
    if (rock_weight > 0.01) {
        vec3 rock_scree = vec3(0.26, 0.25, 0.28);
        albedo = mix(albedo, rock_scree, rock_weight * 0.70);
    }

    // Alpine Snow on high peaks
    float is_snow = 0.0;
    if (v_elev > u_snow_threshold) {
        is_snow = clamp((v_elev - u_snow_threshold) / max(0.01, 1.0 - u_snow_threshold), 0.0, 1.0);
        is_snow = pow(is_snow, 1.6);
        vec3 snow_col = vec3(0.95, 0.96, 0.98);
        albedo = mix(albedo, snow_col, is_snow * 0.95);
    }

    // 2. Diffuse Illumination
    float rough = clamp(u_mountain_roughness * 0.70, 0.15, 1.0);
    if (is_snow > 0.4) rough = 0.30; // Snow has crystalline sheen

    float NdotL = max(0.0, dot(N, L));
    float oren_diffuse = oren_nayar_diffuse(N, L, V, rough);
    // Half-Lambert wrap for natural soft shadow roll-off
    float wrap_diffuse = max(0.0, dot(N, L) * 0.4 + 0.6);
    float diffuse_light = (oren_diffuse * 0.80 + wrap_diffuse * 0.20) * u_sun_intensity;

    // 3. Specular Microfacet (Cook-Torrance GGX)
    vec3 F0 = vec3(0.035); // Dielectric terrain
    if (is_snow > 0.3) F0 = vec3(0.14); // Snow crystals
    vec3 F = fresnel_schlick(max(dot(H, V), 0.0), F0);
    float NDF = distribution_ggx(N, H, rough);
    float G = geometry_smith(N, V, L, rough);
    vec3 specular = (NDF * G * F) / max(4.0 * max(dot(N, V), 0.0) * NdotL, 1e-4);
    specular *= NdotL * u_sun_intensity * 0.28;

    // 4. Hemispherical Sky Ambient Light
    vec3 sky_color = vec3(0.20, 0.36, 0.56);
    vec3 ground_color = vec3(0.26, 0.22, 0.16);
    float hemi = N.z * 0.5 + 0.5;
    vec3 ambient = mix(ground_color, sky_color, hemi) * u_ambient_intensity;

    // 5. Fill Light from opposite quadrant
    vec3 L_fill = normalize(vec3(0.45, -0.65, 0.60));
    float fill_light = max(0.0, dot(N, L_fill)) * 0.12;

    // 6. Composite shaded RGB
    vec3 shaded = albedo * (ambient + diffuse_light + fill_light) + specular;

    // Soft-knee highlight compression
    shaded = shaded / (shaded + vec3(0.28)) * 1.28;

    frag_color = vec4(clamp(shaded, 0.0, 1.0), 1.0);
}
"""


def build_vbo_data(triangles: List[Tuple]) -> Tuple[np.ndarray, float]:
    """Pack triangle list into float32 array: [x, y, z, nx, ny, nz, r, g, b, elev]."""
    n_tris = len(triangles)
    if n_tris == 0:
        return np.zeros((0, 10), dtype=np.float32), 1.0

    pts_a = np.empty((n_tris, 3), dtype=np.float32)
    pts_b = np.empty((n_tris, 3), dtype=np.float32)
    pts_c = np.empty((n_tris, 3), dtype=np.float32)
    colors = np.empty((n_tris, 3), dtype=np.float32)
    norms = np.empty((n_tris, 3), dtype=np.float32)
    elevs = np.empty(n_tris, dtype=np.float32)

    for i, tri in enumerate(triangles):
        if len(tri) == 8:
            pa, pb, pc, col, avg_elev, _, _, norm = tri
        else:
            pa, pb, pc, col, avg_elev, _, _ = tri[:7]
            va = pb - pa
            vb = pc - pa
            norm = np.cross(va, vb)
            nl = np.linalg.norm(norm)
            norm = norm / nl if nl > 1e-6 else np.array([0.0, 0.0, 1.0])

        pts_a[i] = pa
        pts_b[i] = pb
        pts_c[i] = pc
        # Normalize color to [0.0, 1.0]
        colors[i] = np.asarray(col, dtype=np.float32) / 255.0
        norms[i] = norm
        elevs[i] = float(avg_elev)

    max_z = float(max(1.0, pts_a[:, 2].max(), pts_b[:, 2].max(), pts_c[:, 2].max()))

    # Interleave into (n_tris * 3, 10)
    vbo_data = np.empty((n_tris, 3, 10), dtype=np.float32)
    vbo_data[:, 0, :3] = pts_a
    vbo_data[:, 1, :3] = pts_b
    vbo_data[:, 2, :3] = pts_c
    vbo_data[:, :, 3:6] = norms[:, np.newaxis, :]
    vbo_data[:, :, 6:9] = colors[:, np.newaxis, :]
    vbo_data[:, :, 9] = elevs[:, np.newaxis]

    flat_data = np.ascontiguousarray(vbo_data.reshape(-1, 10))
    return flat_data, max_z


class GPUMeshBRDFPipeline:
    """
    ModernGL hardware rasterization pipeline for high-poly CPU mapgen terrain meshes.
    Supports dynamic lighting (azimuth, elevation, intensity, ambient) and BRDF shading.
    """

    def __init__(self):
        self.ctx = None
        self.prog_mesh = None
        self.fbo = None
        self.color_tex = None
        self.depth_rb = None
        self.fbo_size = (0, 0)

        # Mesh VBO caching to avoid re-uploading when only sun/lighting changes
        self._cached_vbo = None
        self._cached_vao = None
        self._cached_vbo_count = 0
        self._cached_mesh_key = None
        self._cached_max_z = 100.0

        self._available = False
        if MODERNGL_AVAILABLE:
            self._init_gl()

    def is_available(self) -> bool:
        return self._available and self.ctx is not None

    def _init_gl(self):
        try:
            self.ctx = moderngl.create_context(standalone=True)
            self.prog_mesh = self.ctx.program(
                vertex_shader=MESH_BRDF_VERT,
                fragment_shader=MESH_BRDF_FRAG,
            )
            self._available = True
        except Exception as exc:
            sys.stderr.write(f"GPUMeshBRDFPipeline init warning: {exc}\n")
            self._available = False

    def _ensure_fbo(self, width: int, height: int):
        if self.fbo is not None and self.fbo_size == (width, height):
            return

        if self.fbo is not None:
            self.fbo.release()
        if self.color_tex is not None:
            self.color_tex.release()
        if self.depth_rb is not None:
            self.depth_rb.release()

        self.color_tex = self.ctx.texture((width, height), 4)
        self.color_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.depth_rb = self.ctx.depth_renderbuffer((width, height))
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color_tex],
            depth_attachment=self.depth_rb,
        )
        self.fbo_size = (width, height)

    def _build_vbo_data(self, triangles: List[Tuple]) -> Tuple[np.ndarray, float]:
        return build_vbo_data(triangles)

    def render_mesh(
        self,
        gen,
        triangles: List[Tuple],
        width: int = 1024,
        height: int = 1024,
        uniforms: Optional[Dict[str, Any]] = None,
        mesh_cache_key: Any = None,
    ) -> pygame.Surface:
        """
        Renders the exact CPU mapgen mesh and colors with dynamic BRDF lighting.
        Returns an RGBA pygame.Surface.
        """
        if not self.is_available():
            raise RuntimeError("GPUMeshBRDFPipeline ModernGL context is unavailable")

        u = uniforms or {}
        sun_azimuth = float(u.get("sun_azimuth", -135.0))
        sun_elevation = float(u.get("sun_elevation", 42.0))
        sun_intensity = float(u.get("sun_intensity", 1.15))
        ambient_intensity = float(u.get("ambient_intensity", 0.45))
        mountain_roughness = float(u.get("mountain_roughness", 1.0))
        snow_threshold = float(u.get("snow_threshold", 0.82))
        rot_pitch = float(u.get("rot_pitch", 0.0))
        rot_yaw = float(u.get("rot_yaw", 0.0))

        # Compute normalized sun direction vector
        az_rad = math.radians(sun_azimuth)
        el_rad = math.radians(max(5.0, min(88.0, sun_elevation)))
        sun_x = math.cos(el_rad) * math.cos(az_rad)
        sun_y = math.cos(el_rad) * math.sin(az_rad)
        sun_z = math.sin(el_rad)
        sun_len = math.hypot(sun_x, sun_y, sun_z)
        sun_dir = (sun_x / sun_len, sun_y / sun_len, sun_z / sun_len)

        # 1. Prepare Framebuffer
        self._ensure_fbo(width, height)
        self.fbo.use()

        # 2. VBO / VAO Caching
        if self._cached_mesh_key != mesh_cache_key or self._cached_vao is None or mesh_cache_key is None:
            if self._cached_vbo is not None:
                self._cached_vbo.release()
            if self._cached_vao is not None:
                self._cached_vao.release()

            vbo_data, max_z = self._build_vbo_data(triangles)
            self._cached_max_z = max_z
            self._cached_vbo_count = len(vbo_data)
            self._cached_vbo = self.ctx.buffer(vbo_data.tobytes())
            self._cached_vao = self.ctx.vertex_array(
                self.prog_mesh,
                [(self._cached_vbo, "3f 3f 3f 1f", "in_pos", "in_norm", "in_color", "in_elev")],
            )
            self._cached_mesh_key = mesh_cache_key

        # 3. Setup Mesh Uniforms
        self.prog_mesh["u_resolution"].value = (float(width), float(height))
        self.prog_mesh["u_max_z"].value = float(self._cached_max_z)
        self.prog_mesh["u_sun_dir"].value = sun_dir
        self.prog_mesh["u_sun_intensity"].value = float(sun_intensity)
        self.prog_mesh["u_ambient_intensity"].value = float(ambient_intensity)
        self.prog_mesh["u_mountain_roughness"].value = float(mountain_roughness)
        self.prog_mesh["u_snow_threshold"].value = float(snow_threshold)
        self.prog_mesh["u_rot_pitch"].value = float(rot_pitch)
        self.prog_mesh["u_rot_yaw"].value = float(rot_yaw)

        # 4. GL State & Render
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)

        # Deep Ocean Sapphire Clear Color (matching CPU mapgen background)
        self.ctx.clear(0.11, 0.19, 0.33, 1.0, depth=1.0)

        if self._cached_vbo_count > 0:
            self._cached_vao.render(moderngl.TRIANGLES, vertices=self._cached_vbo_count)

        # 5. Readback Framebuffer to Pygame Surface
        raw_rgba = self.fbo.read(components=4, alignment=1)
        surf = pygame.image.frombuffer(raw_rgba, (width, height), "RGBA")
        # Flip Y since OpenGL stores pixels bottom-to-top
        surf = pygame.transform.flip(surf, False, True)

        # Helper to project (x, y) into current 3D screen view
        is_rotated = (abs(rot_pitch) > 0.1 or abs(rot_yaw) > 0.1)
        cx, cy = width * 0.5, height * 0.5
        R = max(cx, cy)
        scale_f = 0.90 if is_rotated else 1.0
        yaw_r = math.radians(rot_yaw)
        cos_y, sin_y = math.cos(yaw_r), math.sin(yaw_r)
        pitch_r = math.radians(rot_pitch)
        cos_p, sin_p = math.cos(pitch_r), math.sin(pitch_r)

        def project_pt(px_map: float, py_map: float) -> Tuple[int, int]:
            px = px_map * (width / gen.width)
            py = py_map * (height / gen.height)
            if not is_rotated:
                return (int(px), int(py))
            # Centered
            p_x = px - cx
            p_y = -(py - cy)
            # Yaw
            x1 = p_x * cos_y - p_y * sin_y
            y1 = p_x * sin_y + p_y * cos_y
            # Pitch
            x2 = x1
            y2 = y1 * cos_p
            # NDC
            x_ndc = (x2 / R) * scale_f
            y_ndc = (y2 / R) * scale_f
            sx = int((x_ndc + 1.0) * 0.5 * width)
            sy = int((1.0 - y_ndc) * 0.5 * height)
            return (sx, sy)

        # 6. Draw smooth 2D River Paths directly onto surface in top-down mode
        if not is_rotated and hasattr(gen, "edges") and gen.noisy_edges:
            scale_x = width / gen.width
            scale_y = height / gen.height
            for e in gen.edges:
                if e.river > 0:
                    pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                    if len(pts) >= 2:
                        pts2d = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in pts]
                        w = max(2, int(1.8 * math.sqrt(e.river) * (width / 1000.0)))
                        pygame.draw.lines(surf, (30, 85, 155), False, pts2d, w)

        # 7. Volcanic Lava Fissures (incandescent glowing veins) in top-down mode
        if not is_rotated and hasattr(gen, "edges"):
            scale_x = width / gen.width
            scale_y = height / gen.height
            for e in gen.edges:
                if getattr(e, "lava", False):
                    p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                    p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                    w_outer = max(3, int(4 * (width / 1000.0)))
                    w_inner = max(1, int(2 * (width / 1000.0)))
                    pygame.draw.line(surf, (255, 60, 0), p0, p1, w_outer)
                    pygame.draw.line(surf, (255, 210, 50), p0, p1, w_inner)

        return surf
