/**
 * Optional, offline jsdom integration tests. No ComfyUI process, GPU, model,
 * websocket, or browser is involved. The real extension/controller/renderer run
 * against a small public-widget lifecycle mock and coherent preview responses.
 * Run: KREA2_JSDOM_PATH=/path/to/jsdom/lib/api.js node --test tests/dom/krea2_ui.test.js
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {DEFAULT_JSON, DEFAULT_STATE, VIEW_IDS, PART_IDS, PRESETS, parseState, serializeState} from '../../web/state.js';
import {PROFILE, LAYOUT_PROFILE, PROFILES} from '../../web/profile.js';
import {installDesigner, getDesigner, createExtension} from '../../web/integration.js';

let JSDOM;
try {
  ({JSDOM} = await import(process.env.KREA2_JSDOM_PATH ? pathToFileURL(process.env.KREA2_JSDOM_PATH).href : 'jsdom'));
} catch (error) {
  // An explicitly configured dependency must work; never silently skip a bad path.
  if (process.env.KREA2_JSDOM_PATH) throw error;
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
}
const domTest = (name, fn) => test(name, {
  skip: !JSDOM && 'Optional jsdom unavailable; install jsdom or set KREA2_JSDOM_PATH to its lib/api.js.',
  concurrency: false,
}, fn);
const tick = () => new Promise(resolve => setImmediate(resolve));
function choose(element, value) { element.value = value; element.dispatchEvent(new Event('change', {bubbles: true})); }
function type(element, value) { element.value = value; element.dispatchEvent(new Event('input', {bubbles: true})); }
function key(element, value, extra = {}) {
  const event = new KeyboardEvent('keydown', {key: value, bubbles: true, cancelable: true, ...extra});
  element.dispatchEvent(event); return event;
}
function customHeight(root) { choose(root.querySelector('[data-height-presets]'), 'custom'); return root.querySelector('[data-field="body_height"]'); }
function partEditor(root, part) {
  root.querySelector('[data-tab="parts"]').click();
  choose(root.querySelector('[data-part-select]'), part);
  return root.querySelector('[data-part-prompt]');
}
function savedWidgets(item) { return item.widgets.filter(widget => widget.serialize !== false && widget.options?.serialize !== false); }

function setup() {
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {url: 'http://localhost/'});
  const keys = ['window', 'document', 'AbortController', 'Event', 'KeyboardEvent', 'HTMLElement', 'ResizeObserver'];
  const globals = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const key of keys.filter(key => key !== 'ResizeObserver')) globalThis[key] = dom.window[key];
  const observers = new Set();
  globalThis.ResizeObserver = class {
    observe() { observers.add(this); }
    disconnect() { observers.delete(this); }
  };
  const frames = new Map(); let nextFrame = 0;
  window.requestAnimationFrame = fn => { frames.set(++nextFrame, fn); return nextFrame; };
  window.cancelAnimationFrame = id => frames.delete(id);
  const flushFrames = () => { const pending = [...frames]; frames.clear(); for (const [, fn] of pending) fn(0); };
  let locale = 'en';
  const settings = new dom.window.EventTarget(), listeners = new Set();
  const addListener = settings.addEventListener.bind(settings), removeListener = settings.removeEventListener.bind(settings);
  settings.addEventListener = (name, fn, options) => { if (name === 'Comfy.Locale.change') listeners.add(fn); addListener(name, fn, options); };
  settings.removeEventListener = (name, fn, options) => { if (name === 'Comfy.Locale.change') listeners.delete(fn); removeListener(name, fn, options); };
  const requests = [], history = [], canvasEvents = [], registry = new Set(), nodes = [];
  const before = new Map();
  const graph = {
    _nodes: nodes,
    beforeChange(node) { before.set(node, node.widgets.find(widget => widget.name === 'state_json').value); },
    afterChange(node) { history.push({node, before: before.get(node), after: node.widgets.find(widget => widget.name === 'state_json').value}); before.delete(node); },
    // A layout-only node must not read connected images or edit connections.
    getNodeById() { throw new Error('Image auto-sourcing must not inspect connected nodes'); },
  };
  const app = {graph, extensionManager: {setting: {get: () => locale}}, ui: {settings}, canvas: {
    emitBeforeChange() { canvasEvents.push('before'); }, emitAfterChange() { canvasEvents.push('after'); },
  }};
  const api = {fetchApi(path, opts) {
    assert.ok(PROFILES.some(profile => profile.previewPath === path), `Unexpected endpoint: ${path}`);
    return new Promise((resolve, reject) => requests.push({path, opts, resolve, reject}));
  }};
  const extension = createExtension(app, api);
  function node(profile = PROFILE, raw = DEFAULT_JSON, {prefix = false, identity = 'both', officialSetter = false, install = true} = {}) {
    const element = document.createElement('textarea'); element.value = raw;
    const inputAbort = new AbortController(), widgetChanges = [], setterCalls = [];
    const original = {name: 'state_json', type: 'customtext', value: raw, options: {}, element,
      onRemove() { inputAbort.abort(); registry.delete(original); element.remove(); },
    };
    element.addEventListener('input', () => { original.value = element.value; }, {signal: inputAbort.signal});
    if (officialSetter) original.options.setValue = function (value) { setterCalls.push([this, value]); original.value = value; return 'setter-return'; };
    const initialSetter = original.options.setValue;
    const item = {
      type: identity === 'comfyClass' ? 'DecoratedNode' : profile.nodeType,
      comfyClass: identity === 'type' ? undefined : profile.nodeType,
      widgets: prefix ? [{name: 'unrelated', value: 'untouched'}, original] : [original],
      inputs: Object.freeze([{name: 'state_json', widget: {name: 'state_json'}, _widget: original}]),
      outputs: Object.freeze([]), graph, size: [300, 100],
      onConfigure() { return 'configure-return'; },
      onAdded() { registry.add(original); document.body.append(element); return 'add-return'; },
      onRemoved() { for (const widget of [...this.widgets]) widget.onRemove?.(); return 'remove-return'; },
      onWidgetChanged(...args) { widgetChanges.push(args); },
      addInput() { throw new Error('Designer must not create an image input'); },
      connect() { throw new Error('Designer must not auto-connect images'); },
      setSize(size) { this.size = size; }, setDirtyCanvas() {},
      addDOMWidget(name, widgetType, root, options) {
        const widget = {name, type: widgetType, element: root, options,
          onRemove() { registry.delete(widget); root.remove(); },
        };
        Object.defineProperty(widget, 'value', {get: options.getValue, set: options.setValue});
        this.widgets.push(widget); document.body.append(root); registry.add(widget);
        const previous = this.onAdded;
        this.onAdded = function (...args) { const result = previous?.apply(this, args); registry.add(widget); return result; };
        return widget;
      },
    };
    nodes.push(item); item.onAdded();
    const descriptor = Object.getOwnPropertyDescriptor(original, 'value');
    if (install) extension.nodeCreated(item);
    return {item, original, record: getDesigner(item), descriptor, widgetChanges, setterCalls, initialSetter};
  }
  function resolve(index = requests.length - 1, {width = 2208, height = 1280, ...extra} = {}) {
    const request = requests[index]; assert.ok(request, `No request ${index}`);
    const state = parseState(JSON.parse(request.opts.body).state_json);
    const count = state.views.length;
    request.resolve({ok: true, status: 200, json: async () => ({width, height, max_resolution: 16384,
      layout: {canvas: [width, height], panels: state.views.map((id, i) => ({id, rect: [i / count, 0, 1 / count, 1]})), feet_y: state.views.some(id => id.startsWith('body_')) ? 1 : null},
      ...extra,
    })});
  }
  return {dom, app, api, extension, requests, history, canvasEvents, registry, frames, observers, listeners, node, resolve, flushFrames,
    locale(value) { locale = value; settings.dispatchEvent(new Event('Comfy.Locale.change')); },
    cleanup() {
      for (const item of nodes) { getDesigner(item)?.dispose({reinstall: false}); item.onRemoved?.(); }
      dom.window.close();
      for (const [key, descriptor] of globals) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
    },
  };
}

for (const profile of PROFILES) {
  const suite = (name, fn) => domTest(`${profile.nodeType}: ${name}`, fn);

  suite('preserves canonical widget identity, position, value descriptor and the only saved designer input', t => {
    const h = setup(); t.after(h.cleanup);
    const {item, original, record, descriptor} = h.node(profile, DEFAULT_JSON, {prefix: true});
    assert.ok(record); assert.equal(record.original, original); assert.equal(record.originalIndex, 1);
    assert.equal(item.widgets[1], original); assert.deepEqual(savedWidgets(item).map(w => w.name), ['unrelated', 'state_json']);
    assert.deepEqual(Object.getOwnPropertyDescriptor(original, 'value'), descriptor);
    assert.equal(original.options.dynamicPrompts, false); assert.equal(original.hidden, true); assert.equal(original.element.hidden, true);
    assert.equal(record.widget.name, 'krea2_designer_ui'); assert.equal(record.widget.serialize, false); assert.equal(record.widget.options.serialize, false);
    assert.equal(record.ui.root.getAttribute('aria-label'), profile.displayName);
    assert.equal(h.requests[0].path, profile.previewPath); assert.deepEqual(JSON.parse(h.requests[0].opts.body), {state_json: DEFAULT_JSON});
    assert.equal(installDesigner(item, h.app, h.api), record); assert.equal(item.widgets.length, 3);
    assert.equal(item.onAdded(), 'add-return'); assert.equal(item.onConfigure({}), 'configure-return');
    assert.equal(original.value, DEFAULT_JSON); assert.equal(h.history.length, 0);
    assert.deepEqual(item.size, [870, 930]);
  });

  suite('all view buttons and presets immediately save; last view stays selected', t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    for (const [name, views] of Object.entries(PRESETS)) {
      choose(root.querySelector(`#${root.dataset.instance}-preset`), name);
      assert.deepEqual(parseState(original.value).views, views);
      assert.deepEqual([...root.querySelectorAll('.krea2-card[aria-pressed="true"]')].map(card => card.dataset.view), views);
    }
    choose(root.querySelector(`#${root.dataset.instance}-preset`), 'detail');
    for (const view of VIEW_IDS.slice(0, -1)) {
      const before = h.history.length; root.querySelector(`[data-view="${view}"]`).click();
      assert.equal(parseState(original.value).views.includes(view), false); assert.equal(h.history.length, before + 1);
    }
    const saved = original.value; root.querySelector(`[data-view="${VIEW_IDS.at(-1)}"]`).click();
    assert.equal(original.value, saved); assert.match(root.querySelector('.krea2-error').textContent, /at least one/);
    assert.equal(root.querySelector('select.krea2-select').value, 'custom');
    assert.deepEqual(h.canvasEvents, h.history.flatMap(() => ['before', 'after']));
  });

  suite('latest rapid preview wins even when earlier aborted requests return later', async t => {
    const h = setup(); t.after(h.cleanup); const {record} = h.node(profile); const root = record.ui.root;
    root.querySelector('[data-view="hands"]').click(); root.querySelector('[data-view="feet"]').click();
    const saved = record.controller.raw, count = h.history.length;
    assert.equal(h.requests.length, 3); assert.equal(h.requests[0].opts.signal.aborted, true); assert.equal(h.requests[1].opts.signal.aborted, true);
    assert.equal(root.querySelector('[data-mode="manual"]').disabled, true);
    h.resolve(2, {width: 3072, height: 1536}); await tick();
    assert.equal(record.controller.isCurrentPreview, true); assert.equal(record.controller.preview.width, 3072);
    h.resolve(0, {width: 1024, height: 1024}); h.resolve(1, {width: 2048, height: 1024}); await tick();
    assert.equal(record.controller.preview.width, 3072); assert.equal(record.controller.raw, saved); assert.equal(h.history.length, count);
    assert.deepEqual([...root.querySelectorAll('[data-panel]')].map(panel => panel.dataset.panel), parseState(saved).views);
    assert.equal(root.querySelector('.krea2-dimensions').textContent, '3,072 × 1,536');
    assert.ok(h.requests.every(request => request.path === profile.previewPath));
  });

  suite('Japanese and English change labels without rewriting saved state or numeric drafts', t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    const editor = partEditor(root, 'footwear'); type(editor, '黒いブーツ');
    root.querySelector('[data-tab="layout"]').click(); const input = customHeight(root); type(input, '999');
    const saved = original.value, count = h.history.length, requests = h.requests.length;
    h.locale('ja-JP'); assert.equal(root.lang, 'ja'); assert.equal(root.querySelector('[data-view="hands"] .krea2-card-label').textContent, '両手');
    assert.match(root.querySelector('[data-tab="parts"]').textContent, /部位指定/); assert.match(root.querySelector('[data-part-select] option[value="other"]').textContent, /全体・その他/);
    assert.equal(input.value, '999'); assert.match(input.closest('.krea2-number-field').textContent, /未確定/);
    h.locale('en-US'); assert.equal(root.lang, 'en'); assert.equal(root.querySelector('[data-view="hands"] .krea2-card-label').textContent, 'Hands');
    h.locale('de-DE'); assert.equal(root.lang, 'en');
    assert.equal(original.value, saved); assert.equal(h.history.length, count); assert.equal(h.requests.length, requests); assert.equal(editor.value, '黒いブーツ');
  });

  suite('all eight part fields save independently with literal text, multiline and IME-safe Enter', t => {
    const h = setup(); t.after(h.cleanup); const {record, original, widgetChanges} = h.node(profile); const root = record.ui.root;
    const before = original.value; const editor = partEditor(root, PART_IDS[0]);
    assert.equal(original.value, before); assert.equal(h.history.length, 0);
    assert.deepEqual([...root.querySelector('[data-part-select]').options].map(option => option.value), PART_IDS);
    assert.equal(root.querySelectorAll('.krea2-part-panel textarea').length, 1); assert.equal(editor.maxLength, 1000);
    const values = Object.fromEntries(PART_IDS.map((part, i) => [part, `${i}: 日本語 "literal" {red|blue}\nC:\\pattern 🌸`]));
    for (const [part, text] of Object.entries(values)) {
      type(partEditor(root, part), text);
      assert.equal(parseState(original.value).part_prompts[part], text);
      assert.equal(h.history.at(-1).after, original.value);
      assert.equal(widgetChanges.at(-1)[0], 'state_json'); assert.equal(widgetChanges.at(-1)[3], original);
    }
    assert.equal(h.history.length, 8); assert.deepEqual(parseState(original.value).part_prompts, values);
    assert.equal(parseState(original.value).schema_version, 2);
    for (const [part, text] of Object.entries(values)) assert.equal(partEditor(root, part).value, text);
    editor.focus(); editor.setSelectionRange(4, 4);
    assert.equal(key(editor, 'Enter', {isComposing: true}).defaultPrevented, false); assert.equal(editor.selectionStart, 4);
    assert.equal(key(editor, 'Enter').defaultPrevented, false); editor.dispatchEvent(new Event('blur')); editor.dispatchEvent(new Event('compositionend'));
    assert.equal(h.history.length, 8);
    type(partEditor(root, 'hands'), ''); delete values.hands;
    assert.deepEqual(parseState(original.value).part_prompts, values); assert.equal(h.history.length, 9);
  });

  suite('invalid part drafts remain visible without changing canonical state and restore clears them', t => {
    const h = setup(); t.after(h.cleanup); const {record, original, item} = h.node(profile); const root = record.ui.root;
    const editor = partEditor(root, 'face'); type(editor, 'サングラス'); const saved = original.value;
    type(editor, 'x'.repeat(1001)); assert.equal(original.value, saved); assert.equal(editor.getAttribute('aria-invalid'), 'true');
    partEditor(root, 'hands'); partEditor(root, 'face'); assert.equal(editor.value.length, 1001);
    h.locale('ja'); assert.equal(editor.value.length, 1001); assert.match(root.querySelector('.krea2-part-note').textContent, /1000/);
    item.onConfigure({}); assert.equal(editor.value, 'サングラス'); assert.equal(editor.getAttribute('aria-invalid'), 'false');
    type(editor, '\uD800'); assert.equal(original.value, saved); assert.equal(editor.getAttribute('aria-invalid'), 'true');
    assert.equal(h.history.length, 1);
  });

  suite('Auto/Manual dimensions and numeric drafts commit once, reject invalid input, and cancel cleanly', async t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    assert.equal(root.querySelector('[data-mode="manual"]').disabled, true);
    const height = customHeight(root); type(height, '673'); key(height, 'Enter');
    assert.equal(original.value, DEFAULT_JSON); assert.equal(height.getAttribute('aria-invalid'), 'true'); assert.equal(h.history.length, 0);
    type(height, '672'); key(height, 'Enter'); height.dispatchEvent(new Event('blur'));
    assert.equal(parseState(original.value).size.body_height, 672); assert.equal(h.history.length, 1);
    h.resolve(undefined, {width: 1344, height: 768}); await tick();
    const width = root.querySelector('[data-field="manual_width"]');
    assert.equal(width.value, '1344'); assert.equal(width.disabled, true); assert.equal(parseState(original.value).size.manual_width, 2240);
    root.querySelector('[data-mode="manual"]').click();
    assert.deepEqual(parseState(original.value).size, {mode: 'manual', body_height: 672, manual_width: 1344, manual_height: 768});
    const saved = original.value; type(width, '1500'); assert.equal(original.value, saved); key(width, 'Enter');
    assert.equal(original.value, saved); assert.equal(width.getAttribute('aria-invalid'), 'true');
    key(width, 'Escape'); assert.equal(width.value, '1344'); assert.equal(width.getAttribute('aria-invalid'), 'false');
    type(width, '1536'); width.dispatchEvent(new Event('blur')); key(width, 'Enter');
    assert.equal(parseState(original.value).size.manual_width, 1536); assert.equal(h.history.length, 3);
    const manualHeight = root.querySelector('[data-field="manual_height"]');
    type(manualHeight, '799'); key(manualHeight, 'Enter');
    assert.equal(parseState(original.value).size.manual_height, 768); assert.equal(manualHeight.getAttribute('aria-invalid'), 'true');
    type(manualHeight, '800'); key(manualHeight, 'Enter'); manualHeight.dispatchEvent(new Event('blur'));
    assert.equal(parseState(original.value).size.manual_height, 800); assert.equal(h.history.length, 4);
    root.querySelector('[data-view="hands"]').click(); assert.equal(parseState(original.value).size.manual_width, 1536);
    root.querySelector('.krea2-link-button').click(); assert.equal(parseState(original.value).size.mode, 'auto');
    assert.equal(root.querySelector('[data-height-presets]').disabled, false);
  });

  suite('Undo/Redo source restoration retains exact JSON and clears stale drafts without creating history', async t => {
    const h = setup(); t.after(h.cleanup); const {record, original, item} = h.node(profile); const root = record.ui.root;
    const editor = partEditor(root, 'face'); type(editor, 'サングラス'); const before = original.value;
    type(editor, '丸いサングラス'); const after = original.value, count = h.history.length;
    type(editor, 'x'.repeat(1001)); assert.equal(editor.getAttribute('aria-invalid'), 'true');
    original.value = before; h.flushFrames();
    assert.equal(editor.value, 'サングラス'); assert.equal(editor.getAttribute('aria-invalid'), 'false'); assert.equal(record.controller.raw, before);
    original.value = after; h.flushFrames(); assert.equal(editor.value, '丸いサングラス');
    const pretty = JSON.stringify(parseState(before), null, 2); original.value = pretty;
    assert.equal(item.onConfigure({}), 'configure-return'); h.extension.afterConfigureGraph();
    assert.equal(original.value, pretty); assert.equal(editor.value, 'サングラス'); assert.equal(h.history.length, count);
    const restoredRequest = h.requests.length - 1; h.resolve(0); await tick(); assert.equal(record.controller.isCurrentPreview, false);
    h.resolve(restoredRequest); await tick(); assert.equal(record.controller.isCurrentPreview, true); assert.equal(original.value, pretty);
  });

  suite('official widget setter retains receiver/return and external source is read before a UI action', t => {
    const h = setup(); t.after(h.cleanup); const {record, original, setterCalls, initialSetter} = h.node(profile, DEFAULT_JSON, {officialSetter: true});
    const restored = serializeState({...structuredClone(DEFAULT_STATE), views: ['feet']});
    assert.equal(original.options.setValue(restored), 'setter-return'); assert.equal(setterCalls.length, 1); assert.equal(setterCalls[0][0], original.options);
    assert.deepEqual(record.controller.state.views, ['feet']); assert.equal(h.history.length, 0);
    original.value = serializeState({...structuredClone(DEFAULT_STATE), views: ['hands']});
    record.ui.root.querySelector('[data-view="feet"]').click(); assert.deepEqual(parseState(original.value).views, ['hands', 'feet']);
    record.dispose({reinstall: false}); assert.equal(original.options.setValue, initialSetter);
  });

  suite('server and malformed-preview failures retain saved state and recover via Retry', async t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    h.requests[0].resolve({ok: false, status: 422, json: async () => ({error: {code: 'invalid_size', message: 'Invalid width'}})}); await tick();
    assert.equal(original.value, DEFAULT_JSON); assert.equal(root.querySelector('.krea2-retry').hidden, false);
    assert.match(root.querySelector('.krea2-error').textContent, /whole number/); assert.equal(root.querySelector('.krea2-json-editor').hidden, false);
    root.querySelector('.krea2-retry').click(); h.resolve(undefined, {layout: {canvas: [2208, 1280], panels: [], feet_y: null}}); await tick();
    assert.equal(record.controller.isCurrentPreview, false); assert.match(root.querySelector('.krea2-error').textContent, /invalid preview/);
    root.querySelector('.krea2-retry').click(); h.resolve(); await tick();
    assert.equal(record.controller.isCurrentPreview, true); assert.equal(root.querySelector('.krea2-retry').hidden, true); assert.equal(root.querySelector('.krea2-error').hidden, true);
    assert.equal(original.value, DEFAULT_JSON); assert.equal(h.history.length, 0);
  });

  suite('malformed raw JSON is preserved until explicit valid repair; schema 3 stays rejected', t => {
    const h = setup(); t.after(h.cleanup); const bad = ' {"schema_version": 3, "views": ["hands"]}';
    const {record, original} = h.node(profile, bad); const root = record.ui.root;
    assert.equal(original.value, bad); assert.equal(record.controller.state, null); assert.equal(h.requests.length, 0);
    assert.ok([...root.querySelectorAll('[data-view]')].every(card => card.disabled)); assert.equal(partEditor(root, 'face').disabled, true);
    const raw = root.querySelector('.krea2-json-editor textarea'); assert.equal(raw.value, bad);
    type(raw, '{still broken'); assert.equal(original.value, bad); root.querySelector('.krea2-apply').click(); assert.equal(original.value, bad);
    type(raw, DEFAULT_JSON); assert.equal(original.value, bad); root.querySelector('.krea2-apply').click();
    assert.equal(original.value, DEFAULT_JSON); assert.equal(h.history.length, 1); assert.equal(h.requests.length, 1);
    assert.equal(root.querySelector('[data-view="hands"]').disabled, false); assert.equal(partEditor(root, 'face').disabled, false);
  });

  suite('a stale successful preview cannot enable Manual after a newer network failure', async t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    h.resolve(); await tick(); assert.equal(root.querySelector('[data-mode="manual"]').disabled, false);
    root.querySelector('[data-view="hands"]').click(); const saved = original.value;
    assert.equal(root.querySelector('.krea2-stage').classList.contains('krea2-stale'), true);
    assert.equal(root.querySelector('[data-mode="manual"]').disabled, true);
    h.requests.at(-1).reject(new Error('Offline')); await tick();
    assert.equal(record.controller.preview.width, 2208); assert.equal(record.controller.isCurrentPreview, false);
    assert.equal(root.querySelector('[data-mode="manual"]').disabled, true); assert.equal(original.value, saved);
    root.querySelector('.krea2-retry').click(); h.resolve(undefined, {width: 2560, height: 1280}); await tick();
    root.querySelector('[data-mode="manual"]').click();
    assert.equal(parseState(original.value).size.manual_width, 2560);
    assert.equal(parseState(original.value).size.mode, 'manual'); assert.equal(h.history.length, 2);
  });

  suite('accessible tabs and part controls support keyboard navigation without saved-state changes', t => {
    const h = setup(); t.after(h.cleanup); const {record, original} = h.node(profile); const root = record.ui.root;
    const layout = root.querySelector('[data-tab="layout"]'), parts = root.querySelector('[data-tab="parts"]');
    assert.equal(layout.getAttribute('aria-selected'), 'true'); assert.equal(parts.tabIndex, -1);
    key(layout, 'ArrowRight'); assert.equal(parts.getAttribute('aria-selected'), 'true'); assert.equal(document.activeElement, parts);
    assert.equal(root.querySelector('#' + parts.getAttribute('aria-controls')).hidden, false);
    for (const input of root.querySelectorAll('.krea2-part-panel select, .krea2-part-panel textarea')) {
      assert.equal(root.querySelector(`label[for="${input.id}"]`)?.control, input);
    }
    key(parts, 'Home'); assert.equal(document.activeElement, layout); assert.equal(layout.getAttribute('aria-selected'), 'true');
    assert.equal(original.value, DEFAULT_JSON); assert.equal(h.history.length, 0);
  });

  suite('repeated remove/re-add disposes requests, observers, locale and DOM handlers without duplication', async t => {
    const h = setup(); t.after(h.cleanup); const {item, original} = h.node(profile); let active = getDesigner(item);
    for (let cycle = 0; cycle < 5; cycle++) {
      const root = active.ui.root, requestIndex = h.requests.length - 1, saved = original.value;
      assert.equal(h.frames.size, 1); assert.equal(h.observers.size, 1); assert.equal(h.listeners.size, 1);
      assert.equal(item.onRemoved(), 'remove-return'); assert.equal(active.controller.disposed, true); assert.equal(getDesigner(item), undefined);
      assert.equal(h.frames.size, 0); assert.equal(h.observers.size, 0); assert.equal(h.listeners.size, 0);
      assert.equal(document.contains(root), false); assert.equal(h.registry.has(active.widget), false); assert.equal(h.requests[requestIndex].opts.signal.aborted, true);
      const language = root.lang, history = h.history.length; h.locale(language === 'ja' ? 'en' : 'ja');
      root.querySelector('[data-view="hands"]').click(); assert.equal(original.value, saved); assert.equal(root.lang, language); assert.equal(h.history.length, history);
      h.resolve(requestIndex); await tick(); assert.equal(active.controller.preview, null);
      assert.equal(item.onAdded(), 'add-return'); const next = getDesigner(item); assert.ok(next); assert.notEqual(next, active);
      assert.equal(original.value, saved); assert.equal(next.controller.raw, saved);
      assert.equal(item.widgets.filter(widget => widget.name === 'state_json').length, 1);
      assert.equal(item.widgets.filter(widget => widget.serialize === false).length, 1);
      assert.equal(h.registry.size, 2); assert.equal(document.querySelectorAll('.krea2-designer').length, 1);
      assert.deepEqual(savedWidgets(item), [original]);
      // Frontend removes canonical textarea listeners on deletion. Re-add must
      // restore input propagation without creating a second saved widget.
      const restored = serializeState({...structuredClone(DEFAULT_STATE), views: cycle % 2 ? ['hands'] : ['feet']});
      type(original.element, restored); h.flushFrames(); assert.equal(next.controller.raw, restored); assert.deepEqual(next.controller.state.views, parseState(restored).views);
      active = next;
    }
    active.dispose({reinstall: false}); active.dispose({reinstall: false});
    assert.equal(original.hidden, undefined); assert.equal(original.element.hidden, false); assert.deepEqual(item.widgets, [original]);
    assert.equal(h.frames.size, 0); assert.equal(h.observers.size, 0); assert.equal(h.listeners.size, 0);
  });
}

domTest('both node profiles have independent state, DOM, SVG IDs, pending requests and disposal', async t => {
  const h = setup(); t.after(h.cleanup); const first = h.node(PROFILE), second = h.node(LAYOUT_PROFILE);
  assert.notEqual(first.record.ui.root, second.record.ui.root);
  assert.deepEqual(h.requests.map(request => request.path), [PROFILE.previewPath, LAYOUT_PROFILE.previewPath]);
  type(partEditor(first.record.ui.root, 'head_hair'), 'red hair');
  assert.equal(second.original.value, DEFAULT_JSON); assert.equal(second.record.controller.state.schema_version, 1);
  second.record.ui.root.querySelector('[data-view="feet"]').click(); assert.equal(first.record.controller.state.views.includes('feet'), false);
  h.resolve(2); h.resolve(3); await tick();
  const ids = [...document.querySelectorAll('[id]')].map(element => element.id); assert.equal(ids.length, new Set(ids).size);
  assert.equal(document.querySelectorAll('link[data-krea2-character-sheet]').length, 1);
  const saved = second.original.value; first.item.onRemoved();
  assert.equal(h.listeners.size, 1); assert.equal(h.frames.size, 1); assert.equal(h.observers.size, 1);
  h.locale('ja'); assert.equal(second.record.ui.root.lang, 'ja'); assert.equal(second.original.value, saved);
  assert.equal(second.record.controller.isCurrentPreview, true);
});

domTest('type-only and comfyClass-only layout identities are recognized without image sourcing or role state', t => {
  const h = setup(); t.after(h.cleanup);
  for (const identity of ['type', 'comfyClass']) {
    const {record, item, original} = h.node(LAYOUT_PROFILE, DEFAULT_JSON, {identity});
    assert.ok(record); assert.equal(h.requests.at(-1).path, LAYOUT_PROFILE.previewPath);
    assert.deepEqual(Object.keys(parseState(original.value)), ['schema_version', 'views', 'size']);
    assert.equal(item.inputs.length, 1); assert.equal(item.inputs[0]._widget, original); assert.deepEqual(item.outputs, []);
    assert.equal(record.ui.root.querySelectorAll('img, input[type="file"]').length, 0);
    assert.equal(record.ui.root.getAttribute('aria-label'), LAYOUT_PROFILE.displayName);
  }
  const unknown = {type: 'EmptyLatentImage', widgets: []}; h.extension.nodeCreated(unknown); assert.equal(getDesigner(unknown), undefined);
  assert.equal(h.requests.length, 2);
});

domTest('duplicate instances of either profile never share part drafts, saved bytes or SVG IDs', t => {
  const h = setup(); t.after(h.cleanup);
  for (const profile of PROFILES) {
    const first = h.node(profile); type(partEditor(first.record.ui.root, 'face'), 'sunglasses');
    const second = h.node(profile, first.original.value), saved = second.original.value;
    type(partEditor(first.record.ui.root, 'face'), 'round glasses');
    assert.equal(second.original.value, saved); assert.equal(partEditor(second.record.ui.root, 'face').value, 'sunglasses');
    type(partEditor(first.record.ui.root, 'face'), 'x'.repeat(1001)); assert.equal(partEditor(second.record.ui.root, 'face').value, 'sunglasses');
  }
  const ids = [...document.querySelectorAll('svg [id]')].map(element => element.id); assert.equal(ids.length, new Set(ids).size);
});

domTest('failed partial DOM installation rolls back widgets and hooks while preserving raw fallback input', t => {
  const h = setup(); t.after(h.cleanup);
  for (const profile of PROFILES) {
    const {item, original} = h.node(profile, DEFAULT_JSON, {install: false});
    const previousAdded = item.onAdded; let removed = false;
    item.addDOMWidget = function (name, type, element, options) {
      this.widgets.push({name, type, element, options, onRemove() { removed = true; }});
      this.onAdded = () => 'leaked'; throw new Error('unsupported DOM registration');
    };
    assert.equal(installDesigner(item, h.app, h.api), null); assert.equal(removed, true);
    assert.deepEqual(item.widgets, [original]); assert.equal(item.onAdded, previousAdded);
    assert.equal(original.value, DEFAULT_JSON); assert.equal(original.element.hidden, false); assert.equal(original.options.dynamicPrompts, false);
    assert.equal(item.krea2DesignerCompatibility.graphical, false); assert.match(original.options.tooltip, /Graphical designer unavailable/);
    assert.equal(h.listeners.size, 0); assert.equal(h.frames.size, 0); assert.equal(h.observers.size, 0);
  }
});
