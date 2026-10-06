/**
 * state_store.js — Centralized Reactive State Store & Event Dispatcher
 * Replaces scattered global variables with a single observable state container.
 */
(function (root) {
  'use strict';

  function createStore(initialState = {}) {
    const state = {
      world: null,
      stateVersion: null,
      selectedTileName: null,
      selectedTileDetail: null,
      hoveredTileName: null,
      isPlaying: false,

      // Camera State
      camera: {
        x: 0,
        y: 0,
        zoom: 1.0,
        isCentered: false
      },

      // Navigation & Active Subsystems
      ui: {
        activeDrawer: null,         // 'build' | 'gov' | 'diplomacy' | 'debt' | 'science' | 'military' | 'progress' | null
        activeRightTab: 'overview', // 'overview' | 'charts' | 'cadastre' | 'citizens' | 'policies' | 'workhouse' | 'news'
        activeLayer: 'overview',    // 1..9 thematic layers
        activeBuildCat: 'industry',
        activeBuildTier: 'all',
        activeGovScope: 'tile',
        activeDebtScope: 'domestic',
        activeScienceEra: 1,
        activeChartMode: 'economic',
        activeCompareTab: '1',
        activeCompareDrilldown: 'country',
        activeProgressMode: 'active'
      },

      // Map Overlays & Display Preferences
      settings: {
        showTradeRoutes: true,
        showTradeArrows: true,
        showArbitrageRings: true,
        usePhotorealTerrain: true,
        pollIntervalMs: 1000
      },

      ...initialState
    };

    const listeners = new Map(); // eventName -> Set<Function>

    function on(event, callback) {
      if (!listeners.has(event)) {
        listeners.set(event, new Set());
      }
      listeners.get(event).add(callback);
      return () => off(event, callback);
    }

    function off(event, callback) {
      if (listeners.has(event)) {
        listeners.get(event).delete(callback);
      }
    }

    function emit(event, data) {
      if (listeners.has(event)) {
        listeners.get(event).forEach(cb => {
          try {
            cb(data, state);
          } catch (err) {
            console.error(`Error in listener for '${event}':`, err);
          }
        });
      }
      // Wildcard listener
      if (listeners.has('*')) {
        listeners.get('*').forEach(cb => {
          try {
            cb(event, data, state);
          } catch (err) {
            console.error(`Error in wildcard listener for '${event}':`, err);
          }
        });
      }
    }

    function getState() {
      return state;
    }

    function setState(slice, partial) {
      if (typeof slice === 'string' && state[slice] && typeof state[slice] === 'object') {
        Object.assign(state[slice], partial);
        emit(`${slice}_changed`, state[slice]);
      } else if (typeof slice === 'object') {
        Object.assign(state, slice);
        emit('state_changed', state);
      }
    }

    // Action Dispatcher
    function dispatch(action, payload) {
      switch (action) {
        case 'SET_WORLD': {
          const prevVer = state.stateVersion;
          state.world = payload;
          state.stateVersion = payload ? payload.version : null;
          state.isPlaying = Boolean(payload && (payload.playing !== undefined ? payload.playing : payload.is_playing));
          emit('world_updated', { world: payload, prevVersion: prevVer });
          break;
        }

        case 'SELECT_TILE': {
          if (state.selectedTileName !== payload) {
            state.selectedTileName = payload;
            state.selectedTileDetail = null;
            emit('tile_selected', payload);
          }
          break;
        }

        case 'SET_TILE_DETAIL': {
          state.selectedTileDetail = payload;
          emit('tile_detail_updated', payload);
          break;
        }

        case 'SET_HOVERED_TILE': {
          if (state.hoveredTileName !== payload) {
            state.hoveredTileName = payload;
            emit('tile_hovered', payload);
          }
          break;
        }

        case 'SET_ACTIVE_DRAWER': {
          state.ui.activeDrawer = payload;
          emit('drawer_changed', payload);
          break;
        }

        case 'SET_ACTIVE_TAB': {
          state.ui.activeRightTab = payload;
          emit('tab_changed', payload);
          break;
        }

        case 'SET_ACTIVE_LAYER': {
          state.ui.activeLayer = payload;
          emit('layer_changed', payload);
          break;
        }

        case 'SET_CAMERA': {
          Object.assign(state.camera, payload);
          emit('camera_changed', state.camera);
          break;
        }

        case 'UPDATE_SETTINGS': {
          Object.assign(state.settings, payload);
          emit('settings_changed', state.settings);
          break;
        }

        default:
          emit(action, payload);
      }
    }

    return Object.freeze({
      getState,
      setState,
      dispatch,
      on,
      off
    });
  }

  const CoCStateStore = Object.freeze({
    createStore
  });
  root.CoCStateStore = CoCStateStore;
  root.RegnumStateStore = CoCStateStore;
})(typeof globalThis !== 'undefined' ? globalThis : window);
