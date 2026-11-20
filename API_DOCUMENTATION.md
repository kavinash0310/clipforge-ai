# API documentation

The local API defaults to `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `/docs` while the service is running.

## `GET /api/health`

Returns service name, version, and status. Does not expose local paths.

## `GET /api/overview`

Returns SQLite-derived totals for recordings, ready recordings, clips, active and failed jobs, pending approvals, completed publications, plus the six most recently updated jobs. `updated_at` is the time the snapshot was generated.

## `GET /api/system`

Returns OS and Python versions; CPU name/core count; total and available memory; free disk space; FFmpeg/ffprobe versions; NVIDIA GPU and memory if available; Ollama connectivity and configured model presence; transcription package availability; and the local data path. External tool probes use short timeouts.

## `GET /api/settings`

Returns the persisted local settings. Defaults are semi-automatic mode, one concurrent job, a 75% CPU target, processing and emergency stop off, local Ollama URL, and public uploads disabled.

## `PATCH /api/settings`

Accepts any subset of:

```json
{
  "automation_mode": "semi_automatic",
  "processing_paused": false,
  "emergency_stop": false,
  "max_concurrent_jobs": 1,
  "cpu_limit_percent": 75,
  "ollama_url": "http://127.0.0.1:11434",
  "ollama_model": "qwen3.5:4b",
  "public_uploads_enabled": false
}
```

Concurrency is limited to 1–4 and the CPU target to 25–95%. Ollama must use a localhost HTTP URL. Unknown keys and invalid values are rejected. The response contains the full updated settings object.

