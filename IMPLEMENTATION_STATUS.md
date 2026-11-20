# Implementation status

## Phase 1 — Foundation and dashboard

**Status:** Complete.

- [x] Local FastAPI service and loopback configuration
- [x] SQLite schema and persisted settings
- [x] Dashboard reads real counts and recent jobs from SQLite
- [x] System health reads hardware and installed tool state
- [x] Manual, semi-automatic, and automatic mode preferences; semi-automatic default
- [x] Pause and emergency-stop settings
- [x] Run backend unit checks and frontend production build
- [x] Run the app and verify UI/API integration
- [x] Verify desktop and narrow-screen layout
- [x] Update status with results

## Upcoming milestones

- Scheduling, resource controls, recovery, and end-to-end documentation

## Scope decisions

- Semi-automatic operation is the default.
- Source video files must remain untouched.
- Processing requires explicit source authorization confirmation at import.
- YouTube upload integration is active and private-only; public visibility is not exposed.

## Phase 1 verification

- `python -m unittest discover -s backend/tests -v`: 3 tests passed.
- `npm run build`: TypeScript check and Vite production build passed.
- Live API check: health, overview, settings, system probes, and frontend root returned successfully.
- Browser check: dashboard and settings rendered; viewport test found no horizontal overflow at 390 px.

## Phase 3 — Transcription and highlight detection

**Status:** Complete.

- [x] Local video import with required authorization confirmation and duplicate prevention
- [x] FFmpeg media inspection without changing or copying the original
- [x] Background jobs, progress stages, persisted errors, and bounded retries
- [x] faster-whisper local transcription with Tiny/Base/Small and CPU int8
- [x] SRT and transcript JSON output under local application data
- [x] Audio-energy analysis and FFmpeg scene-change detection
- [x] Explainable, weighted highlight ranking with context windows and overlap suppression
- [x] Dashboard queue and transcript/candidate review with SRT download
- [x] First-run model download and PyAV compatibility verified

## Phase 3 verification

- `python -m unittest discover -s backend/tests -v`: 7 tests passed.
- `npm run build`: TypeScript check and Vite production build passed.
- `python -m compileall -q backend/clipforge backend/tests`: passed.
- Synthetic spoken-video integration: inspection and analysis jobs completed; faster-whisper recognized “No way, that was a clutch. Let's go.”; candidate score 80.95; transcript/SRT and analysis API persisted successfully.
- API guards: duplicate imports returned `409`; missing authorization returned `400`; protected subtitle route returned `200` for a completed analysis.
- Transcription uses a local CPU model; PyAV below 19 is pinned because the released faster-whisper decoder is not compatible with PyAV 19.

## Phase 4 — Clip generation and editing

**Status:** Complete.

- [x] Persisted render jobs linked to reviewed candidate clips, with retry and pause recovery
- [x] Candidate-relative trim using the original source timestamps
- [x] Vertical 1080 × 1920 render with blurred backdrop and full gameplay frame
- [x] Burned-in, styled subtitles plus downloadable clip SRT
- [x] Caption text and timing correction, add/remove lines, and edit persistence
- [x] Preview and MP4 download through confined local output routes
- [x] ffprobe validates output dimensions and duration before marking it ready
- [x] Original source hash remains unchanged through render and re-render

## Phase 4 verification

- `python -m unittest discover -s backend/tests -v`: 10 tests passed.
- `npm --prefix frontend run build`: TypeScript check and Vite production build passed.
- `python -m compileall -q backend/clipforge backend/tests`: passed.
- Synthetic FFmpeg render: H.264, 1080 × 1920, 3-second output with subtitle burn-in.
- API/worker integration: queued and completed two renders; preview and SRT returned `200`; edited caption persisted through re-render; source SHA-256 was unchanged.

## Phase 5 — Local clip metadata

**Status:** Complete.

- [x] Persisted metadata records associated with candidate clips
- [x] Background metadata jobs with queue recovery, pause, retry, and progress state
- [x] Local Ollama generation using supplied game, tone, highlight signals, and caption context
- [x] Offline template fallback when the local model is unavailable or returns invalid output
- [x] Editable title, description, hashtags, and search tags in the clip editor
- [x] Metadata API routes and UI polling/save flow
- [x] Removed the inactive review-queue placeholder and its empty legacy table during database initialization
- [x] Kept source authorization confirmation on import; generated metadata makes no copyright or platform-outcome guarantees

## Phase 5 verification

- `python -m unittest discover -s backend/tests -v`: 12 tests passed.
- `npm --prefix frontend run build`: TypeScript check and Vite production build passed.
- Synthetic API/worker integration: local-model-unavailable path completed with offline template metadata; manual metadata edit persisted; the overview no longer exposes the inactive queue metric.
- Fresh and existing empty-database migration checks confirm that the obsolete empty placeholder table is removed.

## Phase 6 — YouTube connection and private uploads

**Status:** Complete.

- [x] Desktop Google OAuth with random loopback callback, PKCE S256, offline refresh, and state validation
- [x] Current-user Windows DPAPI storage for refresh tokens and resumable upload session URLs
- [x] Rendered, authorized clip upload with metadata and an explicit private privacy setting
- [x] Chunked resumable transfer, server-range recovery, pause/restart recovery, and bounded retry
- [x] Idempotent per-clip publication records and duplicate-click prevention
- [x] Google account disconnect/revoke and local credential removal
- [x] Per-video 28-day views, likes, comments, and shares via YouTube Analytics
- [x] YouTube dashboard with connection, upload progress/retry, publication links, and cached analytics

## Phase 6 verification

- `python -m unittest discover -s backend/tests -v`: 21 tests passed, including the Windows DPAPI roundtrip.
- `npm --prefix frontend run build`: TypeScript check and Vite production build passed.
- `python -m compileall -q backend/clipforge backend/tests`: passed.
- Mocked OAuth callback verified PKCE scopes, state exchange, token save, and refresh-token use; mocked upload verified forced private visibility, chunk range resume, and returned video ID/link.
- Database checks verified private status, retryable publication history, analytics persistence, duplicate blocking, and the source-authorization guard.
- Live Google upload was not run because a user-owned Desktop OAuth client file and channel consent are required.

## Next

- Phase 7: scheduling and resource controls.
- Phase 8: integration optimization and documentation completion.

