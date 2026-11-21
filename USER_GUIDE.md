# User guide

## Phase 1 dashboard

Start the backend and UI using [INSTALLATION.md](INSTALLATION.md). The Overview page reads its totals from the local SQLite database. With a fresh install, zero counts and “No activity yet” are the expected real state.

The readiness card reports FFmpeg, NVIDIA GPU, faster-whisper, and Ollama availability. Settings shows detected CPU, memory, free disk, transcription model, and the app data path.

## Generate captioned clips

1. Open **Create clips** and choose **Upload video**, **Paste a link**, or **Local path**. Uploads and direct media-file links are copied into the configured output folder's `sources` directory; local paths are read in place. A link must return a video file directly (MP4, MKV, MOV, AVI, MPEG, or WebM). YouTube, Twitch, and Kick watch pages are not direct video files. For your own YouTube upload, download its MP4 from [YouTube Studio](https://studio.youtube.com) first.
2. Confirm that you own the recording or are authorized to use it.
3. In **02 · Make it your format**, choose 1–100 clips, minimum and maximum clip lengths (15–45 seconds), platform frame, 720p/1080p/4K resolution, and source/24/30/60 fps. Optionally enter a topic phrase to rank moments with matching transcript words higher. In **03 · Frame your moment**, choose Fast or Deep analysis, Balanced/Action/Dialogue, and a blur, fit, or crop position. Deep analysis adds a low-resolution visual-motion scan. In **04 · Give it a voice**, choose a spoken language (including Hinglish) or auto-detect, caption style, and caption motion. In **05 · Style & extras**, optionally add a hook, outro, watermark/logo, social card, background, credit line, or local music bed. Auto color balance and portrait cleanup are enabled by default; adjust their strength or turn them off there. Then choose **Make clips**. Inspection starts first, then ClipForge queues analysis automatically.
4. On first use, faster-whisper downloads the selected model into app data. Transcription and moment ranking run locally. Open **View results** to review ranked highlights, search the transcript, or choose **Clip here** to make a clip around a passage. In **AI Parts**, set how many moments to find and an optional focus phrase, then choose **Suggest parts**. ClipForge asks the configured local Ollama model to return real 15–45 second ranges. Review the timestamps, select the parts you want, and choose **Create selected clips**. If Ollama cannot provide usable ranges, ClipForge falls back to its ranked local highlights.
5. ClipForge queues renders in the selected format with captions and generates a title, description, hashtags, and relevant search tags for each result.
6. In the clip editor, review the source frame with the centered 9:16 safe-area guide. Set in/out points from the playhead with **I**, **O**, or the buttons; Space plays or pauses. Draw gameplay and facecam boxes to use gameplay-only, picture-in-picture, circular facecam, camera-above/below-gameplay, or side-by-side layouts. Save and reuse framing presets. Import SRT/ASS/WebVTT captions or edit lines; set the frame, resolution, frame rate, caption look, font, size, colors, words per line, and caption animation. Open **More visual styling** for automatic exposure/color balance, portrait cleanup, templates, background colors/images, logo placement/size/opacity, and credit text. The color grade is estimated from low-resolution samples of the selected source range. Cleanup uses mild denoise and sharpening; with a drawn facecam and camera layout, it targets that crop. Adjust strengths or disable either option. Adjust the opening hook, outro ribbon, and music bed volume/peak/riser/fade. Select **Render clip**; a changed style can be rendered again. Choose **Apply style to source clips** to re-render every candidate from that recording with the selected styling.

## Live clipping

Open **Live clipping** and enter a stream endpoint on this PC, such as `rtmp://127.0.0.1:1935/live/clipforge`. Start a local RTMP/SRT/UDP ingest service and configure OBS or another encoder to publish to that endpoint. ClipForge keeps a short rolling buffer, lets you capture the last 15, 30, or 45 seconds, then queues that file for transcription, highlight detection, captions, formatting, and metadata. The live page shows buffered seconds and lets you stop capture while retaining the recent buffer. Capture input is limited to localhost. It does not connect to public Twitch or YouTube live watch pages.

Moment scores rank audio peaks, speech, excitement cues, and scene changes. The selected moment mix changes how those signals are weighted. The requested count is a maximum; a source may produce fewer clips when moments do not meet the signal threshold. Candidates shorter than the requested duration can occur when the source itself is shorter.

## My clips

Open **My clips** to search and filter your finished edits, view previews and generated metadata, rate clips from one to five stars, open the editor for any clip, and download one MP4 or the whole rendered batch as a ZIP. YouTube takes you to the upload and schedule controls for individual clips.

