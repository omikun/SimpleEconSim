// HTTP transport for the same-origin simulation API.
(function (root) {
  'use strict';

  function createStateSync({ fetchImpl, getToken, onCommandResult, onNetworkError }) {
    const request = fetchImpl || root.fetch.bind(root);
    const token = getToken || (() => root.COC_API_TOKEN || '');

    return Object.freeze({
      fetchState(version = null) {
        const since = version ? `&since=${encodeURIComponent(version)}` : '';
        return request(`/api/state?compact=1${since}`);
      },

      fetchTile(name) {
        return request(`/api/tile?name=${encodeURIComponent(name)}`);
      },

      async sendCommand(commandType, payload = {}) {
        try {
          const tok = token();
          const response = await request('/api/command', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-COC-Token': tok
            },
            body: JSON.stringify({ cmd_type: commandType, type: commandType, cmd: commandType, payload })
          });
          const result = await response.json();
          if (onCommandResult) await onCommandResult(result);
          return result;
        } catch (error) {
          if (onNetworkError) onNetworkError(error);
          return null;
        }
      }
    });
  }

  root.CoCStateSync = Object.freeze({ createStateSync });
})(typeof globalThis !== 'undefined' ? globalThis : window);
