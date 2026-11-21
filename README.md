# ClipForge AI

ClipForge AI is a local-first gaming content studio for turning recordings you own or are authorized to use into short-form clips. Add footage by browser upload, local path, or direct public video-file link. Choose up to 100 highlights and a target duration; inspection then launches AI analysis, captioning, vertical rendering, and metadata generation. Download clips individually or as a ZIP, then upload or schedule them on YouTube. Uploaded and linked sources are copied into the configured output folder's `sources` directory; local paths stay at their current locations. Set `CLIPFORGE_OUTPUT_DIR` to choose where sources and rendered videos go.

## Current status

The studio includes a dashboard, searchable My Clips library, local transcription and highlight ranking, clip editing, YouTube metadata and scheduling, batch downloads/uploads, and a colorful orchid/pink/cyan UI. The Create workflow includes platform presets, variable 15–45 second clip lengths, 720p/1080p/4K output, source or 24/30/60 fps, crop/blur/fit positioning, 52 speech languages plus Hinglish, caption styles and motion, hooks, outro text, social cards, custom backgrounds and logos, credits, and an optional local music bed. Fast analysis ranks audio, speech, excitement, and scene signals; Deep analysis also scans low-resolution visual motion. Saved clip ratings can gradually tune ranking weights. The transcript panel can ask the configured local Ollama model to suggest multiple parts, then create selected source ranges as editable clips; if Ollama is unavailable, existing local highlight scores are used. The editor includes draw-to-frame gameplay and facecam layouts, saved framing presets, caption import/correction, and the same visual style controls as clip creation. Live clipping captures a rolling buffer from a local RTMP, SRT, or UDP stream and queues clips for the same workflow. Public platform watch-page extraction, public chat scraping, and unattended creator monitoring are not supported. Dashboard totals come from SQLite, so a fresh database shows zero activity instead of sample metrics.

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

Earlier project verification passed the existing backend suite, production UI build, mocked API/worker flow, and a synthetic FFmpeg render. The current feature additions have not been run through those checks. A YouTube connection requires a user-provided Desktop OAuth client file and Google account consent.

See [INSTALLATION.md](INSTALLATION.md) for setup and custom output paths, [USER_GUIDE.md](USER_GUIDE.md) for the workflow, and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for completed phases.

