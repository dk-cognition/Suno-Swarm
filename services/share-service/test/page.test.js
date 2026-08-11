const test = require('node:test');
const assert = require('node:assert');
const { page } = require('../src/server');

test('page renders the title into head and og metadata', () => {
  const html = page('Neon Dusk', '<p>hi</p>');
  assert.ok(html.includes('<title>Neon Dusk · Suno-Swarm</title>'));
  assert.ok(html.includes('og:title" content="Neon Dusk"'));
  assert.ok(html.includes('<p>hi</p>'));
});
