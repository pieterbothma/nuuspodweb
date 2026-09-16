-- Verkiesing 2026, Fase 2b, Task 1 — herstelrondte 1, punt 3: partye/kandidate behou
-- hulle id's deur die publisering. Toegepas op projek xxysgvanarnirxoxrbkj met die
-- Supabase MCP apply_migration-hulpmiddel.
--
-- publiseer_tabel het vir hierdie twee datastelle 'n eksplisiete kolomlys SONDER `id`
-- ingevoeg, so public.partye.id en public.kandidate.id is deur hulle identity-kolomme
-- gegenereer. Twee gevolge:
--   - stg_kandidate.party_id het na stg_partye-id's gewys wat nie meer in public.partye
--     bestaan nie, so elke kandidaat se party kon verkeerd (of 'n FK-fout) word;
--   - nie een van die twee tabelle het 'n natuurlike unieke sleutel nie, so
--     `on conflict do nothing` het geen arbiter gehad en 'n herhaalde bondel (bv. ná 'n
--     kliënt-kant-timeout) sou duplikate skep.
--
-- Beslissing van die koördineerder: die kandidaat-laaier ken die id's deterministies toe,
-- so hulle moet die publisering onveranderd oorleef.
--   1. unieke indeks op `naam` vir partye en stg_partye, en op `id` vir stg_partye en
--      stg_kandidate (die publieke tabelle se PK's dek `id` al);
--   2. publiseer_tabel voeg vir hierdie twee datastelle eksplisiete id's in met
--      OVERRIDING SYSTEM VALUE, bondel op `order by id`, en gebruik `id` as die
--      on-conflict-arbiter, so 'n herhaalde bondel is idempotent en kandidate.party_id
--      bly na die regte party wys.
--
-- Let wel: OVERRIDING SYSTEM VALUE laat public.partye_id_seq / public.kandidate_id_seq
-- agter. Niks anders voeg by hierdie twee tabelle in nie (die laaier ken alle id's toe),
-- maar 'n handmatige INSERT sonder id sou 'n botsing kry — setval dan eers.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. Unieke sleutels
-- ---------------------------------------------------------------------------

create unique index if not exists partye_naam_uniek on public.partye (naam);
create unique index if not exists stg_partye_naam_uniek on public.stg_partye (naam);
create unique index if not exists stg_partye_id_uniek on public.stg_partye (id);
create unique index if not exists stg_kandidate_id_uniek on public.stg_kandidate (id);

-- ---------------------------------------------------------------------------
-- 2. publiseer_tabel
--
-- `oorheers` and `botsing` are two more hard-coded literals chosen by the same CASE over
-- the already allow-listed dataset name; table names still only reach SQL via %I.
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
      kolomme := 'alias, sp_kode';
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
