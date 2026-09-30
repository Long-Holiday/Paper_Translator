import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/scrollSync.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { createScrollSync } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

function viewport(scrollHeight, clientHeight = 400) {
  return { scrollHeight, clientHeight, scrollTop: 0 };
}

function reader() {
  const sync = createScrollSync(2, 1.2);
  const original = viewport(1000);
  const translated = viewport(1400);
  sync.ready('original', original);
  sync.ready('translated', translated);
  return { sync, original, translated };
}

test('scrolling either column synchronizes proportional progress with different page heights', () => {
  const { sync, original, translated } = reader();
  original.scrollTop = 300;
  sync.scroll('original', original);
  assert.equal(translated.scrollTop, 500);
  translated.scrollTop = 750;
  sync.scroll('translated', translated);
  assert.equal(original.scrollTop, 450);
});

test('asynchronous scroll events from the synchronized column do not feed back after rounding', () => {
  const { sync, original, translated } = reader();
  let actualTop = 0;
  Object.defineProperty(translated, 'scrollTop', {
    get: () => actualTop,
    set: (value) => { actualTop = Math.round(value); },
  });
  original.scrollTop = 100;
  sync.scroll('original', original);
  assert.equal(translated.scrollTop, 167);
  sync.scroll('translated', translated);
  sync.scroll('translated', translated);
  assert.equal(original.scrollTop, 100);
  translated.scrollTop = 400;
  sync.scroll('translated', translated);
  assert.equal(original.scrollTop, 240);
});

test('forward page changes reset both columns to the top, ignoring scroll events during rendering', () => {
  const { sync, original, translated } = reader();
  original.scrollTop = 600;
  sync.scroll('original', original);
  sync.setView(3, 1.2);
  sync.scroll('translated', translated);
  sync.ready('original', original);
  assert.equal(original.scrollTop, 0);
  assert.equal(translated.scrollTop, 1000);
  sync.scroll('translated', translated);
  sync.ready('translated', translated);
  assert.equal(translated.scrollTop, 0);
});

test('backward page changes position both columns at their respective bottoms', () => {
  const { sync, original, translated } = reader();
  sync.setView(1, 1.2);
  original.scrollHeight = 1200;
  translated.scrollHeight = 1600;
  sync.ready('translated', translated);
  sync.ready('original', original);
  assert.equal(original.scrollTop, 800);
  assert.equal(translated.scrollTop, 1200);
});

test('zoom retains reading progress regardless of which column finishes rendering first', () => {
  const { sync, original, translated } = reader();
  translated.scrollTop = 500;
  sync.scroll('translated', translated);
  sync.setView(2, 1.5);
  original.scrollHeight = 1600;
  translated.scrollHeight = 2000;
  sync.ready('translated', translated);
  sync.ready('original', original);
  assert.equal(original.scrollTop, 600);
  assert.equal(translated.scrollTop, 800);
});

test('a translation that loads later joins at the current reading position', () => {
  const sync = createScrollSync(1, 1.2);
  const original = viewport(1000);
  const translated = viewport(1400);
  sync.ready('original', original);
  original.scrollTop = 450;
  sync.scroll('original', original);
  sync.ready('translated', translated);
  assert.equal(translated.scrollTop, 750);
});

test('a column without vertical overflow cannot erase the scrollable column progress', () => {
  const { sync, original, translated } = reader();
  translated.scrollHeight = 300;
  original.scrollTop = 300;
  sync.scroll('original', original);
  sync.scroll('translated', translated);
  assert.equal(original.scrollTop, 300);
  sync.setView(2, 1.5);
  translated.scrollHeight = 1400;
  sync.ready('translated', translated);
  assert.equal(translated.scrollTop, 500);
});

test('overscroll stays within bounds and stale viewport events are ignored', () => {
  const { sync, original, translated } = reader();
  original.scrollTop = 700;
  sync.scroll('original', original);
  assert.equal(translated.scrollTop, 1000);
  original.scrollTop = -50;
  sync.scroll('original', original);
  assert.equal(translated.scrollTop, 0);
  const oldOriginal = original;
  sync.ready('original', viewport(1000));
  oldOriginal.scrollTop = 600;
  sync.scroll('original', oldOriginal);
  assert.equal(translated.scrollTop, 0);
});
