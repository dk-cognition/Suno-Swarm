const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'suno-share-'));
const artifactRoot = path.join(testRoot, 'artifacts');
fs.mkdirSync(artifactRoot);
fs.writeFileSync(path.join(artifactRoot, 'cover.txt'), 'safe artifact');
fs.writeFileSync(path.join(testRoot, 'secret.txt'), 'outside artifact root');
process.env.SWARM_ARTIFACT_ROOT = artifactRoot;

const { app, resolveWithin } = require('../src/server');

test.after(() => fs.rmSync(testRoot, { recursive: true, force: true }));

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
    resolveWithin('/var/lib/swarm/artifacts', '../artifacts-evil/x'),
    null
  );
});

function request(server, requestPath) {
  const { port } = server.address();
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path: requestPath }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve({
        statusCode: res.statusCode,
        body: Buffer.concat(chunks).toString(),
      }));
    });
    req.on('error', reject);
  });
}

test('artifact endpoint serves files inside the artifact root', async (t) => {
  const server = app.listen(0);
  t.after(() => new Promise((resolve) => server.close(resolve)));

  const response = await request(server, '/artifact?key=cover.txt');
  assert.strictEqual(response.statusCode, 200);
  assert.strictEqual(response.body, 'safe artifact');
});

test('artifact endpoint rejects traversal outside the artifact root', async (t) => {
  const server = app.listen(0);
  t.after(() => new Promise((resolve) => server.close(resolve)));

  const response = await request(server, '/artifact?key=../secret.txt');
  assert.strictEqual(response.statusCode, 404);
  assert.ok(!response.body.includes('outside artifact root'));
});
