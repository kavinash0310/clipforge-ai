# Security

- The development server and local API bind only to loopback.
- CORS allows only the local Vite origins used by this project.
- Settings reject unknown fields; Ollama URLs must resolve to localhost.
- Original video files are referenced by path and are not copied into the database.
- Runtime probes have short timeouts and return status rather than raw command output.
- `client_secrets.json`, DPAPI credential blobs, environment files, databases, and generated media are ignored by Git.
- YouTube OAuth uses the desktop-app PKCE flow, a loopback callback bound to `127.0.0.1`, and CSRF state validation.
- Refresh tokens and resumable upload session URLs are stored in a current-Windows-user DPAPI encrypted file under the app data directory, never in SQLite or source control.
- The Google Desktop OAuth client is a public client; its downloaded client JSON is local configuration, not a confidential application secret. Do not commit it.
- Uploads set YouTube privacy to `private` explicitly. A unique publication record per clip prevents a repeated click from starting a second upload; retries reuse the encrypted resumable session.

Report vulnerabilities privately to the repository owner. Do not include OAuth credentials, source videos, or personal access tokens in an issue.

