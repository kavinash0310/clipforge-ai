from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from .youtube_auth import YouTubeAuth, youtube_oauth


YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
YOUTUBE_UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
CHUNK_SIZE = 8 * 1024 * 1024
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


class YouTubeAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _decode_error(body: bytes, status_code: int) -> YouTubeAPIError:
    try:
        result = json.loads(body.decode("utf-8"))
        details = result.get("error", {}) if isinstance(result, dict) else {}
        message = details.get("message") or details.get("status") or "YouTube request failed."
        reasons = [
            str(item.get("reason"))
            for item in details.get("errors", [])
            if isinstance(item, dict) and item.get("reason")
        ]
        if reasons:
            message = f"{message} ({', '.join(reasons[:3])})"
    except (UnicodeError, json.JSONDecodeError, AttributeError):
        message = "YouTube returned an error response."
    return YouTubeAPIError(f"YouTube returned HTTP {status_code}: {str(message)[:500]}", status_code=status_code)


def _send(request: urllib.request.Request, *, timeout: int = 60) -> tuple[int, Any, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise YouTubeAPIError("Network transfer to YouTube failed; the upload can be retried.") from error


def _api_json(
    method: str,
    url: str,
    *,
    query: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    auth: YouTubeAuth = youtube_oauth,
) -> dict[str, Any]:
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {auth.access_token()}",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
        method=method,
    )
    status, _headers, payload = _send(request)
    if status < 200 or status >= 300:
        raise _decode_error(payload, status)
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise YouTubeAPIError("YouTube returned an invalid JSON response.") from error
    if not isinstance(result, dict):
        raise YouTubeAPIError("YouTube returned an invalid response.")
    return result


def current_channel(*, auth: YouTubeAuth = youtube_oauth) -> dict[str, str] | None:
    result = _api_json("GET", f"{YOUTUBE_API}/channels", query={"part": "id,snippet", "mine": "true"}, auth=auth)
    channels = result.get("items") or []
    if not channels:
        return None
    channel = channels[0]
    snippet = channel.get("snippet") or {}
    return {"channel_id": str(channel.get("id") or ""), "title": str(snippet.get("title") or "YouTube channel")}


def upload_fields(clip: dict[str, Any]) -> tuple[str, str, list[str]]:
    title = " ".join(str(clip.get("upload_title") or clip.get("candidate_title") or "Gaming highlight").split())[:100]
    description = str(clip.get("upload_description") or "").strip()[:5000]
    hashtags = []
    for tag in clip.get("hashtags", []):
        value = "#" + "".join(char for char in str(tag).lstrip("#") if char.isalnum() or char == "_")
        if len(value) > 1 and value.casefold() not in {item.casefold() for item in hashtags}:
            hashtags.append(value[:41])
        if len(hashtags) == 8:
            break
    if hashtags:
        suffix = " ".join(hashtags)
        if suffix.casefold() not in description.casefold():
            description = f"{description}\n\n{suffix}".strip()[:5000]
    tags: list[str] = []
    seen: set[str] = set()
    for tag in [*hashtags, *clip.get("tags", [])]:
        value = " ".join(str(tag).lstrip("#").split())[:100]
        if not value or value.casefold() in seen:
            continue
        if sum(len(item) for item in tags) + len(value) + max(len(tags), 0) > 500:
            break
        tags.append(value)
        seen.add(value.casefold())
        if len(tags) == 20:
            break
    return title, description, tags


def _checked_upload_uri(uri: str) -> str:
    parsed = urllib.parse.urlsplit(uri)
    if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com" or not parsed.path.startswith("/upload/youtube/v3/videos"):
        raise YouTubeAPIError("YouTube returned an invalid resumable upload URL.")
    return uri


def _session_status(session_uri: str, size: int, *, auth: YouTubeAuth) -> tuple[int, int, dict[str, Any] | None]:
    request = urllib.request.Request(
        session_uri,
        data=b"",
        headers={
            "Authorization": f"Bearer {auth.access_token()}",
            "Content-Length": "0",
            "Content-Range": f"bytes */{size}",
        },
        method="PUT",
    )
    status, headers, payload = _send(request, timeout=45)
    if status in {200, 201}:
        try:
            body = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise YouTubeAPIError("The completed YouTube upload returned invalid JSON.") from error
        return status, size, body
    if status == 308:
        received = headers.get("Range", "") if headers else ""
        if received:
            try:
                offset = int(received.rsplit("-", 1)[1]) + 1
            except (IndexError, ValueError) as error:
                raise YouTubeAPIError("YouTube returned an invalid resumable upload range.") from error
        else:
            offset = 0
        return status, min(offset, size), None
    if status in {404, 410}:
        raise YouTubeAPIError(
            "The saved YouTube upload session expired. ClipForge stopped to prevent an accidental duplicate; start a new publication after checking your channel.",
            status_code=status,
        )
    raise _decode_error(payload, status)


