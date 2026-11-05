# Antigravity master implementation prompt

Copy the following prompt to Antigravity together with this entire `docs/` folder.

---

You are implementing **CodeVault** in this workspace. Read every file in `docs/` before editing. Treat them as the authoritative product and technical specification. If documents conflict, use this priority order: `README.md`, API contract, data model, security model, then execution plan.

Build a production-minded v1 in incremental phases. The product consists of a visible TypeScript VS Code extension, a Python 3.12 FastAPI backend, and Supabase PostgreSQL/private Storage. Its only permitted use is authorized repository/source-code storage. Do not implement hidden interfaces, background workspace scanning, stealth behavior, exam/interview cheating flows, bypass mechanisms, arbitrary binary storage, or any capability outside documented scope.

## Required implementation behavior

- Implement the repository structure and each phase in `07-phased-execution-plan.md` in order.
- Use Argon2id password hashes, signed 15-minute JWT access tokens, 30-day rotating opaque refresh tokens stored as hashes, and VS Code SecretStorage for the refresh token.
- Enforce the exact 5,242,880-byte per-user quota server-side under concurrency. Enforce the 1 MiB per-file limit, UTF-8/source-text rules, normalized display paths, authenticated ownership checks, and private backend-only Storage access.
- Implement every endpoint and error envelope in `05-rest-api-contract.md`; keep the OpenAPI schema accurate.
- Create versioned Supabase migrations for schema, indexes, RLS/revokes, and private bucket configuration. Do not place service role credentials in the extension.
- Add the mandatory tests and acceptance checks from `08-testing-and-acceptance.md`.

## Secrets and configuration

Never invent, guess, print, commit, or substitute secrets. Use only placeholders such as `USER_PROVIDED_LONG_RANDOM_SECRET` in `.env.example` files. When a real Supabase project, deployment host, Marketplace publisher, API domain, or secret is required, stop that specific external operation and state exactly which user-provided value is needed. Continue with any local/mock/test work that does not require it.

## Working protocol

1. First inspect the workspace and report the plan, assumptions, and existing files.
2. At the start and end of each phase, report: files changed, commands run, test/lint/build result, and any blocker. Use exact command output summaries; do not claim a command ran if it did not.
3. Keep changes small and coherent. Run focused tests immediately after each feature, then phase-wide tests before proceeding.
4. Use a strict TypeScript configuration and typed Python models. Prefer parameterized queries/ORM, explicit error types, safe logging, and no source-content logging.
5. If a test fails, diagnose and fix only issues caused by this implementation. Do not suppress tests, weaken security checks, or silently skip a phase.
6. Before packaging/publishing, run the documented full validation suite and provide a concise release checklist. Do not publish or create external accounts without explicit user authorization and required credentials.

## Final handoff format

When implementation is complete, provide:

- A concise summary mapped to the nine handover documents.
- Exact changed-file list.
- Exact commands executed and pass/fail results.
- Local run instructions.
- Tests not run and why.
- Required user-provided credentials/configuration, clearly labeled.
- Any remaining risks or deferred work.

Do not claim production deployment or Marketplace publication until the user has supplied the necessary credentials and explicitly requested those actions.
