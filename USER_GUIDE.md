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
- Set the maximum worker slots and CPU thread budget for this machine. CPU-heavy analysis, rendering, and local metadata jobs run one at a time; lighter I/O work may share remaining slots.
- To limit when queued work starts, enable **Use a weekly schedule**, set start/end times, and select weekdays. Times use this computer's local timezone. A window that ends earlier than it starts runs overnight, assigned to its start day; equal times mean all day. Running jobs finish when the window closes, while new jobs wait.
- Pause processing to stop new work from starting.
- Emergency stop is a separate persisted control that future workers must check before processing or publishing.

## Connect YouTube and upload privately

1. In Google Cloud Console, create a project, enable **YouTube Data API v3** and **YouTube Analytics API**, then create an OAuth client with application type **Desktop app**. Google desktop apps use the system browser and PKCE for the loopback flow; see [Google's Desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).
2. Download the client JSON and place it at `%LOCALAPPDATA%\ClipForgeAI\client_secrets.json`. Keep this file private and out of source control. If the OAuth consent screen is in Testing mode, add your Google account as a test user.
3. Open ClipForge's **YouTube** page and choose **Connect YouTube**. Complete Google's account consent in the browser. Refresh tokens and resumable upload session URLs are stored in a DPAPI-protected file under app data.
4. Render a clip, then choose **Upload privately**. ClipForge explicitly sets YouTube privacy to `private`; repeating the action reuses the existing publication record instead of starting another upload. Failed transfers can resume from the saved upload session using **Retry upload**.
5. Select **Refresh analytics** to load the latest available 28-day views, likes, comments, and shares for uploaded clips.

Only rendered clips with a source authorization confirmation can be uploaded. Google account consent is required for OAuth access. Upload sessions eventually expire; if the saved session expires, ClipForge stops and asks you to check the channel before starting another publication. Google's `videos.insert` method treats privacy as public if omitted, so ClipForge always sends the explicit private setting ([API reference](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)). Analytics use the [YouTube Analytics reports API](https://developers.google.com/youtube/analytics/reference/reports/query).

## Generate clip metadata

1. Open a candidate in Media library and scroll to **Title, description & tags** in the clip editor.
2. Enter a game or category and choose a tone, then select **Generate metadata**.
3. ClipForge uses the configured local Ollama model when available. If Ollama is unavailable or returns invalid output, it creates a short offline template instead. No clip media is sent to a hosted metadata service.
4. Review and edit the title, description, hashtags, and search tags, then select **Save edits**. The metadata is stored locally with the clip.

Generated copy is a draft based on the clip context; verify that it accurately describes the video. Metadata generation does not determine copyright status or guarantee protection from platform claims or strikes. The source authorization check at import remains required.

