# Learning roadmap

## Phase 1 learning goals

1. **React and TypeScript:** component state, API calls, derived UI state, accessible controls, and responsive CSS. Alternative: Vue or server-rendered templates. Test by checking loading, error, empty, and populated states. Interview explanation: “The UI renders persisted backend data and refreshes without owning the domain state.”
2. **FastAPI and Pydantic:** typed routes, validation, startup lifecycle, and local API boundaries. Alternative: Flask or Django. Test health, valid settings updates, and invalid payloads. Interview explanation: “The API schema rejects invalid settings before they reach storage.”
3. **SQLite:** durable settings, relational schema, foreign keys, indexes, and WAL. Alternative: PostgreSQL for multi-user/server use. Test fresh initialization and repeat initialization. Interview explanation: “SQLite avoids a separate database service for one local creator.”
4. **System diagnostics:** bounded subprocess probes and safe platform-specific hardware reads. Alternative: WMI-only or a native diagnostics module. Test with tools available and absent. Interview explanation: “Capability detection is advisory and must not silently enable unsupported acceleration.”

## Later learning goals

- FFmpeg filters and stream probing.
- Faster-whisper inference, quantization, CPU/GPU selection, and caption correction.
- Event scoring, context windows, and quality evaluation.
- Resumable job design, retries, idempotency, and resource limits.
- Resource controls, worker recovery, and publishing safeguards.

## Phase 3 engineering notes

### Speech transcription and SRT

- **What:** Local timestamped speech recognition and subtitle export.
- **Why:** Candidate review benefits from searchable context and usable captions.
- **How:** FFmpeg normalizes audio to temporary mono 16 kHz PCM. faster-whisper uses a cached model with CPU int8; recognized segments are persisted as JSON and SRT. The original source path stays untouched.
- **Technology choice:** faster-whisper uses CTranslate2 and allows quantized CPU inference. PyAV is limited to a compatible release until the released decoder is updated.
- **Alternatives:** whisper.cpp or another local speech model; CPU/GPU choice after runtime profiling.
- **How to verify:** Inspect recognized text/timestamps, download SRT, compare against a known spoken test recording, and monitor failed-job detail.
- **Interview explanation:** “I normalize arbitrary recording audio to one known shape before running a quantized local ASR model, then persist timed segments for reuse by downstream modules.”

### Candidate detection and ranking

- **What:** Finds timestamp windows with stronger audio, speech, reaction phrases, or scene transitions.
- **Why:** A long recording needs a shortlist, while explainable signals make the shortlist auditable.
- **How:** One-second RMS levels and transcript segments are combined with FFmpeg scene cuts. Weighted scoring ranks bounded context windows; overlap suppression avoids near-duplicate candidates.
- **Technology choice:** Deterministic Python scoring and FFmpeg signal extraction keep the process local and reproducible.
- **Alternatives:** Game-specific event detectors, OpenCV features, learned video highlight models, or local-LLM reranking.
- **How to verify:** Unit-test flat-signal rejection, signal contributions, context coverage, ranking, and overlap; inspect signal labels alongside a test clip.
- **Interview explanation:** “The score is not a claim of entertainment quality: it is a transparent ranking that helps a human find moments faster.”

## Phase 4 engineering notes

### Clip rendering and subtitle correction

- **What:** Trims a candidate range into a vertical MP4, burns in corrected captions, and provides a local preview and downloads.
- **Why:** Ranked timestamps need a usable short-form output, while caption edits and preview keep the creator in control before later review and publishing.
- **How:** A render job uses the candidate's source start/end, crops a scaled copy into a blurred 9:16 backdrop, keeps the complete gameplay frame in the foreground, adds a clip-relative ASS track, encodes H.264/AAC, and validates the MP4 with ffprobe. Caption JSON and SRT use timestamps relative to the new clip.
- **Technology choice:** FFmpeg filters, `libx264`, libass, SQLite job state, and a browser video element keep rendering local and easy to inspect.
- **Alternatives:** Center-crop with face/object tracking, hardware encoding after a capability check, or a standalone timeline editor.
- **How to verify:** Render a synthetic recording, compare its output duration and dimensions, review SRT and burned captions, edit a line and re-render, and compare a hash of the original file before and after.
- **Interview explanation:** “The source video is treated as immutable input. The candidate supplies source timestamps, while caption timing is relative to the trimmed clip; an edit invalidates the preview so stale media is never presented as current.”

