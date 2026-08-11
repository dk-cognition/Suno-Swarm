# Contributing

## Getting set up

```bash
cp .env.example .env
cd services/api && pip install -r requirements.txt
cd ../render-worker && pip install -r requirements.txt
cd ../share-service && npm install
cd ../../web && npm install
```

## Conventions

- Python: FastAPI routers stay thin; business logic goes in `app/services/`.
- Database access is always through a `Session` dependency; no module-level sessions.
- New endpoints must declare their auth dependency explicitly
  (`Depends(current_user)` or `Depends(require_admin)`).
- Object storage keys are always constructed server-side by `app/services/storage.py`.
- JavaScript: CommonJS in `share-service`, ESM in `web`.

## Tests

```bash
cd services/api && pytest
cd services/share-service && npm test
```

## Pull requests

1. One logical change per PR; include the affected service in the title, e.g. `api: ...`.
2. Update `docs/` when you change a contract.
3. Security-relevant findings should be filed as issues with the `security` label — see
  [`docs/SECURITY.md`](docs/SECURITY.md).
