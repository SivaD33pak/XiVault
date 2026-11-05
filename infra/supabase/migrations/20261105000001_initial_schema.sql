-- Initial XiVault Schema Migration
-- Enables pgcrypto, sets up tables, constraints, indexes, and defense-in-depth RLS.

create extension if not exists pgcrypto;

-- 1. Users table
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  username text not null unique check (username ~ '^[a-z0-9_-]{3,32}$'),
  password_hash text not null,
  created_at timestamptz not null default now(),
  disabled_at timestamptz
);

-- 2. User Quotas table (15 MiB total per user)
create table if not exists public.user_quotas (
  user_id uuid primary key references public.users(id) on delete cascade,
  used_bytes bigint not null default 0 check (used_bytes >= 0 and used_bytes <= 15728640),
  quota_bytes bigint not null default 15728640 check (quota_bytes = 15728640),
  updated_at timestamptz not null default now()
);

-- 3. Refresh Sessions table
create table if not exists public.refresh_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  replaced_by uuid references public.refresh_sessions(id),
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

create index if not exists refresh_sessions_active_idx 
  on public.refresh_sessions(user_id, expires_at) 
  where revoked_at is null;

-- 4. Files table (Max 1 MiB per file, GIN full-text search)
create table if not exists public.files (
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

create index if not exists files_owner_created_idx 
  on public.files(owner_id, created_at desc, id desc);

create index if not exists files_search_idx 
  on public.files using gin(search_vector);

-- 5. Enable Row-Level Security (RLS) on all tables
alter table public.users enable row level security;
alter table public.user_quotas enable row level security;
alter table public.refresh_sessions enable row level security;
alter table public.files enable row level security;

-- 6. Deny all direct client access (FastAPI service role only)
revoke all on public.users, public.user_quotas, public.refresh_sessions, public.files from anon, authenticated;
