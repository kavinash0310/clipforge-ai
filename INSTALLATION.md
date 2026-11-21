# Installation on Windows

## Prerequisites

- Windows 11, Python 3.12, Node.js, and npm.
- FFmpeg and ffprobe available on `PATH`. The FFmpeg build must include `libx264` and the `subtitles` filter (libass) for vertical clip rendering.
- Optional: NVIDIA driver and Ollama with a local model.

The app is designed to keep its baseline footprint small. Model weights are installed separately by the user and are not included in the repository.

## Development setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm --prefix frontend install
```

After setup, double-click `Start ClipForge.bat` in the project folder. It starts the backend and frontend in the background, then opens `http://127.0.0.1:5173` in your browser. Double-click `Stop ClipForge.bat` to stop those instances. Logs are in `%LOCALAPPDATA%\ClipForgeAI\launcher`. The launcher saves generated videos to `D:\Clip Forge` as previously configured.

Run the backend and frontend in separate terminals:

```powershell
$env:PYTHONPATH = "backend"
python -m uvicorn clipforge.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. For a single local endpoint, build the UI with `npm --prefix frontend run build`, then run the backend and open `http://127.0.0.1:8000`.

The first analysis downloads the selected faster-whisper model into the app data directory. Transcription uses CPU int8. The dependency file constrains PyAV below version 19 because the released faster-whisper decoder still passes an argument removed in PyAV 19.

To check render support, run `ffmpeg -hide_banner -encoders` and confirm `libx264`, then run `ffmpeg -hide_banner -filters` and confirm `subtitles`.

## Data and output locations

Default Windows app data: `%LOCALAPPDATA%\ClipForgeAI`; generated video output defaults to `%LOCALAPPDATA%\ClipForgeAI\output`. Set `CLIPFORGE_DATA_DIR` before starting the service to move the database, models, and OAuth credentials. Set `CLIPFORGE_OUTPUT_DIR` to choose a separate folder for generated videos. For example, in the backend terminal run `$env:CLIPFORGE_OUTPUT_DIR = "D:\Clip Forge"` before launching Uvicorn. Restart the backend after changing either variable. Keep the app database, generated outputs, and credentials out of Git.