## Phase 5 engineering notes

### Local metadata drafting

- **What:** Drafts searchable clip titles, descriptions, hashtags, and tags using the selected game/category and tone.
- **Why:** Repetitive metadata work can be reduced without sending clip context to a hosted generation service.
- **How:** A persisted clip job sends bounded context to a local Ollama endpoint and validates the returned JSON. When Ollama is unavailable or its output is invalid, deterministic templates provide an offline draft. The editor saves creator corrections in SQLite.
- **Technology choice:** Ollama's localhost API with Python's standard HTTP client, plus offline templates and SQLite persistence.
- **Alternatives:** Manual writing, hosted generation with an external data boundary, or a different local model server.
- **How to verify:** Run the metadata unit checks, force the local endpoint unavailable to check fallback, exercise API generation/edit routes, and build the frontend.
- **Interview explanation:** “Generation is an optional local aid: the persistent job and fallback make the feature useful even when the language model is missing.”

Generated copy should be fact-checked. It does not assess copyright status or assure platform outcomes.

## Phase 6 engineering notes

### YouTube OAuth, upload, and analytics

- **What:** Connects a YouTube channel, uploads a rendered clip privately, resumes interrupted uploads, prevents duplicate publication records, and reads channel metrics.
- **Why:** A local editing workflow needs a reliable handoff to the creator's channel, while default private visibility and explicit account consent keep publishing under the user's control.
- **How:** A desktop OAuth flow uses PKCE S256 and a random loopback port. The worker starts YouTube's resumable upload protocol, stores the session URI inside the encrypted credential blob, checks the server's acknowledged byte range after interruption, and resumes with the same publication event. A channel analytics report returns per-video views, likes, comments, and shares for the latest available 28-day interval.
- **Technology choice:** Standard-library HTTPS requests, Google OAuth Desktop, Windows DPAPI, SQLite jobs/publication events, YouTube Data API v3, and YouTube Analytics API.
- **Alternatives:** Google API client libraries, a browser-side upload, or hosted token storage. Local transfer and token storage avoid placing recordings or refresh tokens on a ClipForge server.
- **How to verify:** Run OAuth, DPAPI, upload-resume, analytics parsing, idempotency, and authorization checks; run a real upload only with a creator-owned client JSON and account consent.
- **Interview explanation:** “Persisting the resumable session separately from the event row lets a worker restart without creating a second video, and explicit private status avoids relying on a platform default.”

Google Desktop OAuth is a public-client flow and requires Google account consent. A Google OAuth project in external Testing status can issue refresh tokens that expire after seven days. See [Google's Desktop OAuth documentation](https://developers.google.com/identity/protocols/oauth2/native-app) and [OAuth refresh-token behavior](https://developers.google.com/identity/protocols/oauth2).

## Phase 7 engineering notes

### Weekly processing schedule and resource budget

- **What:** Adds an optional weekly local-time window for queued jobs and makes concurrency/CPU controls affect worker behavior.
- **Why:** Long analysis and FFmpeg renders should run when the creator chooses, without allowing several memory-heavy tasks to compete on a local 16 GB system.
- **How:** A deterministic schedule evaluator handles weekdays, boundary times, and windows crossing midnight. The worker gates job starts while preserving queued records. One CPU-heavy job may run at a time, with configured spare slots available for I/O work. The CPU target maps to a conservative thread count for Whisper and FFmpeg rather than claiming a hard OS utilization cap.
- **Technology choice:** SQLite settings, Python `datetime`, asyncio task slots, and FFmpeg/CTranslate2 thread parameters.
- **Alternatives:** Launching ClipForge through Windows Task Scheduler, Windows job objects for hard resource quotas, or allowing multiple high-memory jobs after profiling.
- **How to verify:** Unit-test local weekday/overnight windows, selected days, equal-time full-day windows, safe queue claiming, and thread budget limits; build the Settings page.
- **Interview explanation:** “Scheduling is a persisted queue gate, so closed windows never discard work. CPU use is approximated through bounded parallelism and per-job thread counts, with the limit clearly distinguished from an OS-enforced quota.”

