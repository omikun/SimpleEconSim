// Loads and paints the optional continuous terrain backdrop.
(function (root) {
  'use strict';

  function createTerrainLayer(onChange = () => {}) {
    let image = new Image();
    let seed = null;
    let loading = false;
    let loaded = false;

    function sync(nextSeed) {
      if (!nextSeed || (seed === nextSeed && (loaded || loading))) return;
      seed = nextSeed;
      loading = true;
      loaded = false;
      image = new Image();
      image.onload = () => { loaded = true; loading = false; onChange(); };
      image.onerror = () => { loaded = false; loading = false; onChange(); };
      image.src = `/api/terrain.png?seed=${encodeURIComponent(nextSeed)}&t=${Date.now()}`;
    }

    function draw(ctx, bounds) {
      if (!loaded || !bounds) return false;
      const width = bounds.width > 0 ? bounds.width : bounds.max_x - bounds.min_x;
      const height = bounds.height > 0 ? bounds.height : bounds.max_y - bounds.min_y;
      if (!(width > 0 && height > 0)) return false;
      ctx.drawImage(image, bounds.min_x, bounds.min_y, width, height);
      return true;
    }

    return Object.freeze({ sync, draw, get loaded() { return loaded; } });
  }

  root.CoCTerrainLayer = Object.freeze({ createTerrainLayer });
})(typeof window !== 'undefined' ? window : globalThis);
