import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/components/pdfLayout.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const { pageTop, scaledScrollTop } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

test('jumping to a page includes all preceding pages of different sizes', () => {
  assert.equal(pageTop([800, 1000, 600], 1, 1.2), 0);
  assert.equal(pageTop([800, 1000, 600], 3, 1.2), 2184);
});

test('zoom preserves position within a later page without scaling gaps', () => {
  const heights = [800, 1000, 600];
  const top = pageTop(heights, 3, 1.2) + 300;
  assert.equal(scaledScrollTop(heights, top, 1.2, 2), pageTop(heights, 3, 2) + 500);
});

test('zooming while between pages keeps the offset within the fixed gap', () => {
  assert.equal(scaledScrollTop([800, 1000], 800 * 1.2 + 6, 1.2, 2), 1600 + 6);
  assert.equal(scaledScrollTop([800], 0, 1.2, 0.6), 0);
});
