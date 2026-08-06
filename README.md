# my-map-app

`my-map-app` is a Vue 3 + Flask + Celery full-stack map and detection system. The repository now uses commit-safe config templates plus local override files so runtime secrets and artifacts do not need to live in version control.

## Repo layout

- `front/`: Vue 3 + Vite + Pinia frontend
- `backend/`: Flask API, Celery tasks, repositories, tests
- `scripts/`: preflight, acceptance, release gate, runtime backup, and post-deploy verification entrypoints
- `detection_server_agent.py`: remote detection agent HTTP service
- `detection_server_agent.service.example`: hardened systemd unit example for the agent
- `detection_server_agent.env.example`: `EnvironmentFile` template for the agent
- `docs/HANDOVER_RUNBOOK.md`: operator handover and go-live checklist

## Config and secrets

Backend config loading order:

1. `backend/.env`
2. `backend/.env.local`

`backend/.env` and `backend/.env.local` are both ignored by Git; `backend/.env.example` is the committed template. Copy it to `backend/.env.local` and put real secrets there. Process environment variables take precedence over both files.

Frontend config:

- copy `front/.env.example` to `front/.env.local`
- keep `VITE_MAPBOX_TOKEN` in `front/.env.local`
- create `front/.env.production` (ignored by Git) pointing production builds at `http://replace-with-your-server-ip:5000`

Agent config:

- copy `detection_server_agent.env.example` to `/etc/detection-agent/agent.env`
- keep `AGENT_TOKEN`, TLS key paths, callback allowlist and logging config there
- do not commit runtime agent secrets to the repository
- for direct local agent runs, place overrides in `detection_server_agent.env.local`

Backend startup now fails fast when template values are still being used for critical secrets such as `AUTH_SECRET`, `DETECTION_ARTIFACT_PASSWORD`, `DETECTION_AGENT_TOKEN`, or callback credentials behind `DETECTION_WEBHOOK_BASE_URL`.

## Required rotations after migrating old config

If this repo previously stored live values in `backend/.env`, rotate at least:

- `AUTH_SECRET`
- `DEFAULT_ADMIN_PASSWORD`
- `DETECTION_AGENT_TOKEN`
- `DETECTION_WEBHOOK_TOKEN`
- any reused Mapbox token if it was not meant to be public

## Callback trust boundary

The detection agent now rejects callback URLs unless they satisfy all of the following:

- host matches `AGENT_CALLBACK_ALLOWED_HOSTS`
- port is `443` or explicitly listed in `AGENT_CALLBACK_ALLOWED_PORTS`
- scheme is `https` unless `AGENT_CALLBACK_ALLOW_INSECURE_HTTP=true`
- target is not `localhost`, loopback or private-network space unless `AGENT_CALLBACK_ALLOW_PRIVATE_HOSTS=true`
- callback token is present when `AGENT_CALLBACK_REQUIRE_TOKEN=true`

The backend webhook also verifies:

- bearer token or `X-Webhook-Token`
- `X-Webhook-Timestamp`
- `X-Webhook-Signature`

Signature verification is enabled by default with `DETECTION_WEBHOOK_REQUIRE_SIGNATURE=true`.

## Source vs runtime directories

Source and committed configuration:

- `front/`
- `backend/`
- `detection_server_agent.py`
- `detection_server_agent.service.example`
- `detection_server_agent.env.example`

Runtime-only data and control paths:

- `backend/data/artifacts/`
- `backend/data/celery/`
- `backend/logs/`
- `backend/control/`
- `backend/db_backups/`
- `data/`
- `control/`

## Runtime boundary

These paths are runtime-only and should stay out of version control:

- `backend/.env.local`
- `front/.env.local`
- `backend/data/artifacts/`
- `backend/data/celery/`
- `backend/logs/`
- `backend/control/`
- `backend/db_backups/`
- `data/`
- `control/`

`backend/data/index_with_geo_utf.csv` remains a source asset and is intentionally kept.

## Local verification

Preflight:

```bash
python scripts/preflight_check.py
python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env
```

