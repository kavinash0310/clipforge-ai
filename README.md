# ClipForge AI

ClipForge AI is a local-first gaming content studio for turning local recordings you own or are authorized to use into short-form clips. It can rank highlights, caption and render batches of vertical clips, generate relevant metadata, download clips individually or as a ZIP, and schedule YouTube publishing. Originals remain at their current paths. The app stores its database and local models under `%LOCALAPPDATA%\ClipForgeAI` on Windows by default. Set `CLIPFORGE_OUTPUT_DIR` to save rendered video files in a different folder.

## Current status

Phase 1 is complete: dashboard, saved settings, database foundation, and hardware checks. Phase 3 is complete: authorized local import, FFmpeg inspection, faster-whisper transcription, SRT output, and deterministic highlight ranking. Phase 4 is complete: candidate trimming, 9:16 rendering, editable captions, and local preview/download. Phase 5 is complete: local metadata generation and editing with Ollama and an offline fallback. Phase 6 is complete: desktop OAuth with PKCE, DPAPI-protected credentials, resumable private YouTube uploads, scheduled publishing, duplicate prevention, retry, and channel analytics. Phase 7 is complete: a weekly local-time processing schedule, effective worker concurrency, and per-job CPU thread budgets. Phase 8 is complete: repeatable API/worker integration coverage, a real synthetic FFmpeg render check, and documentation updates. Batch clip generation now queues rendering and metadata automatically. Dashboard totals are queried from SQLite, so a fresh database shows zero activity rather than sample metrics.

## Run in development

On Windows, after completing setup below, double-click **Start ClipForge.bat** to launch the API and frontend and open the dashboard. Double-click **Stop ClipForge.bat** to stop the instances started by that launcher. Logs are saved under `%LOCALAPPDATA%\ClipForgeAI\launcher`.

1. Install Python 3.12+, Node.js, and FFmpeg/ffprobe.
2. In PowerShell, from the repository root:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   npm --prefix frontend install
   ```

3. Start the API in one terminal:

   ```powershell
   $env:PYTHONPATH = "backend"
   python -m uvicorn clipforge.main:app --app-dir backend --host 127.0.0.1 --port 8000
   ```

4. Start the dashboard in a second terminal:

   ```powershell
   npm --prefix frontend run dev
   ```

5. Open <http://127.0.0.1:5173>. The API is at <http://127.0.0.1:8000/api/health>.

For a single local server, build the UI with `npm --prefix frontend run build`, then start the API. FastAPI serves the built frontend on port 8000.

## Verify the backend and UI

See [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) for what the automated suite exercises and which external services are mocked.

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

The current verification passed 31 backend tests, the TypeScript/Vite production build, Python compilation, a full mocked API/worker workflow, and a real synthetic FFmpeg render. A live YouTube connection requires a user-provided Desktop OAuth client file and Google account consent.

See [INSTALLATION.md](INSTALLATION.md) for setup and custom output paths, [USER_GUIDE.md](USER_GUIDE.md) for the workflow, and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for completed phases.

