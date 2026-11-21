from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from collections.abc import AsyncIterable
from email.message import Message
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import httpx

from .config import OUTPUT_DIR


MAX_SOURCE_BYTES = 20 * 1024 * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".mov", ".avi", ".webm", ".mpeg", ".mpg"}
VIDEO_MIME_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/x-m4v": ".m4v",
    "video/x-matroska": ".mkv",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    "video/mpeg": ".mpeg",
    "application/octet-stream": None,
}


class SourceImportError(ValueError):
    pass


def _safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = "".join(character for character in name if character.isprintable() and character not in '<>:"|?*')
    name = " ".join(name.split()).strip(" .")
    return name[:180] or "video"


def _extension(filename: str, content_type: str | None) -> str:
    suffix = Path(_safe_filename(filename)).suffix.lower()
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if suffix in VIDEO_EXTENSIONS:
        return suffix
    if media_type in VIDEO_MIME_EXTENSIONS and VIDEO_MIME_EXTENSIONS[media_type]:
        return VIDEO_MIME_EXTENSIONS[media_type] or ".mp4"
    raise SourceImportError("Use a supported video file: MP4, M4V, MKV, MOV, AVI, MPEG, or WebM.")


async def _save_stream(filename: str, content_type: str | None, chunks: AsyncIterable[bytes]) -> tuple[Path, str]:
    safe_name = _safe_filename(filename)
    suffix = _extension(safe_name, content_type)
    source_directory = OUTPUT_DIR / "sources"
    source_directory.mkdir(parents=True, exist_ok=True)
    source_path = source_directory / f"source-{uuid4().hex}{suffix}"
    partial_path = source_path.with_suffix(source_path.suffix + ".part")
    size = 0
    try:
        with partial_path.open("wb") as output:
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise SourceImportError("Videos must be 20 GB or smaller.")
                output.write(chunk)
        if size == 0:
            raise SourceImportError("The selected video is empty.")
        os.replace(partial_path, source_path)
    except BaseException as error:
        partial_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)
        if isinstance(error, SourceImportError) or not isinstance(error, Exception):
            raise
        raise SourceImportError("The video upload did not finish.") from error

    if Path(safe_name).suffix.lower() not in VIDEO_EXTENSIONS:
        safe_name = f"{Path(safe_name).stem or 'video'}{suffix}"
    return source_path, safe_name


async def save_uploaded_video(filename: str, content_type: str | None, chunks: AsyncIterable[bytes]) -> tuple[Path, str]:
    return await _save_stream(filename, content_type, chunks)


def _validate_public_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise SourceImportError("Paste a valid public HTTP or HTTPS video link.") from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise SourceImportError("Paste a public HTTP or HTTPS link to a direct video file.")
    if len(url) > 4096:
        raise SourceImportError("The video link is too long.")
    try:
        answers = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise SourceImportError("The video link host could not be reached.") from error
    addresses = {answer[4][0].split("%", 1)[0] for answer in answers}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise SourceImportError("Links to private or local network addresses are not supported.")


def _link_filename(url: str, suffix: str, disposition: str | None = None) -> str:
    header = Message()
    if disposition:
        header["content-disposition"] = disposition
    name = header.get_filename() or Path(unquote(urlsplit(url).path)).name
    name = _safe_filename(name)
    if Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
        name = f"{Path(name).stem or 'video'}{suffix}"
    return name


async def download_direct_video(url: str) -> tuple[Path, str]:
    current_url = url.strip()
    timeout = httpx.Timeout(connect=20, read=120, write=20, pool=20)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for redirect_count in range(6):
            await asyncio.to_thread(_validate_public_url, current_url)
            try:
                async with client.stream("GET", current_url, headers={"User-Agent": "ClipForge/1.0"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirect_count == 5:
                            raise SourceImportError("The video link redirected too many times.")
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code < 200 or response.status_code >= 300:
                        raise SourceImportError(f"The video host returned HTTP {response.status_code}.")

                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    suffix_from_url = Path(urlsplit(current_url).path).suffix.lower()
                    disposition = response.headers.get("content-disposition")
                    header_filename = Message()
                    if disposition:
                        header_filename["content-disposition"] = disposition
                    suffix_from_header = Path(_safe_filename(header_filename.get_filename() or "")).suffix.lower()
                    if not content_type.startswith("video/") and content_type != "application/octet-stream":
                        raise SourceImportError("This is a webpage or playlist, not a direct video-file link.")
                    if content_type == "application/octet-stream" and suffix_from_url not in VIDEO_EXTENSIONS and suffix_from_header not in VIDEO_EXTENSIONS:
                        raise SourceImportError("The host did not identify this as a video file. Use a direct MP4, MKV, MOV, AVI, MPEG, or WebM link.")
                    source_hint = suffix_from_url if suffix_from_url in VIDEO_EXTENSIONS else suffix_from_header
                    suffix = _extension(f"video{source_hint}" if source_hint else "video", content_type)
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > MAX_SOURCE_BYTES:
                        raise SourceImportError("Videos must be 20 GB or smaller.")
                    filename = _link_filename(current_url, suffix, disposition)
                    source_path, display_name = await _save_stream(filename, content_type, response.aiter_bytes())
                    return source_path, display_name
            except httpx.HTTPError as error:
                raise SourceImportError("ClipForge could not download that direct video file.") from error
    raise SourceImportError("The video link could not be imported.")