Minimum acceptance pipeline:

```bash
python scripts/acceptance_check.py
python scripts/acceptance_check.py --agent-env-file /etc/detection-agent/agent.env
```

Final release gate:

```bash
python scripts/release_gate.py --mode local --skip-health
python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
```

Runtime backup:

```bash
python scripts/backup_runtime.py
python scripts/backup_runtime.py --agent-env-file /etc/detection-agent/agent.env --include-env
```

Post-deploy verification:

```bash
python scripts/post_deploy_check.py --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
```

Backend only:

```bash
cd backend
python -m unittest discover -s tests -v
```

Frontend only:

```bash
cd front
npm run lint
npm run build
```

Health endpoints after startup:

```bash
curl http://replace-with-your-server-ip:5000/api/health
curl https://replace-with-your-server-ip:18080/api/v1/health
```

## Release gate

Use `scripts/release_gate.py` as the final promotion entrypoint.

- local mode:
  - intended for a developer workstation or pre-merge validation
  - runs preflight plus acceptance
  - health probing is optional
- deploy mode:
  - intended for the real deployment host or release candidate environment
  - requires `--agent-env-file`
  - should be paired with `--backend-health-url` and `--agent-health-url`
  - fails if preflight has hard errors, acceptance fails, frontend build artifact is missing, or health endpoints return an error state

Warnings are shown separately from hard failures:

- must pass:
  - preflight errors
  - acceptance failures
  - missing `front/dist/index.html`
  - backend or agent health returning `status=error`
- acceptable warning only after review:
  - health `status=warning`
  - skipped acceptance for post-deploy smoke
  - skipped health probes in local mode
  - backend database path exists later than config creation but has not been initialized yet

## Deployment shortest path

For a fresh Ubuntu/Debian server that already has this repository checked out, use the bootstrap script:

```bash
cd /home/ubuntu/my-map-app
PUBLIC_HOST=your-server-ip sudo -E bash deploy/bootstrap-new-server.sh
```

The script installs Miniconda from the Tsinghua mirror, configures conda/pip mirrors, creates the `starlink` conda env, installs Node.js/npm, installs backend and frontend dependencies, builds the frontend, writes `my-map-backend.service` and `my-map-frontend.service`, starts both services, and prints the generated admin password when it creates `backend/.env.local`. Existing `backend/.env.local` and `front/.env.production.local` are preserved unless `FORCE_ENV=1` is set; when preserving `backend/.env.local`, the script still ensures `CORS_ORIGINS` includes the current frontend origin derived from `PUBLIC_HOST`.

1. Copy `backend/.env.example` to `backend/.env.local` and replace all template secrets.
2. Copy `front/.env.example` to `front/.env.local`, keep `VITE_MAPBOX_TOKEN` there, and use `front/.env.production` for `VITE_API_BASE_URL=http://replace-with-your-server-ip:5000`.
3. Copy `detection_server_agent.env.example` to `/etc/detection-agent/agent.env` and set `AGENT_TOKEN`, callback allowlist, log path, probe path, artifact path, and TLS files.
4. Run `python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env`.
5. Start backend API and Celery worker.
6. Start the detection agent service.
7. Start or deploy the frontend.
8. Verify `/api/health`, `/api/v1/health`, backend unit tests, frontend lint, and frontend build.

## Smoke runbook

Minimal release rehearsal, before exposing traffic:

1. Run `python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`.
2. Confirm the summary ends with `Release gate passed.`.
3. If warnings remain, review them before promoting traffic. `status=warning` on a health endpoint is not an automatic blocker, but it must be understood and accepted.
4. Confirm frontend build output exists at `front/dist/index.html`.
5. Confirm backend health reports:
   - `status` is `ok` or an explicitly accepted `warning`
   - `errors` is empty
   - `paths.databasePath.path` points to the expected SQLite file
6. Confirm agent health reports:
   - `callbackAllowlistConfigured=true`
   - `callbackRequireToken=true`
   - `errors` is empty
