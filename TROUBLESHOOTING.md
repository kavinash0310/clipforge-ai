# Troubleshooting

## Dashboard says the local API is unavailable

Confirm the backend is running on `127.0.0.1:8000`. Check `/api/health`. If the frontend is on a different port, use the Vite dev command from this repository so its `/api` proxy is active.

## FFmpeg or ffprobe is missing

Run `ffmpeg -version` and `ffprobe -version` in the same terminal used to start ClipForge. Add their installation directory to `PATH`, then restart the service.

## GPU is not detected

The diagnostics call `nvidia-smi`. Install a compatible NVIDIA driver and verify that command works. A detected GPU does not by itself prove that model libraries can use it; the processing phase will run a model-level preflight and keep a CPU fallback.

## Ollama shows offline

Start the Ollama app/service and verify its local API on `127.0.0.1:11434`. The app does not download model weights automatically. Confirm the configured model exists with `ollama list`.

## Reset local data

Stop ClipForge and back up `%LOCALAPPDATA%\ClipForgeAI` before changing or removing it. Removing the SQLite database resets settings and app records; it does not remove original recordings.

