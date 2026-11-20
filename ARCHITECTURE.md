# Architecture

## Goals

- Keep media and metadata on the creator's machine by default.
- Use one Python service and one local UI, with SQLite for durable state.
- Keep processing modules replaceable and run long work as resumable jobs.
- Never overwrite source recordings; write generated media separately.
- Require a person to approve publication unless the creator explicitly changes policy.

## Local application structure

```mermaid
flowchart TD
    UI[React + TypeScript dashboard\nlocalhost] <-->|REST| API[FastAPI local service]
    API --> DB[(SQLite\nsettings, jobs, media state)]
    API --> Worker[Persisted job worker]
    Worker --> FFmpeg[FFmpeg + libass\nclip render]
    FFmpeg --> Preview[Local MP4 + SRT preview]
    API --> SYS[System probes\nPython, CPU, RAM, disk, GPU, FFmpeg, Ollama]
    API --> FS[Local app data\nSQLite and generated outputs]
    SRC[Original recording paths] -. referenced, not copied .-> API
```

## Processing path

```mermaid
flowchart LR
    Import[Local recording + authorization confirmation] --> Probe[ffprobe metadata]
    Probe --> Extract[FFmpeg mono 16 kHz audio]
    Extract --> ASR[faster-whisper CPU int8 transcript]
    Extract --> Signals[Audio energy signals]
    Probe --> Scenes[FFmpeg scene-change signals]
    ASR --> Score[Deterministic weighted ranking]
    Signals --> Score
    Scenes --> Score
    Score --> Review[Ranked candidate review]
    Review --> Render[FFmpeg clip and vertical render]
    Render --> Preview[Preview and caption correction]
    Preview --> Approval[Human review and correction]
    Approval --> PublishApproval[Explicit publish approval]
    PublishApproval --> YouTube[YouTube OAuth upload]
```

## Technology choices

| Area | Choice | Reason | Alternatives |
| --- | --- | --- | --- |
| API | FastAPI on Python 3.12 | Small typed API; Python media and AI ecosystem | Flask, Django |
| UI | React, TypeScript, Vite | Responsive interactive dashboard with type checking | Vue, Svelte, server-rendered templates |
| State | SQLite | No separate database service; durable local state | DuckDB for analytics, PostgreSQL for multi-user deployments |
| Media | FFmpeg and ffprobe | Mature probing, transcoding, filtering, and subtitle tools | GStreamer, OpenCV for selected vision tasks |
| Transcription | faster-whisper | Local Whisper inference with quantized CPU/GPU modes | whisper.cpp, upstream Whisper |
| Context and metadata | Ollama local API | No paid hosted LLM required | Rule templates, another local model runner |

## Operating boundaries

The service binds to loopback. The browser UI uses same-origin API paths in a production build and a narrow localhost proxy in development. SQLite contains application state, not video bytes. The output directory is separate from source directories. Render jobs reference a reviewed candidate and its clip-relative caption edits; FFmpeg writes a new MP4 and SRT under app data. YouTube access is an opt-in OAuth integration and is not part of the current phase.

Transcription uses CPU `int8` to keep the machine's 4 GB GPU available to the desktop and other local tools. The first analysis downloads the selected faster-whisper model into app data. Candidate scoring is deterministic and combines audio energy, speech context, excitement phrases, and scene-change counts; its score is a ranking aid for human review.

