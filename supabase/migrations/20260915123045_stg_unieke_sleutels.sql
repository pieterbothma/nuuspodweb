-- Verkiesing 2026, Fase 2a — final-review fix round (Important 5): duplicate safety on
-- loader retries. Applied to project xxysgvanarnirxoxrbkj with the Supabase MCP
-- apply_migration tool.
--
-- 1. Unique indexes on the natural keys of the stg_ tables. The stg_ tables were created
--    with LIKE ... (no PK copied), so a retried batch or a partial re-run could insert
--    the same ward/station/place twice without any error. Verified with SELECT before
--    applying: 0 duplicates in each of these five keys (stg_wyke 4,485 rows,
--    stg_stemstasies 23,696, stg_plekke 22,196, stg_plek_wyke 35,582,
--    stg_munisipaliteite 257).
-- 2. bou_plek_wyke(van, tot): a ranged call now first deletes the existing stg_plek_wyke
--    rows for the sp_kodes in its range, so retrying a chunk is idempotent (previously it
--    only ever inserted, and a retry after a client-side timeout duplicated rows). The
--    unranged call keeps its delete-all. SECURITY DEFINER, search_path and grants are
--    unchanged. The function body is otherwise identical to 20260915093428.
-- 3. Sequences: Supabase's default privileges gave anon/authenticated USAGE/SELECT/UPDATE
--    on every public sequence. None of them needs it: identity columns call nextval
--    internally without a privilege check, so the anon insert policy on terugvoer keeps
--    working.

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. Unique natural keys on stg_ tables
-- ---------------------------------------------------------------------------

create unique index stg_wyke_wyk_id_uniek on public.stg_wyke (wyk_id);
create unique index stg_stemstasies_vd_nommer_uniek on public.stg_stemstasies (vd_nommer);
create unique index stg_plekke_sp_kode_uniek on public.stg_plekke (sp_kode);
create unique index stg_plek_wyke_sp_kode_wyk_id_uniek on public.stg_plek_wyke (sp_kode, wyk_id);
create unique index stg_munisipaliteite_kode_uniek on public.stg_munisipaliteite (kode);

-- ---------------------------------------------------------------------------
-- 2. bou_plek_wyke(van, tot): ranged calls replace their own range
-- ---------------------------------------------------------------------------

create or replace function public.bou_plek_wyke(van integer default null, tot integer default null)
 returns integer
 language plpgsql
 security definer
 set search_path to 'public', 'extensions'
as $function$
declare
  ingevoeg integer;
begin
  if van is null and tot is null then
    delete from public.stg_plek_wyke where true;
  else
    -- Same row numbering as the insert below, so exactly this range's rows are replaced.
    delete from public.stg_plek_wyke pw
    using (
      select sp_kode
      from (
        select sp_kode, row_number() over (order by sp_kode) as rn
        from public.stg_plekke
        where geom is not null
      ) genommer
      where (van is null or rn >= van)
        and (tot is null or rn <= tot)
    ) reeks
    where pw.sp_kode = reeks.sp_kode;
  end if;

  with plekke_nommer as (
    select
      sp_kode,
      geom as geom_ru,
      row_number() over (order by sp_kode) as rn
    from public.stg_plekke
    where geom is not null
  ),
  plekke_geldig as materialized (
    select
      sp_kode,
      geom_ru,
      ST_CollectionExtract(ST_MakeValid(geom_ru), 3) as geldig
    from plekke_nommer
    where (van is null or rn >= van)
      and (tot is null or rn <= tot)
  ),
  wyke_geldig as materialized (
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
$function$;

revoke all on function public.bou_plek_wyke(integer, integer) from public, anon, authenticated;
grant execute on function public.bou_plek_wyke(integer, integer) to service_role;

-- ---------------------------------------------------------------------------
-- 3. No sequence privileges for anon/authenticated
-- ---------------------------------------------------------------------------

revoke all on sequence public.partye_id_seq, public.kandidate_id_seq,
  public.plek_aliasse_id_seq, public.data_weergawes_id_seq
  from anon, authenticated;

-- Drop 1's sequences (nuusstroom_id_seq, terugvoer_id_seq) and any other public sequence.
revoke all on all sequences in schema public from anon, authenticated;
