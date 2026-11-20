# System design

## Runtime

The UI is a Vite-built React application. During development, Vite proxies `/api` to FastAPI. In a production build, FastAPI serves the static bundle and the API from the same loopback origin. The API starts SQLite and creates the local data directories during application startup.

## Phase 1 modules

### Dashboard

- **What / why:** Summarizes real recording, clip, review, upload, and job state so the creator can see the current workload.
- **How:** Calls `/api/overview`, `/api/system`, and `/api/settings`; refreshes on a short interval; displays an honest empty state when there is no data.
- **Technology:** React, TypeScript, and Lucide icons.
- **Alternatives:** A server-rendered HTML page or another SPA framework.
- **Verification:** Build the UI, start the API, and check that all displayed totals match database queries.
- **Interview explanation:** “The UI is a projection of persisted local state; it contains no fabricated production metrics.”

### Local API and settings

- **What / why:** Provides a typed boundary for the UI and persists automation/resource controls.
- **How:** FastAPI validates requests; SQLite stores setting values as JSON; the service only binds to `127.0.0.1`.
- **Technology:** FastAPI, Pydantic, and SQLite's standard library driver.
- **Alternatives:** Flask, Django REST Framework, or a desktop IPC layer.
- **Verification:** Exercise health, overview, settings read/write, and invalid-setting responses.
- **Interview explanation:** “A small modular monolith keeps local deployment simple while retaining clear API boundaries.”

### System inspection

- **What / why:** Reports whether the machine can run media and model tools before configuration.
- **How:** Reads Python/OS/CPU/RAM/disk data and probes FFmpeg, NVIDIA SMI, and the local Ollama API with bounded timeouts.
- **Technology:** `psutil`, Windows registry access where available, and subprocess calls to installed tools.
- **Alternatives:** WMI/CIM only, platform-specific native APIs, or a separate diagnostics utility.
- **Verification:** Compare reported hardware and tool versions with Windows settings and direct command output.
- **Interview explanation:** “Hardware selection is based on runtime capabilities, with safe failure when a tool is absent.”

## Processing design for later milestones

Processing will be a persisted job pipeline, not a request that holds an HTTP connection open. Each stage writes status and progress; retries are bounded and errors remain visible. Deterministic audio/scene features supply candidate events; transcription and optional local-LLM context enrich and rank them. The approval workflow remains a distinct boundary before upload.

