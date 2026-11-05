# Phased execution plan

Each phase is complete only when its deliverables and focused tests pass. Do not begin a dependent phase with known failing tests.

## Phase 0 — Bootstrap and guardrails

**Dependencies:** none.  
**Deliverables:** monorepo layout; Python 3.12 FastAPI project; Node 20+ TypeScript extension project; formatters/linting; `.gitignore`; `.env.example` files; CI skeleton; `LICENSE`; root README linking this package.  
**Exit checks:** API starts locally, extension compiles, no real secret is committed.

## Phase 1 — Database and Supabase

**Dependencies:** Phase 0; user-provided Supabase project credentials.  
**Deliverables:** migration files implementing the schema, indexes, RLS/revokes, private `codevault-files` bucket setup, local Supabase instructions, and seed-free migration test.  
**Exit checks:** migration applies to a clean local database; `anon` cannot select application rows or storage objects.

## Phase 2 — Authentication API

**Dependencies:** Phase 1; `CODEVAULT_JWT_SECRET` from user/operator.  
**Deliverables:** config validation, user/quota creation, Argon2 registration/login, signed access token, hashed rotating refresh sessions, logout, rate limiting, error envelope/request ID, unit and API tests.  
**Exit checks:** invalid credentials do not reveal account existence; refresh replay revokes sessions; protected route rejects invalid/expired token.

## Phase 3 — Vault API

**Dependencies:** Phase 2; server-only Supabase URL/service-role key.  
**Deliverables:** source/text validation, safe MIME/language map, SHA-256, quota locking, private upload, list/cursor, FTS search, proxied download, delete and cleanup/reconciliation hooks.  
**Exit checks:** owner isolation, 1 MiB file bound, exact 5 MiB quota, duplicate behavior, rollback cleanup, content stream integrity.

## Phase 4 — VS Code extension

**Dependencies:** Phase 2; Phase 3 for end-to-end paths.  
**Deliverables:** configuration, SecretStorage session manager, auth commands, visible CodeVault view, quota status, explicit upload picker/confirmation, list/search/download/delete commands, accessible progress/error UX, unit tests with VS Code mocks.  
**Exit checks:** extension has no embedded service credentials; logout clears secret; no background scanning or upload.

## Phase 5 — Integration, packaging, and operations

**Dependencies:** Phases 1–4.  
**Deliverables:** Dockerfile, deployment config for selected host, health/readiness routes, production config checklist, CI tests/build/package, VSIX package, Marketplace listing assets/text, privacy policy and support contact placeholders.  
**Exit checks:** clean environment deployment works with user-provided secrets; VSIX installs and completes a smoke test against staging.

## Phase 6 — Release gate

**Dependencies:** Phase 5.  
**Deliverables:** threat-model review, dependency/license review, rollback instructions, release notes, signed version tag only if user requests it.  
**Exit checks:** all acceptance criteria pass and the operator has confirmed production secrets, Supabase backup settings, support contact, privacy policy URL, and Marketplace publisher ownership.
