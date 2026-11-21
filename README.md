# ClipForge AI

ClipForge AI is a local-first gaming content studio for turning recordings you own or are authorized to use into short-form clips. Add footage by browser upload, local path, or direct public video-file link. Choose up to 100 highlights and a target duration; inspection then launches AI analysis, captioning, vertical rendering, and metadata generation. Download clips individually or as a ZIP, then upload or schedule them on YouTube. Uploaded and linked sources are copied into the configured output folder's `sources` directory; local paths stay at their current locations. Set `CLIPFORGE_OUTPUT_DIR` to choose where sources and rendered videos go.

## Current status

Phase 1 is complete: dashboard, saved settings, database foundation, and hardware checks. Phase 3 is complete: authorized recording import, FFmpeg inspection, faster-whisper transcription, SRT output, and ranked highlight analysis. Phase 4 is complete: clip editing, configurable aspect ratios/layouts, five caption looks, imported SRT/WebVTT captions, creator watermark, and local preview/download. The studio also includes transcript search and passage clipping, action/dialogue/balanced moment ranking, a searchable My Clips library with ratings and batch download, local metadata generation, YouTube scheduling, and a colorful orchid/cyan visual theme. The create workflow accepts uploaded files, local paths, and direct video-file URLs, then queues analysis automatically after inspection. YouTube/Twitch/Kick watch pages and live streams are not imported as media files. Dashboard totals are queried from SQLite, so a fresh database shows zero activity rather than sample metrics.

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

