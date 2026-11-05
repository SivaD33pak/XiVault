# XiVault for Visual Studio Code

XiVault is a private, secure cloud-backed source-code vault extension. It allows authorized developers to privately archive, search, download, and delete source-code files directly from within VS Code.

## Features

- **Activity Bar Integration**: Dedicated XiVault sidebar view showing your private files and quota usage.
- **Quota Management**: Real-time display of used and remaining space (5 MiB per developer).
- **Full-Text Code Search**: Search across filenames and indexed source code content.
- **Instant Preview**: Download and inspect archived code snippets as read-only documents.
- **Strict Privacy & Isolation**: Each user can only view, search, and manage their own files. No telemetry or unauthorized scanning.

## Commands

- `XiVault: Register` — Register a new individual vault account.
- `XiVault: Log In` — Sign in securely with rotating encrypted tokens.
- `XiVault: Upload File` — Explicitly choose a workspace file to upload.
- `XiVault: Search Files` — Full-text search across all stored files.
- `XiVault: Download File` — Retrieve and view an archived file.
- `XiVault: Delete File` — Permanently delete a file and recover quota.
- `XiVault: Log Out` — Sign out and revoke active sessions.

## Configuration

- `xivault.apiBaseUrl`: Set your self-hosted or organization XiVault backend URL (defaults to `http://127.0.0.1:8000/v1`).
