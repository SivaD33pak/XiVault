# Local setup, deployment, and Marketplace publishing

## Prerequisites

- Node.js 20 LTS or later and npm/pnpm.
- Python 3.12 and a virtual environment manager.
- Docker Desktop for local services (recommended).
- A user-owned Supabase project; Supabase CLI is recommended for local migrations.
- A deployment host selected by the user (container-capable HTTPS host).
- A Microsoft/Visual Studio Marketplace publisher account for publishing.

## Configuration

Create local `.env` files from examples; do not commit them.

```dotenv
# apps/api/.env.example
CODEVAULT_ENV=development
CODEVAULT_API_ORIGIN=http://127.0.0.1:8000
CODEVAULT_JWT_SECRET=USER_PROVIDED_LONG_RANDOM_SECRET
CODEVAULT_JWT_ISSUER=codevault-api
CODEVAULT_JWT_AUDIENCE=codevault-extension
SUPABASE_URL=https://USER_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=USER_PROVIDED_SERVER_ONLY_SECRET
DATABASE_URL=postgresql://USER_PROVIDED_LOCAL_OR_MANAGED_CONNECTION
RATE_LIMIT_BACKEND_URL=USER_PROVIDED_REDIS_OR_DATABASE_URL
```

```json
// apps/extension/.vscode/settings.json (development only)
{ "codevault.apiBaseUrl": "http://127.0.0.1:8000/v1" }
```

The extension must never receive `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, or `CODEVAULT_JWT_SECRET`.

## Local workflow

1. Provision or start local Supabase, then apply `infra/supabase/migrations` in order.
2. Configure API placeholders with values supplied by the user/operator.
3. Create Python environment, install locked API dependencies, run migrations, then start FastAPI in development mode.
4. Install locked extension dependencies, compile/watch TypeScript, and launch the Extension Development Host from VS Code.
5. Run focused API and extension tests before broader test/lint/package commands. Document actual commands in the root README as implementation is created.

## Production deployment

- Build a minimal non-root API container. Run a production ASGI server behind HTTPS; set trusted proxy/host configuration correctly.
- Inject secrets through the host’s secret manager, not build arguments, source control, or plain deployment manifests.
- Run migrations as a controlled release step before rolling the compatible API version.
- Configure `/healthz` (process alive) and `/readyz` (database/storage dependency check without secret disclosure).
- Set alerting for 5xx errors, authentication abuse/rate limits, storage failures, and reconciliation findings. Back up the database per the selected Supabase plan.
- Roll back API image only after verifying migration compatibility; never roll back destructive schema changes without an explicit migration plan.

## Marketplace publishing

1. Choose a unique extension identifier: `USER_PUBLISHER.codevault`; update `package.json` with publisher, display name, version, repository, license, privacy policy URL, support URL, and categories.
2. Create Marketplace publisher credentials/personal access token in the publisher account. Store it only in the user’s secure secret manager or CI secret store.
3. Write a transparent Marketplace README: authorized repository use only; no stealth features; data types collected; API domain; privacy/support links; authentication and deletion behavior.
4. Validate manifest, package a `.vsix`, and install it locally for a clean-profile smoke test.
5. Publish first to a pre-release channel, verify installed behavior against staging, then publish stable after release gate approval.

## Release checklist

- [ ] Production domain and TLS are live.
- [ ] User-provided secrets exist only in server/CI secret stores.
- [ ] Bucket is private and migrations/RLS verified.
- [ ] Privacy policy and support contact are public.
- [ ] Marketplace publisher and extension ownership are confirmed by the user.
- [ ] Staging smoke test and automated checks passed.
