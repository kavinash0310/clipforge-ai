# Changelog

## Unreleased — Phase 6 YouTube integration

- Added a local FastAPI service and SQLite database initialization.
- Added a React/TypeScript dashboard with database-backed workspace totals and honest empty states.
- Added local settings for automation mode, resource limits, pause, and emergency stop.
- Added live CPU, memory, disk, GPU, FFmpeg, transcription-package, and Ollama diagnostics.
- Added authorized local recording import, FFmpeg inspection, persisted jobs, and retry controls.
- Added local faster-whisper CPU int8 transcription, transcript JSON, and SRT export.
- Added deterministic audio/scene candidate ranking and transcript/candidate review in the media library.
- Added persisted clip render jobs, 1080 × 1920 FFmpeg output with a blurred backdrop, and subtitle burn-in.
- Added clip-relative caption editing, SRT download, generated preview, and MP4 download.
- Added persisted clip metadata drafts, local Ollama generation, offline templates, and editable title, description, hashtags, and search tags.
- Added Google Desktop OAuth with PKCE, loopback state validation, Windows DPAPI token storage, and disconnect/revoke.
- Added resumable private YouTube uploads with per-clip duplicate prevention, persisted progress, restart recovery, and retries.
- Added per-video YouTube analytics refresh and channel publication UI.
- Removed the inactive review-queue dashboard placeholder and migrate away the empty legacy table.
- Pinned PyAV below 19 to keep released faster-whisper compatible.
- Added project, installation, API, database, security, rights, user, learning, and status documentation.
- Verified 21 backend checks, production UI build, OAuth callback/token tests, private/resumable upload and analytics API mocks, synthetic FFmpeg rendering, metadata editing, retries, and source-file integrity.

