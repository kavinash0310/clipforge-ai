# Learning roadmap

## Phase 1 learning goals

1. **React and TypeScript:** component state, API calls, derived UI state, accessible controls, and responsive CSS. Alternative: Vue or server-rendered templates. Test by checking loading, error, empty, and populated states. Interview explanation: “The UI renders persisted backend data and refreshes without owning the domain state.”
2. **FastAPI and Pydantic:** typed routes, validation, startup lifecycle, and local API boundaries. Alternative: Flask or Django. Test health, valid settings updates, and invalid payloads. Interview explanation: “The API schema rejects invalid settings before they reach storage.”
3. **SQLite:** durable settings, relational schema, foreign keys, indexes, and WAL. Alternative: PostgreSQL for multi-user/server use. Test fresh initialization and repeat initialization. Interview explanation: “SQLite avoids a separate database service for one local creator.”
4. **System diagnostics:** bounded subprocess probes and safe platform-specific hardware reads. Alternative: WMI-only or a native diagnostics module. Test with tools available and absent. Interview explanation: “Capability detection is advisory and must not silently enable unsupported acceleration.”

## Later learning goals

- FFmpeg filters and stream probing.
- Faster-whisper inference, quantization, CPU/GPU selection, and caption correction.
- Event scoring, context windows, and quality evaluation.
- Resumable job design, retries, idempotency, and resource limits.
- OAuth consent, resumable YouTube upload, quota-aware analytics, and privacy defaults.

