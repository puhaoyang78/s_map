# Frontend

Vue 3 + Vite + Pinia frontend for `my-map-app`.

## Local setup

```sh
npm install
cp .env.example .env.local
```

Set the following in `front/.env.local`:

```env
VITE_MAPBOX_TOKEN=pk.replace-with-your-public-mapbox-token
```

Notes:

- `front/.env.example` is a safe template only.
- `front/.env.local` is ignored by Git and should hold local runtime values.
- local development uses the Vite `/api` proxy by default, so `VITE_API_BASE_URL` is not needed for `npm run dev`.
- production builds read `VITE_API_BASE_URL` from `front/.env.production` (ignored by Git, e.g. `http://replace-with-your-server-ip:5000`).
- restart the dev server after changing any `VITE_` variable.
- the frontend now reads only `VITE_MAPBOX_TOKEN`; legacy localStorage and alternate env fallbacks have been removed.

## Commands

Full-project preflight or acceptance from the repo root:

```sh
python scripts/preflight_check.py
python scripts/acceptance_check.py
python scripts/release_gate.py --mode local --skip-health
python scripts/post_deploy_check.py --backend-health-url http://replace-with-your-server-ip:5000/api/health --agent-health-url https://replace-with-your-server-ip:18080/api/v1/health
```

Development:

```sh
npm run dev
```

Lint:

```sh
npm run lint
```

Production build:

```sh
npm run build
```

Production API base:

```env
VITE_API_BASE_URL=http://replace-with-your-server-ip:5000
```

## Bundle strategy

The frontend keeps the map shell eager but lazily loads heavier non-first-screen pieces:

- `InfoView`
- `SettingsPanel`
- `SnapshotSelector`
- `SnapshotTransition`
- `StarlinkSatellitePanel`
- `satellite.js`
- `three`
