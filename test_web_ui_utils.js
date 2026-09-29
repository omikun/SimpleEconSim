const assert = require('node:assert/strict');
require('./web_client/ui_utils.js');
require('./web_client/state_sync.js');
require('./web_client/hex_geometry.js');

const { escapeHtml, safeClassToken, safeCssColor } = globalThis.RegnumUIUtils;

assert.equal(escapeHtml(`<img src=x onerror='alert(1)'>&`), '&lt;img src=x onerror=&#39;alert(1)&#39;&gt;&amp;');
assert.equal(escapeHtml(null), '');
assert.equal(safeClassToken('state-active_2'), 'state-active_2');
assert.equal(safeClassToken('badge-unrest riot'), 'badge-unrest riot');
assert.equal(safeClassToken('bad token!', 'fallback'), 'fallback');
assert.equal(safeCssColor('#A1b2C3'), '#A1b2C3');
assert.equal(safeCssColor('red; background:url(javascript:alert(1))'), '#38bdf8');

const geometry = globalThis.RegnumHexGeometry;
for (const cell of [{ q: 0, r: 0 }, { q: 3, r: -2 }, { q: -4, r: 5 }]) {
  const point = geometry.axialToPixel(cell.q, cell.r, 50);
  assert.deepEqual(geometry.pixelToAxial(point.x, point.y, 50), cell);
}
assert.deepEqual(geometry.pixelToAxial(0, 0, 50), { q: 0, r: 0 });

const calls = [];
let commandResult;
let networkError;
const sync = globalThis.RegnumStateSync.createStateSync({
  fetchImpl: async (...args) => {
    calls.push(args);
    return { json: async () => ({ success: true }) };
  },
  getToken: () => 'local-token',
  onCommandResult: result => { commandResult = result; },
  onNetworkError: error => { networkError = error; }
});

(async () => {
  await sync.fetchState('instance:1&other=value');
  assert.equal(calls[0][0], '/api/state?compact=1&since=instance%3A1%26other%3Dvalue');
  await sync.fetchTile('A/B');
  assert.equal(calls[1][0], '/api/tile?name=A%2FB');
  await sync.sendCommand('STEP', { count: 1 });
  assert.equal(calls[2][0], '/api/command');
  assert.equal(calls[2][1].headers['X-REGNUM-Token'], 'local-token');
  assert.deepEqual(commandResult, { success: true });
  assert.equal(networkError, undefined);
  console.log('UI utility, geometry, and API transport checks passed');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
