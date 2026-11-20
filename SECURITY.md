# Security

- The development server and local API bind only to loopback.
- CORS allows only the local Vite origins used by this project.
- Settings reject unknown fields; Ollama URLs must resolve to localhost.
- Original video files are referenced by path and are not copied into the database.
- Runtime probes have short timeouts and return status rather than raw command output.
- `client_secrets.json`, OAuth tokens, environment files, databases, and generated media are ignored by Git.
- Phase 1 has no OAuth tokens or remote upload code. Before that integration ships, tokens must be stored outside the repository and protected with Windows DPAPI or the Windows Credential Manager.

Report vulnerabilities privately to the repository owner. Do not include OAuth credentials, source videos, or personal access tokens in an issue.

