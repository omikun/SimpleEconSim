// Static help pages plus the serialized nation registry help page.
(function (root) {
  'use strict';

  function renderHelpPage(page, world = {}) {
    if (page === '1') {
      return `
        <h4>1. Simulation Controls & Viewport</h4>
        <p>• <strong>Axial Hexagonal Projection:</strong> Pan with mouse/drag, pinch to zoom, or use <kbd>+</kbd>/<kbd>-</kbd>/<kbd>R</kbd> keys.</p>
        <p>• <strong>Topographic Rendering Pipeline:</strong> Toggle between GPU photorealistic terrain and vector flat view with <kbd>U</kbd> or the Top Bar button.</p>
        <p>• <strong>9 Map Thematic Layers:</strong> Press <kbd>1</kbd>–<kbd>9</kbd> to inspect Overview, Physical Elevation, Demographics, Economy, Production, Defense, Enclosure, Exploitation, and Ecology.</p>
        <div class="shortcuts-grid mt-3">
          <div><kbd>B</kbd> Build Menu</div><div><kbd>G</kbd> Governance</div>
          <div><kbd>D</kbd> Diplomacy</div><div><kbd>S</kbd> Sovereign Debt</div>
          <div><kbd>T</kbd> Science Tree</div><div><kbd>M</kbd> Military</div>
          <div><kbd>C</kbd> Compare Nations</div><div><kbd>A</kbd> Command Center</div>
        </div>`;
    }
    if (page === '2') {
      return `
        <h4>2. Macroeconomic Accounts & Financial Theory</h4>
        <p>• <strong>Conserved Money (Closed Loop):</strong> Pure closed-loop economy. Money moves strictly through wages, trade, tax, bonds, and contracts (0 Leak / 0 Shift).</p>
        <p>• <strong>Surplus Value & Exploitation Rate (s/v):</strong> Produced value minus subsistence wages. Elevated exploitation generates acute civil unrest and wildcat strikes.</p>
        <p>• <strong>Metabolic Rift:</strong> Intensive agronomy extracts soil phosphorus and nitrogen, sending grain to cities and polluting rivers unless circular sanitation systems are constructed.</p>
        <p>• <strong>ISRB Sovereign Credit Rating:</strong> Ratings from AAA to D determine coupon servicing rates on sovereign public debt offerings.</p>`;
    }
    if (page !== '3') return '';

    const { escapeHtml, safeCssColor } = root.RegnumUIUtils;
    const nations = Array.isArray(world.nations) ? world.nations : [];
    return `
      <h4>3. Procedural World Seeds & Nations Registry</h4>
      <p>• Current World Seed: <strong>${Number(world.seed) || 4242}</strong></p>
      <div class="cards-list mt-2">
        ${nations.map(nation => `
          <div class="item-card">
            <div class="card-top">
              <span class="card-title" style="color:${safeCssColor(nation.flag_color)}">👑 ${escapeHtml(nation.name)}</span>
              <span class="card-badge mastered">${escapeHtml(nation.regime_type || 'Monarchy')}</span>
            </div>
            <div class="card-meta-row">
              <span>Territories: ${Number(nation.tiles_count) || 0}</span>
              <span>GDP: $${Math.round(Number(nation.gdp) || 0).toLocaleString()}</span>
              <span>Rating: ${escapeHtml(nation.credit_rating || 'BBB')}</span>
            </div>
          </div>`).join('')}
      </div>`;
  }

  root.RegnumHelpContent = Object.freeze({ renderHelpPage });
})(typeof globalThis !== 'undefined' ? globalThis : window);
