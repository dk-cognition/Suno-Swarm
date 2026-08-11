# api

FastAPI service that owns authentication, the prompt/render lifecycle, track metadata and the
admin surface.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest
```

## Module map

| Module | Contents |
| --- | --- |
| `app/main.py` | app factory, CORS, router wiring, `/healthz` |
| `app/core/config.py` | env + YAML overlay settings |
| `app/core/security.py` | password hashing, JWT mint/decode, `current_user`, `require_admin` |
| `app/core/db.py` | engine, `SessionLocal`, `get_session` dependency |
| `app/models/models.py` | SQLAlchemy models |
| `app/models/schemas.py` | Pydantic request/response models |
| `app/routers/auth.py` | register, login, refresh, OAuth callback, password reset |
| `app/routers/users.py` | profile read/update, avatar proxy |
| `app/routers/prompts.py` | prompt submission, credit debit, job status/cancel |
| `app/routers/tracks.py` | list/search/update/delete, mixdown + stem download, convert |
| `app/routers/playlists.py` | playlist CRUD, XSPF import, sample pack import |
| `app/routers/admin.py` | user lookup, credit grants, job requeue, flags, config dump |
| `app/routers/webhooks.py` | render callbacks, billing events |
| `app/services/*` | storage, queue, audio and moderation adapters |

Endpoint semantics are documented in [`docs/API.md`](../../docs/API.md).
