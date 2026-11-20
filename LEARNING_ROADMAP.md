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

## Phase 3 engineering notes

### Speech transcription and SRT

- **What:** Local timestamped speech recognition and subtitle export.
- **Why:** Candidate review benefits from searchable context and usable captions.
- **How:** FFmpeg normalizes audio to temporary mono 16 kHz PCM. faster-whisper uses a cached model with CPU int8; recognized segments are persisted as JSON and SRT. The original source path stays untouched.
- **Technology choice:** faster-whisper uses CTranslate2 and allows quantized CPU inference. PyAV is limited to a compatible release until the released decoder is updated.
- **Alternatives:** whisper.cpp or another local speech model; CPU/GPU choice after runtime profiling.
- **How to verify:** Inspect recognized text/timestamps, download SRT, compare against a known spoken test recording, and monitor failed-job detail.
- **Interview explanation:** “I normalize arbitrary recording audio to one known shape before running a quantized local ASR model, then persist timed segments for reuse by downstream modules.”

### Candidate detection and ranking

- **What:** Finds timestamp windows with stronger audio, speech, reaction phrases, or scene transitions.
- **Why:** A long recording needs a shortlist, while explainable signals make the shortlist auditable.
- **How:** One-second RMS levels and transcript segments are combined with FFmpeg scene cuts. Weighted scoring ranks bounded context windows; overlap suppression avoids near-duplicate candidates.
- **Technology choice:** Deterministic Python scoring and FFmpeg signal extraction keep the process local and reproducible.
- **Alternatives:** Game-specific event detectors, OpenCV features, learned video highlight models, or local-LLM reranking.
- **How to verify:** Unit-test flat-signal rejection, signal contributions, context coverage, ranking, and overlap; inspect signal labels alongside a test clip.
- **Interview explanation:** “The score is not a claim of entertainment quality: it is a transparent ranking that helps a human find moments faster.”

