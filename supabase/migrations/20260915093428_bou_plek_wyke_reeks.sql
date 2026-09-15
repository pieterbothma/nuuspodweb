-- bou_plek_wyke: add an optional (van, tot) row-number range over stg_plekke so the
-- overlap computation can be run in chunks from Python instead of one long-running
-- PostgREST call.
--
-- Two problems observed while running Task 5 (plekke-laai) against this function:
--
-- 1. `delete from public.stg_plek_wyke;` (no WHERE clause) is rejected by PostgREST's
--    RPC path with `{"code":"21000","message":"DELETE requires a WHERE clause"}` —
--    reproduced both via the Python loader and a raw curl POST to
--    /rest/v1/rpc/bou_plek_wyke. The identical `select bou_plek_wyke();` run directly
--    via the Supabase SQL/MCP connection (superuser) does NOT hit this error — it
--    times out instead (see #2) — confirming this is a role-scoped safety guard on
--    unqualified DELETE that applies to the service_role/authenticator path PostgREST
--    uses, not a superuser session. Fixed here with `where true`, which satisfies the
--    guard while keeping identical delete-all semantics.
-- 2. The full unranged computation (22 196 places x 4 485 wards, ST_MakeValid +
--    ST_Intersection/geography-area on all pairs) does not finish within the
--    connection's timeout even as superuser — hence the (van, tot) range below,
--    looped in ~2 000-place chunks from `laai_plekke.py`.
--
-- Delete-all only happens when both van and tot are NULL (i.e. the old, no-argument
-- call shape, which Postgres still allows via the defaults below); a ranged call never
-- deletes existing stg_plek_wyke rows, so a chunked loop only ever adds rows.
--
-- MATERIALIZED is added to the two geometry-prep CTEs per the Task 1 review's minor
-- note — it stops the planner from re-evaluating ST_MakeValid/ST_CollectionExtract
-- once per outer-join probe and forces it to run once per CTE per call instead.

drop function if exists public.bou_plek_wyke();

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
