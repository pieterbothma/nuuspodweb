-- Verkiesing 2026, Fase 2a — herstel-rondte 1: bou_plek_wyke hanteer ongeldige geometrie.
-- Fix-forward na verkiesing_fase2_basis (20260915100000). Toegepas met die Supabase MCP
-- apply_migration-hulpmiddel.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. oorvleueling is 'n aandeel (0-1) — klem die boonste grens ook af.
-- ---------------------------------------------------------------------------

alter table public.plek_wyke
  add constraint plek_wyke_oorvleueling_max check (oorvleueling <= 1);

alter table public.stg_plek_wyke
  add constraint stg_plek_wyke_oorvleueling_max check (oorvleueling <= 1);

-- ---------------------------------------------------------------------------
-- 2. bou_plek_wyke(): 'n enkele ongeldige (bv. bogtoets-/self-snydende) veelhoek
--    in stg_plekke of stg_wyke het voorheen ST_Intersection laat omval met
--    "TopologyException: side location conflict" en die hele INSERT laat misluk.
--    Maak elke geometrie een keer per ry geldig (ST_MakeValid + ST_CollectionExtract
--    na net veelhoeke) voordat ST_Intersects/ST_Intersection/ST_Area loop. Die &&-
--    saamloop op die rou geom-kolomme bly voor as 'n indeks-vriendelike grofsif;
--    die geldige weergawes doen die werklike snytoets en -berekening.
-- ---------------------------------------------------------------------------

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

  with plekke_geldig as (
    select
      sp_kode,
      geom as geom_ru,
      ST_CollectionExtract(ST_MakeValid(geom), 3) as geldig
    from public.stg_plekke
    where geom is not null
  ),
  wyke_geldig as (
    select
      wyk_id,
      geom as geom_ru,
      ST_CollectionExtract(ST_MakeValid(geom), 3) as geldig
    from public.stg_wyke
    where geom is not null
  ),
  pare as (
    select
      p.sp_kode,
      w.wyk_id,
      ST_Area(ST_Intersection(p.geldig, w.geldig)::geography) as deursnyding_m2,
      ST_Area(p.geldig::geography) as plek_area_m2
    from plekke_geldig p
    join wyke_geldig w
      on p.geom_ru && w.geom_ru
     and not ST_IsEmpty(p.geldig)
     and not ST_IsEmpty(w.geldig)
     and ST_Intersects(p.geldig, w.geldig)
  )
  insert into public.stg_plek_wyke (sp_kode, wyk_id, oorvleueling)
  select
    sp_kode,
    wyk_id,
    least(1, (deursnyding_m2 / nullif(plek_area_m2, 0)))
  from pare
  where plek_area_m2 > 0
    and (
      (deursnyding_m2 / nullif(plek_area_m2, 0)) >= 0.05
      or deursnyding_m2 >= 10000
    );

  get diagnostics ingevoeg = row_count;
  return ingevoeg;
end;
$$;

revoke all on function public.bou_plek_wyke() from public, anon, authenticated;
grant execute on function public.bou_plek_wyke() to service_role;
