-- "Die nuutste van die IEC" (Piet, 2026-09-17): the IEC's own press releases, headline verbatim,
-- linked to the release on elections.org.za. Official and unedited, so no approval step.

create table if not exists public.ovk_nuus (
  -- The IEC's own item number (___item on the news list); the release page is
  -- https://www.elections.org.za/pw/News-And-Media/News-List/News/IECNews/<id>.
  id integer primary key,
  titel text not null,
  datum date not null,
  url text not null,
  geskep_om timestamptz not null default now()
);

create index if not exists ovk_nuus_datum_idx on public.ovk_nuus (datum desc, id desc);

alter table public.ovk_nuus enable row level security;

drop policy if exists "publiek lees ovk-nuus" on public.ovk_nuus;
create policy "publiek lees ovk-nuus" on public.ovk_nuus
  for select to anon, authenticated using (true);