7. Run one minimum business-path check:
   - log in through the frontend with an admin account
   - load the main map page
   - open the detection page or trigger the region list request once
   - verify there is no new `token mismatch`, `signature verification failed`, or `invalid remote status` message in backend logs
8. Run `python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`.

## Deployment order and dependencies

- backend API: must be configured first because the frontend and webhook callback base URL depend on it
- Celery worker: must run with the same backend config before detection jobs are accepted
- detection agent: depends on its own `EnvironmentFile`, reachable backend ingress, and callback allowlist entries
- frontend: depends on the backend API base URL and public Mapbox token only

## Secret rotation order

1. Rotate `AUTH_SECRET` and `DEFAULT_ADMIN_PASSWORD`.
2. Rotate `DETECTION_ARTIFACT_PASSWORD`.
3. Rotate `DETECTION_AGENT_TOKEN` on both backend and agent.
4. Rotate `DETECTION_WEBHOOK_TOKEN` on the backend side that signs and verifies callbacks.
5. Rerun `python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env`.
6. Recheck `/api/health` and `/api/v1/health` after restarting services.

## Secure deployment checklist

- create `backend/.env.local` from `backend/.env.example`
- create `/etc/detection-agent/agent.env` from `detection_server_agent.env.example`
- rotate `AUTH_SECRET`, `DEFAULT_ADMIN_PASSWORD`, `DETECTION_ARTIFACT_PASSWORD`, `DETECTION_AGENT_TOKEN`, and `DETECTION_WEBHOOK_TOKEN`
- set `AGENT_CALLBACK_ALLOWED_HOSTS` and `AGENT_CALLBACK_ALLOWED_PORTS` to the real backend ingress
- keep `DETECTION_WEBHOOK_BASE_URL` aligned with the externally reachable backend callback URL
- confirm `/var/log/detection-agent`, agent working directory, artifact directory, and backend runtime directories exist and are writable by the current service setup
- keep `AUTH_COOKIE_SECURE=true` and HTTPS-only callback settings in real deployments
- run `python scripts/preflight_check.py --agent-env-file /etc/detection-agent/agent.env`
- run `python scripts/acceptance_check.py --agent-env-file /etc/detection-agent/agent.env` before promoting a build
- run `python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`

## Common deployment failures

- `AUTH_SECRET must be set...`: `backend/.env.local` still contains a template value; rotate it and rerun preflight.
- `DETECTION_ARTIFACT_PASSWORD must be set...`: import/extract will fail later; fix it before startup.
- `AGENT_CALLBACK_ALLOWED_HOSTS must be configured...`: the agent will reject backend callbacks until the ingress hostname is allowlisted.
- `backend database file does not exist yet`: the config path is valid, but data import or snapshot activation has not happened yet.
- `agent env file was not found locally`: local preflight skipped strict agent validation; pass `--agent-env-file` to validate the deployed service config.

## Backup, restore, and rollback

Create a lightweight runtime backup before changing live config or data:

```bash
python scripts/backup_runtime.py --agent-env-file /etc/detection-agent/agent.env --include-env
```

Backup naming rule:

- each backup is created as `backend/db_backups/release-backup-<UTC timestamp>/`
- the directory always contains `manifest.json`
- `manifest.json` is the fastest way to confirm which database file, config file, and env files were captured

What the backup captures:

- the active SQLite database file recorded in `backend/config/db_config.json`
- `backend/config/db_config.json`
- optionally `backend/.env.local`, `front/.env.local`, and the agent `EnvironmentFile`
- a `manifest.json` with restore hints, runtime path summary, and copied file list

What it does not restore automatically:

- `backend/logs/`
- `backend/control/`
- `backend/data/celery/`
- runtime artifacts under `backend/data/artifacts/`

Restore sequence after a failed release:

1. Stop backend API, Celery worker, agent, and frontend.
2. Restore the previous code package or deployment directory.
3. Restore `backend/.env.local` and `/etc/detection-agent/agent.env` from the last known-good backup if configuration changed.
4. Restore the SQLite database file recorded in `manifest.json` to the path recorded in `backend/config/db_config.json` if runtime data changed during the failed release.
5. Start backend API and Celery worker.
6. Start the agent.
7. Start the frontend.
8. Run `python scripts/release_gate.py --mode deploy --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`.
9. Run `python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`.

