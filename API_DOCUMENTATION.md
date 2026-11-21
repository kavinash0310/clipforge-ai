# API documentation

The local API defaults to `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `/docs` while the service is running.

Generated MP4 and SRT files are written under `CLIPFORGE_OUTPUT_DIR` when configured, or `%LOCALAPPDATA%\ClipForgeAI\output` by default on Windows. Set the variable before starting the backend and restart the service after changing it.

## `GET /api/health`

Returns service name, version, and status. Does not expose local paths.

## `GET /api/overview`

Returns SQLite-derived totals for recordings, ready recordings, clips, active and failed jobs, completed publications, plus the six most recently updated jobs. `updated_at` is the time the snapshot was generated.

## `GET /api/system`

Returns OS and Python versions; CPU name/core count; total and available memory; free disk space; FFmpeg/ffprobe versions; NVIDIA GPU and memory if available; Ollama connectivity and configured model presence; transcription package availability; and the local data path. External tool probes use short timeouts.

## `GET /api/recordings`

Returns source paths, metadata, state, authorization confirmation, and transcript model/language when analysis is complete.

## `POST /api/recordings`

Accepts a local `path`, `authorized: true`, and optional `auto_analyze`, `clip_count` (1–100), `clip_duration_seconds` (15–45), and `moment_mix` (`balanced`, `action`, or `dialogue`). When `auto_analyze` is true, inspection queues analysis automatically when the file is ready. The service verifies that the file exists and uses a supported video extension. Duplicate paths return `409`; absent authorization returns `400`.

## `POST /api/recordings/upload`

Accepts the raw video file as the request body and query parameters `filename`, `authorized=true`, `auto_analyze=true`, `clip_count=1`, `clip_duration_seconds=30`, and `moment_mix=balanced`. Supported files are MP4, M4V, MKV, MOV, AVI, MPEG, and WebM, up to 20 GB. The uploaded source is stored in `CLIPFORGE_OUTPUT_DIR\sources` (or the default output directory) before inspection.

## `POST /api/recordings/import-link`

Accepts `{"url":"https://host/video.mp4","authorized":true,"auto_analyze":true,"clip_count":1,"clip_duration_seconds":30,"moment_mix":"balanced"}`. The link must be public HTTP(S) and return a direct video file; local/private network addresses, webpages, and playlists are rejected. Redirects are checked before each request and the source is capped at 20 GB. Platform watch pages such as YouTube, Twitch, and Kick are not direct media-file URLs.

## `POST /api/recordings/browse`

Opens the native Windows video picker and returns the selected path or `null` when cancelled.

## `POST /api/recordings/{recording_id}/analyze`

Accepts `{"clip_count":1,"clip_duration_seconds":30,"moment_mix":"balanced"}`; count is 1–100 (default 1), duration is 15–45 seconds (default 30), and moment mix is `balanced`, `action`, or `dialogue`. Queues local transcription and highlight analysis for an inspected, authorized recording, then automatically queues a vertical render and metadata generation for each returned candidate. Repeated requests return the existing active analysis job. The requested count is a maximum because low-signal sources may yield fewer candidates.

## `GET /api/recordings/{recording_id}/analysis`

Returns transcript segments, analysis summary, candidate scores, timestamps, reason labels, signal breakdowns, per-candidate editable captions, and render status/metadata.

## `POST /api/recordings/{recording_id}/clips/from-transcript`

Accepts `{"start_seconds":72.4,"clip_duration_seconds":30}` and creates a 15–45 second candidate centered near the chosen transcript timestamp, including the matching caption lines. The recording must have a transcript and authorization confirmation.

## `GET /api/recordings/{recording_id}/subtitles`

Downloads the SRT generated for the recording. The resolved file must remain inside ClipForge's local data directory.

## `GET /api/clips`

Lists candidates and generated clips with clip-relative caption segments, render status, dimensions/duration when available, and a local preview URL for completed renders. Generated file paths are not exposed.

## `PATCH /api/clips/{clip_id}/subtitles`

Saves clip-relative caption edits. `segments` is an array of `{ "start": 0.0, "end": 1.5, "text": "Caption text" }` values. Segments are sorted by start time; overlaps and out-of-clip times are rejected. Editing is rejected while a render job is active and invalidates the prior preview until re-rendered.

## `POST /api/clips/{clip_id}/render`

Accepts optional render settings: `aspect_ratio` (`9:16`, `1:1`, `4:5`, `16:9`), `layout` (`blur`, `fit`, `fill`), `caption_style` (`neon`, `impact`, `clean`, `hormozi`, `mrbeast`), and `watermark_text` (up to 60 characters). Queues a local render for an authorized candidate. FFmpeg trims the source timestamps and burns in the saved captions. Re-rendering uses the selected settings; the source recording is read-only.

## `PATCH /api/clips/{clip_id}/rating`

Accepts `{"rating":4}` to save a one-to-five star rating in the local clip library.

## `GET /api/clips/{clip_id}/preview` and `GET /api/clips/{clip_id}/download`

Stream a completed local MP4 inline for the editor or download it as an attachment. Paths are resolved under the ClipForge output directory.

## `POST /api/clips/download-all`

Accepts `{"clip_ids":["..."]}` for 1–500 unique rendered clip IDs and returns `clipforge-clips.zip`. The bundle includes only rendered files inside the configured output directory.

## `GET /api/clips/{clip_id}/subtitles`

Downloads an SRT generated from the current saved caption edits, including edits made since the last render.

## Clip metadata routes

- `GET /api/clips/{clip_id}/metadata` returns the saved game/category, tone, title, description, hashtags, search tags, generator, status, and any generation note.
- `POST /api/clips/{clip_id}/metadata/generate` accepts `{"game_name":"Valorant","tone":"hype"}` and queues a `generate_metadata` job. Tone values are `hype`, `funny`, `clean`, or `competitive`. The worker calls the configured local Ollama endpoint, then falls back to offline templates if the model is unavailable or returns invalid output.
- `PATCH /api/clips/{clip_id}/metadata` saves edited metadata. The request fields are `game_name`, `tone`, `title`, `description`, `hashtags`, and `tags`.

Generated metadata is a draft and must be checked for accuracy. Tags are kept relevant to the clip; they do not guarantee reach.

## YouTube routes

- `GET /api/youtube/status` reports whether the Desktop OAuth JSON is configured, whether a channel is connected, and any local credential-store error.
- `POST /api/youtube/connect` starts a system-browser Google OAuth flow and returns `authorization_url`. It uses PKCE, state validation, and a temporary loopback callback bound to `127.0.0.1`.
- `DELETE /api/youtube/connect` revokes the saved token when reachable and removes the local DPAPI credential blob. Publication history remains in SQLite.
- `GET /api/youtube/publications` lists publication status, progress, scheduled times, video links, failures, and cached analytics.
- `POST /api/clips/{clip_id}/youtube-upload` queues one resumable upload for a completed, authorized clip. Privacy is always `private`. Repeated requests return the existing publication; a failed upload must use `POST /api/jobs/{job_id}/retry` to resume the existing record/session.
- `POST /api/youtube/schedule` accepts `{"clip_ids":["..."],"start_at":"2026-12-01T09:00:00+05:30","interval_minutes":90}` for 1–100 unique rendered clips with completed metadata. `start_at` must include a timezone and be at least 15 minutes in the future. Each following clip is offset by `interval_minutes` (15–4320, default 90). Videos are uploaded as private with YouTube's `status.publishAt`, then published by YouTube at the scheduled time.
- `POST /api/youtube/analytics/refresh` requests the latest available 28-day views, likes, comments, and shares for completed YouTube publications, saves the per-video result, and returns the updated publication list.

Place a Google Desktop OAuth client JSON at `%LOCALAPPDATA%\ClipForgeAI\client_secrets.json` (or in the configured `CLIPFORGE_DATA_DIR`). Enable YouTube Data API v3 and YouTube Analytics API in its project. The OAuth client file and OAuth grants are user-managed; the app does not include a shared client credential. Google consent is required for the account to grant channel scopes. Scheduled videos use YouTube's private-until-publish scheduling. ClipForge accepts direct video-file URLs but does not extract media from YouTube watch pages. See the [Desktop OAuth flow](https://developers.google.com/identity/protocols/oauth2/native-app), [video insert API](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), and [Analytics reports API](https://developers.google.com/youtube/analytics/reference/reports/query).

## `GET /api/jobs`

Returns the local queue with job type, stage, progress, errors, attempts, recording name, and clip ID for clip render, metadata, and YouTube upload jobs.

## `POST /api/jobs/{job_id}/retry`

Requeues a failed job while retries remain. Analysis starts over at audio extraction; interrupted YouTube uploads reuse the protected resumable session and publication record.

## `GET /api/settings`

Returns persisted local settings. The schedule is disabled by default, so queued jobs may start at any time. The 75% CPU setting becomes a conservative per-job thread budget; it is not a hard operating-system CPU cap.

## `PATCH /api/settings`

Accepts any subset of:

```json
{
  "automation_mode": "semi_automatic",
  "processing_paused": false,
  "emergency_stop": false,
  "max_concurrent_jobs": 1,
  "cpu_limit_percent": 75,
  "processing_schedule_enabled": false,
  "processing_schedule_start": "22:00",
  "processing_schedule_end": "06:00",
  "processing_schedule_days": [0, 1, 2, 3, 4, 5, 6],
  "ollama_url": "http://127.0.0.1:11434",
  "ollama_model": "qwen3.5:4b",
  "transcription_model": "base",
  "public_uploads_enabled": false
}
```

Concurrency is limited to 1–4 and the CPU target to 25–95%. At most one CPU-intensive analysis, render, or local metadata job runs at once; I/O jobs may use remaining worker slots. CPU percentage maps to a per-job thread count for transcription and FFmpeg, and does not guarantee an exact OS-level utilization percentage.

The schedule accepts 24-hour `HH:MM` start/end values and Monday-based weekday indexes (`0` Monday through `6` Sunday). It uses the computer's local timezone. Windows crossing midnight belong to the day on which they start; equal start/end times mean the full selected day. At least one unique day is required. Closing the window delays queued work but lets an already-running job finish; pause and emergency stop retain their existing immediate behavior.

Ollama must use a localhost HTTP URL. Unknown keys and invalid values are rejected. The response contains the full updated settings object.

Transcription models are `tiny`, `base`, or `small`. They run with CPU `int8`; the GPU remains available to the desktop and local LLM.

