# LÁTIRA 2.0 frontend

React + TypeScript + Vite + Tailwind UI for the LÁTIRA API.

## Run

Start the FastAPI backend at `http://localhost:8000`, then in this directory:

```sh
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. Production bundle: `npm run build`.

In `LATIRA_ENV=demo` (default in `run.sh`/`run.bat`), the login screen displays a passwordless demo profile selector (`Astronaut`, `Medical officer`, `Administrator`) resolved server-side. In `LATIRA_ENV=production`, standard username/password login is enforced and demo accounts are only seeded on an empty database if `LATIRA_DEMO_PASSWORD` is configured. See `../docs/MANUAL_DEMO.md` and `../docs/fase2/FASE2_GUIA_DEMO_LATI.md`.

Language choice, bearer token, and LÁTI voice-reply preference are stored in `localStorage`. UI capabilities follow the authenticated role and API permissions. In LÁTI chat, astronauts can type or use Web Speech API microphone recognition (`SpeechRecognition`) and hear replies via `speechSynthesis` with non-overlapping playback and stop controls, while external generative AI runs strictly server-side with automatic honest fallback when unconfigured or unavailable. Pose upload/live/recording is connected to `/api/pose/*` (`503` / `not_configured` when optional Ultralytics weights are absent), thermography stores uploaded/captured images without estimating core temperature, and NASA/CSA integrations distinguish catalogued scientific references from live public OSDR study metadata queries.
