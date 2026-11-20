# System design

## Runtime

The UI is a Vite-built React application. During development, Vite proxies `/api` to FastAPI. In a production build, FastAPI serves the static bundle and the API from the same loopback origin. The API starts SQLite and creates the local data directories during application startup.

## Platform modules

### Dashboard

- **What / why:** Summarizes real recording, clip, review, upload, and job state so the creator can see the current workload.
- **How:** Calls `/api/overview`, `/api/system`, and `/api/settings`; refreshes on a short interval; displays an honest empty state when there is no data.
- **Technology:** React, TypeScript, and Lucide icons.
- **Alternatives:** A server-rendered HTML page or another SPA framework.
- **Verification:** Build the UI, start the API, and check that all displayed totals match database queries.
- **Interview explanation:** “The UI is a projection of persisted local state; it contains no fabricated production metrics.”

### Local API and settings

- **What / why:** Provides a typed boundary for the UI and persists automation/resource controls.
- **How:** FastAPI validates requests; SQLite stores setting values as JSON; the service only binds to `127.0.0.1`.
- **Technology:** FastAPI, Pydantic, and SQLite's standard library driver.
- **Alternatives:** Flask, Django REST Framework, or a desktop IPC layer.
- **Verification:** Exercise health, overview, settings read/write, and invalid-setting responses.
- **Interview explanation:** “A small modular monolith keeps local deployment simple while retaining clear API boundaries.”

### System inspection

- **What / why:** Reports whether the machine can run media and model tools before configuration.
- **How:** Reads Python/OS/CPU/RAM/disk data and probes FFmpeg, NVIDIA SMI, and the local Ollama API with bounded timeouts.
- **Technology:** `psutil`, Windows registry access where available, and subprocess calls to installed tools.
- **Alternatives:** WMI/CIM only, platform-specific native APIs, or a separate diagnostics utility.
- **Verification:** Compare reported hardware and tool versions with Windows settings and direct command output.
- **Interview explanation:** “Hardware selection is based on runtime capabilities, with safe failure when a tool is absent.”

### Local transcription and subtitles

- **What / why:** Converts speech in a recording to timestamped text and an SRT file for caption correction.
- **How:** FFmpeg extracts a temporary mono 16 kHz WAV. faster-whisper loads Tiny, Base, or Small with CPU `int8`, iterates timestamped segments, and writes transcript JSON/SRT atomically per recording. Temporary audio is removed when the job ends.
- **Technology:** faster-whisper/CTranslate2 and FFmpeg. PyAV is constrained below version 19 while the currently released faster-whisper decoder uses the older `av.open` signature.
- **Alternatives:** whisper.cpp, another local ASR runtime, or SRT-only caption export.
- **Verification:** Run a spoken recording through the queue; check recognized text, segment timings, SRT output, and the analysis API response.
- **Interview explanation:** “The original media remains read-only. A temporary standardized audio stream makes inference predictable; transcript artifacts and progress are persisted separately.”

### Deterministic highlight ranking

- **What / why:** Surfaces promising timestamp ranges without depending on an LLM to inspect every moment.
- **How:** One-second RMS audio buckets, transcript speech density and excitement cues, and FFmpeg scene cuts feed a weighted score. Context windows surround activity; highly overlapping candidates are suppressed; the best candidates include signal breakdowns and reason labels.
- **Technology:** Python signal summaries, FFmpeg scene selection, SQLite candidate rows.
- **Alternatives:** OpenCV visual features, a learned highlight model, game-specific event detectors, or local-LLM context as an additional signal.
- **Verification:** Unit checks cover context, score ordering, overlap selection, flat-signal rejection, and an end-to-end synthetic spoken recording.
- **Interview explanation:** “The ranking is explainable and repeatable; transcript excerpts and signal reasons show why a moment ranked highly, while a person decides whether it is entertaining.”

## Phase 4: clip generation and caption editing

### Clip generation and caption editing

