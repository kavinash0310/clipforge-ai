# Database design

SQLite is created at `%LOCALAPPDATA%\ClipForgeAI\clipforge.db` on Windows. `CLIPFORGE_DATA_DIR` can override the base path for a portable setup or tests. WAL mode and foreign-key enforcement are enabled per connection.

## Current tables

- `app_settings`: one JSON value per setting key and its update timestamp.
- `recordings`: source path, display name, media status, duration, and an authorization confirmation flag. The original file itself is never stored in SQLite.
- `jobs`: job type, recording relationship, queued/running/paused/failed status, progress, stage, attempt count, and error text.
- `clips`: generated path, title, score, and review status.
- `approvals`: clip review state, note, and review timestamp.
- `publish_events`: platform upload identity, privacy setting, status, and errors.

The latter media tables provide the durable shape for upcoming work; Phase 1 populates settings only. Dashboard aggregates return zeros from empty tables, not fixture values.

## Relationships and indexes

`jobs.recording_id` and `clips.recording_id` point to recordings and become null when a recording record is removed. Approvals and publish events belong to clips and cascade on clip deletion. Status/time indexes support queue and activity views.

## Migration policy

Schema evolution will use explicit numbered SQL migrations before the first released database format. Phase 1 uses idempotent table creation so repeated startup does not reset user data. Tests use temporary database files.

