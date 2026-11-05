# XiVault

XiVault is a secure developer productivity platform consisting of a **VS Code Marketplace Extension** and a **FastAPI service** for authorized developers to privately archive, search, download, and manage their source-code files.

Backed by **Supabase PostgreSQL** and **Supabase Private Storage**, XiVault provides strict owner isolation, transactional per-user quota controls, and encrypted token session management.

## Project Structure

```text
xivault/
  apps/
    api/                       # FastAPI service (Python 3.12+)
    extension/                 # VS Code extension (TypeScript)
  infra/
    supabase/
      migrations/              # Schema, indexes, RLS, storage bucket configuration
  Doc/                         # Specification and handover package
  .github/workflows/           # Continuous Integration
  README.md
```

## Core Specifications

* [Product Requirements](Doc/02-product-requirements.md)
* [System Architecture](Doc/03-system-architecture.md)
* [Data Model & Supabase](Doc/04-data-model-and-supabase.md)
* [REST API Contract](Doc/05-rest-api-contract.md)
* [Security & Threat Model](Doc/06-security-and-threat-model.md)
* [Execution Plan](Doc/07-phased-execution-plan.md)
* [Testing & Acceptance](Doc/08-testing-and-acceptance.md)
* [Setup & Deployment](Doc/09-setup-deployment-marketplace.md)

## Getting Started

### Backend (`apps/api`)
1. Create virtual environment:
   ```bash
   cd apps/api
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\Activate.ps1 on Windows
   pip install -r requirements.txt
   ```
2. Copy configuration:
   ```bash
   cp .env.example .env
   ```
3. Run API:
   ```bash
   uvicorn xivault.main:app --reload --port 8000
   ```

### Extension (`apps/extension`)
1. Install dependencies and build:
   ```bash
   cd apps/extension
   npm install
   npm run compile
   ```
2. Press `F5` in VS Code to launch the Extension Development Host.