- **What / why:** Produces a short vertical MP4 from a ranked candidate and lets the creator correct caption wording and timing before burning it into the video.
- **How:** A persisted render job references one candidate. The worker seeks and trims the source timestamps, draws the full gameplay frame over a blurred 1080 × 1920 background, burns in an ASS subtitle track with FFmpeg/libass, encodes H.264/AAC, probes the result, and atomically replaces the generated clip. Caption edits are stored as clip-relative segments; an edit invalidates the previous preview until another render succeeds.
- **Technology:** FFmpeg `libx264`, subtitles/libass, SQLite job state, SRT for portable caption output, and an HTML video player for local preview.
- **Alternatives:** Center crop with subject tracking, GPU encoding after an encoder preflight, or a timeline editor for frame-level manual cuts.
- **Verification:** Render a short synthetic video; verify its duration, H.264 codec, 1080 × 1920 dimensions, subtitle burn-in/SRT content, preview and download responses, caption edit/rerender behavior, and original-file hash.
- **Interview explanation:** “The editor keeps source timestamps separate from clip-relative captions. A worker owns rendering, writes a new output, validates it with ffprobe, then publishes the preview only after successful validation.”

## Phase 5: local clip metadata

### Metadata drafting and editing

- **What / why:** Creates an editable title, description, hashtags, and search tags for a selected candidate, reducing repetitive copywriting while keeping the text reviewable.
- **How:** The API stores game/category and tone inputs, queues a persisted job tied to the clip, and polls the configured localhost Ollama `/api/generate` endpoint. The prompt contains bounded candidate context and requires a JSON result. Invalid or unavailable model output falls back to deterministic offline templates. Values are normalized and length-limited before they are saved; the UI can edit and save the draft.
- **Technology:** Python `urllib`, local Ollama, SQLite, FastAPI, React, and a deterministic template fallback.
- **Alternatives:** Manual copywriting only, a hosted language model, or platform-specific metadata tools. Hosted generation was not selected so clip context stays local.
- **Verification:** Unit checks cover offline fallback and local-model JSON handling; API/worker integration covers job completion and manual edits; the production frontend build checks the editor UI.
- **Interview explanation:** “The metadata feature keeps generation local and replaceable: a local model improves phrasing, but a deterministic fallback means the workflow still completes without model availability.”

Generated metadata is a draft. It does not verify ownership or licensing and cannot guarantee that a platform will avoid claims or strikes.

## Phase 6: YouTube upload and channel analytics

### OAuth connection and private uploads

- **What / why:** Connects a creator's YouTube channel, uploads rendered clips, tracks publication state, resumes interrupted transfers, and reports channel performance without storing account tokens in SQLite.
- **How:** The UI asks the API to start a Google Desktop OAuth flow. The API creates a random loopback listener, PKCE S256 verifier/challenge, and CSRF state, opens authorization in the system browser, and accepts the callback on `127.0.0.1`. Refresh tokens and resumable session URLs are DPAPI-protected for the current Windows user. Upload jobs are persisted; a resumable session is encrypted before transfer starts; a retry queries the remote byte range and continues from that offset. The insert body explicitly sets `privacyStatus=private`. A serialized database transaction creates one publication event per clip, preventing duplicate upload jobs.
- **Technology:** Google OAuth 2.0 desktop flow, PKCE, Windows DPAPI via `ctypes`, FastAPI, SQLite, YouTube Data API resumable upload, and YouTube Analytics reports API.
- **Alternatives:** Google API client libraries, browser-only uploads, or hosted backend token storage. This local Windows app keeps credentials and video bytes on the creator's PC and implements the small resumable request protocol directly so its session URL can be persisted securely.
- **Verification:** Unit checks cover PKCE/state callback, refresh tokens, DPAPI encryption roundtrip, forced private status, resumable range recovery, per-video analytics, source authorization, and per-clip idempotency. Live API calls require a creator-provided Google Desktop OAuth client and are kept out of automated checks.
- **Interview explanation:** “The upload path is resumable and private by construction. A single durable publication record owns the retry lifecycle, while the remote session URL is protected by the current user's Windows account.”

The Google OAuth Desktop client is a public client; its client JSON is user-provided local configuration and cannot be treated as a confidential secret. User consent is part of Google's account authorization flow. OAuth apps left in external Testing mode may receive refresh tokens that expire after seven days; see [Google's OAuth overview](https://developers.google.com/identity/protocols/oauth2).

## Pipeline and later milestones

Analysis, rendering, metadata generation, and YouTube transfers run as persisted jobs, not requests that hold an HTTP connection open. Each stage writes status and progress; retries are bounded and errors remain visible. Audio and scene features supply candidate events; transcript edits, metadata drafts, and publication events are stored with each candidate. YouTube upload privacy is explicitly private, and OAuth tokens plus upload-session URLs stay in the protected local credential blob.

