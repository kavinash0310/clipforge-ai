# Integration testing

## Run the checks

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
python -m compileall -q backend/clipforge backend/tests
npm --prefix frontend run build
```

Install the Python packages from `requirements.txt` first. The test suite uses FastAPI's `TestClient`, supplied by the pinned `httpx` dependency. The FFmpeg integration check is skipped when `ffmpeg` or `ffprobe` is unavailable.

## What the integration checks cover

- `test_workflow_integration.py` starts the actual FastAPI lifespan and background worker against a temporary database. It drives one recording through import and inspection, analysis, clip rendering, metadata generation, private-upload tracking, and analytics persistence. Media/model/Google calls are mocked, and a temporary source file confirms that pipeline steps leave the original bytes unchanged.
- `test_ffmpeg_integration.py` creates a short synthetic video, runs the real vertical renderer with subtitles, and validates the resulting 1080 × 1920 MP4 with ffprobe.
- Other unit checks cover database migrations, retries, schedule windows, CPU-thread mapping, OAuth state/PKCE, resumable upload recovery, analytics parsing, caption edits, and highlight ranking.

The full workflow test does not contact Google, download Whisper models, or require Ollama. A real YouTube upload remains a separate manual check that requires a user-provided Desktop OAuth client and completed Google account consent; the test suite never uses a real channel.

## Phase 8 optimization notes

The integration pass found and fixed a worker import-scoping bug that caused metadata jobs to fail while decoding their JSON payload. `httpx` is now an explicit project dependency so the API integration test works after a clean dependency install. Resource settings are verified as behavior: queued jobs are gated by schedule, worker slots control concurrency, CPU-intensive jobs serialize, and the CPU target limits per-job threads rather than claiming a hard Windows CPU quota.