## Download clips

In the YouTube page, use **Download** beside one clip or **Download all** to save a ZIP of every rendered clip. From the clip editor, review or correct caption text and download that clip's SRT. Generated MP4 files go to `CLIPFORGE_OUTPUT_DIR` when configured, or `%LOCALAPPDATA%\ClipForgeAI\output` by default (for example `D:\Clip Forge` when that is your configured folder). The original recording remains untouched.

## Schedule YouTube uploads

1. Configure a Google Desktop OAuth client and connect your channel from the YouTube page.
2. Set the start date and time. The default is the next 15 minutes; choose a later date, including a date next week, when needed.
3. Choose **Schedule** on one clip to queue it at the selected start time. Scheduled videos are uploaded as private and YouTube publishes them at the chosen time.
4. Choose **Schedule all ready** to queue every rendered clip that has finished metadata generation. The first uses the selected time; each following upload uses the selected interval (default 90 minutes).
5. Use **Upload privately** for an immediate private upload, or **Upload all privately** to queue every ready clip at once. Use **Retry upload** after a failed transfer to resume its existing YouTube upload.

Times use your computer's local timezone. The first scheduled time must be at least 15 minutes in the future. YouTube can apply channel and API upload limits, so a batch of 100 may need to be spread across multiple days.

Titles, descriptions, and tags are generated from gameplay context, using local Ollama when available and an offline template otherwise. Tags stay relevant to the clip and do not guarantee reach. Review metadata before upload. No metadata or video edit can guarantee that a platform will not make a copyright claim or issue a strike.

Only rendered clips from a local source with authorization confirmation can be uploaded. The app accepts direct public video-file URLs; it does not extract video from platform watch pages.

## Settings

- Select manual, semi-automatic, or automatic as your preferred future workflow. Semi-automatic is the default.
- Set the maximum worker slots and CPU thread budget for this machine. CPU-heavy analysis, rendering, and local metadata jobs run one at a time; lighter I/O work may share remaining slots.
- To limit when queued work starts, enable **Use a weekly schedule**, set start/end times, and select weekdays. Times use this computer's local timezone. A window that ends earlier than it starts runs overnight, assigned to its start day; equal times mean all day. Running jobs finish when the window closes, while new jobs wait.
- Pause processing to stop queued work from starting and request active jobs to pause at their next cancellation check.
- Emergency stop blocks queued work and requests active jobs to stop at their next cancellation check.

## Connect YouTube

1. In Google Cloud Console, create a project, enable **YouTube Data API v3** and **YouTube Analytics API**, then create an OAuth client with application type **Desktop app**. Google desktop apps use the system browser and PKCE for the loopback flow; see [Google's Desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).
2. Download the client JSON and place it at `%LOCALAPPDATA%\ClipForgeAI\client_secrets.json`. Keep this file private and out of source control. If the OAuth consent screen is in Testing mode, add your Google account as a test user.
3. Open ClipForge's **YouTube** page and choose **Connect YouTube**. Complete Google's account consent in the browser. Refresh tokens and resumable upload session URLs are stored in a DPAPI-protected file under app data.
4. Choose **Schedule** on one clip or **Schedule all ready** for a batch. ClipForge uploads scheduled videos as private with YouTube's `publishAt` schedule. To keep a video private, choose **Upload privately** instead.
5. Select **Refresh analytics** to load the latest available 28-day views, likes, comments, and shares for uploaded clips.

Repeated publication requests do not start a second upload for the same clip. Failed transfers can resume from the saved upload session using **Retry upload**. Google account consent is required for OAuth access. Upload sessions eventually expire; if the saved session expires, ClipForge stops and asks you to check the channel before starting another publication. Analytics use the [YouTube Analytics reports API](https://developers.google.com/youtube/analytics/reference/reports/query).

## Generate clip metadata

1. Open a candidate in Media library and scroll to **Title, description & relevant tags** in the clip editor.
2. ClipForge generates metadata automatically after analysis. You can also choose a game/category and tone, then select **Generate metadata** to refresh it.
3. ClipForge uses the configured local Ollama model when available. If Ollama is unavailable or returns invalid output, it creates a short offline template instead. No clip media is sent to a hosted metadata service.
4. Review and edit the title, description, hashtags, and search tags, then select **Save edits**. The metadata is stored locally with the clip.

Generated copy is a draft based on the clip context; verify that it accurately describes the video. Relevant tags can help describe content but are not a guarantee of reach or protection from platform claims or strikes.

