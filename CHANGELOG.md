# Changelog

## Unreleased — Phase 4 clip generation and editing

- Added a local FastAPI service and SQLite database initialization.
- Added a React/TypeScript dashboard with database-backed workspace totals and honest empty states.
- Added local settings for automation mode, resource limits, pause, and emergency stop.
- Added live CPU, memory, disk, GPU, FFmpeg, transcription-package, and Ollama diagnostics.
- Added authorized local recording import, FFmpeg inspection, persisted jobs, and retry controls.
- Added local faster-whisper CPU int8 transcription, transcript JSON, and SRT export.
- Added deterministic audio/scene candidate ranking and transcript/candidate review in the media library.
- Added persisted clip render jobs, 1080 × 1920 FFmpeg output with a blurred backdrop, and subtitle burn-in.
- Added clip-relative caption editing, SRT download, generated preview, and MP4 download.
- Pinned PyAV below 19 to keep released faster-whisper compatible.
- Added project, installation, API, database, security, rights, user, learning, and status documentation.
- Verified ten backend checks, production UI build, synthetic FFmpeg rendering, caption edits, API preview/download, re-render, and source-file integrity.

