-- Verkiesing 2026, Fase 2b, Task 1: soek-, punt- en publiseer-RPCs.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- Bevat, in hierdie orde:
--   1. normaliseer_soekteks(text)      — SQL-eweknie van data/lib/teks.py:normaliseer
--   2. plekke.mp_naam_soek (+ stg_)    — hoofplek-naam, genormaliseer, sonder NU/SH-agtervoegsel
--   3. indekse                          — trigram/GiST/btree vir soek() en vind_wyk()
--   4. vind_wyk(lat, lng)              — punt-in-veelhoek, anon
--   5. soek(q)                          — plek- en stemlokaal-soek, anon
--   6. publiseer_leeg / publiseer_tabel / publiseer_afrond — service_role only

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. normaliseer_soekteks
--
-- Must produce byte-for-byte what data/lib/teks.py:normaliseer produces, because
-- plekke.naam_soek is written by the Python loader and compared against this
-- function's output inside soek().
--
-- Python does: strip -> lower -> NFKD + drop combining marks -> [-'’] to space ->
-- squeeze whitespace -> strip. It does NOT drop other punctuation, so neither does
-- this function ("Alf. Blv" -> "alf. blv", "Bayimani (Dayimani)" ->
-- "bayimani (dayimani)"). The task brief's summary line says "punctuation dropped";
-- dropping it here would break every exact/prefix comparison against naam_soek, so
-- the "produce exactly what normaliseer produces" requirement wins.
--
-- The database has no `unaccent`, so accents are folded with translate() over the
-- lowercase Latin-1 Supplement / Latin Extended-A letters whose NFKD form is a single
-- ASCII letter. lower() runs first, so no uppercase mappings are needed. Characters
-- that NFKD does not decompose (ø, æ, ß, đ, ł, ...) are deliberately left alone,
-- because Python leaves them alone too. Verified against all 22 196 stg_plekke rows:
-- 0 differences between this expression and the stored naam_soek.
-- ---------------------------------------------------------------------------

create or replace function public.normaliseer_soekteks(t text)
returns text
language sql
immutable
strict
parallel safe
set search_path = public, extensions
as $$
  select btrim(
    regexp_replace(
      translate(
        translate(
          lower(btrim(t)),
          'àáâãäåçèéêëìíîïñòóôõöùúûüýÿāăąćĉċčďēĕėęěĝğġģĥĩīĭįĵķĺļľńņňōŏőŕŗřśŝşšţťũūŭůűųŵŷźżžſ',
          'aaaaaaceeeeiiiinooooouuuuyyaaaccccdeeeeegggghiiiijklllnnnooorrrssssttuuuuuuwyzzzs'
        ),
        '-''’',
        '   '
      ),
      '\s+', ' ', 'g'
    )
  );
$$;

revoke all on function public.normaliseer_soekteks(text) from public;
grant execute on function public.normaliseer_soekteks(text) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 2. mp_naam_soek
--
-- Stats SA's MainPlace names carry the same " NU"/" SH" rural suffixes as the
-- sub-place names (527 of 22 196 rows), and they are what makes a query like
-- "Soweto" — a main place with ~97 sub places named Diepkloof, Orlando, Pimville,
-- ... — findable at all.
-- ---------------------------------------------------------------------------

alter table public.plekke add column if not exists mp_naam_soek text;
alter table public.stg_plekke add column if not exists mp_naam_soek text;

-- Backfill. Runs on the migration (direct SQL) connection, not through PostgREST, so
-- the authenticator role's 8s statement_timeout does not apply; public.plekke is empty
-- at this point and stg_plekke is 22 196 rows (~1s).
update public.plekke
   set mp_naam_soek = public.normaliseer_soekteks(regexp_replace(mp_naam, '\s+(NU|SH)$', ''))
 where mp_naam is not null;

update public.stg_plekke
   set mp_naam_soek = public.normaliseer_soekteks(regexp_replace(mp_naam, '\s+(NU|SH)$', ''))
 where mp_naam is not null;

-- ---------------------------------------------------------------------------
-- 3. Indekse
--
-- Already present from 20260915082741_verkiesing_fase2_basis.sql and therefore not
-- recreated here: wyke_geom_gix, plekke_geom_gix (GiST), plekke_naam_soek_trgm,
-- plek_aliasse_alias_trgm, stemstasies_naam_trgm, stemstasies_adres_trgm (GIN trigram).
--
-- Two of the brief's btree indexes are also skipped as exact duplicates of an
-- existing primary key's leading column, which already serves those lookups:
--   plek_wyke.sp_kode          -> plek_wyke_pkey (sp_kode, wyk_id)
--   raad_uitslae_2021.muni_kode -> raad_uitslae_2021_pkey (muni_kode, party_naam)
--
-- The two stemstasies expression indexes are an addition to the brief's list. soek()
-- must compare the *normalised* station name/address (119 of 23 696 names are
-- non-ASCII, so "Morelig" has to find "MÔRELIG ..."), and a seq scan doing that was
-- measured at ~1s for stations alone — too close to the 8s PostgREST budget for a
-- search box. Because these indexes depend on normaliseer_soekteks, any future change
-- to that function's body needs a REINDEX of both.
-- ---------------------------------------------------------------------------

create index if not exists plekke_mp_naam_soek_trgm
  on public.plekke using gin (mp_naam_soek extensions.gin_trgm_ops);

create index if not exists stemstasies_naam_soek_trgm
  on public.stemstasies using gin (public.normaliseer_soekteks(naam) extensions.gin_trgm_ops);

create index if not exists stemstasies_adres_soek_trgm
  on public.stemstasies using gin (public.normaliseer_soekteks(adres) extensions.gin_trgm_ops);

create index if not exists plek_wyke_wyk_id_idx on public.plek_wyke (wyk_id);
create index if not exists stemstasies_wyk_id_idx on public.stemstasies (wyk_id);
create index if not exists kandidate_wyk_id_idx on public.kandidate (wyk_id);
create index if not exists kandidate_muni_kode_idx on public.kandidate (muni_kode);

-- ---------------------------------------------------------------------------
-- 4. vind_wyk
-- ---------------------------------------------------------------------------

create or replace function public.vind_wyk(lat double precision, lng double precision)
returns table (wyk_id text, wyk_nr int, muni_kode text, muni_naam text)
language sql stable security invoker
set search_path = public, extensions
as $$
  select w.wyk_id, w.wyk_nr, w.muni_kode, m.naam
  from public.wyke w
  join public.munisipaliteite m on m.kode = w.muni_kode
  where w.geom is not null
    and lat between -35.0 and -21.0 and lng between 15.0 and 34.0
    and extensions.ST_Intersects(w.geom, extensions.ST_SetSRID(extensions.ST_MakePoint(lng, lat), 4326))
  limit 1;
$$;

revoke all on function public.vind_wyk(double precision, double precision) from public;
grant execute on function public.vind_wyk(double precision, double precision) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 5. soek
--
-- Three place sources (alias, sub-place name, main-place name) and one station source,
-- each carrying a match class: 1 exact, 2 prefix, 3 trigram (similarity > 0.3).
--
-- pg_trgm's `%` operator is index-usable where a bare similarity() call is not, so it
-- carries the class-3 prefilter. The prefix test covers the exact test (an exact match
-- is also a prefix), so the WHERE clauses only need `like` + `%`, and the CASE then
-- assigns the class.
--
-- LIKE metacharacters in the (user-supplied) query are escaped into `qlike`, because
-- normaliseer_soekteks keeps % and _.
--
-- SUPERSEDED by 20260916063223_soek_streng_gelykenis.sql: `%` turned out to be
-- similarity >= threshold, not > threshold, which let a similarity-exactly-0.3 row
-- through, so class 3 now carries an explicit `similarity(...) > 0.3` check. That
-- migration also dropped the `set pg_trgm.similarity_threshold to '0.3'` clause this
-- function was first created with — `pg_trgm` is a reserved GUC prefix, so setting it
-- is superuser-only in any backend that has not already loaded pg_trgm's library, and
-- the clause is removed here too so a replay of this migration cannot fail with 42501.
-- ---------------------------------------------------------------------------

create or replace function public.soek(q text)
returns table (
  soort text,
  etiket text,
  muni_kode text,
  muni_naam text,
  wyk_ids text[],
  wyk_nrs int[],
  teiken text,
  rang int
)
language plpgsql
stable
security invoker
set search_path = public, extensions
as $$
#variable_conflict use_column
declare
  qn text := public.normaliseer_soekteks(coalesce(q, ''));
  qlike text;
  -- The three harbour slivers (Piet, 2026-09-15): Stats SA sub places with no 2026
  -- ward at all. Excluded from search by code, not only by the plek_wyke join.
  hawe constant text[] := array['199056003', '199057014', '199063016'];
begin
  if qn is null or length(qn) < 2 then
    return;
  end if;

  qlike := replace(replace(replace(qn, '\', '\\'), '%', '\%'), '_', '\_') || '%';

  return query
  with alias_treffers as (
    select a.sp_kode,
           min(case
                 when public.normaliseer_soekteks(a.alias) = qn then 1
                 when public.normaliseer_soekteks(a.alias) like qlike then 2
                 else 3
               end) as klas
    from public.plek_aliasse a
    where public.normaliseer_soekteks(a.alias) like qlike
       or public.normaliseer_soekteks(a.alias) % qn
    group by a.sp_kode
  ),
  naam_treffers as (
    select p.sp_kode,
           case
             when p.naam_soek = qn then 1
             when p.naam_soek like qlike then 2
             else 3
           end as klas
    from public.plekke p
    where p.naam_soek like qlike
       or p.naam_soek % qn
  ),
  mp_treffers as (
    select p.sp_kode,
           case
             when p.mp_naam_soek = qn then 1
             when p.mp_naam_soek like qlike then 2
             else 3
           end as klas
    from public.plekke p
    where p.mp_naam_soek is not null
      and (p.mp_naam_soek like qlike or p.mp_naam_soek % qn)
  ),
  -- van_naam: the hit came from the sub-place name or an alias, so the display label is
  -- plekke.naam. A main-place-only hit labels itself with the cleaned mp_naam.
  plek_kandidate as (
    select t.sp_kode, t.klas, true as van_naam from alias_treffers t
    union all
    select t.sp_kode, t.klas, true as van_naam from naam_treffers t
    union all
    select t.sp_kode, t.klas, false as van_naam from mp_treffers t
  ),
  plek_beste as (
    select k.sp_kode, min(k.klas)::int as klas, bool_or(k.van_naam) as van_naam
    from plek_kandidate k
    group by k.sp_kode
  ),
  plek_rye as (
    select
      case when pb.van_naam
           then p.naam
           else btrim(regexp_replace(p.mp_naam, '\s+(NU|SH)$', ''))
      end as etiket,
      w.muni_kode as muni_kode,
      m.naam as muni_naam,
      pb.klas as klas,
      p.landelik as landelik,
      case when m.tipe = 'metro' then 0 else 1 end as metro_rang,
      w.wyk_id as wyk_id,
      w.wyk_nr as wyk_nr
    from plek_beste pb
    join public.plekke p on p.sp_kode = pb.sp_kode
    join public.plek_wyke pw on pw.sp_kode = pb.sp_kode
    join public.wyke w on w.wyk_id = pw.wyk_id
    join public.munisipaliteite m on m.kode = w.muni_kode
    where not (pb.sp_kode = any (hawe))
  ),
  plek_sleutels as (
    select r.etiket, r.muni_kode, r.muni_naam,
           min(r.klas)::int as klas,
           bool_and(r.landelik) as landelik,
           min(r.metro_rang)::int as metro_rang
    from plek_rye r
    group by r.etiket, r.muni_kode, r.muni_naam
  ),
  -- wyk_id determines wyk_nr (wyke pk), so one DISTINCT over the pair keeps wyk_nrs in
  -- exactly the same order as wyk_ids.
  plek_wyke_uniek as (
    select distinct r.etiket, r.muni_kode, r.wyk_id, r.wyk_nr from plek_rye r
  ),
  plek_wyke_saam as (
    select u.etiket, u.muni_kode,
           array_agg(u.wyk_id order by u.wyk_id) as wyk_ids,
           array_agg(u.wyk_nr order by u.wyk_id) as wyk_nrs
    from plek_wyke_uniek u
    group by u.etiket, u.muni_kode
  ),
  plek_uitslae as (
    select
      'plek'::text as soort,
      s.etiket,
      s.muni_kode,
      s.muni_naam,
      a.wyk_ids,
      a.wyk_nrs,
      case when array_length(a.wyk_ids, 1) = 1 then '/wyk/' || a.wyk_ids[1] end as teiken,
      s.klas,
      0 as soort_rang,
      case when s.landelik then 1 else 0 end as landelik_rang,
      s.metro_rang
    from plek_sleutels s
    join plek_wyke_saam a on a.etiket = s.etiket and a.muni_kode = s.muni_kode
  ),
  stasie_treffers as (
    select st.naam as etiket, st.wyk_id,
           least(
             case
               when public.normaliseer_soekteks(st.naam) = qn then 1
               when public.normaliseer_soekteks(st.naam) like qlike then 2
               when public.normaliseer_soekteks(st.naam) % qn then 3
               else 9
             end,
             case
               when public.normaliseer_soekteks(st.adres) = qn then 1
               when public.normaliseer_soekteks(st.adres) like qlike then 2
               when public.normaliseer_soekteks(st.adres) % qn then 3
               else 9
             end
           )::int as klas
    from public.stemstasies st
    where public.normaliseer_soekteks(st.naam) like qlike
       or public.normaliseer_soekteks(st.naam) % qn
       or public.normaliseer_soekteks(st.adres) like qlike
       or public.normaliseer_soekteks(st.adres) % qn
  ),
  stasie_uitslae as (
    select
      'stemlokaal'::text as soort,
      t.etiket,
      w.muni_kode,
      m.naam as muni_naam,
      array[w.wyk_id] as wyk_ids,
      array[w.wyk_nr] as wyk_nrs,
      '/wyk/' || w.wyk_id || '#stemlokale' as teiken,
      t.klas,
      1 as soort_rang,
      0 as landelik_rang,
      case when m.tipe = 'metro' then 0 else 1 end as metro_rang
    from stasie_treffers t
    join public.wyke w on w.wyk_id = t.wyk_id
    join public.munisipaliteite m on m.kode = w.muni_kode
    where t.klas <= 3
  ),
  alles as (
    select * from plek_uitslae
    union all
    select * from stasie_uitslae
  )
  select
    x.soort,
    x.etiket,
    x.muni_kode,
    x.muni_naam,
    x.wyk_ids,
    x.wyk_nrs,
    x.teiken,
    (row_number() over (
      order by x.klas, x.soort_rang, x.landelik_rang, x.metro_rang, x.etiket
    ))::int as rang
  from alles x
  order by x.klas, x.soort_rang, x.landelik_rang, x.metro_rang, x.etiket
  limit 20;
end;
$$;

revoke all on function public.soek(text) from public;
grant execute on function public.soek(text) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 6. Publiseer-RPCs (service_role only)
--
-- The allow-list is repeated in each function on purpose: no shared helper means no
-- extra function to grant, revoke and audit. Table names only ever reach SQL through
-- format('%I'); the column and ordering lists are hard-coded literals chosen by a CASE
-- over the (already allow-listed) dataset name, never built from input.
--
-- publiseer_tabel inserts an explicit column list, so the public tables' identity
-- columns (partye.id, kandidate.id, plek_aliasse.id) are generated on insert instead of
-- being copied from the stg_ twin.
-- ---------------------------------------------------------------------------

create or replace function public.publiseer_leeg(datastel text)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  publiseerbaar constant text[] := array[
    'munisipaliteite', 'wyke', 'stemstasies', 'plekke', 'plek_wyke', 'plek_aliasse',
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde'
  ];
  verwyder bigint;
begin
  if datastel is null or not (datastel = any (publiseerbaar)) then
    raise exception 'onbekende datastel: %', coalesce(datastel, '<nul>');
  end if;

  -- `where true` satisfies PostgREST's safeupdate guard on an unqualified DELETE.
  execute format('delete from public.%I where true', datastel);
  get diagnostics verwyder = row_count;
  return verwyder;
end;
$$;

revoke all on function public.publiseer_leeg(text) from public, anon, authenticated;
grant execute on function public.publiseer_leeg(text) to service_role;

create or replace function public.publiseer_tabel(datastel text, van int, tot int)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  publiseerbaar constant text[] := array[
    'munisipaliteite', 'wyke', 'stemstasies', 'plekke', 'plek_wyke', 'plek_aliasse',
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde'
  ];
  kolomme text;
  orde text;
  ingevoeg bigint;
begin
  if datastel is null or not (datastel = any (publiseerbaar)) then
    raise exception 'onbekende datastel: %', coalesce(datastel, '<nul>');
  end if;
  if van is null or tot is null or van < 1 or tot < van then
    raise exception 'ongeldige reeks: (%, %)', van, tot;
  end if;

  -- Hard-coded per dataset. The ordering key must be deterministic, because the caller
  -- chunks on the row numbers it produces. ctid is the tiebreaker for the three tables
  -- with no natural unique key; it is stable for as long as the stg_ table is not
  -- rewritten, which is exactly the window a publish runs in.
  case datastel
    when 'munisipaliteite' then
      kolomme := 'kode, naam, tipe, distrik_kode, provinsie';
      orde := 'kode';
    when 'wyke' then
      kolomme := 'wyk_id, wyk_nr, muni_kode, geom';
      orde := 'wyk_id';
    when 'stemstasies' then
      kolomme := 'vd_nommer, naam, adres, wyk_id, muni_kode, "bron_lêer", bron_ry';
      orde := 'vd_nommer';
    when 'plekke' then
      kolomme := 'sp_kode, naam, naam_soek, mp_naam, mp_naam_soek, landelik, geom';
      orde := 'sp_kode';
    when 'plek_wyke' then
      kolomme := 'sp_kode, wyk_id, oorvleueling';
      orde := 'sp_kode, wyk_id';
    when 'plek_aliasse' then
      kolomme := 'alias, sp_kode';
      orde := 'alias, sp_kode';
    when 'raad_uitslae_2021' then
      kolomme := 'muni_kode, party_naam, setels_wyk, setels_pv, setels_totaal';
      orde := 'muni_kode, party_naam';
    when 'raad_grootte_2021' then
      kolomme := 'muni_kode, raadsgrootte_totaal, onafhanklike_setels';
      orde := 'muni_kode';
    when 'partye' then
      kolomme := 'naam, afkorting';
      orde := 'naam, coalesce(afkorting, ''''), ctid';
    when 'kandidate' then
      kolomme := 'muni_kode, stembrief, wyk_id, lys_posisie, party_id, onafhanklik, '
                 || 'volle_naam, van, "bron_lêer", bron_ry';
      orde := '"bron_lêer", bron_ry, ctid';
    when 'stembrief_volgorde' then
      kolomme := 'muni_kode, stembrief, party_id, posisie';
      orde := 'muni_kode, stembrief, party_id';
    else
      raise exception 'geen ordeningsleutel vir datastel: %', datastel;
  end case;

  -- on conflict do nothing (no target, so every unique index counts) makes a retried
  -- chunk idempotent.
  execute format(
    'insert into public.%I (%s) '
    'select %s from ('
    '  select %s, row_number() over (order by %s) as rn from public.%I'
    ') genommer where rn between $1 and $2 '
    'on conflict do nothing',
    datastel, kolomme, kolomme, kolomme, orde, 'stg_' || datastel
  ) using van, tot;

  get diagnostics ingevoeg = row_count;
  return ingevoeg;
end;
$$;

revoke all on function public.publiseer_tabel(text, int, int) from public, anon, authenticated;
grant execute on function public.publiseer_tabel(text, int, int) to service_role;

create or replace function public.publiseer_afrond(datastelle text[], bron_datum date)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  publiseerbaar constant text[] := array[
    'munisipaliteite', 'wyke', 'stemstasies', 'plekke', 'plek_wyke', 'plek_aliasse',
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde'
  ];
  -- Local copy so the INSERT's VALUES list cannot be read as the data_weergawes column
  -- of the same name.
  v_bron_datum date := bron_datum;
  v_nou timestamptz := now();
  ds text;
  telling bigint;
begin
  if datastelle is null or array_length(datastelle, 1) is null then
    raise exception 'geen datastelle gegee nie';
  end if;

  foreach ds in array datastelle loop
    if ds is null or not (ds = any (publiseerbaar)) then
      raise exception 'onbekende datastel: %', coalesce(ds, '<nul>');
    end if;
  end loop;

  foreach ds in array datastelle loop
    execute format('select count(*) from public.%I', ds) into telling;
    insert into public.data_weergawes (datastel, bron_datum, rye, gelaai_om, gepubliseer_om)
    values (ds, v_bron_datum, telling, v_nou, v_nou);
  end loop;
end;
$$;

revoke all on function public.publiseer_afrond(text[], date) from public, anon, authenticated;
grant execute on function public.publiseer_afrond(text[], date) to service_role;
