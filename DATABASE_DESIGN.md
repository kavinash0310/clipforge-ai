# Database design

SQLite is created at `%LOCALAPPDATA%\ClipForgeAI\clipforge.db` on Windows. `CLIPFORGE_DATA_DIR` can override the base path for a portable setup or tests. WAL mode and foreign-key enforcement are enabled per connection.

## Current tables

- `app_settings`: one JSON value per setting key and its update timestamp.
- `recordings`: source path, display name, media status, duration, and an authorization confirmation flag. The original file itself is never stored in SQLite.
- `recording_metadata`: ffprobe-derived media streams and probe timestamp.
- `recording_transcripts`: transcript language/model, output paths, timestamped segments, and generation time.
- `recording_analyses`: scene cuts, audio profile summary, scoring method/weights, and candidate count.
- `jobs`: inspection, analysis, or render job type, recording and optional clip relationships, queued/running/paused/failed status, progress, stage, attempt count, and error text.
- `clips`: candidate start/end, title, score, reason labels, signal breakdown, clip-relative editable subtitle segments, generated path, render metadata, and candidate/render status.
- `approvals`: clip review state, note, and review timestamp.
- `publish_events`: platform upload identity, privacy setting, status, and errors.

Recording, metadata, transcript, analysis, and candidate tables are populated by the current workflow. Approval and publication tables support later work. Dashboard aggregates return zeros from an empty database, not fixture values.

## Relationships and indexes

Metadata, transcript, and analysis rows cascade with their recording. `jobs.recording_id` and `clips.recording_id` point to recordings and become null when a recording record is removed. `jobs.clip_id` points to render candidates and becomes null when a clip record is removed. Approvals and publish events belong to clips and cascade on clip deletion. Status/time indexes support queue and activity views.

## Migration policy

Startup uses idempotent table creation and additive column checks so existing local records are retained. A numbered migration system will be introduced before a released database format. Tests use temporary database files.

