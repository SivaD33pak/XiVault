# System architecture and responsibilities

## Component model

```text
VS Code Extension (TypeScript)
  - visible commands/views, selection, safe local token storage
  - HTTPS + Bearer access token
             |
             v
FastAPI API (Python)
  - authentication, validation, authorization, quota transaction
  - service-role Supabase client / PostgreSQL transaction
             |                         |
             v                         v
Supabase PostgreSQL                Private Storage bucket: codevault-files
users, sessions, files, quota      user-id/file-id object names
```

## Responsibilities

### VS Code extension

- Implements visible UI and explicit user-driven commands.
- Reads only a selected file using `workspace.fs`; calculates local SHA-256 as a preflight check but treats server hash as authoritative.
- Keeps API base URL in `codevault.apiBaseUrl` setting. Uses `SecretStorage` for refresh token and username only; never writes tokens to settings or output channels.
- Uses a single retry after a successful token refresh. Does not retry non-idempotent uploads automatically.

### FastAPI service

- Owns all account logic, password hashing, JWT validation, refresh rotation, file validation, ownership checks, quota updates, and object lifecycle.
- Uses `Authorization: Bearer <access JWT>` on all vault endpoints.
- Uploads to a private Supabase bucket under `{user_id}/{file_id}`. It never creates public/signed URLs for v1; download is proxied as a streaming HTTP response.
- Reconciles a failed object/database transaction by deleting orphaned storage objects and logging a correlation ID.

### Supabase

- Stores relational records and private file objects.
- Has RLS enabled as defense in depth. Runtime API accesses using a service-role server credential, so service code remains the primary authorization layer.
- Direct browser/extension Supabase access is prohibited in v1.

## Key sequences

### Upload

1. Extension validates selection and sends multipart content to `POST /v1/files`.
2. API authenticates, validates UTF-8/type/size/hash, locks that user’s quota row, and verifies remaining space.
3. API writes the private object, inserts metadata, increments `used_bytes`, and commits.
4. API deletes the object if the database transaction fails; it returns updated quota and file metadata.

### Download and delete

1. API authenticates and looks up file by both `id` and `owner_id`.
2. For download, API streams the private object with safe attachment metadata.
3. For delete, API deletes the object and metadata in a recoverable, logged workflow, decrements quota exactly once, then returns `204`.

## Design boundaries

- Maximum indexed content is 256 KiB. Larger allowed files are retained but path-only searchable; this limits database growth.
- Filename/path are stored as normalized POSIX-relative display paths. Reject absolute paths, `..`, NUL, and control characters.
- API pagination uses opaque base64url cursor containing `(created_at, id)`; default page size 25, maximum 100.
