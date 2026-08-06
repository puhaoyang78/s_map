# Handover Runbook

This file is the shortest handoff entry for operators who need to publish, verify, troubleshoot, and roll back `my-map-app`.

## Current delivery status

- backend startup validation, preflight, acceptance, release gate, and runtime backup scripts are already wired into the repository
- backend `/api/health` and agent `/api/v1/health` are the primary health endpoints
- release promotion is expected to go through `scripts/release_gate.py`
- runtime backup is expected to go through `scripts/backup_runtime.py`
- post-restart verification is expected to go through `scripts/post_deploy_check.py`

## Files and secrets you must prepare

Required runtime files:

- `backend/.env.local`
- `front/.env.local`
- `front/.env.production`
- `/etc/detection-agent/agent.env`

Values that must not remain as template defaults:

- `AUTH_SECRET`
- `DEFAULT_ADMIN_PASSWORD`
- `DETECTION_ARTIFACT_PASSWORD`
- `DETECTION_AGENT_TOKEN`
- `DETECTION_WEBHOOK_TOKEN`
- `VITE_MAPBOX_TOKEN`
- `AGENT_TOKEN`
- `AGENT_CALLBACK_ALLOWED_HOSTS`

## Unified command entrypoints

Preflight:

```bash
python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env
```

Acceptance:

```bash
python scripts/acceptance_check.py --agent-env-file /etc/detection-agent/agent.env
```

Release gate:

```bash
python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
```

`--skip-acceptance` and `--skip-health` are accepted only in `--mode local`; in `--mode deploy` the gate rejects them and always runs the full acceptance pipeline and health probes.

Runtime backup:

```bash
python scripts/backup_runtime.py --agent-env-file /etc/detection-agent/agent.env --include-env
```

Post-deploy verification:

```bash
python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
```

## Go-live order

1. Rotate secrets and update `backend/.env.local`, `front/.env.local`, `front/.env.production`, and `/etc/detection-agent/agent.env`.
2. Run `python scripts/backup_runtime.py --agent-env-file /etc/detection-agent/agent.env --include-env`.
3. Run `python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env`.
4. Run `python scripts/acceptance_check.py --agent-env-file /etc/detection-agent/agent.env`.
5. Run `python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url ... --agent-health-url ...`.
6. Restart services in this order:
   - backend API
   - Celery worker
   - detection agent
   - frontend/static service
7. Run `python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url ... --agent-health-url ...`.
8. Run one minimum business smoke:
   - admin login
   - map page load
   - one detection-region request or detection-page open

## Stop / go rules

Stop the release immediately if any of the following happens:

- `preflight` reports any `ERROR`
- `acceptance` fails
- `release_gate` ends with `Release gate failed.`
- backend or agent health returns `status=error`
- webhook logs show new `token mismatch` after config rotation
- webhook logs show repeated `signature verification failed` after aligned restart

Warning that can be temporarily accepted only with explicit operator review:

- backend or agent health returns `status=warning` with empty `errors`
- `post_deploy_check.py` warns that no recent backup directory exists, if a manual backup was already taken elsewhere
- missing database warning before initial snapshot/data import

Warning that should block production traffic until resolved:

- callback allowlist warnings
- secret/template-value warnings
- log path or artifact path permission warnings

## Rollback order

1. Stop backend API, worker, agent, and frontend.
2. Restore previous code or deployment package.
3. Restore previous `backend/.env.local` and `/etc/detection-agent/agent.env`.
4. Restore the SQLite file recorded in the last backup `manifest.json` if runtime data changed.
5. Start backend API, worker, agent, and frontend in normal order.
6. Run `python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url ... --agent-health-url ...`.
7. Run `python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url ... --agent-health-url ...`.

## Runtime-only directories

Do not commit or package these as source files:

- `backend/.env.local`
- `front/.env.local`
- `backend/data/artifacts/`
- `backend/data/celery/`
- `backend/logs/`
- `backend/control/`
- `backend/db_backups/`
- `data/`
- `control/`

## Day-1 watch list

During the first day after release, check:

- backend `/api/health`
- agent `/api/v1/health`
- `front/dist/index.html` is the deployed build output
- backend log for:
  - `token mismatch`
  - `signature verification failed`
  - `invalid remote status`
  - `webhook callback not applied: reason=remote_job_id_mismatch`
- runtime directories remain writable
- latest backup directory is recorded under `backend/db_backups/`

## Fast troubleshooting entry

Configuration issue:

- check `backend/.env.local` and `/etc/detection-agent/agent.env`
- rerun `preflight`

Agent communication issue:

- check agent health
- check callback allowlist and agent token alignment

Webhook security issue:

- check `DETECTION_WEBHOOK_TOKEN`
- compare backend and agent callback config
- inspect backend log lines for exact failure reason

Frontend deployment issue:

- check `front/.env.production` and `front/.env.local`
- confirm deployed assets came from the current `front/dist/`
- inspect browser requests to backend health and first API calls
