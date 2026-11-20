# Database design

SQLite is created at `%LOCALAPPDATA%\ClipForgeAI\clipforge.db` on Windows. `CLIPFORGE_DATA_DIR` can override the base path for a portable setup or tests. WAL mode and foreign-key enforcement are enabled per connection.

## Current tables

- `app_settings`: one JSON value per setting key and its update timestamp.
- `recordings`: source path, display name, media status, duration, and an authorization confirmation flag. The original file itself is never stored in SQLite.
- `recording_metadata`: ffprobe-derived media streams and probe timestamp.
- `recording_transcripts`: transcript language/model, output paths, timestamped segments, and generation time.
- `recording_analyses`: scene cuts, audio profile summary, scoring method/weights, and candidate count.
- `jobs`: inspection or analysis job type, recording relationship, queued/running/paused/failed status, progress, stage, attempt count, and error text.
- `clips`: candidate start/end, title, score, reason labels, signal breakdown, generated path, and review status.
- `approvals`: clip review state, note, and review timestamp.
- `publish_events`: platform upload identity, privacy setting, status, and errors.

Recording, metadata, transcript, analysis, and candidate tables are populated by the current workflow. Approval and publication tables support later work. Dashboard aggregates return zeros from an empty database, not fixture values.

## Relationships and indexes

Metadata, transcript, and analysis rows cascade with their recording. `jobs.recording_id` and `clips.recording_id` point to recordings and become null when a recording record is removed. Approvals and publish events belong to clips and cascade on clip deletion. Status/time indexes support queue and activity views.

## Migration policy

Schema evolution will use explicit numbered SQL migrations before the first released database format. Phase 1 uses idempotent table creation so repeated startup does not reset user data. Tests use temporary database files.

