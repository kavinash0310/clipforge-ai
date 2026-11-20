# ClipForge AI

ClipForge AI is a local-first gaming content studio for turning recordings you own or are authorized to use into reviewed short-form clips. Originals remain at their current paths. The app stores its database and generated outputs under `%LOCALAPPDATA%\ClipForgeAI` on Windows.

## Current status

Phase 1 is complete: the dashboard, local settings, database foundation, and hardware/tool health checks are implemented and verified. Video processing and publishing are still upcoming. Dashboard totals are queried from SQLite; an empty database therefore shows zero activity rather than sample metrics.

## Run in development

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

## Verify the foundation

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

The current verification run passed all three database checks, the TypeScript/Vite production build, and live API/static-dashboard integration.

See [INSTALLATION.md](INSTALLATION.md), [USER_GUIDE.md](USER_GUIDE.md), and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for current behavior and the next milestones.

