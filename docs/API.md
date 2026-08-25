# API Reference (`services/api`)

Base URL: `http://localhost:8000`. All authenticated endpoints expect
`Authorization: Bearer <access_token>`.

## Auth — `/auth`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/register` | Create a user and a personal workspace. |
| `POST` | `/auth/login` | Exchange email + password for an access token. |
| `POST` | `/auth/refresh` | Mint a new access token from a refresh token. |
| `GET` | `/auth/oauth/callback` | OAuth code exchange; redirects to `next`. |
| `POST` | `/auth/password/reset` | Issue a password reset token. |

```http
POST /auth/login
{"email": "artist@example.com", "password": "hunter2"}

200 {"access_token": "eyJ...", "refresh_token": "...", "token_type": "bearer"}
```

## Users — `/users`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/users/me` | Current profile, workspace and credit balance. |
| `PATCH` | `/users/me` | Update profile fields. |
| `GET` | `/users/{user_id}` | Public profile. |
| `GET` | `/users/{user_id}/avatar` | Proxy the user's remote avatar. |

## Prompts & render jobs — `/prompts`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/prompts` | Submit a prompt, debit credits, enqueue a render job. |
| `GET` | `/prompts/{prompt_id}` | Prompt plus derived jobs. |
| `GET` | `/prompts/jobs/{job_id}` | Job status and stage timings. |
| `POST` | `/prompts/jobs/{job_id}/cancel` | Cancel a queued or running job. |

```http
POST /prompts
{
  "text": "dream pop with shoegaze guitars, female vocals",
  "genre": "dream-pop",
  "bpm": 96,
  "duration_seconds": 120,
  "reference_audio_url": "https://cdn.example.com/melody.wav"
}

202 {"prompt_id": "...", "job_id": "...", "status": "queued"}
```

## Tracks — `/tracks`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/tracks` | List tracks in the caller's workspace. |
| `GET` | `/tracks/search?q=` | Full-text search over title, prompt and tags. |
| `GET` | `/tracks/{track_id}` | Track metadata + signed artifact URLs. |
| `PATCH` | `/tracks/{track_id}` | Rename / retag / toggle visibility. |
| `DELETE` | `/tracks/{track_id}` | Soft delete. |
| `GET` | `/tracks/{track_id}/download` | Download the mixdown. |
| `GET` | `/tracks/{track_id}/stems/{name}` | Download a single stem file. |
| `POST` | `/tracks/{track_id}/convert` | Transcode to another container/codec. |

## Playlists — `/playlists`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/playlists` | Create a playlist. |
| `GET` | `/playlists/{playlist_id}` | Playlist with ordered tracks. |
| `POST` | `/playlists/{playlist_id}/tracks` | Append a track. |
| `POST` | `/playlists/import` | Import an XSPF/XML playlist document. |
| `POST` | `/playlists/import/samplepack` | Import a `.zip` sample pack. |

## Admin — `/admin`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/admin/users` | Paginated user list with emails. |
| `POST` | `/admin/users/{user_id}/credits` | Grant credits. |
| `GET` | `/admin/jobs` | Job queue overview. |
| `POST` | `/admin/jobs/{job_id}/requeue` | Requeue a failed job. |
| `POST` | `/admin/flags` | Set a feature flag. |
| `GET` | `/admin/debug/config` | Non-sensitive runtime configuration; secrets are reported only as configured/unconfigured booleans. |

## Webhooks — `/webhooks`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/webhooks/render` | Worker callback with rendered artifacts. |
| `POST` | `/webhooks/billing` | Payment provider events (`invoice.paid`, `refund`). |

## Error envelope

```json
{"detail": "human readable message", "code": "track_not_found"}
```

Status codes used: `400` validation, `401` missing/invalid token, `403` authorization,
`404` not found, `409` conflict, `429` rate limited, `503` queue unavailable.
