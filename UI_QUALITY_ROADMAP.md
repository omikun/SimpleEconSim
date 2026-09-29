# UI Quality Roadmap

This roadmap captures the main quality issues found across the desktop and web clients and orders fixes by risk and user impact.

## 1. Protect the LAN control surface and render API data safely

- Require a per-server token for commands and shutdown requests; deliver it only to the same-origin web client.
- Remove wildcard CORS and make shutdown a token-protected `POST` operation.
- Escape or validate server-provided strings, classes, and style values before rendering web UI templates.
- Bound request sizes and return clear client errors for malformed command bodies. (Implemented in the second UI hardening commit.)
- Cover token delivery, unauthorized commands, shutdown methods, request size and payload shape in endpoint tests. (Implemented.)

## 2. Make desktop redraws follow visible state changes

- Separate static map, dynamic map overlays, and individual panels into independently invalidated render layers.
- Track concrete cache dependencies such as world revision, selection, camera, and panel state instead of frame ticks.
- Measure frame time and cache hit rates so redraw improvements can be checked on large worlds. (Map and terrain caches record hits, misses, and cumulative render/scale time.)
- Cache the smooth-scaled static terrain image across redraws at the same source and viewport dimensions. (Implemented; covered by cache invalidation tests.)

## 3. Reduce UI module complexity

- Split the web client into focused modules for map rendering, panels, commands, and API/state synchronization. (Safety helpers, hex geometry, charts, and API transport have been extracted; suite panel renderers remain in `client.js`.)
- Split desktop panel composition from map drawing and share stable presentation helpers where appropriate. (The desktop viewer already delegates panels, charts, camera, and map rendering to separate `worldview_*` modules.)
- Keep public entry points small and document ownership of state between modules.

## 4. Improve validation and diagnostics

- Add focused browser tests for safe rendering, command flows, and state refresh behavior.
- Add desktop render-cache tests for invalidation and selection changes.
- Replace broad exception swallowing in UI paths with narrow error handling and actionable diagnostics.
- Keep scratch backups and generated refactor copies out of the source tree.

## Progress

Section 1 is implemented across two commits, including endpoint validation. The web client now has separate DOM-independent safety, hex geometry, chart rendering, and REST transport modules, with direct Node checks and server static-asset tests. Desktop smooth terrain scaling is cached across unchanged redraws and covered by invalidation tests, with map and scale-cache hit/miss/timing metrics. Headless full-frame testing succeeds with classic hex topology; the default Voronoi path still depends on a ModernGL context unavailable in this environment (`cannot choose pixel format`). UI fetch failures and optional resistance UI failures now report actionable diagnostics; font fallback and camera inversion catch only expected errors. Remaining work is the larger animated/static renderer separation, additional web suite panel modules, and browser-level interaction coverage beyond the available Node checks.

## Delivery order

Continue with desktop render-layer extraction and isolated web panel modules, then narrow broad UI exception handlers and expand browser interaction coverage. Validate each phase independently before committing it.
