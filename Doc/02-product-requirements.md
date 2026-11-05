# Product requirements and user stories

## Product objective

Give authorized developers a visible, straightforward VS Code workflow for privately archiving small source-code files they are entitled to use, then retrieving them through search.

## Personas

- **Developer:** owns or is authorized to work with a repository and wants a private cloud-backed code reference.
- **Operator:** configures Supabase and the deployed API, manages service credentials, and investigates operational issues without viewing file content unnecessarily.

## Functional requirements

### Account and session

- Registration accepts a unique username (3–32 characters, lowercase letters, digits, `_`, `-`) and a password of at least 12 characters.
- Login creates a session and returns an access token plus refresh token according to the API contract.
- The extension stores the refresh token using VS Code `SecretStorage`; it retains access token only in memory.
- Logout revokes the current refresh token and clears local secrets.

### Files

- The extension uploads an explicitly user-selected workspace file; no automatic scanning or background upload.
- Allow UTF-8 text and source files from a documented extension allowlist; reject binary content and files greater than 1 MiB.
- Enforce 5,242,880 bytes of total stored object size per user on the server.
- Each saved record includes original path, detected language, content type, byte size, SHA-256 hash, creation time, and updated time.
- Users can list, search, download, and permanently delete only their own files.
- Search matches paths and indexed text content. Results show paths, language, size, and excerpts, but not another user’s metadata or content.

### Extension UX

- Provide a visible Activity Bar view named **CodeVault** and command-palette commands: `CodeVault: Register`, `Log In`, `Upload File`, `Refresh Files`, `Search Files`, `Download File`, `Delete File`, and `Log Out`.
- Clearly show login state, storage used/remaining, operation status, and errors with actionable text.
- Require a confirmation before delete. Download opens the result as a read-only VS Code text document by default; an explicit command may save it to an approved local destination.

## User stories

| ID | Story | Acceptance outcome |
| --- | --- | --- |
| US-01 | As a developer, I register so I can have an individual vault. | Invalid usernames/passwords fail with clear errors; duplicate names are rejected. |
| US-02 | As a developer, I log in and remain signed in securely. | Reopen refreshes a valid session from SecretStorage without exposing tokens. |
| US-03 | As a developer, I choose an authorized source file to upload. | UI shows selected path/size and requests upload only after explicit confirmation. |
| US-04 | As a developer, I see my quota before and after upload. | Used and remaining bytes match server values. |
| US-05 | As a developer, I browse and search my vault. | Results are paginated, scoped to my account, and searchable by path/content. |
| US-06 | As a developer, I retrieve a file for legitimate work. | Retrieved content opens read-only with the stored filename/language. |
| US-07 | As a developer, I delete an obsolete file. | Confirmation is required and both database record/object are removed. |
| US-08 | As an operator, I can deploy safely. | Secrets are server-only, private bucket is configured, and health checks work. |

## Out of scope

- Hidden, minimized, overlay, or stealth workflows.
- Academic integrity violations, live interview assistance, policy evasion, or disallowed-content concealment.
- Collaboration, public links, teams, payments, web UI, Git repository credential collection, code execution, AI code generation, or arbitrary binary storage.

## Product metrics (post-v1)

- Successful upload rate, download success rate, API error rate, and quota-rejection count, recorded without source content, password, token, or full file path.
