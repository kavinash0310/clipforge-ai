from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .config import DATA_DIR
from .secret_store import WindowsSecretStore


YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CLIENT_SECRETS_PATH = DATA_DIR / "client_secrets.json"


def load_installed_client(path: Path = CLIENT_SECRETS_PATH) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Add a Google Desktop OAuth client file at {path}.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("The Google OAuth client file could not be read as JSON.") from error
    client = raw.get("installed") if isinstance(raw, dict) else None
    if not isinstance(client, dict):
        raise RuntimeError("Use a Google OAuth client JSON file for a Desktop app.")
    client_id = client.get("client_id")
    if not isinstance(client_id, str) or not client_id.endswith(".apps.googleusercontent.com"):
        raise RuntimeError("The Desktop OAuth client file has no valid client_id.")
    values = {
        "client_id": client_id,
        "client_secret": str(client.get("client_secret") or ""),
        "auth_uri": str(client.get("auth_uri") or AUTHORIZATION_ENDPOINT),
        "token_uri": str(client.get("token_uri") or TOKEN_ENDPOINT),
    }
    if values["auth_uri"] != AUTHORIZATION_ENDPOINT or values["token_uri"] != TOKEN_ENDPOINT:
        raise RuntimeError("The OAuth client file must use Google's standard authorization and token endpoints.")
    return values


