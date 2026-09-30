import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/wheelPageNavigation.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { attachWheelPageNavigation } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

function reader({ page = 2, totalPages = 4, scrollTop = 600, scrollHeight = 1000 } = {}) {
  const state = { page, totalPages, ready: true };
  const changes = [];
  const container = new EventTarget();
  Object.assign(container, { scrollTop, clientHeight: 400, scrollHeight });
  const cleanup = attachWheelPageNavigation(container, () => state, (nextPage) => {
    changes.push(nextPage);
    state.page = nextPage;
  });
  const wheel = (deltaY, timeStamp = 1000, props = {}) => {
    const event = new Event('wheel', { cancelable: true });
    Object.defineProperties(event, Object.fromEntries(Object.entries({
      deltaY, deltaX: 0, deltaMode: 0, ctrlKey: false, timeStamp, ...props,
    }).map(([key, value]) => [key, { value }])));
    container.dispatchEvent(event);
    return event;
  };
  return { state, changes, container, cleanup, wheel };
}

test('scrolls within the page normally and changes pages only at its edges', () => {
  const view = reader({ scrollTop: 200 });
  assert.equal(view.wheel(120).defaultPrevented, false);
  assert.equal(view.wheel(-120).defaultPrevented, false);
  assert.deepEqual(view.changes, []);
  view.container.scrollTop = 600;
  assert.equal(view.wheel(120).defaultPrevented, true);
  assert.deepEqual(view.changes, [3]);
  view.container.scrollTop = 0;
  view.wheel(-120, 1800);
  assert.deepEqual(view.changes, [3, 2]);
});

test('does not go beyond the first or last page', () => {
  const first = reader({ page: 1, scrollTop: 0 });
  const last = reader({ page: 4 });
  first.wheel(-120);
  last.wheel(120);
  assert.deepEqual(first.changes, []);
  assert.deepEqual(last.changes, []);
});

test('short pages can be turned in either direction', () => {
  const view = reader({ scrollTop: 0, scrollHeight: 300 });
  view.wheel(120);
  view.wheel(-120, 1800);
  assert.deepEqual(view.changes, [3, 2]);
});

test('small trackpad movements accumulate and inertia does not immediately turn another page', () => {
  const view = reader();
  view.wheel(20, 1000);
  view.wheel(20, 1050);
  assert.deepEqual(view.changes, []);
  view.wheel(20, 1100);
  view.wheel(120, 1150);
  view.wheel(120, 1300);
  assert.deepEqual(view.changes, [3]);
  view.wheel(120, 1800);
  assert.deepEqual(view.changes, [3, 4]);
});

test('separate small gestures and direction reversals do not combine into a page turn', () => {
  const view = reader({ scrollTop: 0, scrollHeight: 300 });
  view.wheel(40, 1000);
  view.wheel(40, 1500);
  view.wheel(-40, 1550);
  assert.deepEqual(view.changes, []);
  view.wheel(-20, 1600);
  assert.deepEqual(view.changes, [1]);
});

test('horizontal scrolling and pinch zoom keep their native behavior', () => {
  const view = reader();
  assert.equal(view.wheel(120, 1000, { ctrlKey: true }).defaultPrevented, false);
  assert.equal(view.wheel(120, 1100, { deltaX: 240 }).defaultPrevented, false);
  assert.deepEqual(view.changes, []);
});

test('waits for page rendering and removes the listener on cleanup', () => {
  const view = reader();
  view.state.ready = false;
  view.wheel(120);
  assert.deepEqual(view.changes, []);
  view.state.ready = true;
  view.wheel(120, 1800);
  assert.deepEqual(view.changes, [3]);
  view.cleanup();
  assert.equal(view.wheel(120, 2600).defaultPrevented, false);
  assert.deepEqual(view.changes, [3]);
});

test('normalizes line and page wheel units', () => {
  const lines = reader();
  const pages = reader();
  lines.wheel(4, 1000, { deltaMode: 1 });
  pages.wheel(1, 1000, { deltaMode: 2 });
  assert.deepEqual(lines.changes, [3]);
  assert.deepEqual(pages.changes, [3]);
});
