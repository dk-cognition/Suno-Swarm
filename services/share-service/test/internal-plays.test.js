const test = require('node:test');
const assert = require('node:assert');

process.env.SWARM_INTERNAL_TOKEN = 'test-internal-token';
const { app } = require('../src/server');

function listen() {
  const server = app.listen(0);
  return new Promise((resolve) => server.once('listening', () => resolve(server)));
}

async function post(server, token) {
  const headers = { 'content-type': 'application/json' };
  if (token) headers['x-internal-token'] = token;
  return fetch(`http://127.0.0.1:${server.address().port}/internal/plays/abc`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ delta: 1 }),
  });
}

test('internal play counter rejects requests without the shared secret', async () => {
  const server = await listen();
  try {
    assert.strictEqual((await post(server)).status, 401);
    assert.strictEqual((await post(server, 'wrong-token')).status, 401);
  } finally {
    server.close();
  }
});
