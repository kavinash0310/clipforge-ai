# API documentation

The local API defaults to `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `/docs` while the service is running.

## `GET /api/health`

Returns service name, version, and status. Does not expose local paths.

## `GET /api/overview`

Returns SQLite-derived totals for recordings, ready recordings, clips, active and failed jobs, pending approvals, completed publications, plus the six most recently updated jobs. `updated_at` is the time the snapshot was generated.

## `GET /api/system`

Returns OS and Python versions; CPU name/core count; total and available memory; free disk space; FFmpeg/ffprobe versions; NVIDIA GPU and memory if available; Ollama connectivity and configured model presence; transcription package availability; and the local data path. External tool probes use short timeouts.

## `GET /api/recordings`

Returns source paths, metadata, state, authorization confirmation, and transcript model/language when analysis is complete.

## `POST /api/recordings`

Accepts a local `path` and `authorized: true`. The service verifies that the file exists and uses a supported video extension, then queues non-destructive ffprobe inspection. Duplicate paths return `409`; absent authorization returns `400`.

## `POST /api/recordings/browse`

Opens the native Windows video picker and returns the selected path or `null` when cancelled.

## `POST /api/recordings/{recording_id}/analyze`

Queues transcription and highlight analysis for an inspected, authorized recording. Repeated requests return the existing active analysis job. The first run downloads the configured model; audio decoding, transcription, and scoring then run locally. Interrupted analysis can be retried from the start.

## `GET /api/recordings/{recording_id}/analysis`

Returns transcript segments, analysis summary, candidate scores, timestamps, reason labels, signal breakdowns, per-candidate editable captions, and render status/metadata.

## `GET /api/recordings/{recording_id}/subtitles`

Downloads the SRT generated for the recording. The resolved file must remain inside ClipForge's local data directory.

## `GET /api/clips`

Lists candidates and generated clips with clip-relative caption segments, render status, dimensions/duration when available, and a local preview URL for completed renders. Generated file paths are not exposed.

## `PATCH /api/clips/{clip_id}/subtitles`

Saves clip-relative caption edits. `segments` is an array of `{ "start": 0.0, "end": 1.5, "text": "Caption text" }` values. Segments are sorted by start time; overlaps and out-of-clip times are rejected. Editing is rejected while a render job is active and invalidates the prior preview until re-rendered.

## `POST /api/clips/{clip_id}/render`

Queues an idempotent local `render_clip` job for an authorized candidate. FFmpeg trims the source timestamps, creates a 1080 × 1920 H.264 MP4 with a blurred background behind the full gameplay frame, and burns in the saved captions. The source recording is read-only.

## `GET /api/clips/{clip_id}/preview` and `GET /api/clips/{clip_id}/download`

Stream a completed local MP4 inline for the editor or download it as an attachment. Paths are resolved under the ClipForge output directory.

## `GET /api/clips/{clip_id}/subtitles`

Downloads an SRT generated from the current saved caption edits, including edits made since the last render.

## `GET /api/jobs`

Returns the local queue with job type, stage, progress, errors, attempts, recording name, and clip ID for render jobs.

## `POST /api/jobs/{job_id}/retry`

Requeues a failed job while retries remain. Analysis starts over at audio extraction; prior results remain visible until replacement succeeds.

## `GET /api/settings`

Returns the persisted local settings. Defaults are semi-automatic mode, one concurrent job, a 75% CPU target, processing and emergency stop off, local Ollama URL, and public uploads disabled.

## `PATCH /api/settings`

Accepts any subset of:

```json
{
  "automation_mode": "semi_automatic",
  "processing_paused": false,
  "emergency_stop": false,
  "max_concurrent_jobs": 1,
  "cpu_limit_percent": 75,
  "ollama_url": "http://127.0.0.1:11434",
  "ollama_model": "qwen3.5:4b",
  "transcription_model": "base",
  "public_uploads_enabled": false
}
```

Concurrency is limited to 1–4 and the CPU target to 25–95%. Ollama must use a localhost HTTP URL. Unknown keys and invalid values are rejected. The response contains the full updated settings object.

Transcription models are `tiny`, `base`, or `small`. They run with CPU `int8`; the GPU remains available to the desktop and local LLM.