def upload_private_video(
    *,
    event_id: str,
    file_path: Path,
    title: str,
    description: str,
    tags: list[str],
    progress: Callable[[float, str], None],
    check_cancel: Callable[[], None],
    auth: YouTubeAuth = youtube_oauth,
) -> dict[str, str]:
    if not file_path.is_file():
        raise YouTubeAPIError("The rendered clip file no longer exists.")
    if not title.strip():
        raise YouTubeAPIError("Add a title to the clip metadata before uploading.")
    file_size = file_path.stat().st_size
    if file_size <= 0:
        raise YouTubeAPIError("The rendered clip file is empty.")
    session_uri = auth.upload_session(event_id)
    offset = 0
    if session_uri:
        session_uri = _checked_upload_uri(session_uri)
        status, offset, completed = _session_status(session_uri, file_size, auth=auth)
        if completed:
            video_id = str(completed.get("id") or "")
            if not video_id:
                raise YouTubeAPIError("The completed upload response did not include its video ID.")
            auth.set_upload_session(event_id, None)
            return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}
        progress(min(90, 15 + (offset / file_size) * 75), "resuming_upload")
    else:
        metadata = {
            "snippet": {"title": title.strip()[:100], "description": description[:5000], "tags": tags},
            "status": {"privacyStatus": "private"},
        }
        query = urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": "false"})
        request = urllib.request.Request(
            f"{YOUTUBE_UPLOAD_API}?{query}",
            data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {auth.access_token()}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(file_size),
            },
            method="POST",
        )
        status, headers, payload = _send(request)
        if status < 200 or status >= 300:
            raise _decode_error(payload, status)
        session_uri = headers.get("Location") if headers else None
        if not session_uri:
            raise YouTubeAPIError("YouTube did not return a resumable upload session URL.")
        session_uri = _checked_upload_uri(session_uri)
        auth.set_upload_session(event_id, session_uri)
        progress(15, "upload_started")

    transient_attempts = 0
    with file_path.open("rb") as video:
        while offset < file_size:
            check_cancel()
            video.seek(offset)
            chunk = video.read(min(CHUNK_SIZE, file_size - offset))
            if not chunk:
                raise YouTubeAPIError("The rendered clip changed while uploading.")
            end = offset + len(chunk) - 1
            request = urllib.request.Request(
                session_uri,
                data=chunk,
                headers={
                    "Authorization": f"Bearer {auth.access_token()}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                },
                method="PUT",
            )
            try:
                status, headers, payload = _send(request)
            except YouTubeAPIError:
                transient_attempts += 1
                if transient_attempts > 5:
                    raise
                time.sleep(min(2 ** (transient_attempts - 1), 20))
                status, offset, completed = _session_status(session_uri, file_size, auth=auth)
                if completed:
                    payload = json.dumps(completed).encode("utf-8")
                else:
                    progress(min(90, 15 + (offset / file_size) * 75), "resuming_upload")
                    continue
            if status in TRANSIENT_STATUS_CODES:
                transient_attempts += 1
                if transient_attempts > 5:
                    raise _decode_error(payload, status)
                time.sleep(min(2 ** (transient_attempts - 1), 20))
                status, offset, completed = _session_status(session_uri, file_size, auth=auth)
                if completed:
                    payload = json.dumps(completed).encode("utf-8")
                    status = 201
                else:
                    progress(min(90, 15 + (offset / file_size) * 75), "resuming_upload")
                    continue
            if status == 308:
                received = headers.get("Range", "") if headers else ""
                offset = int(received.rsplit("-", 1)[1]) + 1 if received else 0
                transient_attempts = 0
                progress(min(90, 15 + (offset / file_size) * 75), "uploading_video")
                continue
            if status not in {200, 201}:
                raise _decode_error(payload, status)
            try:
                result = json.loads(payload.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise YouTubeAPIError("YouTube returned invalid JSON after the video upload.") from error
            video_id = str(result.get("id") or "")
            if not video_id:
                raise YouTubeAPIError("YouTube completed the transfer but did not return a video ID.")
            auth.set_upload_session(event_id, None)
            progress(100, "complete")
            return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}
    raise YouTubeAPIError("The YouTube upload ended before the video was accepted.")


def channel_analytics(
    video_ids: list[str],
    *,
    auth: YouTubeAuth = youtube_oauth,
    today: date | None = None,
) -> dict[str, dict[str, int]]:
    if not video_ids:
        return {}
    end_date = (today or date.today()) - timedelta(days=1)
    start_date = end_date - timedelta(days=27)
    output: dict[str, dict[str, int]] = {}
    for first in range(0, len(video_ids), 200):
        ids = video_ids[first:first + 200]
        result = _api_json("GET", YOUTUBE_ANALYTICS_API, query={
            "ids": "channel==MINE",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": "views,likes,comments,shares",
            "dimensions": "video",
            "filters": f"video=={','.join(ids)}",
            "sort": "-views",
            "maxResults": "200",
        }, auth=auth)
        headers = result.get("columnHeaders") or []
        names = [str(item.get("name", "")) for item in headers]
        for row in result.get("rows") or []:
            values = dict(zip(names, row))
            video_id = str(values.pop("video", ""))
            if video_id:
                output[video_id] = {name: int(value or 0) for name, value in values.items()}
    return output
