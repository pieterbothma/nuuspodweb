-- Verkiesing 2026: stg_leeg mag ook die twee 2021-wykuitslag-stg_-tabelle leegmaak.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.

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
    'stg_plekke', 'stg_plek_wyke', 'stg_plek_aliasse',
    'stg_wyk_2021_opsomming', 'stg_wyk_uitslae_2021'
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
