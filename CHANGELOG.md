# Changelog

## Unreleased — batch clips and YouTube scheduling

- Added clip count selection from 1–100 and requested durations of 15, 30, or 45 seconds.
- Automatically queue captioned vertical renders and relevant upload metadata for generated highlights.
- Added per-clip MP4 downloads and a ZIP download for rendered clips.
- Added individual and batch YouTube schedules with a local date/time picker, a 15-minute default for one clip, and a 90-minute default batch interval.
- Scheduled videos upload as private and use YouTube's publish time; immediate uploads remain private.
- Added scheduled times to publication history and exclude upcoming videos from analytics refresh.
- Added a `scheduled_at` database migration for existing ClipForge installs.
- Updated the user and API guides; the local importer remains the supported media source and does not fetch arbitrary YouTube links.

## Unreleased — Phase 8 integration and documentation

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
- Added an optional weekly local-time schedule for queued job starts, including overnight windows and weekday selection.
- Enforced configured worker slots while serializing CPU-intensive analysis, rendering, and local metadata generation.
- Applied the CPU thread budget to faster-whisper and FFmpeg processing.
- Documented schedule boundaries and the thread budget's limits in the API and user guide.
- Added a repeatable FastAPI/worker end-to-end test from source import through YouTube analytics persistence with external services mocked.
- Added a real synthetic FFmpeg render integration test that checks vertical dimensions, duration, and SRT output.
- Fixed worker JSON payload decoding for metadata jobs and declared the HTTP test client dependency explicitly.
- Added a configurable generated-video output directory with support for paths containing spaces.
- Added integration test instructions and updated the roadmap for Phase 8 completion.
- Removed the inactive review-queue dashboard placeholder and migrate away the empty legacy table.
- Pinned PyAV below 19 to keep released faster-whisper compatible.
- Added project, installation, API, database, security, rights, user, learning, and status documentation.
- Phase 6 verification passed 21 backend checks, OAuth callback/token tests, private/resumable upload and analytics API mocks, metadata editing, retries, and source-file integrity.
- Phase 8 verification passed 31 backend checks, the production UI build, compilation, a full mocked API/worker workflow, and a real synthetic FFmpeg render.

