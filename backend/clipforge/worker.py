from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from .database import (
    claim_next_job,
    complete_clip_metadata,
    complete_youtube_publication,
    create_render_job,
    get_clip_youtube_upload_input,
    get_clip_generation_input,
    get_clip_render_input,
    get_recording_analysis,
    read_settings,
    recover_interrupted_jobs,
    save_analysis_result,
    queue_metadata_generation,
    resume_paused_jobs,
    save_recording_metadata,
    set_clip_render_status,
    set_clip_metadata_status,
    set_youtube_publication_status,
    update_job,
    update_recording_status,
)
from .config import OUTPUT_DIR
from .clip_rendering import render_vertical_clip
from .media import probe_video, resolve_music_asset, validate_video_path
from .highlights import generate_highlights
from .transcription import transcribe_recording
from .metadata import generate_clip_metadata
from .resource_limits import cpu_thread_budget
from .scheduling import schedule_window_is_open
from .youtube_api import upload_private_video


logger = logging.getLogger("clipforge.worker")


class PauseRequested(Exception):
    pass


def _ensure_not_paused() -> None:
    settings = read_settings()
    if settings["emergency_stop"] or settings["processing_paused"]:
        raise PauseRequested("Processing paused by creator.")


def _process_job(job: dict[str, Any]) -> None:
    job_id = job["id"]
    recording_id = job["recording_id"]
    try:
        if job["job_type"] not in {"inspect_recording", "analyze_recording", "render_clip", "generate_metadata", "youtube_upload"}:
            raise RuntimeError(f"Unsupported job type: {job['job_type']}")

        from .database import list_recordings

        recording = next((item for item in list_recordings() if item["id"] == recording_id), None)
        if recording is None:
            raise RuntimeError("The recording record no longer exists.")
        if not recording["authorized"]:
            raise RuntimeError("This recording has no authorization confirmation.")

        settings = read_settings()
        if settings["emergency_stop"] or settings["processing_paused"]:
            update_job(job_id, status="paused", stage="paused", progress=0)
            if job["job_type"] == "render_clip" and job.get("clip_id"):
                set_clip_render_status(job["clip_id"], "paused")
            elif job["job_type"] == "generate_metadata" and job.get("clip_id"):
                set_clip_metadata_status(job["clip_id"], "paused")
            elif job["job_type"] == "youtube_upload" and job.get("clip_id"):
                event_id = json.loads(job.get("payload_json") or "{}").get("event_id")
                if event_id:
                    set_youtube_publication_status(event_id, "paused")
            else:
                update_recording_status(recording_id, "ready" if job["job_type"] == "analyze_recording" else "queued")
            return

        cpu_threads = cpu_thread_budget(settings["cpu_limit_percent"])

        path = validate_video_path(recording["file_path"]) if job["job_type"] in {"inspect_recording", "analyze_recording", "render_clip"} else None
        if job["job_type"] == "inspect_recording":
            update_job(job_id, stage="probing", progress=12)
            metadata = probe_video(path)
            _ensure_not_paused()
            save_recording_metadata(recording_id, metadata)
            update_recording_status(recording_id, "ready", metadata["duration_seconds"])
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
            inspect_payload = json.loads(job.get("payload_json") or "{}")
            auto_analysis = inspect_payload.get("auto_analysis")
            if isinstance(auto_analysis, dict):
                queued = create_analysis_job(
                    recording_id,
                    clip_count=auto_analysis.get("clip_count", 1),
                    clip_duration_seconds=auto_analysis.get("clip_duration_seconds", 30),
                    moment_mix=auto_analysis.get("moment_mix", "balanced"),
                )
                logger.info("Queued automatic clip analysis for recording %s as job %s", recording_id, queued["id"])
        elif job["job_type"] == "analyze_recording":
            if recording.get("duration_seconds") is None:
                raise RuntimeError("Recording metadata is missing. Run inspection before analysis.")
            settings = read_settings()
            last_cancel_check = [0.0]

            def check_cancel() -> None:
                now = time.monotonic()
                if now - last_cancel_check[0] >= 2.0:
                    _ensure_not_paused()
                    last_cancel_check[0] = now

            def progress(value: int, _segment_count: int, stage: str) -> None:
                update_job(job_id, stage=stage, progress=value)

            result = transcribe_recording(
                source=path,
                recording_id=recording_id,
                model_name=settings["transcription_model"],
                cpu_threads=cpu_threads,
                progress=progress,
                check_cancel=check_cancel,
            )
            check_cancel()
            payload = json.loads(job.get("payload_json") or "{}")
            candidates = generate_highlights(
                duration_seconds=recording["duration_seconds"],
                energy_by_second=result["energy_by_second"],
                scene_cuts=result["scene_cuts"],
                transcript_segments=result["transcript"]["segments"],
                max_candidates=max(1, min(int(payload.get("clip_count", 1)), 100)),
                window_seconds=max(15, min(int(payload.get("clip_duration_seconds", 30)), 45)),
                moment_mix=str(payload.get("moment_mix", "balanced")),
            )
            clip_ids = save_analysis_result(recording_id, result, candidates)
            if payload.get("auto_process", True):
                for clip_id in clip_ids:
                    check_cancel()
                    create_render_job(clip_id)
                    queue_metadata_generation(clip_id, "", "hype")
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
        elif job["job_type"] == "render_clip":
            clip_id = job.get("clip_id")
            if not clip_id:
                raise RuntimeError("The render job is missing its candidate clip.")
            clip = get_clip_render_input(clip_id)
            if clip is None:
                raise RuntimeError("The clip candidate no longer exists.")
            if not clip["authorized"]:
                raise RuntimeError("The source recording has no authorization confirmation.")
            update_job(job_id, stage="preparing_subtitles", progress=12)
            clip_path = OUTPUT_DIR / recording_id / "clips" / f"{clip_id}.mp4"
            render_options = json.loads(job.get("payload_json") or "{}")
            music_source = resolve_music_asset(render_options["music_asset_id"]) if render_options.get("music_asset_id") else None

            def render_progress(value: int, stage: str) -> None:
                update_job(job_id, stage=stage, progress=value)

            rendered = render_vertical_clip(
                source=path,
                destination=clip_path,
                start_seconds=float(clip["start_seconds"]),
                end_seconds=float(clip["end_seconds"]),
                subtitles=clip["subtitles"],
                render_options=render_options,
                music_source=music_source,
                progress=render_progress,
                check_cancel=_ensure_not_paused,
                cpu_threads=cpu_threads,
            )
            set_clip_render_status(
                clip_id,
                "rendered",
                file_path=rendered["file_path"],
                render_metadata={key: value for key, value in rendered.items() if key != "file_path" and key != "subtitle_path"},
            )
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
        elif job["job_type"] == "generate_metadata":
            clip_id = job.get("clip_id")
            if not clip_id:
                raise RuntimeError("The metadata job is missing its candidate clip.")
            clip = get_clip_generation_input(clip_id)
            if clip is None or not clip["authorized"]:
                raise RuntimeError("The authorized candidate context is unavailable.")
            payload = json.loads(job.get("payload_json") or "{}")
            settings = read_settings()
            update_job(job_id, stage="generating_metadata", progress=20)
            generated = generate_clip_metadata(
                clip=clip,
                game_name=payload.get("game_name", ""),
                tone=payload.get("tone", "hype"),
                ollama_url=settings["ollama_url"],
                ollama_model=settings["ollama_model"],
            )
            _ensure_not_paused()
            complete_clip_metadata(clip_id, generated)
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
        else:
            clip_id = job.get("clip_id")
            if not clip_id:
                raise RuntimeError("The YouTube upload job is missing its candidate clip.")
            payload = json.loads(job.get("payload_json") or "{}")
            event_id = payload.get("event_id")
            if not event_id:
                raise RuntimeError("The YouTube upload job is missing its publication record.")
            clip = get_clip_youtube_upload_input(clip_id)
            if clip is None or not clip["authorized"]:
                raise RuntimeError("The authorized rendered candidate context is unavailable.")
            source = Path(clip["rendered_path"]).resolve() if clip.get("rendered_path") else None
            if source is None or not source.is_relative_to(OUTPUT_DIR.resolve()) or not source.is_file():
                raise RuntimeError("The rendered clip file is unavailable inside ClipForge output storage.")
            if clip["clip_status"] != "rendered":
                raise RuntimeError("Render the clip again before uploading it.")
            if not clip["upload_title"]:
                raise RuntimeError("Add a title to the clip metadata before uploading.")
            from .youtube_api import upload_fields

            title, description, tags = upload_fields(clip)

            def upload_progress(value: float, stage: str) -> None:
                update_job(job_id, stage=stage, progress=value)
                set_youtube_publication_status(event_id, "uploading", progress=value)

            result = upload_private_video(
                event_id=event_id,
                file_path=source,
                title=title,
                description=description,
                tags=tags,
                publish_at=payload.get("scheduled_at"),
                progress=upload_progress,
                check_cancel=_ensure_not_paused,
            )
            complete_youtube_publication(event_id, result["video_id"])
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
    except PauseRequested:
        update_job(job_id, status="paused", stage="paused", error_message="")
        if job["job_type"] == "render_clip" and job.get("clip_id"):
            set_clip_render_status(job["clip_id"], "paused")
        elif job["job_type"] == "generate_metadata" and job.get("clip_id"):
            set_clip_metadata_status(job["clip_id"], "paused")
        elif job["job_type"] == "youtube_upload" and job.get("clip_id"):
            event_id = json.loads(job.get("payload_json") or "{}").get("event_id")
            if event_id:
                set_youtube_publication_status(event_id, "paused")
        elif job["job_type"] == "analyze_recording":
            update_recording_status(recording_id, "ready")
        else:
            update_recording_status(recording_id, "queued")
    except Exception as error:  # A failed job remains visible and retryable.
        logger.exception("Recording job %s failed", job_id)
        update_job(job_id, status="failed", stage="failed", error_message=str(error)[:1000])
        if job["job_type"] == "render_clip" and job.get("clip_id"):
            set_clip_render_status(job["clip_id"], "failed")
        elif job["job_type"] == "generate_metadata" and job.get("clip_id"):
            set_clip_metadata_status(job["clip_id"], "failed", error_message=str(error)[:1000])
        elif job["job_type"] == "youtube_upload" and job.get("clip_id"):
            event_id = json.loads(job.get("payload_json") or "{}").get("event_id")
            if event_id:
                set_youtube_publication_status(event_id, "failed", error_message=str(error)[:1000])
        else:
            current_analysis = get_recording_analysis(recording_id) if job["job_type"] == "analyze_recording" else None
            update_recording_status(recording_id, "analyzed" if current_analysis and current_analysis["transcript"] else "failed")


async def run_worker() -> None:
    await asyncio.to_thread(recover_interrupted_jobs)
    active: dict[asyncio.Task[None], str] = {}
    while True:
        completed = {task for task in active if task.done()}
        for task in completed:
            active.pop(task, None)
            try:
                task.result()
            except Exception:
                logger.exception("Background processing task exited unexpectedly")

        settings = await asyncio.to_thread(read_settings)
        schedule_open = schedule_window_is_open(settings)
        if not settings["emergency_stop"] and not settings["processing_paused"] and schedule_open:
            await asyncio.to_thread(resume_paused_jobs)
            limit = max(1, min(int(settings["max_concurrent_jobs"]), 4))
            while len(active) < limit:
                cpu_job_active = any(job_type in {"analyze_recording", "render_clip", "generate_metadata"} for job_type in active.values())
                job = await asyncio.to_thread(claim_next_job, allow_cpu_intensive=not cpu_job_active)
                if job is None:
                    break
                task = asyncio.create_task(asyncio.to_thread(_process_job, job))
                active[task] = job["job_type"]
        await asyncio.sleep(0.5)

