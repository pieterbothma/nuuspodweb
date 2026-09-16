-- Verkiesing 2026, Fase 2b, Task 1 — herstel-rondte 1: `%` is >= drempel, nie > nie.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- 20260916062706_wyksoeker_rpcs leaned on pg_trgm's `%` operator alone for match class 3,
-- on the assumption (from the pg_trgm docs' wording, "greater than the current similarity
-- threshold") that `x % y` is exactly `similarity(x, y) > 0.3`. Measured against the real
-- data it is >=: soek('Habour') returned the place "Habhu" in Ntabankulu, whose
-- similarity('habhu', 'habour') is exactly 0.3, which the spec's `> 0.3` excludes. That
-- also broke the harbour-sliver rule's test (soek('Habour') must return no place rows at
-- all: the three Stats SA "Habour" slivers are excluded by sp_kode, and nothing else may
-- come through in their place).
--
-- Fix: keep `%` only as the index-accelerated prefilter (it is a strict superset of the
-- wanted set) and let an explicit extensions.similarity(...) > 0.3 in the CASE assign
-- class 3, then drop everything that lands on the sentinel class 9. Same shape for all
-- four candidate sources.
--
-- The `set pg_trgm.similarity_threshold to '0.3'` clause is also dropped. Because pg_trgm
-- is installed, `pg_trgm` is a reserved GUC prefix, so in a backend that has not yet
-- loaded pg_trgm's library the name is an unrecognised placeholder and only a superuser
-- may set it — CREATE OR REPLACE FUNCTION failed with 42501 on the retry, and worse, the
-- clause would have run on every *call* as the invoking role (anon). `%` therefore relies
-- on the server default of 0.3; verified 2026-09-16 that pg_db_role_setting carries no
-- pg_trgm override for any role or database. If the default were ever raised, `%` would
-- stop being a superset and soek() would return fewer class-3 (fuzzy) rows — it can never
-- return a row the explicit similarity check rejects.
--
-- Also recorded here: anon's statement_timeout is 3s (authenticated and service_role get
-- 8s), so the site's own budget for soek() is 3s, which is why every candidate source
-- goes through a GIN trigram index instead of a sequential scan.

set search_path = public, extensions;

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
  with alias_rou as (
    select a.sp_kode,
           case
             when public.normaliseer_soekteks(a.alias) = qn then 1
             when public.normaliseer_soekteks(a.alias) like qlike then 2
             when extensions.similarity(public.normaliseer_soekteks(a.alias), qn) > 0.3 then 3
             else 9
           end as klas
    from public.plek_aliasse a
    where public.normaliseer_soekteks(a.alias) like qlike
       or public.normaliseer_soekteks(a.alias) % qn
  ),
  alias_treffers as (
    select z.sp_kode, min(z.klas) as klas
    from alias_rou z
    where z.klas <= 3
    group by z.sp_kode
  ),
  naam_rou as (
    select p.sp_kode,
           case
             when p.naam_soek = qn then 1
             when p.naam_soek like qlike then 2
             when extensions.similarity(p.naam_soek, qn) > 0.3 then 3
             else 9
           end as klas
    from public.plekke p
    where p.naam_soek like qlike
       or p.naam_soek % qn
  ),
  naam_treffers as (
    select z.sp_kode, z.klas from naam_rou z where z.klas <= 3
  ),
  mp_rou as (
    select p.sp_kode,
           case
             when p.mp_naam_soek = qn then 1
             when p.mp_naam_soek like qlike then 2
             when extensions.similarity(p.mp_naam_soek, qn) > 0.3 then 3
             else 9
           end as klas
    from public.plekke p
    where p.mp_naam_soek is not null
      and (p.mp_naam_soek like qlike or p.mp_naam_soek % qn)
  ),
  mp_treffers as (
    select z.sp_kode, z.klas from mp_rou z where z.klas <= 3
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
               when extensions.similarity(public.normaliseer_soekteks(st.naam), qn) > 0.3 then 3
               else 9
             end,
             case
               when public.normaliseer_soekteks(st.adres) = qn then 1
               when public.normaliseer_soekteks(st.adres) like qlike then 2
               when extensions.similarity(public.normaliseer_soekteks(st.adres), qn) > 0.3 then 3
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
