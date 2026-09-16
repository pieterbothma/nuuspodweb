-- Verkiesing 2026, Fase 2b, Task 12 — plek_aliasse kry 'n gestoorde soekkolom.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- `plek_aliasse_alias_trgm` indekseer die rou `alias`-kolom, maar soek() filter op
-- `normaliseer_soekteks(alias)`, so die beplanner kon die indeks nooit gebruik nie en het
-- die normaliseerder vier keer per ry per oproep uitgevoer. Hierdie migrasie:
--   1. voeg `alias_soek` by as 'n GENERATED ALWAYS ... STORED-kolom. Anders as
--      plekke.naam_soek (wat die laaier skryf) hoef die laaier en publiseer_tabel niks te
--      weet nie: publiseer_tabel voeg 'n eksplisiete kolomlys in (alias, sp_kode, muni_kode)
--      en Postgres bereken die kolom self. stg_plek_aliasse kry dit nie — soek() lees
--      nooit stg nie, en stg het geen trigram-indeks nie.
--      Let wel: as normaliseer_soekteks() ooit verander, moet die kolom herbereken word
--      (bv. `update public.plek_aliasse set alias = alias`), want gestoorde waardes volg
--      nie 'n nuwe funksieliggaam vanself nie.
--   2. vervang die ongebruikte rou-kolom-indeks met 'n trigram- en 'n voorvoegselindeks op
--      `alias_soek`, soos plekke.naam_soek s'n.
--   3. herskep soek() — identies aan 20260916073043 buiten dat alias_rou `a.alias_soek`
--      lees in plaas van `public.normaliseer_soekteks(a.alias)`. security invoker, stable
--      en die EXECUTE-regte bly presies soos hulle was.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. Kolom
-- ---------------------------------------------------------------------------

alter table public.plek_aliasse
  add column if not exists alias_soek text
  generated always as (public.normaliseer_soekteks(alias)) stored;

-- ---------------------------------------------------------------------------
-- 2. Indekse
-- ---------------------------------------------------------------------------

drop index if exists public.plek_aliasse_alias_trgm;
drop index if exists public.stg_plek_aliasse_alias_trgm;

create index if not exists plek_aliasse_alias_soek_trgm
  on public.plek_aliasse using gin (alias_soek extensions.gin_trgm_ops);
create index if not exists plek_aliasse_alias_soek_voorvoegsel
  on public.plek_aliasse using btree (alias_soek text_pattern_ops);

-- ---------------------------------------------------------------------------
-- 3. soek(): alias_rou lees die gestoorde kolom
-- ---------------------------------------------------------------------------

