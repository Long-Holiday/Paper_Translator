import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/api/papers.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { subscribeTranslationUpdates } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

class FakeEventSource {
  static last;
  listeners = new Map();
  closed = false;
  constructor(url) {
    this.url = url;
    FakeEventSource.last = this;
  }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  close() { this.closed = true; }
  emit(name, payload) { this.listeners.get(name)?.({ data: JSON.stringify(payload) }); }
}

test('a single connection subscribes to multiple paper IDs and delivers progress', () => {
  globalThis.EventSource = FakeEventSource;
  const received = [];
  const close = subscribeTranslationUpdates([2, 5], (updates) => received.push(updates));
  const connection = FakeEventSource.last;
  assert.equal(connection.url, '/api/papers/events?ids=2&ids=5');
  const update = { papers: [{ id: 2, translation_status: 'translating', translation_progress: 35 }], removed_ids: [] };
  connection.emit('papers', update);
  assert.deepEqual(received, [update]);
  assert.equal(connection.closed, false);
  close();
});

test('the server done event closes the connection to prevent automatic reconnect', () => {
  globalThis.EventSource = FakeEventSource;
  subscribeTranslationUpdates([1], () => {});
  const connection = FakeEventSource.last;
  connection.emit('done', {});
  assert.equal(connection.closed, true);
});

test('page cleanup closes an active connection', () => {
  globalThis.EventSource = FakeEventSource;
  const close = subscribeTranslationUpdates([1], () => {});
  const connection = FakeEventSource.last;
  close();
  assert.equal(connection.closed, true);
});
