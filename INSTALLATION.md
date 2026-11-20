# Installation on Windows

## Prerequisites

- Windows 11, Python 3.12, Node.js, and npm.
- FFmpeg and ffprobe available on `PATH`.
- Optional: NVIDIA driver and Ollama with a local model.

The app is designed to keep its baseline footprint small. Model weights are installed separately by the user and are not included in the repository.

## Development setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm --prefix frontend install
```

Run the backend and frontend in separate terminals:

```powershell
$env:PYTHONPATH = "backend"
python -m uvicorn clipforge.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. For a single local endpoint, build the UI with `npm --prefix frontend run build`, then run the backend and open `http://127.0.0.1:8000`.

## Data location

Default Windows data: `%LOCALAPPDATA%\ClipForgeAI`. Set `CLIPFORGE_DATA_DIR` before starting the service to select another directory. Keep the app database, generated outputs, and credentials out of Git.

