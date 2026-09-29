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
- Measure frame time and cache hit rates so redraw improvements can be checked on large worlds.

## 3. Reduce UI module complexity

- Split the web client into focused modules for map rendering, panels, commands, and API/state synchronization.
- Split desktop panel composition from map drawing and share stable presentation helpers where appropriate.
- Keep public entry points small and document ownership of state between modules.

## 4. Improve validation and diagnostics

- Add focused browser tests for safe rendering, command flows, and state refresh behavior.
- Add desktop render-cache tests for invalidation and selection changes.
- Replace broad exception swallowing in UI paths with narrow error handling and actionable diagnostics.
- Keep scratch backups and generated refactor copies out of the source tree.

## Progress

Section 1 is implemented across two commits, including endpoint validation. Section 2 requires extracting animation and overlay passes from the current monolithic desktop map renderer; cache invalidation depends on those boundaries to avoid freezing labels, river flow, and trade markers. Sections 3 and 4 remain queued.

## Delivery order

Continue with the desktop render-layer extraction, then web and desktop module boundaries, and finish by expanding automated UI coverage and diagnostics. Validate each phase independently before committing it.
