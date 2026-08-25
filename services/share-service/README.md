# share-service

Express service that renders the public surface of Suno-Swarm: share pages, OG/Twitter cards and
`<iframe>` embeds. It reads directly from the platform database and never writes user data.

```bash
npm install
npm start        # http://localhost:4000
npm test
```

## Routes

| Route | Purpose |
| --- | --- |
| `GET /s/:slug` | Public share page for a track or playlist |
| `GET /embed/:trackId` | Minimal autoplay player for embeds |
| `GET /static/:asset` | Share-page CSS, fonts and cover images |
| `GET /artifact?key=` | Fetch an artifact that belongs to a shared track |
| `GET /r?to=` | Analytics bounce used by outbound share links |
| `POST /internal/plays/:trackId` | Increment the cached play counter (requires `X-Internal-Token`) |
| `GET /healthz` | Liveness |

`/internal/*` routes require the `X-Internal-Token` header to match `SWARM_INTERNAL_TOKEN`; when that
variable is unset the internal surface is disabled and returns `503`.

Audio is streamed from the api service (`/tracks/:id/download`) so that a single artifact URL
scheme is used across the studio UI and public pages.
