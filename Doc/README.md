# CodeVault implementation handover

CodeVault is a VS Code Marketplace extension and FastAPI service for authorized users to privately store, find, download, and delete source-code files from repositories they are permitted to access. It is a normal developer productivity product, not a tool for stealth, concealment, bypassing controls, or use during exams/interviews where assistance is prohibited.

## Handover purpose

This folder is the complete specification for an implementation agent. Build the extension in TypeScript, the API in Python/FastAPI, and use Supabase PostgreSQL plus private Supabase Storage. Follow the documents in this order:

1. [Product requirements](02-product-requirements.md)
2. [Architecture](03-system-architecture.md)
3. [Data and Supabase policies](04-data-model-and-supabase.md)
4. [API contract](05-rest-api-contract.md)
5. [Security model](06-security-and-threat-model.md)
6. [Execution plan](07-phased-execution-plan.md)
7. [Testing and acceptance](08-testing-and-acceptance.md)
8. [Setup, deployment, and publishing](09-setup-deployment-marketplace.md)
9. [Antigravity implementation prompt](10-antigravity-master-prompt.md)

## Explicit decisions

| Topic | Decision |
| --- | --- |
| Accounts | Local username/password accounts managed by the FastAPI service; no Supabase Auth. |
| Passwords | Argon2id via `pwdlib`/Argon2; never reversible or logged. |
| Sessions | Short-lived signed JWT access tokens (15 minutes) and rotating opaque refresh tokens (30 days) stored hashed in PostgreSQL. |
| Files | Source-code/text files only, maximum 1 MiB per file; private object storage. |
| Quota | 5,242,880 bytes per user, enforced transactionally by the backend before upload. |
| Storage access | Backend service role only. Extension gets file bytes only through authenticated API endpoints. |
| Search | PostgreSQL full-text search over file path and UTF-8 text content; unavailable for files above the preview/index limit. |
| Scope | One user owns each file. Sharing, teams, repository cloning, background syncing, telemetry, and hidden UI are out of scope for v1. |

## Proposed repository layout

```text
codevault/
  apps/
    extension/                 # VS Code extension (TypeScript)
    api/                       # FastAPI service (Python)
  infra/
    supabase/
      migrations/              # Schema, indexes, RLS, storage configuration
  docs/                        # This handover package
  .github/workflows/           # CI after core implementation works
  README.md
```

## Non-negotiable constraints

- Do not ship an extension feature that hides its presence, suppresses normal VS Code indicators, evades policy controls, or targets academic/exam cheating.
- Never put `SUPABASE_SERVICE_ROLE_KEY`, JWT signing keys, or user passwords in the extension, repository history, logs, screenshots, or documentation examples.
- All ownership, quota, file-type validation, and authorization checks are backend-enforced; UI validation is only a usability aid.
- Use only configuration placeholders in committed `.env.example` files.

## Definition of done

A user can register, log in, upload an authorized text/source file, see remaining quota, list and search only their files, download a selected file, delete it, log out, and install the extension from a Marketplace package. Automated tests demonstrate authorization and quota boundaries.
