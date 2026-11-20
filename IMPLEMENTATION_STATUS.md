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

- Metadata, review queue, approval, and removal workflow
- YouTube OAuth, private upload, retry, duplicate prevention, and analytics
- Scheduling, resource controls, recovery, and end-to-end documentation

## Scope decisions

- Semi-automatic operation is the default.
- Source video files must remain untouched.
- Processing requires explicit source authorization confirmation at import.
- Public publishing remains disabled until explicit approval is implemented.

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

## Next

- Phase 5: metadata generation, review and approval workflow, and removal handling.
- Phase 6: YouTube OAuth and private uploads.
- Phase 7: scheduling and analytics.
- Phase 8: integration optimization and documentation completion.

