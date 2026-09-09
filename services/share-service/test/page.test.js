const test = require('node:test');
const assert = require('node:assert');
const { page, escapeHtml } = require('../src/server');

test('page escapes markup in the title', () => {
  const html = page('<script>alert(1)</script>"x', '<p>hi</p>');
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('<title>&lt;script&gt;alert(1)&lt;/script&gt;&quot;x · Suno-Swarm</title>'));
  assert.ok(html.includes('og:title" content="&lt;script&gt;alert(1)&lt;/script&gt;&quot;x"'));
});

test('escapeHtml encodes all HTML-significant characters and handles null', () => {
  assert.strictEqual(escapeHtml(`<a href="x" title='y'>&</a>`), '&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;');
  assert.strictEqual(escapeHtml(null), '');
  assert.strictEqual(escapeHtml(undefined), '');
  assert.strictEqual(escapeHtml(42), '42');
});

test('page renders the title into head and og metadata', () => {
  const html = page('Neon Dusk', '<p>hi</p>');
  assert.ok(html.includes('<title>Neon Dusk · Suno-Swarm</title>'));
  assert.ok(html.includes('og:title" content="Neon Dusk"'));
  assert.ok(html.includes('<p>hi</p>'));
});
