-- Verkiesing 2026: amptelike 2021-wykuitslae op wyke met dieselfde grense.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- Piet (2026-09-16): a ward page shows its 2021 ward result only when the 2026 ward consists
-- of exactly the same voting districts as a 2021 ward (1 991 of 4 485 wards, 35 of them
-- renumbered). The figures are the IEC's official 2021 per-voting-district results summed
-- per ward — no estimate. Every other ward says its boundaries changed and points to the
-- municipality's official 2021 council result. The internal VD remap stays internal.
--
-- Only the ward ballot is stored. The IEC's 2021 file names independents collectively as
-- "INDEPENDENT", so several independents in one ward are one row.
--
-- Contains:
--   1. wyk_2021_opsomming (one row per matched 2026 ward) and wyk_uitslae_2021 (votes per
--      party), their stg_ twins, RLS read for anon
--   2. publiseer_leeg / publiseer_tabel / publiseer_afrond learn the two datasets

set search_path = public, extensions;

create table if not exists public.wyk_2021_opsomming (
  wyk_id text primary key references public.wyke (wyk_id),
  wyk_id_2021 text not null check (wyk_id_2021 ~ '^[0-9]{8}$'),
  wyk_nr_2021 integer not null check (wyk_nr_2021 > 0),
  geregistreer integer not null check (geregistreer >= 0),
  geldige_stemme integer not null check (geldige_stemme >= 0),
  bedorwe_stemme integer not null check (bedorwe_stemme >= 0),
  stemdistrikte integer not null check (stemdistrikte > 0)
);

create table if not exists public.wyk_uitslae_2021 (
  wyk_id text not null references public.wyk_2021_opsomming (wyk_id),
  party_naam text not null check (length(party_naam) between 1 and 200),
  stemme integer not null check (stemme >= 0),
  primary key (wyk_id, party_naam)
);

create table if not exists public.stg_wyk_2021_opsomming (like public.wyk_2021_opsomming including defaults including constraints);
create table if not exists public.stg_wyk_uitslae_2021 (like public.wyk_uitslae_2021 including defaults including constraints);
alter table public.stg_wyk_2021_opsomming drop constraint if exists stg_wyk_2021_opsomming_pkey;
alter table public.stg_wyk_2021_opsomming add primary key (wyk_id);
alter table public.stg_wyk_uitslae_2021 add primary key (wyk_id, party_naam);

alter table public.wyk_2021_opsomming enable row level security;
alter table public.wyk_uitslae_2021 enable row level security;
alter table public.stg_wyk_2021_opsomming enable row level security;
alter table public.stg_wyk_uitslae_2021 enable row level security;

drop policy if exists "publiek lees wyk_2021_opsomming" on public.wyk_2021_opsomming;
create policy "publiek lees wyk_2021_opsomming" on public.wyk_2021_opsomming for select to anon using (true);
drop policy if exists "publiek lees wyk_uitslae_2021" on public.wyk_uitslae_2021;
create policy "publiek lees wyk_uitslae_2021" on public.wyk_uitslae_2021 for select to anon using (true);

-- ---------------------------------------------------------------------------
-- 2. Publish functions
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
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde',
    'wyk_2021_opsomming', 'wyk_uitslae_2021'
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

create or replace function public.publiseer_tabel(datastel text, van int, tot int)
returns bigint
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  publiseerbaar constant text[] := array[
    'munisipaliteite', 'wyke', 'stemstasies', 'plekke', 'plek_wyke', 'plek_aliasse',
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde',
    'wyk_2021_opsomming', 'wyk_uitslae_2021'
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
    when 'wyk_2021_opsomming' then
      kolomme := 'wyk_id, wyk_id_2021, wyk_nr_2021, geregistreer, geldige_stemme, bedorwe_stemme, stemdistrikte';
      orde := 'wyk_id';
    when 'wyk_uitslae_2021' then
      kolomme := 'wyk_id, party_naam, stemme';
      orde := 'wyk_id, party_naam';
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

create or replace function public.publiseer_afrond(datastelle text[], bron_datum date, gelaai_om timestamptz default null)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  publiseerbaar constant text[] := array[
    'munisipaliteite', 'wyke', 'stemstasies', 'plekke', 'plek_wyke', 'plek_aliasse',
    'raad_uitslae_2021', 'raad_grootte_2021', 'partye', 'kandidate', 'stembrief_volgorde',
    'wyk_2021_opsomming', 'wyk_uitslae_2021'
  ];
  -- Local copies so the INSERT's VALUES list cannot be read as the data_weergawes
  -- columns of the same name.
  v_nou timestamptz := now();
  v_bron_datum date := bron_datum;
  v_gelaai_om timestamptz := coalesce(gelaai_om, v_nou);
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
    values (ds, v_bron_datum, telling, v_gelaai_om, v_nou);
  end loop;
end;
$$;

revoke all on function public.publiseer_leeg(text) from public, anon, authenticated;
revoke all on function public.publiseer_tabel(text, int, int) from public, anon, authenticated;
revoke all on function public.publiseer_afrond(text[], date, timestamptz) from public, anon, authenticated;
grant execute on function public.publiseer_leeg(text) to service_role;
grant execute on function public.publiseer_tabel(text, int, int) to service_role;
grant execute on function public.publiseer_afrond(text[], date, timestamptz) to service_role;
