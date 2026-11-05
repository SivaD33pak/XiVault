# Testing strategy and acceptance criteria

## Test layers

| Layer | Scope | Required examples |
| --- | --- | --- |
| Unit | Pure backend/extension logic | username/password/path validation, MIME map, hash, cursor codec, JWT claim validation, refresh hashing. |
| API integration | FastAPI + ephemeral PostgreSQL/Supabase test environment | auth lifecycle, quota lock/delta, ownership checks, file validation, search, download, delete. |
| Database policy | migrations and roles | RLS enabled, `anon`/`authenticated` denied, constraints/indexes present. |
| Extension | VS Code test host/mocks | SecretStorage behavior, command registration, picker/confirm flow, retry-once refresh, error UI. |
| End-to-end | packaged extension + staging API | register through delete, login persistence, remaining quota, download read-only. |
| Security/regression | CI | dependency audit, secret scan, static analysis, malformed token/input corpus. |

## Mandatory test cases

- Register creates exactly one quota row; duplicate username returns `409`.
- Password hash is never equal to input and does not appear in response or logs.
- Login fails with the same external response for unknown username and wrong password.
- Expired/malformed/wrong-audience JWTs return `401`.
- Refresh token rotation invalidates old token; replay revokes all sessions.
- User A cannot list, search, download, or delete User B’s file, including guessed UUIDs.
- Upload rejects binary data, invalid UTF-8, unsupported extension/MIME, absolute/traversal path, zero-byte file, and 1,048,577-byte file.
- Concurrent uploads that individually fit but jointly exceed 5,242,880 bytes allow at most the quota amount.
- Failed metadata insertion removes the just-uploaded storage object; failed deletion never creates negative quota.
- Search treats special characters as input, not SQL; result is owner-scoped and paginated.
- Extension never persists access tokens to settings or logs; refresh token is cleared by logout.

## Acceptance criteria

1. All required test suites run with documented commands and pass on a clean checkout.
2. Coverage targets: 80% backend line coverage and 70% extension line coverage, with all authorization/quota branches explicitly covered. Targets do not replace meaningful tests.
3. `ruff`/`mypy` (or selected equivalent) pass for API; `eslint`/TypeScript strict compile pass for extension.
4. Production build has no known critical dependency vulnerability without a documented, user-approved exception.
5. Manual staging smoke test completes register → upload → list → search → download → delete → logout.
6. A reviewer confirms no source content, credentials, or tokens occur in diagnostic logs/test fixtures.

## Test data rules

Use invented harmless source snippets and random test credentials. Do not place real repositories, private keys, personal data, or service credentials in fixtures or screenshots.
