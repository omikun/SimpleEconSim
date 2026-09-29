// Small, DOM-independent helpers shared by web UI modules.
(function (root) {
  'use strict';

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function safeClassToken(value, fallback = '') {
    const tokens = String(value ?? '').trim().split(/\s+/).filter(Boolean);
    return tokens.length && tokens.every(token => /^[a-zA-Z0-9_-]+$/.test(token))
      ? tokens.join(' ')
      : fallback;
  }

  function safeCssColor(value, fallback = '#38bdf8') {
    const color = String(value ?? '');
    return /^#[0-9a-fA-F]{3,8}$/.test(color) ? color : fallback;
  }

  root.RegnumUIUtils = Object.freeze({ escapeHtml, safeClassToken, safeCssColor });
})(typeof globalThis !== 'undefined' ? globalThis : window);