create or replace function public.soek(q text)
returns table (
  soort text,
  etiket text,
  muni_kode text,
  muni_naam text,
  provinsie text,
  adres text,
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
  hawe constant text[] := array['199056003', '199057014', '199063016'];
begin
  if qn is null or length(qn) < 2 then
    return;
  end if;

  qlike := replace(replace(replace(qn, '\', '\\'), '%', '\%'), '_', '\_') || '%';

  return query
  with alias_rou as (
    select a.alias, a.sp_kode, a.muni_kode as muni_beperk,
           case
             when a.alias_soek = qn then 1
             when a.alias_soek like qlike then 2
             when extensions.similarity(a.alias_soek, qn) > 0.3::real then 3
             else 9
           end as klas
    from public.plek_aliasse a
    where a.alias_soek like qlike
       or a.alias_soek % qn
  ),
  -- Etiket = die alias self, in die kanonieke vorm wat in plek_aliasse staan.
  alias_treffers as (
    select z.alias as etiket, z.sp_kode, z.muni_beperk, min(z.klas)::int as klas
    from alias_rou z
    where z.klas <= 3
    group by z.alias, z.sp_kode, z.muni_beperk
  ),
  naam_rou as (
    select p.sp_kode,
           case
             when p.naam_soek = qn then 1
             when p.naam_soek like qlike then 2
             when extensions.similarity(p.naam_soek, qn) > 0.3::real then 3
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
             when extensions.similarity(p.mp_naam_soek, qn) > 0.3::real then 3
             else 9
           end as klas
    from public.plekke p
    where p.mp_naam_soek is not null
      and (p.mp_naam_soek like qlike or p.mp_naam_soek % qn)
  ),
  mp_treffers as (
    select z.sp_kode, z.klas from mp_rou z where z.klas <= 3
  ),
  -- van_naam: as die plek op sy eie naam EN op sy hoofplek tref, wen die sub-pleknaam.
  naam_mp_kandidate as (
    select t.sp_kode, t.klas, true as van_naam from naam_treffers t
    union all
    select t.sp_kode, t.klas, false as van_naam from mp_treffers t
  ),
  naam_mp_beste as (
    select k.sp_kode, min(k.klas)::int as klas, bool_or(k.van_naam) as van_naam
    from naam_mp_kandidate k
    group by k.sp_kode
  ),
  naam_mp_treffers as (
    select
      case when b.van_naam
           then p.naam
           else btrim(regexp_replace(p.mp_naam, '\s+(NU|SH)$', ''))
      end as etiket,
      b.sp_kode,
      b.klas,
      null::text as muni_beperk
    from naam_mp_beste b
    join public.plekke p on p.sp_kode = b.sp_kode
  ),
  -- (etiket, sp_kode), nie net sp_kode nie: een plek kan onder sy alias én onder sy eie
  -- naam opduik, en dan hoort dit in albei etikette se groepe.
  plek_etikette as (
    select e.etiket, e.sp_kode, min(e.klas)::int as klas,
           -- 'n onbeperkte treffer (eie naam of hoofplek) wen oor 'n alias se beperking:
           -- dieselfde etiket wat langs die alias ook op die pleknaam tref, moet steeds
           -- al sy munisipaliteite wys.
           case when bool_or(e.muni_beperk is null) then null else min(e.muni_beperk) end
             as muni_beperk
    from (
      select t.etiket, t.sp_kode, t.klas, t.muni_beperk from alias_treffers t
      union all
      select t.etiket, t.sp_kode, t.klas, t.muni_beperk from naam_mp_treffers t
    ) e
    group by e.etiket, e.sp_kode
  ),
  plek_rye as (
    select
      pe.etiket as etiket,
      w.muni_kode as muni_kode,
      m.naam as muni_naam,
      m.provinsie as provinsie,
      pe.klas as klas,
      p.landelik as landelik,
      case when m.tipe = 'metro' then 0 else 1 end as metro_rang,
      w.wyk_id as wyk_id,
      w.wyk_nr as wyk_nr
    from plek_etikette pe
    join public.plekke p on p.sp_kode = pe.sp_kode
    join public.plek_wyke pw on pw.sp_kode = pe.sp_kode
    join public.wyke w on w.wyk_id = pw.wyk_id
    join public.munisipaliteite m on m.kode = w.muni_kode
    where not (pe.sp_kode = any (hawe))
      and (pe.muni_beperk is null or w.muni_kode = pe.muni_beperk)
  ),
  plek_sleutels as (
    select r.etiket, r.muni_kode, r.muni_naam, r.provinsie,
           min(r.klas)::int as klas,
           bool_and(r.landelik) as landelik,
           min(r.metro_rang)::int as metro_rang
    from plek_rye r
    group by r.etiket, r.muni_kode, r.muni_naam, r.provinsie
  ),
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
      s.provinsie,
      null::text as adres,
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
    select st.naam as etiket, nullif(btrim(st.adres), '') as adres, st.wyk_id,
           least(
             case
               when st.naam_soek = qn then 1
               when st.naam_soek like qlike then 2
               when extensions.similarity(st.naam_soek, qn) > 0.3::real then 3
               else 9
             end,
             case
               when st.adres_soek = qn then 1
               when st.adres_soek like qlike then 2
               when extensions.similarity(st.adres_soek, qn) > 0.3::real then 3
               else 9
             end
           )::int as klas
    from public.stemstasies st
    where st.naam_soek like qlike
       or st.naam_soek % qn
       or st.adres_soek like qlike
       or st.adres_soek % qn
  ),
  stasie_uitslae as (
    select
      'stemlokaal'::text as soort,
      t.etiket,
      w.muni_kode,
      m.naam as muni_naam,
      m.provinsie,
      t.adres,
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
    x.provinsie,
    x.adres,
    x.wyk_ids,
    x.wyk_nrs,
    x.teiken,
    (row_number() over (
      order by x.klas, x.soort_rang, x.landelik_rang, x.metro_rang, x.etiket,
             x.muni_kode, x.wyk_ids
    ))::int as rang
  from alles x
  order by x.klas, x.soort_rang, x.landelik_rang, x.metro_rang, x.etiket,
             x.muni_kode, x.wyk_ids
  limit 20;
end;
$$;

revoke all on function public.soek(text) from public;
grant execute on function public.soek(text) to anon, authenticated, service_role;

notify pgrst, 'reload schema';
