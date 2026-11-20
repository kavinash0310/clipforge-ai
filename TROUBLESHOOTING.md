# Troubleshooting

## Dashboard says the local API is unavailable

Confirm the backend is running on `127.0.0.1:8000`. Check `/api/health`. If the frontend is on a different port, use the Vite dev command from this repository so its `/api` proxy is active.

## FFmpeg or ffprobe is missing

Run `ffmpeg -version` and `ffprobe -version` in the same terminal used to start ClipForge. Add their installation directory to `PATH`, then restart the service.

## GPU is not detected

The diagnostics call `nvidia-smi`. Install a compatible NVIDIA driver and verify that command works. A detected GPU does not by itself prove that model libraries can use it; the processing phase will run a model-level preflight and keep a CPU fallback.

## Ollama shows offline

Start the Ollama app/service and verify its local API on `127.0.0.1:11434`. The app does not download model weights automatically. Confirm the configured model exists with `ollama list`. Metadata generation can still finish with offline templates; transcription and rendering do not depend on Ollama.

## Metadata uses an offline template

Confirm the local Ollama endpoint and configured model in Settings. If Ollama is reachable but returns invalid JSON, ClipForge also uses the template fallback. Retry generation after fixing the model, or edit and save the template draft directly. Generated metadata is a draft and cannot guarantee a platform's copyright or enforcement outcome.

## Transcription fails while decoding audio

Reinstall project dependencies with `python -m pip install -r requirements.txt`. faster-whisper 1.2.1 is incompatible with PyAV 19's changed `av.open` signature, so this project constrains PyAV below 19.

## A vertical clip render fails

Check `ffmpeg -hide_banner -encoders` for `libx264` and `ffmpeg -hide_banner -filters` for `subtitles`. Install an FFmpeg build that includes both. Open the failed render job in Media library for FFmpeg's error detail, then retry after correcting the environment or caption timing. The source recording is not modified.

## First transcription takes a while

The selected Whisper model downloads when you first analyze a recording. The queue shows its current stage. After the model is cached in app data, transcription runs locally without sending recording audio to a hosted service.

## Reset local data

Stop ClipForge and back up `%LOCALAPPDATA%\ClipForgeAI` before changing or removing it. Removing the SQLite database resets settings and app records; it does not remove original recordings.