Shortest rollback path when the release fails before data changes:

1. Restore previous code.
2. Restore previous env files.
3. Restart services in backend -> worker -> agent -> frontend order.
4. Run the deploy-mode release gate for confirmation (deploy mode no longer accepts `--skip-acceptance`; for a quick health-only check use `post_deploy_check.py` as shown above).

## Operations and troubleshooting runbook

If `preflight` fails:

1. Read the exact `ERROR` line.
2. Fix the file or variable named in that line.
3. Rerun `python scripts/preflight_check.py` or the deploy variant with `--agent-env-file`.

If `acceptance` fails:

1. Re-run the failing command directly:
   - backend tests: `cd backend && python -m unittest discover -s tests -v`
   - frontend lint: `cd front && npm run lint`
   - frontend build: `cd front && npm run build`
2. Fix the failing step before returning to `scripts/release_gate.py`.

If `/api/health` returns `status=warning`:

1. Check `warnings` and `errors` in the JSON payload.
2. `errors` must be empty to continue.
3. A missing database file warning can be acceptable only before first data import or snapshot activation.
4. A callback or secret-related warning should block promotion until understood.

If `/api/v1/health` returns `status=warning` or `status=error`:

1. Check `paths.probeScript.path`, `paths.artifactDir.path`, and `paths.logFile.path`.
2. Fix missing files or permissions first.
3. Ensure `callbackAllowlistConfigured=true` before release.

If backend logs show webhook failures:

- `token mismatch`:
  - compare `DETECTION_WEBHOOK_TOKEN` on backend with the callback token seen by the agent
  - restart backend and agent after fixing mismatched values
- `signature verification failed (missing_signature_headers)`:
  - confirm the agent is sending `X-Webhook-Timestamp` and `X-Webhook-Signature`
  - confirm the request is still going through the hardened callback path
- `signature verification failed (signature_mismatch)`:
  - rotate and realign `DETECTION_WEBHOOK_TOKEN`
  - check for stale agent config after a secret change
- `invalid remote status`:
  - verify the agent code version matches the backend release
- `webhook callback not applied: reason=...`:
  - `duplicate_event` or `stale_event` is usually safe
  - `remote_job_id_mismatch` needs investigation before more jobs are dispatched

If frontend build passes but runtime still breaks:

1. Verify `front/.env.production` has the correct `VITE_API_BASE_URL`.
2. Confirm the deployed static files really came from the current `front/dist/`.
3. Open browser devtools and confirm `/api/health` and the first API calls go to the expected backend origin.

If the release ships with a bad config:

1. Restore the last known-good env files.
2. Restart backend, worker, and agent.
3. Run the deploy-mode release gate (full checks; `--skip-acceptance` is rejected in deploy mode).
4. Only restore the database backup if the bad release also changed runtime data.

## First-day operations

During the first day after release, check:

- `python scripts/post_deploy_check.py --agent-env-file /etc/detection-agent/agent.env --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health`
- backend `/api/health`
- agent `/api/v1/health`
- frontend static assets are serving the expected `front/dist/` build
- backend log does not show new:
  - `token mismatch`
  - `signature verification failed`
  - `invalid remote status`
  - `webhook callback not applied: reason=remote_job_id_mismatch`
- runtime directories remain writable:
  - `backend/data/artifacts/`
  - `backend/data/celery/`
  - `backend/logs/`
  - `backend/control/`
  - `backend/db_backups/`

Immediate rollback triggers:

- backend or agent health returns `status=error`
- repeated webhook `token mismatch` after confirmed restart
- repeated webhook `signature verification failed` after confirmed secret alignment
- frontend deploy points at the wrong backend origin and cannot be corrected quickly
- SQLite path or runtime directories are not writable after restart

## Handover

For operator handoff, use [HANDOVER_RUNBOOK.md](/E:/my-map-app/docs/HANDOVER_RUNBOOK.md).
