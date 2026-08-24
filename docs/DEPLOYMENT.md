# Deployment & Operations

## Environments

| Env | Cluster | Artifacts bucket | Notes |
| --- | --- | --- | --- |
| local | docker compose | MinIO (`localhost:9000`) | seeded via `scripts/seed.py` |
| staging | EKS `swarm-staging` | `suno-swarm-artifacts-staging` | 1 GPU node group |
| prod | EKS `swarm-prod` | `suno-swarm-artifacts` | autoscaled GPU node group |

## Local stack

```bash
docker compose -f infra/docker/docker-compose.yml up --build
python scripts/seed.py            # demo workspace, users, tracks
```

Services and ports: `api` 8000, `share-service` 4000, `web` 5173, PostgreSQL 5432, Redis 6379,
MinIO 9000/9001.

## Kubernetes

Manifests in [`infra/k8s`](../infra/k8s):

- `api-deployment.yaml` — 3 replicas, `/healthz` probes, config via `ConfigMap` + env.
- `render-worker-deployment.yaml` — GPU node selector, mounts the model cache volume.
- `share-service-deployment.yaml` — 2 replicas.
- `ingress.yaml` — host routing for `api.`, `share.` and the SPA.

```bash
kubectl apply -f infra/k8s/
kubectl -n swarm rollout status deploy/api
```

## Terraform

[`infra/terraform`](../infra/terraform) provisions the artifacts bucket, the app IAM role and the
RDS instance. The artifacts bucket is private: public access is blocked at the bucket level and
clients must use short-lived signed artifact URLs issued by the api.

```bash
cd infra/terraform
terraform init && terraform plan -out tf.plan && terraform apply tf.plan
```

## Configuration reference

| Variable | Service | Description |
| --- | --- | --- |
| `SWARM_DATABASE_URL` | api | PostgreSQL DSN |
| `SWARM_REDIS_URL` | api, worker | Celery broker |
| `SWARM_JWT_SECRET` | api | access token signing key |
| `SWARM_WEBHOOK_SECRET` | api, worker | HMAC key for render callbacks |
| `SWARM_BILLING_WEBHOOK_SECRET` | api | payments provider signing secret |
| `SWARM_S3_BUCKET` / `SWARM_S3_ENDPOINT` | api, worker | object storage |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | api, worker | storage credentials |
| `SWARM_MODEL_DIR` | worker | checkpoint cache |
| `SWARM_DEBUG` | api | verbose errors + SQL echo |

## Runbooks

### Queue backlog growing
1. `GET /admin/jobs` — check `queued` vs `rendering` counts.
2. Scale the worker: `kubectl -n swarm scale deploy/render-worker --replicas=N`.
3. If jobs are stuck in `rendering` > 15 min, requeue: `POST /admin/jobs/{id}/requeue`.

### Renders failing at mastering
Almost always `ffmpeg` — check worker logs for the transcode command line, then verify
`SWARM_FFMPEG_BIN` exists in the image.

### Credit drift
Reconcile `credit_ledger` against provider invoices; `reason=invoice_paid` rows carry the
provider event id in `external_ref`.

## Observability

- Logs: JSON to stdout, shipped by the node agent.
- Metrics: `/metrics` (Prometheus) on api and worker; key series are
  `swarm_render_duration_seconds`, `swarm_jobs_in_flight`, `swarm_credit_debits_total`.
- Traces: OTLP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
