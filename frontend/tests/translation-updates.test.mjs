import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/api/papers.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { pollTranslationUpdates } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);
const flush = () => new Promise((resolve) => setImmediate(resolve));
const snapshot = (status, progress = 0) => ({
  papers: [{ id: 2, translation_status: status, translation_progress: progress }], removed_ids: [],
});

function setup(t, fetcher) {
  const pending = new Map();
  let next = 0;
  const originals = { fetch, setTimeout, clearTimeout };
  globalThis.fetch = fetcher;
  globalThis.setTimeout = (callback, delay) => {
    assert.equal(delay, 1000);
    pending.set(++next, callback);
    return next;
  };
  globalThis.clearTimeout = (id) => pending.delete(id);
  t.after(() => Object.assign(globalThis, originals));
  return {
    pending,
    tick() {
      const [id, callback] = pending.entries().next().value;
      pending.delete(id);
      callback();
    },
  };
}

test('polls multiple IDs once per second and stops on completion', async (t) => {
  const responses = [snapshot('translating', 46), snapshot('completed', 100)];
  const calls = [];
  const timers = setup(t, async (url, options) => {
    calls.push([url, options]);
    return { ok: true, json: async () => responses.shift() };
  });
  const updates = [];
  const stop = pollTranslationUpdates([2, 5], (update) => updates.push(update));
  t.after(stop);
  await flush();
  assert.equal(calls[0][0], '/api/papers/updates?ids=2&ids=5');
  assert.equal(calls[0][1].cache, 'no-store');
  assert.equal(updates[0].papers[0].translation_progress, 46);
  assert.equal(timers.pending.size, 1);
  timers.tick();
  await flush();
  assert.equal(updates[1].papers[0].translation_progress, 100);
  assert.equal(timers.pending.size, 0);
});

test('failure and deletion are delivered and stop polling', async (t) => {
  let update;
  const timers = setup(t, async () => ({ ok: true, json: async () => update }));
  for (update of [snapshot('failed'), { papers: [], removed_ids: [2] }]) {
    const received = [];
    const stop = pollTranslationUpdates([2], (value) => received.push(value));
    await flush();
    assert.deepEqual(received, [update]);
    assert.equal(timers.pending.size, 0);
    stop();
  }
});

test('cleanup aborts an in-flight request and ignores its late result', async (t) => {
  let finish;
  let signal;
  const timers = setup(t, (_url, options) => {
    signal = options.signal;
    return new Promise((resolve) => { finish = resolve; });
  });
  const received = [];
  const stop = pollTranslationUpdates([2], (value) => received.push(value));
  assert.equal(timers.pending.size, 0);
  stop();
  assert.equal(signal.aborted, true);
  finish({ ok: true, json: async () => snapshot('translating', 60) });
  await flush();
  assert.deepEqual(received, []);
  assert.equal(timers.pending.size, 0);
});

test('transient request errors retry and page cleanup clears the timer', async (t) => {
  let calls = 0;
  const timers = setup(t, async () => {
    calls++;
    return calls === 1 ? { ok: false } : { ok: true, json: async () => snapshot('queued') };
  });
  const originalWarn = console.warn;
  console.warn = () => {};
  t.after(() => { console.warn = originalWarn; });
  const received = [];
  const stop = pollTranslationUpdates([2], (value) => received.push(value));
  t.after(stop);
  await flush();
  assert.equal(timers.pending.size, 1);
  timers.tick();
  await flush();
  assert.equal(received.length, 1);
  stop();
  assert.equal(timers.pending.size, 0);
});
