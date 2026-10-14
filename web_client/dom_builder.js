/**
 * dom_builder.js — Safe, Performant DOM Component View Helpers
 * Zero-dependency, injection-proof element generation and list rendering.
 */
(function (root) {
  'use strict';

  /**
   * Create an HTML element with attributes, event listeners, and children.
   * @param {string} tag
   * @param {Object} [props]
   * @param {Array|Node|string|number} [children]
   * @returns {HTMLElement}
   */
  function isNode(val) {
    if (!val || typeof val !== 'object') return false;
    if (typeof Node !== 'undefined') return val instanceof Node;
    return Boolean(val.nodeType || val.tagName);
  }

  function el(tag, props = {}, children = []) {
    const element = document.createElement(tag);

    if (props) {
      for (const [key, val] of Object.entries(props)) {
        if (val === undefined || val === null) continue;

        if (key.startsWith('on') && typeof val === 'function') {
          const eventName = key.slice(2).toLowerCase();
          element.addEventListener(eventName, val);
        } else if (key === 'className' || key === 'class') {
          element.className = String(val);
        } else if (key === 'dataset' && typeof val === 'object') {
          for (const [dKey, dVal] of Object.entries(val)) {
            element.dataset[dKey] = String(dVal);
          }
        } else if (key === 'style' && typeof val === 'object') {
          Object.assign(element.style, val);
        } else if (key === 'style' && typeof val === 'string') {
          element.style.cssText = val;
        } else if (key === 'innerHTML') {
          element.innerHTML = val;
        } else if (key === 'textContent' || key === 'text') {
          element.textContent = String(val);
        } else {
          element.setAttribute(key, String(val));
        }
      }
    }

    if (children !== undefined && children !== null) {
      const childArray = Array.isArray(children) ? children : [children];
      for (const child of childArray) {
        if (child === null || child === undefined || child === false) continue;
        if (typeof child === 'string' || typeof child === 'number') {
          element.appendChild(document.createTextNode(String(child)));
        } else if (isNode(child)) {
          element.appendChild(child);
        }
      }
    }

    return element;
  }

  /**
   * Clear all children from an element safely and quickly.
   * @param {HTMLElement} parent
   */
  function clear(parent) {
    if (!parent) return;
    while (parent.firstChild) {
      parent.removeChild(parent.firstChild);
    }
  }

  /**
   * Render a list of items into a container using an item renderer function.
   * @param {HTMLElement} container
   * @param {Array} items
   * @param {Function} itemRenderer (item, index) => HTMLElement
   * @param {HTMLElement|string} [emptyState]
   */
  function renderList(container, items, itemRenderer, emptyState = null) {
    if (!container) return;
    clear(container);

    if (!items || items.length === 0) {
      if (emptyState) {
        if (typeof emptyState === 'string') {
          container.appendChild(el('div', { className: 'empty-state' }, emptyState));
        } else if (isNode(emptyState)) {
          container.appendChild(emptyState);
        }
      }
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach((item, idx) => {
      const node = itemRenderer(item, idx);
      if (isNode(node)) fragment.appendChild(node);
    });
    container.appendChild(fragment);
  }

  const CoCDOM = Object.freeze({
    el,
    clear,
    renderList
  });
  root.CoCDOM = CoCDOM;
})(typeof globalThis !== 'undefined' ? globalThis : window);
