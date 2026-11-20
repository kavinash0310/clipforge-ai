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

## Edit and render a candidate

1. Open the recording's results and select **Edit captions & render** on a candidate.
2. Correct caption text, adjust each caption's in/out time, add a line, or remove one. Times are relative to the candidate clip.
3. Save caption edits. Saving is required before a new render; edited captions make a prior preview stale until the next render completes.
4. Select **Render vertical clip**. The local queue trims the candidate, scales it to 1080 × 1920, places the full gameplay frame over a blurred background, and burns in the saved captions.
5. Preview the rendered MP4 in the editor or download the MP4 and clip SRT. Generated files are stored under `%LOCALAPPDATA%\ClipForgeAI\output`; the original recording remains untouched.

Rendering uses FFmpeg's `libx264` encoder and subtitles/libass filter. If a render fails, the queue retains the error and offers a retry. Caption edits are locked while the render is queued, running, or paused.

## Settings

- Select manual, semi-automatic, or automatic as your preferred future workflow. Semi-automatic is the default.
- Set a conservative job concurrency and CPU target for this machine.
- Pause processing to stop new work from starting.
- Emergency stop is a separate persisted control that future workers must check before processing or publishing.

Publishing and analytics are not available yet.

## Generate clip metadata

1. Open a candidate in Media library and scroll to **Title, description & tags** in the clip editor.
2. Enter a game or category and choose a tone, then select **Generate metadata**.
3. ClipForge uses the configured local Ollama model when available. If Ollama is unavailable or returns invalid output, it creates a short offline template instead. No clip media is sent to a hosted metadata service.
4. Review and edit the title, description, hashtags, and search tags, then select **Save edits**. The metadata is stored locally with the clip.

Generated copy is a draft based on the clip context; verify that it accurately describes the video. Metadata generation does not determine copyright status or guarantee protection from platform claims or strikes. The source authorization check at import remains required.

