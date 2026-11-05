# Authentication, security, and threat model

## Security controls

- Hash passwords with Argon2id using `pwdlib.PasswordHash.recommended()` (or an explicitly equivalent current Argon2id configuration). Verify in constant-time library code. Never implement hashing manually.
- Issue JWT access tokens signed with `CODEVAULT_JWT_SECRET` using HS256 initially; include `sub` (user UUID), `sid`, `iat`, `exp`, `iss`, `aud`, and `jti`. Validate all expected claims and allow only the configured algorithm.
- Generate refresh tokens from at least 32 cryptographically random bytes, encode base64url, store only a cryptographic hash, and rotate them on every refresh.
- Set access token TTL to 15 minutes and refresh expiry to 30 days. Server clock uses UTC and permits no unbounded leeway.
- Apply rate limits by IP plus username: register/login 5 attempts per 15 minutes, refresh 20 per 15 minutes, uploads 30 per hour per user. Choose an implementation backed by Redis or PostgreSQL suitable for the deployment topology.
- Enforce HTTPS, trusted-host middleware, restrictive CORS for the extension’s declared origin needs (not `*` in production), request body limits, security headers, structured redacted logs, and dependency vulnerability scanning.

## Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Credential stuffing | Argon2id, login rate limits, generic invalid-credential errors, no username enumeration endpoint. |
| Token theft | TLS, memory-only access token, VS Code SecretStorage refresh token, short TTL, refresh rotation/reuse detection, redacted logs. |
| IDOR/cross-user access | Query resources by `(file_id, owner_id)` on every request; no client-controlled owner ID. |
| Quota race | Lock quota row and update exact byte delta in the upload/delete transaction. |
| Malicious upload | Server-side size/type/UTF-8/path validation, storage bucket private, no execution or preview in browser. |
| SQL/injection/search abuse | ORM/parameterized SQL, bounded query length/page sizes, FTS query parameterization. |
| Storage exposure | Private bucket, service role only on backend, no public objects/URLs, opaque storage keys. |
| Orphaned objects | Compensating deletion plus scheduled reconciler and request-id logs. |
| Secret leakage | `.env` ignored, `.env.example` placeholders only, CI secret store, secret scanning. |

## Extension security

- Declare minimum permissions/capabilities only. Do not read a workspace except after user command and user-selected URI.
- Do not send source content to analytics, logs, crash reports, clipboard, webviews, or any third party.
- Use `vscode.window.showInputBox({ password: true })` for password entry; never persist it.
- Validate TLS certificate normally; do not provide a disable-TLS setting.

## Incident response

The operator can disable a user (`disabled_at`), revoke all sessions, rotate JWT/signing and Supabase service credentials, review request IDs/redacted audit events, and notify affected users. Credential rotation must invalidate old JWTs by changing a version/key identifier or issuing a forced session invalidation policy.
