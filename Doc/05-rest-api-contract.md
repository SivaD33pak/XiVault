# REST API contract

Base URL: `https://<USER_PROVIDED_API_DOMAIN>/v1`. JSON uses UTF-8. All error bodies follow:

```json
{"error":{"code":"quota_exceeded","message":"Storage quota exceeded.","request_id":"..."}}
```

## Authentication

### `POST /auth/register`

Request: `{"username":"dev_user","password":"USER_PROVIDED_PASSWORD"}`. Returns `201`:

```json
{"user":{"id":"uuid","username":"dev_user","created_at":"2026-11-05T00:00:00Z"},"quota":{"used_bytes":0,"quota_bytes":5242880,"remaining_bytes":5242880}}
```

Errors: `409 username_taken`, `422 validation_error`, `429 rate_limited`.

### `POST /auth/login`

Request equals registration. Returns `200`:

```json
{"access_token":"JWT","token_type":"bearer","expires_in":900,"refresh_token":"opaque-secret","user":{"id":"uuid","username":"dev_user"}}
```

Errors: `401 invalid_credentials`, `429 rate_limited`.

### `POST /auth/refresh`

Request: `{"refresh_token":"opaque-secret"}`. Returns same token shape as login with a rotated refresh token. Errors: `401 invalid_refresh_token`. Rotation revokes the presented token atomically; reuse of a revoked token revokes all active sessions for that user and returns `401 refresh_token_reuse`.

### `POST /auth/logout`

Bearer-authenticated. Body: `{"refresh_token":"opaque-secret"}`. Returns `204`, even if token was already revoked for the logged-in user.

## Vault endpoints

All require `Authorization: Bearer <access_token>`.

### `GET /me/quota`

Returns `200`: `{"used_bytes":123,"quota_bytes":5242880,"remaining_bytes":5242757}`.

### `POST /files`

`multipart/form-data` fields: `file` (required upload) and `display_path` (required normalized workspace-relative path). Returns `201`:

```json
{"file":{"id":"uuid","display_path":"src/main.py","language":"python","content_type":"text/x-python","byte_size":123,"sha256":"64-hex","created_at":"...","updated_at":"..."},"quota":{"used_bytes":123,"quota_bytes":5242880,"remaining_bytes":5242757}}
```

Errors: `400 invalid_path|invalid_text_encoding|unsupported_file_type`, `401 unauthorized`, `409 duplicate_file`, `413 file_too_large`, `422 validation_error`, `429 rate_limited`, `507 quota_exceeded`.

### `GET /files?cursor=<opaque>&limit=25`

Returns `200`: `{"items":[{"id":"uuid","display_path":"src/main.py","language":"python","byte_size":123,"created_at":"..."}],"next_cursor":null}`. Default `25`, maximum `100`.

### `GET /files/search?q=<query>&cursor=<opaque>&limit=25`

`q` is 1–200 visible characters. Returns list shape plus `excerpt` for content matches. Use parameterized `websearch_to_tsquery('simple', q)`; do not interpolate query text into SQL.

### `GET /files/{file_id}/download`

Returns `200` binary stream with `Content-Type` stored MIME and sanitized `Content-Disposition: attachment; filename="..."`. Errors: `404 file_not_found`; never disclose whether another user owns the ID.

### `DELETE /files/{file_id}`

Returns `204`. It is idempotent for a file already absent to that same user (`204`), and `404` for unknown/other-owner IDs. On success it decrements quota by stored `byte_size` once.

## Common semantics

- `401` means missing, expired, malformed, or invalid authentication; extension then attempts one refresh.
- `403` is reserved for a valid identity blocked by account state. Never use it to confirm cross-user resource existence.
- Every response adds `X-Request-ID`; logs include it but no secret or source content.
- Publish OpenAPI automatically at `/docs` only in non-production or behind operator authentication. Always make `/openapi.json` available to the extension build only if it contains no internal details.