def _post_form(url: str, values: dict[str, str], timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            details = json.loads(error.read().decode("utf-8"))
            message = details.get("error_description") or details.get("error") or "OAuth request failed."
        except (UnicodeError, json.JSONDecodeError):
            message = "OAuth request failed."
        raise RuntimeError(f"Google OAuth returned HTTP {error.code}: {str(message)[:300]}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Google OAuth could not be reached. Check the network and retry.") from error
    if not isinstance(result, dict):
        raise RuntimeError("Google OAuth returned an invalid response.")
    return result


class YouTubeAuth:
    def __init__(self, store_factory: Callable[[], Any] | None = None):
        self._store_factory = store_factory or (lambda: WindowsSecretStore(DATA_DIR / "youtube_credentials.dpapi"))
        self._lock = threading.RLock()
        self._pending: dict[str, Any] | None = None

    def _store(self) -> Any:
        try:
            return self._store_factory()
        except RuntimeError as error:
            raise RuntimeError(f"Secure token storage is unavailable: {error}") from error

    def start(self) -> dict[str, str]:
        client = load_installed_client()
        store = self._store()
        with self._lock:
            if self._pending and self._pending["status"] == "pending":
                raise RuntimeError("A YouTube account connection is already in progress.")
            state = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
            pending: dict[str, Any] = {
                "state": state,
                "verifier": verifier,
                "client": client,
                "status": "pending",
                "error": None,
                "started_at": time.time(),
                "store": store,
                "manager": self,
                "server": None,
            }
            server = _OAuthCallbackServer(("127.0.0.1", 0), pending)
            server.daemon_threads = True
            pending["server"] = server
            redirect_uri = f"http://127.0.0.1:{server.server_port}"
            pending["redirect_uri"] = redirect_uri
            self._pending = pending
            threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
            expiry = threading.Timer(600, self._expire, args=(pending,))
            expiry.daemon = True
            expiry.start()
        query = urllib.parse.urlencode({
            "client_id": client["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return {"authorization_url": f"{client['auth_uri']}?{query}", "status": "pending"}

    def _expire(self, pending: dict[str, Any]) -> None:
        with self._lock:
            if pending["status"] == "pending":
                pending["status"] = "error"
                pending["error"] = "YouTube connection timed out. Start again when ready."
                pending["server"].shutdown()

    def _finish_callback(self, pending: dict[str, Any], query: dict[str, list[str]]) -> tuple[int, str]:
        returned_state = query.get("state", [""])[0]
        if not hmac.compare_digest(returned_state, pending["state"]):
            return 400, "The account connection state did not match. Return to ClipForge and try again."
        provider_error = query.get("error", [""])[0]
        if provider_error:
            with self._lock:
                pending["status"] = "error"
                pending["error"] = "Google account connection was cancelled or denied."
            return 400, "Google account connection was cancelled or denied. You can close this window."
        code = query.get("code", [""])[0]
        if not code:
            return 400, "Google did not return an authorization code. Return to ClipForge and try again."
        try:
            client = pending["client"]
            tokens = _post_form(client["token_uri"], {
                "code": code,
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "redirect_uri": pending["redirect_uri"],
                "grant_type": "authorization_code",
                "code_verifier": pending["verifier"],
            })
            if not tokens.get("access_token"):
                raise RuntimeError("Google did not return an access token.")
            tokens["expires_at"] = time.time() + max(0, int(tokens.get("expires_in", 3600)) - 45)
            saved = pending["store"].read()
            previous_tokens = saved.get("oauth") or {}
            if not tokens.get("refresh_token") and previous_tokens.get("refresh_token"):
                tokens["refresh_token"] = previous_tokens["refresh_token"]
            saved["oauth"] = tokens
            pending["store"].write(saved)
            with self._lock:
                pending["status"] = "connected"
                pending["error"] = None
            return 200, "ClipForge is connected to YouTube. You can close this window."
        except Exception as error:
            with self._lock:
                pending["status"] = "error"
                pending["error"] = str(error)[:300]
            return 500, "ClipForge could not finish connecting. Return to the app to see the error."

    def status(self) -> dict[str, Any]:
        configured = CLIENT_SECRETS_PATH.is_file()
        error = None
        try:
            stored = self._store().read()
            connected = bool(stored.get("oauth"))
        except RuntimeError as store_error:
            connected = False
            error = str(store_error)
        with self._lock:
            pending = self._pending
            pending_status = pending["status"] if pending else None
            pending_error = pending["error"] if pending and pending["status"] == "error" else None
        visible_pending_status = pending_status if pending_status in {"pending", "error"} else None
        return {
            "configured": configured,
            "connected": connected,
            "status": "connected" if connected else (visible_pending_status or "not_connected"),
            "error": error or pending_error,
            "client_secrets_path": str(CLIENT_SECRETS_PATH),
        }

    def access_token(self) -> str:
        with self._lock:
            store = self._store()
            saved = store.read()
            tokens = saved.get("oauth")
            if not isinstance(tokens, dict):
                raise RuntimeError("Connect a YouTube account before using uploads or analytics.")
            if float(tokens.get("expires_at", 0)) > time.time() + 20:
                return str(tokens["access_token"])
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                raise RuntimeError("The YouTube session expired. Disconnect and connect the account again.")
            client = load_installed_client()
            refreshed = _post_form(client["token_uri"], {
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "refresh_token": str(refresh_token),
                "grant_type": "refresh_token",
            })
            if not refreshed.get("access_token"):
                raise RuntimeError("Google did not return a refreshed access token.")
            updated = {**tokens, **refreshed, "refresh_token": refresh_token}
            updated["expires_at"] = time.time() + max(0, int(refreshed.get("expires_in", 3600)) - 45)
            saved["oauth"] = updated
            store.write(saved)
            return str(updated["access_token"])

    def upload_session(self, event_id: str) -> str | None:
        return self._store().read().get("upload_sessions", {}).get(event_id)

    def set_upload_session(self, event_id: str, session_uri: str | None) -> None:
        store = self._store()
        value = store.read()
        sessions = value.setdefault("upload_sessions", {})
        if session_uri:
            sessions[event_id] = session_uri
        else:
            sessions.pop(event_id, None)
        store.write(value)

    def disconnect(self) -> None:
        store = self._store()
        try:
            value = store.read()
        except RuntimeError:
            store.clear()
            value = {"oauth": None}
        tokens = value.get("oauth") or {}
        current_token = tokens.get("refresh_token") or tokens.get("access_token")
        if current_token:
            try:
                urllib.request.urlopen(
                    urllib.request.Request(
                        REVOKE_ENDPOINT,
                        data=urllib.parse.urlencode({"token": current_token}).encode("ascii"),
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        method="POST",
                    ),
                    timeout=10,
                ).close()
            except (OSError, urllib.error.URLError):
                pass
        store.clear()
        with self._lock:
            pending = self._pending
            self._pending = None
            if pending and pending["status"] == "pending":
                pending["status"] = "error"
                pending["error"] = "YouTube account connection was cancelled."
        if pending and pending.get("server"):
            threading.Thread(target=pending["server"].shutdown, daemon=True).start()


class _OAuthCallbackServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], pending: dict[str, Any]):
        self.pending = pending
        super().__init__(address, _OAuthCallbackHandler)


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: _OAuthCallbackServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler interface.
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != "/":
            self.send_error(404)
            return
        status, message = self.server.pending["manager"]._finish_callback(self.server.pending, urllib.parse.parse_qs(parsed.query))
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>ClipForge YouTube</title></head>"
            "<body style='font:16px system-ui;margin:3rem auto;max-width:38rem;padding:0 1rem'>"
            f"<h2>{html.escape(message)}</h2><p>Return to ClipForge to continue.</p></body></html>"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        if status in {200, 500}:
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, _format: str, *_args: object) -> None:
        return


youtube_oauth = YouTubeAuth()
