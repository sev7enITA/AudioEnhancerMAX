const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const { setImmediate } = require('node:timers/promises');

test('reopening the credentials panel preserves progress and prevents duplicate signing', async () => {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) {
      elements.set(id, {
        disabled: false,
        textContent: '',
        events: new Map(),
        addEventListener(name, listener) { this.events.set(name, listener); },
        dispatch(name) { return this.events.get(name)(); },
      });
    }
    return elements.get(id);
  };
  element('compliance-format').value = 'wav';
  const pending = [];
  const state = {
    fileId: 'fixture', processedVersion: 'processed', processedRevision: 'current',
    hasProcessed: true, isProcessing: false,
  };
  const fetch = (_url, options) => options.method === 'POST'
    ? new Promise(resolve => { pending.push(resolve); })
    : Promise.resolve({ok: true, json: async () => ({inspect: true, sign: true})});
  vm.runInNewContext(fs.readFileSync('frontend/js/content-credentials.js', 'utf8'), {
    document: {getElementById: element}, state, fetch,
    readApiError: async () => 'Signing request interrupted',
  });
  await setImmediate();

  const panel = element('credentials-export');
  const button = element('credentials-export-button');
  const status = element('credentials-export-status');
  const first = button.dispatch('click');
  panel.open = true;
  panel.dispatch('toggle');
  await setImmediate();

  assert.equal(button.disabled, true);
  assert.equal(status.textContent, 'Signing and verifying a copy…');
  await button.dispatch('click');
  assert.equal(pending.length, 1);
  pending[0]({ok: false});
  await first;
  assert.equal(button.disabled, false);
});
