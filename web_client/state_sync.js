// HTTP transport for the same-origin simulation API.
(function (root) {
  'use strict';

  function createStateSync({ fetchImpl, getToken, onCommandResult, onNetworkError }) {
    const request = fetchImpl || root.fetch.bind(root);
    const token = getToken || (() => root.COC_API_TOKEN || '');

    const makeId = () => root.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    let clientId;
    try {
      clientId = root.sessionStorage?.getItem('coc-command-client') || makeId();
      root.sessionStorage?.setItem('coc-command-client', clientId);
    } catch (_) { clientId = makeId(); }

    return Object.freeze({
      fetchState(version = null) {
        const since = version ? `&since=${encodeURIComponent(version)}` : '';
        return request(`/api/state?compact=1${since}`);
      },

      fetchTile(name) {
        return request(`/api/tile?name=${encodeURIComponent(name)}`);
      },

      async sendCommand(commandType, payload = {}, options = {}) {
        const body = JSON.stringify({ cmd_type: commandType, type: commandType,
          cmd: commandType, payload, client_id: clientId,
          command_id: options.commandId || makeId() });
        let result;
        for (let attempt = 0; attempt < 2; attempt += 1) {
          try {
            const response = await request('/api/command', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-COC-Token': token() },
              body
            });
            if (response.ok === false) throw new Error(`HTTP ${response.status}`);
            result = await response.json();
            break;
          } catch (error) {
            if (attempt === 1) {
              if (onNetworkError) onNetworkError(error);
              return null;
            }
          }
        }
        if (onCommandResult) await onCommandResult(result);
        return result;
      }

    });
  }

  root.CoCStateSync = Object.freeze({ createStateSync });
})(typeof globalThis !== 'undefined' ? globalThis : window);
