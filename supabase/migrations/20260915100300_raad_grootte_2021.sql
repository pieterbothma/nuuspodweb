-- Task 6 fix round 1 (review Important #1): council size and independent ward
-- councillors weren't stored anywhere, so "no majority" was computed against the
-- party-seat sum only — wrong when a council has independent ward councillors, since
-- they hold real council seats without belonging to any party. Adds a per-council
-- companion table (one row per council: printed council size B, and independent ward
-- councillors C from the same "Seat Calculation Detail" PDFs Task 6 already parses).
--
-- Shape matches the review's ruling exactly for the stg_ table (muni_kode as its own
-- primary key here, unlike stg_raad_uitslae_2021 which has many rows per council —
-- this table has exactly one). Public counterpart follows the existing
-- public/stg_ pairing convention from 20260915100000_verkiesing_fase2_basis.sql.

set search_path = public, extensions;

create table public.raad_grootte_2021 (
  muni_kode text primary key references public.munisipaliteite (kode),
  raadsgrootte_totaal int not null,
  onafhanklike_setels int not null default 0
);

create table public.stg_raad_grootte_2021 (
  muni_kode text primary key,
  raadsgrootte_totaal int not null,
  onafhanklike_setels int not null default 0
);

-- RLS + regte: publieke tabel (soos raad_uitslae_2021 in die basis-migrasie)
alter table public.raad_grootte_2021 enable row level security;

revoke all on public.raad_grootte_2021 from anon, authenticated;
grant select on public.raad_grootte_2021 to anon;

create policy "publiek lees raad_grootte_2021" on public.raad_grootte_2021
  for select to anon using (true);

-- RLS + regte: stg_-tabel — RLS aan, geen beleide, alles herroep (soos elke ander stg_).
alter table public.stg_raad_grootte_2021 enable row level security;

revoke all on public.stg_raad_grootte_2021 from anon, authenticated;

-- stg_leeg moet nou ook hierdie tabel kan leegmaak.
create or replace function public.stg_leeg(tabel text)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  toegelaat constant text[] := array[
    'stg_munisipaliteite', 'stg_wyke', 'stg_partye', 'stg_stemstasies', 'stg_kandidate',
    'stg_stembrief_volgorde', 'stg_raad_uitslae_2021', 'stg_raad_grootte_2021',
    'stg_plekke', 'stg_plek_wyke', 'stg_plek_aliasse'
  ];
begin
  if tabel is null or not (tabel = any (toegelaat)) then
    raise exception 'onbekende stg-tabel: %', coalesce(tabel, '<nul>');
  end if;

  execute format('truncate table public.%I', tabel);
end;
$$;

revoke all on function public.stg_leeg(text) from public, anon, authenticated;
grant execute on function public.stg_leeg(text) to service_role;
