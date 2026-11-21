# API documentation

The local API defaults to `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `/docs` while the service is running.

Generated MP4 and SRT files are written under `CLIPFORGE_OUTPUT_DIR` when configured, or `%LOCALAPPDATA%\ClipForgeAI\output` by default on Windows. Set the variable before starting the backend and restart the service after changing it.

## `GET /api/health`

Returns service name, version, and status. Does not expose local paths.

## Live capture routes

- `GET /api/live/status` reports whether a local stream capture is running and the number of buffered five-second segments.
- `POST /api/live/start` accepts `{"source_url":"rtmp://127.0.0.1:1935/live/clipforge"}`. Input must use RTMP, SRT, or UDP and resolve to `localhost`, `127.0.0.1`, or `::1`. A local ingest service must publish the stream to the configured endpoint.
- `POST /api/live/stop` stops capture and leaves the recent buffer available for clipping.
- `POST /api/live/clip` accepts `{"duration_seconds":30,"transcription_language":"auto","render_options":{...}}` with a duration of 15, 30, or 45 seconds. It creates a local recording and queues the standard AI analysis and render workflow.

The live capture does not download or extract public platform watch pages. The rolling buffer is bounded to the latest 36 completed segments (about three minutes).

## `GET /api/overview`

Returns SQLite-derived totals for recordings, ready recordings, clips, active and failed jobs, completed publications, plus the six most recently updated jobs. `updated_at` is the time the snapshot was generated.

## `GET /api/system`

Returns OS and Python versions; CPU name/core count; total and available memory; free disk space; FFmpeg/ffprobe versions; NVIDIA GPU and memory if available; Ollama connectivity and configured model presence; transcription package availability; and the local data path. External tool probes use short timeouts.

## `GET /api/recordings`

Returns source paths, metadata, state, authorization confirmation, and transcript model/language when analysis is complete.

## `POST /api/recordings`

Accepts a local `path`, `authorized: true`, and optional `auto_analyze`, `clip_count` (1–100), `clip_duration_seconds` (15–45), `clip_min_seconds` and `clip_max_seconds` (each 15–45, minimum must not exceed maximum), `analysis_mode` (`fast` or `deep`), `moment_mix` (`balanced`, `action`, or `dialogue`), `transcription_language`, `render_options`, and `focus_prompt` (up to 160 characters). A focus phrase gives transcript windows with matching words a small ranking boost. Deep mode includes a low-resolution visual-motion signal. When `auto_analyze` is true, inspection queues analysis automatically when the file is ready. The service verifies that the file exists and uses a supported video extension. Duplicate paths return `409`; absent authorization returns `400`.

## `POST /api/recordings/upload`

Accepts the raw video file as the request body and query parameters `filename`, `authorized=true`, `auto_analyze=true`, `clip_count=1`, `clip_duration_seconds=30`, `clip_min_seconds=15`, `clip_max_seconds=45`, `analysis_mode=fast`, and `moment_mix=balanced`, plus `transcription_language`, `render_options` (JSON-encoded), and `focus_prompt`. Supported files are MP4, M4V, MKV, MOV, AVI, MPEG, and WebM, up to 20 GB. The uploaded source is stored in `CLIPFORGE_OUTPUT_DIR\sources` (or the default output directory) before inspection.

## `POST /api/recordings/import-link`

Accepts `{"url":"https://host/video.mp4","authorized":true,"auto_analyze":true,"clip_count":1,"clip_duration_seconds":30,"clip_min_seconds":15,"clip_max_seconds":45,"analysis_mode":"fast","moment_mix":"balanced","transcription_language":"auto","render_options":{...},"focus_prompt":"ranked comeback"}`. The link must be public HTTP(S) and return a direct video file; local/private network addresses, webpages, and playlists are rejected. Redirects are checked before each request and the source is capped at 20 GB. Platform watch pages such as YouTube, Twitch, and Kick are not direct media-file URLs.

## `POST /api/recordings/browse`

Opens the native Windows video picker and returns the selected path or `null` when cancelled.

## `POST /api/music/upload`

Accepts raw MP3, M4A, AAC, WAV, OGG, FLAC, or OPUS audio with a `filename` query parameter. Files up to 200 MB are stored under the configured output folder's local `assets/music` directory and checked for a readable audio stream. The response contains an opaque `asset_id` and display name.

## `POST /api/recordings/{recording_id}/analyze`

Accepts `{"clip_count":1,"clip_duration_seconds":30,"clip_min_seconds":15,"clip_max_seconds":45,"analysis_mode":"fast","moment_mix":"balanced","transcription_language":"auto","render_options":{...},"focus_prompt":"ranked comeback"}`; count is 1–100 (default 1), durations are 15–45 seconds, analysis mode is `fast` or `deep`, and moment mix is `balanced`, `action`, or `dialogue`. The language selector includes Hinglish and the supported Whisper language codes. Deep mode adds a low-resolution visual-motion scan. A focus phrase (up to 160 characters) gives transcript windows with matching words a small ranking boost. Queues local transcription and highlight analysis for an inspected, authorized recording, then automatically queues a render in the requested format and metadata generation for each returned candidate. Repeated requests return the existing active analysis job. The requested count is a maximum because low-signal sources may yield fewer candidates.

## `GET /api/recordings/{recording_id}/analysis`

Returns transcript segments, analysis summary, candidate scores, timestamps, reason labels, signal breakdowns, per-candidate editable captions, and render status/metadata.

## `POST /api/recordings/{recording_id}/ai-parts`

Accepts `{"count":5,"focus_prompt":"clutch plays"}` with a count from 1 to 100 and an optional focus phrase of up to 160 characters. Requires a transcript and the recording's existing authorization confirmation. ClipForge asks the configured localhost Ollama model for distinct source ranges between 15 and 45 seconds, validates timestamps and source bounds, and returns `parts`, `provider`, `model_name`, and a note. If Ollama is unavailable or its ranges are invalid, ranked local highlight candidates are returned instead. The local model receives transcript text and timestamps, not source video files.

## `GET /api/recordings/{recording_id}/source-preview`

Streams the authorized local source file for in-browser scene review. The response is served from the stored recording path after the file extension and authorization state are checked.

## `POST /api/recordings/{recording_id}/clips/from-transcript`

Accepts `{"start_seconds":72.4,"clip_duration_seconds":30}` and creates a 15–45 second candidate centered near the chosen transcript timestamp, including the matching caption lines. The recording must have a transcript and authorization confirmation.

## `POST /api/recordings/{recording_id}/clips/from-range`

Accepts an exact `{"start_seconds":72.4,"end_seconds":103.8}` range and creates a transcript-backed clip with matching relative captions. The range must be between 15 and 45 seconds and fit inside the source recording.

## `POST /api/images/upload`

Accepts a raw PNG, JPEG, or WebP image body with a `filename` query parameter. Images are limited to 25 MB, checked against their file signatures, and stored under the configured output folder's local image-assets directory. The response contains an opaque `asset_id` and display name for render options.

## `POST /api/recordings/{recording_id}/clips/render`

Accepts the same render settings as the per-clip render route and applies them to all clips from that recording. Active renders are returned as existing jobs; completed clips are re-rendered when their settings differ.

## `GET /api/recordings/{recording_id}/subtitles`

Downloads the SRT generated for the recording. The resolved file must remain inside ClipForge's local data directory.

## `GET /api/clips`

Lists candidates and generated clips with clip-relative caption segments, render status, dimensions/duration when available, and a local preview URL for completed renders. Generated file paths are not exposed.

## `PATCH /api/clips/{clip_id}/subtitles`

Saves clip-relative caption edits. `segments` is an array of `{ "start": 0.0, "end": 1.5, "text": "Caption text" }` values. Segments are sorted by start time; overlaps and out-of-clip times are rejected. Editing is rejected while a render job is active and invalidates the prior preview until re-rendered.

## `POST /api/clips/{clip_id}/render`

Accepts optional render settings: `aspect_ratio` (`9:16`, `1:1`, `4:5`, `16:9`), `format_preset` (`youtube_shorts`, `tiktok`, `instagram_reels`, `instagram_portrait`, `square`, `landscape`, `custom`), `resolution` (`720`, `1080`, `2160`), `frame_rate` (`source`, `24`, `30`, `60`), and `layout` (`blur`, `blur_top`, `blur_bottom`, `fit`, `fill`, `fill_top`, `fill_bottom`, `gameplay_only`, `facecam_overlay`, `facecam_circle`, `camera_top`, `camera_bottom`, `side_by_side`, `no_facecam`). `gameplay_box` and `facecam_box` are normalized rectangles shaped like `{"x":0.1,"y":0.1,"width":0.7,"height":0.7}`; each dimension must be at least 4% of the source. Gameplay-only requires `gameplay_box`; camera layouts require `facecam_box`. For picture-in-picture, `facecam_position` accepts `top_left`, `top_right`, `bottom_left`, `bottom_right`, or `bottom_center`; `facecam_size_percent` ranges from 16 to 50. Other settings include five `caption_style` presets, `caption_animation` (`static`, `word_highlight`, `pop_in`, `pop_in_line`, `one_by_one`, `build_up`), hook/outro text and timing, social `template` values (`none`, `x_light`, `x_dark`, `tiktok_hook`, `breaking_news`), `background_mode` (`none`, `blur`, `color`, `gradient`, `image`), validated hex colors, optional uploaded background/logo asset IDs, logo position/size/opacity, credit text, frame padding and background dimming, caption font/size/colors/words-per-line, and an optional music asset with base/peak volume, riser, and fade settings. Queues a local render for an authorized candidate. FFmpeg trims the source timestamps and burns in captions/overlays; music is mixed with source audio and faded at both ends. Re-rendering uses the selected settings; the source recording is read-only.

## `PATCH /api/clips/{clip_id}/range`

Accepts source-relative `start_seconds` and `end_seconds`. The new range must fit inside the source and be 15–45 seconds long. Caption segments are trimmed to the new range and shifted to remain clip-relative.

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

