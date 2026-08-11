# render-worker

Celery worker that turns a queued `RenderJob` into a rendered track.

```bash
pip install -r requirements.txt
celery -A worker.tasks worker -l info -c "${SWARM_CONCURRENCY:-1}"
```

Stages and configuration are documented in
[`docs/GENERATION_PIPELINE.md`](../../docs/GENERATION_PIPELINE.md).

In this reference implementation the diffusion model is stubbed: `pipeline.infer` emits a silent
wav of the requested duration when no checkpoint is present in `SWARM_MODEL_DIR`, so the full
job lifecycle (conditioning → separation → mastering → callback) can be exercised end to end
without a GPU.
