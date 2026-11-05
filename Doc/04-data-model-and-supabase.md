# Data model, Supabase RLS, and Storage policies

## Schema

Apply SQL through versioned Supabase migrations. The service role creates application rows; migrations use explicit constraints and indexes.

```sql
create extension if not exists pgcrypto;

create table public.users (
  id uuid primary key default gen_random_uuid(),
  username text not null unique check (username ~ '^[a-z0-9_-]{3,32}$'),
  password_hash text not null,
  created_at timestamptz not null default now(),
  disabled_at timestamptz
);

create table public.user_quotas (
  user_id uuid primary key references public.users(id) on delete cascade,
  used_bytes bigint not null default 0 check (used_bytes >= 0 and used_bytes <= 5242880),
  quota_bytes bigint not null default 5242880 check (quota_bytes = 5242880),
  updated_at timestamptz not null default now()
);

create table public.refresh_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  replaced_by uuid references public.refresh_sessions(id),
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);
create index refresh_sessions_active_idx on public.refresh_sessions(user_id, expires_at) where revoked_at is null;

create table public.files (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users(id) on delete cascade,
  display_path text not null,
  storage_key text not null unique,
  language text not null,
  content_type text not null,
  byte_size integer not null check (byte_size > 0 and byte_size <= 1048576),
  sha256 char(64) not null,
  indexed_content text,
  search_vector tsvector generated always as (
    setweight(to_tsvector('simple', coalesce(display_path, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(indexed_content, '')), 'B')
  ) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, display_path, sha256)
);
create index files_owner_created_idx on public.files(owner_id, created_at desc, id desc);
create index files_search_idx on public.files using gin(search_vector);
```

Create `user_quotas` in the registration transaction. Update quota only while holding `SELECT ... FOR UPDATE` on the account’s quota row, then write exact deltas in the same database transaction as metadata changes.

## Private bucket

Create bucket `codevault-files` with `public = false`, allowed MIME types limited to `text/*`, `application/json`, and the source MIME types selected by the backend, and file-size limit `1048576`. Backend validates independently because bucket MIME metadata is not sufficient security control.

Object key format: `<owner UUID>/<file UUID>`. Do not derive keys from filenames or repository paths.

## RLS baseline

Enable RLS on all application tables. Because no direct client Supabase access is supported, deny access by default to `anon` and `authenticated`. Keep service-role use server-only; service-role bypasses RLS and must never leave FastAPI.

```sql
alter table public.users enable row level security;
alter table public.user_quotas enable row level security;
alter table public.refresh_sessions enable row level security;
alter table public.files enable row level security;

revoke all on public.users, public.user_quotas, public.refresh_sessions, public.files from anon, authenticated;
revoke all on storage.objects from anon, authenticated;
```

Optional future direct-access policy (not enabled in v1): map Supabase Auth `auth.uid()` to `owner_id` and permit only matching rows/first storage-key segment. Do not add that route without adopting Supabase Auth and removing the current local-JWT model.

## Retention and operations

- Deletion is permanent in v1. Backups and recovery follow the configured Supabase retention plan.
- A scheduled operational reconciliation job compares `files.storage_key` with private bucket keys and reports or removes verified orphans; it never exposes contents in logs.
- Store timestamps in UTC. Use UUIDs, parameterized SQL, and database migrations only.
