from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

from clipforge import youtube_auth
from clipforge.secret_store import WindowsSecretStore


class _MemoryStore:
    def __init__(self) -> None:
        self.value = {"oauth": None, "upload_sessions": {}, "channel": None}

    def read(self) -> dict[str, object]:
        return json.loads(json.dumps(self.value))

    def write(self, value: dict[str, object]) -> None:
        self.value = json.loads(json.dumps(value))

    def clear(self) -> None:
        self.value = {"oauth": None, "upload_sessions": {}, "channel": None}


class YouTubeAuthTests(unittest.TestCase):
    def test_desktop_flow_uses_pkce_state_and_saves_refresh_token(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        client_path = Path(temporary.name) / "client_secrets.json"
        client_path.write_text("{}", encoding="utf-8")
        store = _MemoryStore()
        manager = youtube_auth.YouTubeAuth(store_factory=lambda: store)
        client = {
            "client_id": "clipforge.apps.googleusercontent.com",
            "client_secret": "desktop-client-secret",
            "auth_uri": youtube_auth.AUTHORIZATION_ENDPOINT,
            "token_uri": youtube_auth.TOKEN_ENDPOINT,
        }
        with (
            patch.object(youtube_auth, "CLIENT_SECRETS_PATH", client_path),
            patch.object(youtube_auth, "load_installed_client", return_value=client),
            patch.object(youtube_auth, "_post_form", return_value={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}),
        ):
            result = manager.start()
            authorization = urllib.parse.urlsplit(result["authorization_url"])
            query = urllib.parse.parse_qs(authorization.query)
            self.assertEqual(query["code_challenge_method"], ["S256"])
            self.assertEqual(query["access_type"], ["offline"])
            self.assertIn("youtube.upload", query["scope"][0])
            self.assertIn("yt-analytics.readonly", query["scope"][0])
            callback = f"{manager._pending['redirect_uri']}?" + urllib.parse.urlencode({"code": "sample-code", "state": query["state"][0]})
            with urllib.request.urlopen(callback, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"connected to YouTube", response.read())

        self.assertEqual(manager.status()["status"], "connected")
        self.assertEqual(store.read()["oauth"]["refresh_token"], "refresh")
        self.assertEqual(manager.access_token(), "access")

    def test_expired_access_token_is_refreshed_and_keeps_existing_refresh_token(self) -> None:
        store = _MemoryStore()
        store.write({"oauth": {"access_token": "old", "refresh_token": "keep-me", "expires_at": 0}, "upload_sessions": {}, "channel": None})
        manager = youtube_auth.YouTubeAuth(store_factory=lambda: store)
        client = {
            "client_id": "clipforge.apps.googleusercontent.com",
            "client_secret": "desktop-client-secret",
            "auth_uri": youtube_auth.AUTHORIZATION_ENDPOINT,
            "token_uri": youtube_auth.TOKEN_ENDPOINT,
        }
        with patch.object(youtube_auth, "load_installed_client", return_value=client), patch.object(
            youtube_auth, "_post_form", return_value={"access_token": "fresh", "expires_in": 3600}
        ) as exchange:
            self.assertEqual(manager.access_token(), "fresh")
        self.assertEqual(store.read()["oauth"]["refresh_token"], "keep-me")
        self.assertEqual(exchange.call_args.args[1]["grant_type"], "refresh_token")

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI is required for the production credential store.")
    def test_dpapi_store_encrypts_tokens_and_upload_sessions(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "credentials.dpapi"
        store = WindowsSecretStore(path)
        secret = "refresh-token-that-must-not-be-plaintext"
        store.write({"oauth": {"refresh_token": secret}, "upload_sessions": {"event": "https://www.googleapis.com/upload/session"}})
        self.assertNotIn(secret.encode(), path.read_bytes())
        self.assertEqual(store.read()["oauth"]["refresh_token"], secret)
        store.clear()
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
