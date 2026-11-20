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

## Pipeline and later milestones

Analysis and rendering run as persisted jobs, not requests that hold an HTTP connection open. Each stage writes status and progress; retries are bounded and errors remain visible. Audio and scene features supply candidate events; transcript edits are stored for each candidate. Human review remains a distinct boundary before later publishing work.

