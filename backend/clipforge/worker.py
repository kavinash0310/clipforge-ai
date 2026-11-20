from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from .database import (
    claim_next_job,
    get_recording_analysis,
    read_settings,
    recover_interrupted_jobs,
    save_analysis_result,
    resume_paused_jobs,
    save_recording_metadata,
    update_job,
    update_recording_status,
)
from .media import probe_video, validate_video_path
from .highlights import generate_highlights
from .transcription import transcribe_recording


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
        if job["job_type"] not in {"inspect_recording", "analyze_recording"}:
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
            update_recording_status(recording_id, "ready" if job["job_type"] == "analyze_recording" else "queued")
            return

        path = validate_video_path(recording["file_path"])
        if job["job_type"] == "inspect_recording":
            update_job(job_id, stage="probing", progress=12)
            metadata = probe_video(path)
            _ensure_not_paused()
            save_recording_metadata(recording_id, metadata)
            update_recording_status(recording_id, "ready", metadata["duration_seconds"])
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
        else:
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
                cpu_threads=min(4, os.cpu_count() or 1),
                progress=progress,
                check_cancel=check_cancel,
            )
            check_cancel()
            candidates = generate_highlights(
                duration_seconds=recording["duration_seconds"],
                energy_by_second=result["energy_by_second"],
                scene_cuts=result["scene_cuts"],
                transcript_segments=result["transcript"]["segments"],
            )
            save_analysis_result(recording_id, result, candidates)
            update_job(job_id, status="complete", stage="complete", progress=100, error_message="")
    except PauseRequested:
        update_job(job_id, status="paused", stage="paused", error_message="")
        update_recording_status(recording_id, "ready")
    except Exception as error:  # A failed job remains visible and retryable.
        logger.exception("Recording job %s failed", job_id)
        update_job(job_id, status="failed", stage="failed", error_message=str(error)[:1000])
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
        if not settings["emergency_stop"] and not settings["processing_paused"]:
            await asyncio.to_thread(resume_paused_jobs)
            limit = max(1, min(int(settings["max_concurrent_jobs"]), 4))
            while len(active) < limit and "analyze_recording" not in active.values():
                job = await asyncio.to_thread(claim_next_job)
                if job is None:
                    break
                task = asyncio.create_task(asyncio.to_thread(_process_job, job))
                active[task] = job["job_type"]
                if job["job_type"] == "analyze_recording":
                    break
        await asyncio.sleep(0.5)

