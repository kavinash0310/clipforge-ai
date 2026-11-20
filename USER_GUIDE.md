# User guide

## Phase 1 dashboard

Start the backend and UI using [INSTALLATION.md](INSTALLATION.md). The Overview page reads its totals from the local SQLite database. With a fresh install, zero counts and “No activity yet” are the expected real state.

The readiness card reports FFmpeg, NVIDIA GPU, faster-whisper, and Ollama availability. Settings shows detected CPU, memory, free disk, transcription model, and the app data path.

## Import and analyze a recording

1. Open Media library and choose a local video or paste its path.
2. Confirm that you own the recording or have permission to use it. This does not clear rights to game assets, music, or voice chat in the recording.
3. Wait for the inspection job to finish. ClipForge reads the source path and does not overwrite or copy the original.
4. Choose Analyze. On first use, faster-whisper downloads the selected model into app data. Audio extraction, transcription, scene analysis, and scoring then run locally.
5. Open View results to inspect the transcript, download the SRT, and review ranked highlight candidates and their signal reasons.

Candidate scores rank audio peaks, speech, excitement cues, and scene changes. They are review aids; they do not guarantee that a moment is entertaining or ready to publish.

## Settings

- Select manual, semi-automatic, or automatic as your preferred future workflow. Semi-automatic is the default.
- Set a conservative job concurrency and CPU target for this machine.
- Pause processing to stop new work from starting.
- Emergency stop is a separate persisted control that future workers must check before processing or publishing.

Clip extraction, vertical rendering, editing, approval, and upload are not available yet.

