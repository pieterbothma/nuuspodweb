-- Verkiesing 2026, Drop 1: headline rail, Verkiesings-Vrydag episodes, reader feedback.
-- Applied to project xxysgvanarnirxoxrbkj with the Supabase MCP apply_migration tool.

create table public.nuusstroom (
  id bigint generated always as identity primary key,
  titel text not null check (length(titel) between 1 and 500),
  bron text not null,
  bron_tipe text not null check (bron_tipe in ('nasionaal', 'streek', 'gemeenskap', 'openbare uitsaaier')),
  url text not null unique check (url ~ '^https?://'),
  gepubliseer_om timestamptz not null,
  ingevoeg_om timestamptz not null default now(),
  versteek boolean not null default false
);
create index nuusstroom_sigbaar_idx on public.nuusstroom (gepubliseer_om desc) where not versteek;

create table public.episodes (
  video_id text primary key check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  titel text not null,
  uitsaaidatum date not null,
  gepubliseer_om timestamptz,
  handmatig boolean not null default false,
  versteek boolean not null default false,
  bygewerk_om timestamptz not null default now()
);

create table public.terugvoer (
  id bigint generated always as identity primary key,
  bladsy text not null check (bladsy ~ '^/' and length(bladsy) <= 200),
  gevind boolean not null,
  geskep_om timestamptz not null default now()
);

alter table public.nuusstroom enable row level security;
alter table public.episodes enable row level security;
alter table public.terugvoer enable row level security;

revoke all on public.nuusstroom, public.episodes, public.terugvoer from anon, authenticated;
grant select on public.nuusstroom, public.episodes to anon;
grant insert (bladsy, gevind) on public.terugvoer to anon;

create policy "publiek lees sigbare stroom" on public.nuusstroom
  for select to anon using (not versteek);
create policy "publiek lees sigbare episodes" on public.episodes
  for select to anon using (not versteek);
create policy "publiek stuur terugvoer" on public.terugvoer
  for insert to anon with check (true);
