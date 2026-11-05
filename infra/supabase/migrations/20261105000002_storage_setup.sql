-- Storage bucket setup for private XiVault files
-- Enforces public = false, 1 MiB limit, text MIME types, and denies direct client access.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'xivault-files',
  'xivault-files',
  false,
  1048576,
  array['text/*', 'application/json']
)
on conflict (id) do update set
  public = false,
  file_size_limit = 1048576;

revoke all on storage.objects from anon, authenticated;
