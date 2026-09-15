-- Verkiesing 2026, Fase 2a: wyk-soeker basisdata.
-- Skema, stg_-tabelle en bedienerfunksies (service-role only).
-- Applied to project xxysgvanarnirxoxrbkj with the Supabase MCP apply_migration tool.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 0. Uitbreidings
-- ---------------------------------------------------------------------------
create extension if not exists postgis with schema extensions;
create extension if not exists pg_trgm with schema extensions;

-- ---------------------------------------------------------------------------
-- 1. Publieke tabelle (spec §4)
-- ---------------------------------------------------------------------------

create table public.munisipaliteite (
  kode text primary key,
  naam text not null,
  tipe text not null check (tipe in ('metro', 'plaaslik', 'distrik')),
  distrik_kode text references public.munisipaliteite (kode),
  provinsie text not null
);

create table public.wyke (
  wyk_id text primary key check (wyk_id ~ '^\d{8}$'),
  wyk_nr int not null,
  muni_kode text not null references public.munisipaliteite (kode),
  geom extensions.geometry(MultiPolygon, 4326)
);

create table public.partye (
  id bigint generated always as identity primary key,
  naam text not null,
  afkorting text
);

create table public.stemstasies (
  vd_nommer text primary key,
  naam text not null,
  adres text not null,
  wyk_id text not null references public.wyke (wyk_id),
  muni_kode text not null references public.munisipaliteite (kode),
  bron_lêer text not null,
  bron_ry int not null
);

create table public.kandidate (
  id bigint generated always as identity primary key,
  muni_kode text not null references public.munisipaliteite (kode),
  stembrief text not null check (stembrief in ('wyk', 'pv_plaaslik', 'pv_distrik')),
  wyk_id text references public.wyke (wyk_id),
  lys_posisie int,
  party_id bigint references public.partye (id),
  onafhanklik boolean not null default false,
  volle_naam text not null,
  van text not null,
  bron_lêer text not null,
  bron_ry int not null
);

create table public.stembrief_volgorde (
  muni_kode text not null references public.munisipaliteite (kode),
  stembrief text not null check (stembrief in ('wyk', 'pv_plaaslik', 'pv_distrik')),
  party_id bigint not null references public.partye (id),
  posisie int not null,
  primary key (muni_kode, stembrief, party_id)
);

create table public.raad_uitslae_2021 (
  muni_kode text not null references public.munisipaliteite (kode),
  party_naam text not null,
  setels_wyk int not null default 0,
  setels_pv int not null default 0,
  setels_totaal int not null default 0,
  primary key (muni_kode, party_naam)
);

create table public.plekke (
  sp_kode text primary key,
  naam text not null,
  naam_soek text not null,
  mp_naam text,
  landelik boolean not null default false,
  geom extensions.geometry(MultiPolygon, 4326)
);

create table public.plek_wyke (
  sp_kode text not null references public.plekke (sp_kode),
  wyk_id text not null references public.wyke (wyk_id),
  oorvleueling numeric not null check (oorvleueling >= 0),
  primary key (sp_kode, wyk_id)
);

create table public.plek_aliasse (
  id bigint generated always as identity primary key,
  alias text not null,
  sp_kode text not null references public.plekke (sp_kode),
  unique (alias, sp_kode)
);

create table public.data_weergawes (
  id bigint generated always as identity primary key,
  datastel text not null,
  bron_url text,
  bron_datum date,
  rye int,
  gelaai_om timestamptz,
  gepubliseer_om timestamptz
);

-- ---------------------------------------------------------------------------
-- 2. stg_-tabelle: identiese vorm, geen FK's, geen PK/indekse op id.
--    (LIKE ... INCLUDING DEFAULTS INCLUDING CONSTRAINTS bring NOT NULL en
--    CHECK-beperkings oor, maar geen FK's, PK's of identity nie.)
-- ---------------------------------------------------------------------------

