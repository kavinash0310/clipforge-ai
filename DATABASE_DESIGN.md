# Database design

SQLite is created at `%LOCALAPPDATA%\ClipForgeAI\clipforge.db` on Windows. `CLIPFORGE_DATA_DIR` can override the base path for a portable setup or tests. WAL mode and foreign-key enforcement are enabled per connection.

## Current tables

- `app_settings`: one JSON value per setting key and its update timestamp.
- `recordings`: source path, display name, media status, duration, and an authorization confirmation flag. The original file itself is never stored in SQLite.
- `recording_metadata`: ffprobe-derived media streams and probe timestamp.
- `recording_transcripts`: transcript language/model, output paths, timestamped segments, and generation time.
- `recording_analyses`: scene cuts, audio profile summary, scoring method/weights, and candidate count.
- `jobs`: inspection, analysis, render, metadata-generation, or YouTube-upload type; recording and optional clip relationships; JSON payload; queued/running/paused/failed status; progress, stage, attempt count, and error text.
- `clips`: candidate start/end, title, score, reason labels, signal breakdown, clip-relative editable subtitle segments, generated path, render metadata, and candidate/render status.
- `clip_metadata`: game and tone context, editable title and description, tags and hashtags, generator, status, and update time.
- `publish_events`: one YouTube publication record per clip, linked job, remote video ID, explicit privacy status, progress, status/error, cached per-video analytics, and update times. OAuth tokens and resumable session URLs are excluded from SQLite and stored in the protected local credential blob.

Recording, metadata, transcript, analysis, candidate, clip-metadata, job, and publication tables are populated by the current workflow. Dashboard aggregates return zeros from an empty database, not fixture values.

## Relationships and indexes

Metadata, transcript, and analysis rows cascade with their recording. `jobs.recording_id` and `clips.recording_id` point to recordings and become null when a recording record is removed. `jobs.clip_id` points to render candidates and becomes null when a clip record is removed. Clip metadata and publish events belong to clips and cascade on clip deletion. Status/time indexes support queue and activity views.

## Migration policy

Startup uses idempotent table creation and additive column checks so existing local records are retained. A numbered migration system will be introduced before a released database format. Tests use temporary database files.

