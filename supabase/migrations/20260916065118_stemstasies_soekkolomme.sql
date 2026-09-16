-- Verkiesing 2026, Fase 2b, Task 1 — herstelrondte 1, punt 1: gestoorde soekkolomme
-- op stemstasies. Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP
-- apply_migration-hulpmiddel.
--
-- soek() het die stasienaam en -adres by navraagtyd genormaliseer, teen 'n paar
-- uitdrukking-indekse op normaliseer_soekteks(naam)/(adres). Dit werk, maar 'n
-- 2-karakter navraag ('st') se trigram-tak lewer ~19 500 kandidaatrye op en die
-- bitmap-hertoets moet normaliseer_soekteks dan op elkeen van hulle bereken:
-- soek('st') was 1 901 ms van anon se 3s statement_timeout. `plekke` ly nie daaronder
-- nie, want sy naam_soek is 'n gewone gestoorde kolom (dieselfde navraag: 14,8 ms).
--
-- Hierdie migrasie gee stemstasies dieselfde vorm as plekke:
--   1. naam_soek + adres_soek op public.stemstasies en public.stg_stemstasies
--   2. backfill in bondels van 5 000 vd_nommers, dan NOT NULL (soos plekke.naam_soek)
--   3. die vier uitdrukking-indekse word deur gewone kolomindekse vervang, met
--      dieselfde name en dieselfde vorm as plekke se paar (GIN-trigram + btree
--      text_pattern_ops). Dit laat die "REINDEX as normaliseer_soekteks verander"-
--      gevaar heeltemal verdwyn — geen indeks hang meer van die funksie af nie.
--   4. soek() en publiseer_tabel('stemstasies', ...) gebruik die kolomme
--
-- data/laai_stemstasies.py skryf die twee velde nou ook, so 'n volgende laai vul hulle.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. Kolomme
-- ---------------------------------------------------------------------------

alter table public.stemstasies add column if not exists naam_soek text;
alter table public.stemstasies add column if not exists adres_soek text;
alter table public.stg_stemstasies add column if not exists naam_soek text;
alter table public.stg_stemstasies add column if not exists adres_soek text;

-- ---------------------------------------------------------------------------
-- 2. Backfill in bondels
--
-- Runs on the migration (direct SQL) connection, so the authenticator role's 8s
-- statement_timeout does not apply — but chunked anyway, so the same block can be
-- replayed against a bigger table without a long single statement.
-- ---------------------------------------------------------------------------

do $$
declare
  bondel constant int := 5000;
  gedoen int;
begin
  loop
    update public.stemstasies s
       set naam_soek = public.normaliseer_soekteks(s.naam),
           adres_soek = public.normaliseer_soekteks(s.adres)
     where s.vd_nommer in (
             select vd_nommer from public.stemstasies
             where naam_soek is null or adres_soek is null
             order by vd_nommer
             limit bondel
           );
    get diagnostics gedoen = row_count;
    exit when gedoen = 0;
  end loop;

  loop
    update public.stg_stemstasies s
       set naam_soek = public.normaliseer_soekteks(s.naam),
           adres_soek = public.normaliseer_soekteks(s.adres)
     where s.vd_nommer in (
             select vd_nommer from public.stg_stemstasies
             where naam_soek is null or adres_soek is null
             order by vd_nommer
             limit bondel
           );
    get diagnostics gedoen = row_count;
    exit when gedoen = 0;
  end loop;
end;
$$;

alter table public.stemstasies alter column naam_soek set not null;
alter table public.stemstasies alter column adres_soek set not null;
alter table public.stg_stemstasies alter column naam_soek set not null;
alter table public.stg_stemstasies alter column adres_soek set not null;

-- ---------------------------------------------------------------------------
-- 3. Indekse: uitdrukking -> kolom, dieselfde name
-- ---------------------------------------------------------------------------

drop index if exists public.stemstasies_naam_soek_trgm;
drop index if exists public.stemstasies_adres_soek_trgm;
drop index if exists public.stemstasies_naam_soek_voorvoegsel;
drop index if exists public.stemstasies_adres_soek_voorvoegsel;

create index stemstasies_naam_soek_trgm
  on public.stemstasies using gin (naam_soek extensions.gin_trgm_ops);
create index stemstasies_adres_soek_trgm
  on public.stemstasies using gin (adres_soek extensions.gin_trgm_ops);
create index stemstasies_naam_soek_voorvoegsel
  on public.stemstasies (naam_soek text_pattern_ops);
create index stemstasies_adres_soek_voorvoegsel
  on public.stemstasies (adres_soek text_pattern_ops);

-- ---------------------------------------------------------------------------
-- 4a. soek(): stasietreffers kom nou van die gestoorde kolomme.
--     Identies aan 20260916063438 buiten die stasie_treffers-CTE.
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
             when extensions.similarity(public.normaliseer_soekteks(a.alias), qn) > 0.3::real then 3
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
-- 4b. publiseer_tabel: stemstasies dra nou naam_soek + adres_soek oor.
--     Identies aan 20260916062706 buiten daardie een kolomlys.
-- ---------------------------------------------------------------------------

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

  case datastel
    when 'munisipaliteite' then
      kolomme := 'kode, naam, tipe, distrik_kode, provinsie';
      orde := 'kode';
    when 'wyke' then
      kolomme := 'wyk_id, wyk_nr, muni_kode, geom';
      orde := 'wyk_id';
    when 'stemstasies' then
      kolomme := 'vd_nommer, naam, naam_soek, adres, adres_soek, wyk_id, muni_kode, '
                 || '"bron_lêer", bron_ry';
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
