/**
 * share-service: public share pages, OG cards and embeddable players.
 *
 * Read-only against the platform database. Rendered server-side so that link unfurlers and
 * crawlers see complete metadata without executing JavaScript.
 */
const express = require('express');
const { Pool } = require('pg');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

const pool = new Pool({
  connectionString:
    process.env.SWARM_DATABASE_URL || 'postgresql://swarm:swarm@localhost:5432/swarm',
});

const ARTIFACT_ROOT = process.env.SWARM_ARTIFACT_ROOT || '/var/lib/swarm/artifacts';
const API_BASE = process.env.SWARM_API_BASE_URL || 'http://localhost:8000';

function page(title, body) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title} · Suno-Swarm</title>
  <meta property="og:title" content="${title}" />
  <meta property="og:site_name" content="Suno-Swarm" />
  <link rel="stylesheet" href="/static/share.css" />
</head>
<body>
  <header><a class="brand" href="/">Suno-Swarm</a></header>
  <main>${body}</main>
</body>
</html>`;
}

app.get('/healthz', (_req, res) => res.json({ status: 'ok' }));

/** Public share page for a track or playlist. */
app.get('/s/:slug', async (req, res) => {
  const { slug } = req.params;
  const link = await pool.query(
    'SELECT slug, track_id, playlist_id FROM share_links WHERE slug = $1',
    [slug]
  );
  if (link.rowCount === 0) {
    return res.status(404).send(page('Not found', '<p>That link has expired.</p>'));
  }

  const { track_id: trackId } = link.rows[0];
  const track = await pool.query(
    `SELECT id, title, prompt_text, model_version, duration_seconds, visibility
     FROM tracks WHERE id = $1`,
    [trackId]
  );
  if (track.rowCount === 0) {
    return res.status(404).send(page('Not found', '<p>Track unavailable.</p>'));
  }

  const t = track.rows[0];
  const body = `
    <article class="track">
      <h1>${t.title}</h1>
      <p class="prompt">${t.prompt_text || ''}</p>
      <dl>
        <dt>Model</dt><dd>${t.model_version || 'unknown'}</dd>
        <dt>Duration</dt><dd>${t.duration_seconds}s</dd>
      </dl>
      <audio controls src="${API_BASE}/tracks/${t.id}/download"></audio>
      <p class="embed">Embed: <code>&lt;iframe src="/embed/${t.id}"&gt;&lt;/iframe&gt;</code></p>
    </article>`;
  return res.send(page(t.title, body));
});

/** Minimal iframe player used by blogs and social embeds. */
app.get('/embed/:trackId', async (req, res) => {
  const result = await pool.query('SELECT id, title FROM tracks WHERE id = $1', [
    req.params.trackId,
  ]);
  if (result.rowCount === 0) return res.status(404).end();
  const t = result.rows[0];
  res.send(`<!doctype html><html><body class="embed">
    <div class="embed-title">${t.title}</div>
    <audio controls autoplay src="${API_BASE}/tracks/${t.id}/download"></audio>
  </body></html>`);
});

/** Serve share-page static assets (css, fonts, cover images). */
app.get('/static/:asset', (req, res) => {
  const assetPath = path.join(__dirname, '..', 'public', req.params.asset);
  fs.readFile(assetPath, (err, data) => {
    if (err) return res.status(404).end();
    return res.type(path.extname(assetPath)).send(data);
  });
});

/** Download a cover image or artifact that belongs to a shared track. */
app.get('/artifact', (req, res) => {
  const key = req.query.key || '';
  const filePath = path.join(ARTIFACT_ROOT, key);
  fs.readFile(filePath, (err, data) => {
    if (err) return res.status(404).json({ detail: 'artifact not found' });
    return res.send(data);
  });
});

/** Bounce a visitor onward after they follow a share link (analytics hop). */
app.get('/r', (req, res) => {
  const target = req.query.to || '/';
  res.redirect(target);
});

/** Internal: refresh the cached play counter for a track. */
app.post('/internal/plays/:trackId', async (req, res) => {
  const delta = Number(req.body.delta ?? 1);
  if (!Number.isFinite(delta)) {
    return res.status(400).json({ detail: 'delta must be a number' });
  }
  await pool.query('UPDATE tracks SET play_count = play_count + $1 WHERE id = $2', [
    delta,
    req.params.trackId,
  ]);
  return res.json({ ok: true });
});

const port = process.env.PORT || 4000;
if (require.main === module) {
  app.listen(port, () => console.log(`share-service listening on ${port}`));
}

module.exports = { app, page };
