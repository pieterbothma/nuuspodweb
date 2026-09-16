-- Verkiesing 2026, Fase 2b, Task 1 — herstelrondte 2: 'n alias dra sy teiken-
-- munisipaliteit. Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP
-- apply_migration-hulpmiddel.
--
-- Herstelrondte 2 se punt 1 het die alias-resolusie op `aliasse.csv` se
-- `munisipaliteit_naam` laat filter, en punt 2 het die landelike " NU"/" SH"-agtervoegsel
-- laat vou, sodat "Mahikeng" nou al 11 Mafikeng-sub-plekke (dorp + landelik) dek en
-- dieselfde 26 wyke as die hoofplek "Mafikeng" gee. Dit het egter 'n nuwe fout oopgemaak:
-- die landelike sub-plek "Mafikeng NU" strek oor VIER munisipaliteite (NW381 Ratlou,
-- NW383 Mafikeng, NW384 Ditsobotla, NW385 Ramotshere Moiloa), en omdat soek() plek-rye per
-- (etiket, muni_kode) groepeer, het "Mahikeng" toe vier rye gegee — een vir Mafikeng (26
-- wyke) plus drie oorloop-rye van 1-2 wyke in buurmunisipaliteite waaroor die alias niks
-- sê nie. Die vereiste is één gegroepeerde ry.
--
-- Die resolusie kan dit nie oplos nie: dit kies sub-plekke, en hierdie een sub-plek lê
-- werklik in vier munisipaliteite. soek() moet dus weet wat die alias se teiken is, so
-- `plek_aliasse` (en sy stg_-eweknie) kry 'n `muni_kode`-kolom wat die laaier uit
-- `aliasse.csv` se `munisipaliteit_naam` skryf. In soek() neem 'n alias-treffer met 'n
-- gestelde muni_kode net daardie munisipaliteit se wyke; is die kolom NULL, gedra die
-- alias hom presies soos voorheen. 'n Plek wat langs die alias ook op sy eie naam of sy
-- hoofplek tref, bly onbeperk — daardie treffer is nie aan een munisipaliteit gebind nie.
--
-- publiseer_tabel('plek_aliasse', ...) dra die nuwe kolom oor.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. Kolom
-- ---------------------------------------------------------------------------

alter table public.plek_aliasse
  add column if not exists muni_kode text references public.munisipaliteite (kode);
alter table public.stg_plek_aliasse add column if not exists muni_kode text;

-- ---------------------------------------------------------------------------
-- 2. soek(): 'n beperkte alias wys net sy eie munisipaliteit
--    Identies aan 20260916070604 buiten die muni_beperk-draad.
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
             when public.normaliseer_soekteks(a.alias) = qn then 1
             when public.normaliseer_soekteks(a.alias) like qlike then 2
             when extensions.similarity(public.normaliseer_soekteks(a.alias), qn) > 0.3::real then 3
             else 9
           end as klas
    from public.plek_aliasse a
    where public.normaliseer_soekteks(a.alias) like qlike
       or public.normaliseer_soekteks(a.alias) % qn
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

-- ---------------------------------------------------------------------------
-- 3. publiseer_tabel: plek_aliasse dra nou muni_kode oor.
--    Identies aan 20260916070014 buiten daardie een kolomlys.
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
  oorheers text := '';
  botsing text := '';
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
      kolomme := 'alias, sp_kode, muni_kode';
      orde := 'alias, sp_kode';
    when 'raad_uitslae_2021' then
      kolomme := 'muni_kode, party_naam, setels_wyk, setels_pv, setels_totaal';
      orde := 'muni_kode, party_naam';
    when 'raad_grootte_2021' then
      kolomme := 'muni_kode, raadsgrootte_totaal, onafhanklike_setels';
      orde := 'muni_kode';
    when 'partye' then
      kolomme := 'id, naam, afkorting';
      orde := 'id';
      oorheers := 'overriding system value';
      botsing := '(id)';
    when 'kandidate' then
      kolomme := 'id, muni_kode, stembrief, wyk_id, lys_posisie, party_id, onafhanklik, '
                 || 'volle_naam, van, "bron_lêer", bron_ry';
      orde := 'id';
      oorheers := 'overriding system value';
      botsing := '(id)';
    when 'stembrief_volgorde' then
      kolomme := 'muni_kode, stembrief, party_id, posisie';
      orde := 'muni_kode, stembrief, party_id';
    else
      raise exception 'geen ordeningsleutel vir datastel: %', datastel;
  end case;

  execute format(
    'insert into public.%I (%s) %s '
    'select %s from ('
    '  select %s, row_number() over (order by %s) as rn from public.%I'
    ') genommer where rn between $1 and $2 '
    'on conflict %s do nothing',
    datastel, kolomme, oorheers, kolomme, kolomme, orde, 'stg_' || datastel, botsing
  ) using van, tot;

  get diagnostics ingevoeg = row_count;
  return ingevoeg;
end;
$$;

revoke all on function public.publiseer_tabel(text, int, int) from public, anon, authenticated;
grant execute on function public.publiseer_tabel(text, int, int) to service_role;
