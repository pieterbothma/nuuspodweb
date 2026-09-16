-- Verkiesing 2026, Fase 2b, Task 1 — herstelrondte 1, punt 4: publiseer_afrond kry 'n
-- opsionele gelaai_om. Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP
-- apply_migration-hulpmiddel.
--
-- publiseer_afrond het `data_weergawes.gelaai_om = now()` geskryf, wat eintlik die
-- publiseertyd is, nie die laaityd nie (die stg_-tabelle hou nie aan wanneer hulle gelaai
-- is nie). Task 2 weet die werklike laaityd, so dit kan dit nou deurgee; word dit
-- weggelaat, val dit terug op now() soos voorheen.
--
-- Die ou 2-argument-vorm word laat val, anders bestaan twee oorlaaie naas mekaar. Omdat
-- die derde parameter 'n verstek het, bly 'n oproep met net {datastelle, bron_datum}
-- (soos PostgREST se benoemde argumente dit stuur) presies soos voorheen werk.

set search_path = public, extensions;

drop function if exists public.publiseer_afrond(text[], date);

create or replace function public.publiseer_afrond(
  datastelle text[],
  bron_datum date,
  gelaai_om timestamptz default null
)
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

revoke all on function public.publiseer_afrond(text[], date, timestamptz) from public, anon, authenticated;
grant execute on function public.publiseer_afrond(text[], date, timestamptz) to service_role;
