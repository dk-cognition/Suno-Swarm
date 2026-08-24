const test = require('node:test');
const assert = require('node:assert');
const http = require('node:http');
const { app, resolveWithin } = require('../src/server');

test('resolveWithin allows a normal relative filename', () => {
  assert.strictEqual(
    resolveWithin('/var/lib/swarm/artifacts', 'tracks/cover.png'),
    '/var/lib/swarm/artifacts/tracks/cover.png'
  );
});

test('resolveWithin rejects a parent-directory escape', () => {
  assert.strictEqual(resolveWithin('/var/lib/swarm/artifacts', '../etc/passwd'), null);
});

test('resolveWithin rejects a nested parent-directory escape', () => {
  assert.strictEqual(
    resolveWithin('/var/lib/swarm/artifacts', 'a/../../etc/passwd'),
    null
  );
});

test('resolveWithin rejects absolute paths', () => {
  assert.strictEqual(
    resolveWithin('/var/lib/swarm/artifacts', '/etc/passwd'),
    null
  );
});

test('resolveWithin rejects empty and non-string candidates', () => {
  assert.strictEqual(resolveWithin('/var/lib/swarm/artifacts', ''), null);
  assert.strictEqual(resolveWithin('/var/lib/swarm/artifacts', null), null);
  assert.strictEqual(resolveWithin('/var/lib/swarm/artifacts', 42), null);
});

test('resolveWithin rejects paths that only prefix-match the root', () => {
  assert.strictEqual(
    resolveWithin('/var/lib/swarm/artifacts', '/var/lib/swarm/artifacts-evil/x'),
    null
  );
});

function request(server, requestPath) {
  const { port } = server.address();
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path: requestPath }, (res) => {
      res.resume();
      res.on('end', () => resolve(res));
    });
    req.on('error', reject);
  });
}

test('artifact traversal requests return 404', async (t) => {
  const server = app.listen(0);
  t.after(() => new Promise((resolve) => server.close(resolve)));

  const response = await request(server, '/artifact?key=../../../../etc/passwd');
  assert.strictEqual(response.statusCode, 404);
});

test('static traversal requests return 404', async (t) => {
  const server = app.listen(0);
  t.after(() => new Promise((resolve) => server.close(resolve)));

  const response = await request(server, '/static/../src/server.js');
  assert.strictEqual(response.statusCode, 404);
});