create table public.stg_munisipaliteite (like public.munisipaliteite including defaults including constraints);
create table public.stg_wyke (like public.wyke including defaults including constraints);
create table public.stg_partye (like public.partye including defaults including constraints);
create table public.stg_stemstasies (like public.stemstasies including defaults including constraints);
create table public.stg_kandidate (like public.kandidate including defaults including constraints);
create table public.stg_stembrief_volgorde (like public.stembrief_volgorde including defaults including constraints);
create table public.stg_raad_uitslae_2021 (like public.raad_uitslae_2021 including defaults including constraints);
create table public.stg_plekke (like public.plekke including defaults including constraints);
create table public.stg_plek_wyke (like public.plek_wyke including defaults including constraints);
create table public.stg_plek_aliasse (like public.plek_aliasse including defaults including constraints);

-- LIKE always copies NOT NULL, including the implicit NOT NULL from the
-- source's "generated always as identity" id columns — but it does NOT copy
-- the identity generation itself (needs INCLUDING IDENTITY, which would also
-- pull in the FK-adjacent sequence ownership we don't want on staging).
-- Loaders don't supply ids, so relax those three columns back to nullable.
alter table public.stg_partye alter column id drop not null;
alter table public.stg_kandidate alter column id drop not null;
alter table public.stg_plek_aliasse alter column id drop not null;
-- data_weergawes deliberately has no stg_ mirror (brief §Public tables note).

-- ---------------------------------------------------------------------------
-- 3. RLS + regte: publieke tabelle
-- ---------------------------------------------------------------------------

alter table public.munisipaliteite enable row level security;
alter table public.wyke enable row level security;
alter table public.partye enable row level security;
alter table public.stemstasies enable row level security;
alter table public.kandidate enable row level security;
alter table public.stembrief_volgorde enable row level security;
alter table public.raad_uitslae_2021 enable row level security;
alter table public.plekke enable row level security;
alter table public.plek_wyke enable row level security;
alter table public.plek_aliasse enable row level security;
alter table public.data_weergawes enable row level security;

revoke all on public.munisipaliteite, public.wyke, public.partye, public.stemstasies,
  public.kandidate, public.stembrief_volgorde, public.raad_uitslae_2021, public.plekke,
  public.plek_wyke, public.plek_aliasse, public.data_weergawes
  from anon, authenticated;

grant select on public.munisipaliteite, public.wyke, public.partye, public.stemstasies,
  public.kandidate, public.stembrief_volgorde, public.raad_uitslae_2021, public.plekke,
  public.plek_wyke, public.plek_aliasse, public.data_weergawes
  to anon;

create policy "publiek lees munisipaliteite" on public.munisipaliteite for select to anon using (true);
create policy "publiek lees wyke" on public.wyke for select to anon using (true);
create policy "publiek lees partye" on public.partye for select to anon using (true);
create policy "publiek lees stemstasies" on public.stemstasies for select to anon using (true);
create policy "publiek lees kandidate" on public.kandidate for select to anon using (true);
create policy "publiek lees stembrief_volgorde" on public.stembrief_volgorde for select to anon using (true);
create policy "publiek lees raad_uitslae_2021" on public.raad_uitslae_2021 for select to anon using (true);
create policy "publiek lees plekke" on public.plekke for select to anon using (true);
create policy "publiek lees plek_wyke" on public.plek_wyke for select to anon using (true);
create policy "publiek lees plek_aliasse" on public.plek_aliasse for select to anon using (true);
create policy "publiek lees data_weergawes" on public.data_weergawes for select to anon using (true);

-- ---------------------------------------------------------------------------
-- 4. RLS + regte: stg_-tabelle — RLS aan, geen beleide, alles herroep.
-- ---------------------------------------------------------------------------

alter table public.stg_munisipaliteite enable row level security;
alter table public.stg_wyke enable row level security;
alter table public.stg_partye enable row level security;
alter table public.stg_stemstasies enable row level security;
alter table public.stg_kandidate enable row level security;
alter table public.stg_stembrief_volgorde enable row level security;
alter table public.stg_raad_uitslae_2021 enable row level security;
alter table public.stg_plekke enable row level security;
alter table public.stg_plek_wyke enable row level security;
alter table public.stg_plek_aliasse enable row level security;

revoke all on public.stg_munisipaliteite, public.stg_wyke, public.stg_partye,
  public.stg_stemstasies, public.stg_kandidate, public.stg_stembrief_volgorde,
  public.stg_raad_uitslae_2021, public.stg_plekke, public.stg_plek_wyke, public.stg_plek_aliasse
  from anon, authenticated;

-- ---------------------------------------------------------------------------
-- 5. Indekse
-- ---------------------------------------------------------------------------

create index wyke_geom_gix on public.wyke using gist (geom);
create index plekke_geom_gix on public.plekke using gist (geom);
create index stg_wyke_geom_gix on public.stg_wyke using gist (geom);
create index stg_plekke_geom_gix on public.stg_plekke using gist (geom);

create index plekke_naam_soek_trgm on public.plekke using gin (naam_soek extensions.gin_trgm_ops);
create index plek_aliasse_alias_trgm on public.plek_aliasse using gin (alias extensions.gin_trgm_ops);
create index stemstasies_naam_trgm on public.stemstasies using gin (naam extensions.gin_trgm_ops);
create index stemstasies_adres_trgm on public.stemstasies using gin (adres extensions.gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- 6. Bedienerfunksies (service-role only)
-- ---------------------------------------------------------------------------

create or replace function public.stg_leeg(tabel text)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  toegelaat constant text[] := array[
    'stg_munisipaliteite', 'stg_wyke', 'stg_partye', 'stg_stemstasies', 'stg_kandidate',
    'stg_stembrief_volgorde', 'stg_raad_uitslae_2021', 'stg_plekke', 'stg_plek_wyke', 'stg_plek_aliasse'
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

create or replace function public.bou_plek_wyke()
returns integer
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  ingevoeg integer;
begin
  delete from public.stg_plek_wyke;

  insert into public.stg_plek_wyke (sp_kode, wyk_id, oorvleueling)
  select x.sp_kode, x.wyk_id, (x.deursnyding_m2 / nullif(x.plek_area_m2, 0))
  from (
    select
      p.sp_kode,
      w.wyk_id,
      ST_Area(ST_Intersection(p.geom, w.geom)::geography) as deursnyding_m2,
      ST_Area(p.geom::geography) as plek_area_m2
    from public.stg_plekke p
    join public.stg_wyke w
      on p.geom is not null
     and w.geom is not null
     and ST_Intersects(p.geom, w.geom)
  ) x
  where (x.deursnyding_m2 / nullif(x.plek_area_m2, 0)) >= 0.05
     or x.deursnyding_m2 >= 10000;

  get diagnostics ingevoeg = row_count;
  return ingevoeg;
end;
$$;

revoke all on function public.bou_plek_wyke() from public, anon, authenticated;
grant execute on function public.bou_plek_wyke() to service_role;

create or replace function public.kontroleer_wyke()
returns table (
  wyke_totaal int,
  met_geom int,
  sonder_geom int,
  selftoets_geslaag int,
  selftoets_gefaal int,
  gefaalde_ids text[]
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_totaal int;
  v_met int;
  v_sonder int;
  v_geslaag int := 0;
  v_gefaal int := 0;
  v_gefaalde text[] := array[]::text[];
  ry record;
  treffers text[];
begin
  select count(*) into v_totaal from public.stg_wyke;
  select count(*) into v_met from public.stg_wyke where geom is not null;
  v_sonder := v_totaal - v_met;

  for ry in
    select w.wyk_id, ST_PointOnSurface(w.geom) as punt
    from public.stg_wyke w
    where w.geom is not null
  loop
    select array_agg(w2.wyk_id) into treffers
    from public.stg_wyke w2
    where w2.geom is not null
      and ST_Contains(w2.geom, ry.punt);

    if treffers is not null and array_length(treffers, 1) = 1 and treffers[1] = ry.wyk_id then
      v_geslaag := v_geslaag + 1;
    else
      v_gefaal := v_gefaal + 1;
      v_gefaalde := v_gefaalde || ry.wyk_id;
    end if;
  end loop;

  return query select v_totaal, v_met, v_sonder, v_geslaag, v_gefaal, v_gefaalde;
end;
$$;

revoke all on function public.kontroleer_wyke() from public, anon, authenticated;
grant execute on function public.kontroleer_wyke() to service_role;
