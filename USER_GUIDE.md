# User guide

## Phase 1 dashboard

Start the backend and UI using [INSTALLATION.md](INSTALLATION.md). The Overview page reads its totals from the local SQLite database. With a fresh install, zero counts and “No activity yet” are the expected real state.

The readiness card reports FFmpeg, NVIDIA GPU, transcription package, and Ollama availability. Settings shows detected CPU, memory, free disk, and the app data path.

## Settings

- Select manual, semi-automatic, or automatic as your preferred future workflow. Semi-automatic is the default.
- Set a conservative job concurrency and CPU target for this machine.
- Pause processing to stop new work from starting.
- Emergency stop is a separate persisted control that future workers must check before processing or publishing.

Video ingestion, clip editing, approval, and upload are not available in Phase 1.

