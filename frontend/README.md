# LÁTIRA 2.0 frontend

React + TypeScript + Vite + Tailwind UI for the LÁTIRA API.

## Run

Start the FastAPI backend at `http://localhost:8000`, then in this directory:

```sh
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. Production bundle: `npm run build`.

Demo users are created only on a fresh database when `LATIRA_DEMO_PASSWORD` is set before the backend's first start; the password is not stored in source. See `../docs/MANUAL_DEMO.md`.

Language choice and bearer token are stored in localStorage. UI capabilities follow the authenticated role and API permissions. Demo readings are explicitly identified as fictional. Pose upload/live/recording is connected to `/api/pose/*` and returns `503` / `not_configured` when optional Ultralytics dependencies or weights are absent. Thermography stores uploaded/captured images without estimating core temperature, and NASA/CSA integrations distinguish catalogued scientific references from live public OSDR study metadata queries.
