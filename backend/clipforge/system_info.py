from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from .config import DATA_DIR


def _run(args: list[str], timeout: float = 2.5) -> str | None:
    executable = shutil.which(args[0])
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *args[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _version(command: str) -> str | None:
    output = _run([command, "-version"])
    if not output:
        return None
    first_line = output.splitlines()[0]
    parts = first_line.split()
    return " ".join(parts[:3]) if parts else first_line


def _gpu_info() -> dict[str, Any]:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return {"available": False, "name": None, "memory_total_mb": None, "memory_free_mb": None, "driver_version": None}

    first = output.splitlines()[0].split(",")
    if len(first) < 4:
        return {"available": False, "name": None, "memory_total_mb": None, "memory_free_mb": None, "driver_version": None}
    try:
        total = int(first[1].strip())
        free = int(first[2].strip())
    except ValueError:
        total, free = None, None
    return {
        "available": True,
        "name": first[0].strip(),
        "memory_total_mb": total,
        "memory_free_mb": free,
        "driver_version": first[3].strip(),
    }


def _cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if name.strip():
                    return name.strip()
        except (ImportError, OSError):
            pass
    return os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or "Unknown processor"


def _ollama_status(base_url: str, model: str) -> dict[str, Any]:
    endpoint = base_url.rstrip("/") + "/api/tags"
    try:
        request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=0.8) as response:
            body = json.loads(response.read().decode("utf-8"))
        installed = [item.get("name", "") for item in body.get("models", [])]
        model_present = any(name == model or name.startswith(model + ":") for name in installed)
        return {"online": True, "model_configured": model, "model_available": model_present}
    except (OSError, ValueError, urllib.error.URLError):
        return {"online": False, "model_configured": model, "model_available": False}


def collect_system_info(ollama_url: str, ollama_model: str) -> dict[str, Any]:
    memory = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(str(DATA_DIR if DATA_DIR.exists() else Path.home()))
        disk_info = {"free_bytes": disk.free, "total_bytes": disk.total}
    except OSError:
        disk_info = {"free_bytes": None, "total_bytes": None}

    return {
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu": {"name": _cpu_name(), "logical_processors": psutil.cpu_count(logical=True)},
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "percent_used": memory.percent,
        },
        "disk": disk_info,
        "media_tools": {
            "ffmpeg_version": _version("ffmpeg"),
            "ffprobe_version": _version("ffprobe"),
        },
        "gpu": _gpu_info(),
        "ollama": _ollama_status(ollama_url, ollama_model),
        "transcription_package_installed": importlib.util.find_spec("faster_whisper") is not None,
        "data_directory": str(DATA_DIR),
    }

