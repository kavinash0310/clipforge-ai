# Changelog

## Unreleased — Neon-inspired clip studio

- Reworked the studio palette to orchid, hot pink, and cyan with brighter accents and matching editor surfaces.
- Added the workflow stages **Make it your format**, **Frame your moment**, **Give it a voice**, and **Style & extras**, with platform aspect presets, 720p/1080p/4K output, source/24/30/60 fps, more crop/blur positions, transcription language, caption presets, hooks, creator marks, and music beds.
- Added an optional transcript phrase boost for highlight ranking and ASS subtitle-file import alongside SRT/WebVTT.
- Added source-video review with a 9:16 safe-area guide and I/O/Space trim shortcuts.
- Added draggable gameplay and facecam regions with gameplay-only, picture-in-picture, stacked, and side-by-side render layouts.
- Added an **Upload all privately** batch action beside YouTube scheduling and the existing all-clips download.
- Added live local-stream capture with a rolling segment buffer, 15/30/45-second clips, status polling, and automatic queuing into transcription, highlight selection, captioning, and rendering.
- Added loopback-only RTMP/SRT/UDP validation for live input and capture shutdown on app exit.
- Added a searchable My clips library with ready/in-progress filters, individual/ZIP downloads, direct editor links, and saved one-to-five star ratings.
- Added Balanced, Action, and Dialogue moment scoring mixes to upload, local-path, direct-file-link, and re-analysis flows.
- Added transcript search and one-click passage-to-clip creation with the matching caption lines.
- Added render controls for Shorts, square, portrait, and landscape output; blurred, fit, or crop layouts; five caption styles; and optional creator watermark.
- Added SRT and WebVTT caption import to the clip editor and isolated per-clip ASS files for concurrent renders.
- Added source-relative clip trimming with caption adjustment, opening hook overlays, and one-action styling across clips from the same source recording.
- Added custom caption font, size, colors, and words-per-line controls, plus final outro ribbons.
- Added locally stored background audio with a volume control and fade-in/fade-out during rendering.
- Added optional word-highlight caption animation with per-word timing.
- Documented new editor controls and API routes.

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

