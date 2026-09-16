-- Verkiesing 2026: plaaslike nuus — net die blad se eie munisipaliteite bevestig 'n plek.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- The first live run (1 089 community stories) showed that letting a municipality named in
-- the text confirm itself puts tour and national stories on distant councils ("Sean Paul
-- brings dancehall hits to GrandWest" → Cape Town, Durban, Pretoria; "Stellenbosch
-- University's robot George" → George). Every outlet on the list is a community paper
-- with hand-set home municipalities, so only those confirm a place or a municipality now.
--
-- The site's read functions also drop the same headline syndicated across sister titles
-- (Cape Community Media runs one story in several papers), keeping the newest copy.

set search_path = public, extensions;

create or replace function public.koppel_nuus(teks text, munis text[])
returns table (muni_kode text, wyk_id text, plek text, vlak text)
language sql
stable
security definer
set search_path = public, extensions
as $$
  with woorde as (
    select regexp_split_to_array(public.normaliseer_nuusteks(teks), ' ') as w
  ),
  ngramme as (
    select s, n, array_to_string(w[s:s + n - 1], ' ') as k
    from woorde,
         generate_series(1, coalesce(array_length(w, 1), 0)) as s,
         generate_series(1, 5) as n
    where s + n - 1 <= array_length(w, 1)
  ),
  treffers as (
    select g.s, g.n, p.*
    from ngramme g
    join public.plek_name p on p.naam_soek = g.k
    where not (p.gewone_woord and g.n = 1)
      and p.muni_kode = any (munis)
  ),
  langste as (
    select * from treffers a
    where not exists (
      select 1 from treffers b
      where b.n > a.n and b.s <= a.s and a.s + a.n <= b.s + b.n
    )
  ),
  plek_rye as (
    select b.muni_kode, u.wyk_id, b.naam as plek,
           case when cardinality(b.wyk_ids) <= 3 then 'wyk' else 'dorp' end as vlak,
           cardinality(b.wyk_ids) as grootte
    from langste b, unnest(b.wyk_ids) as u(wyk_id)
    where not b.is_muni
  ),
  per_wyk as (
    select distinct on (r.wyk_id) r.muni_kode, r.wyk_id, r.plek, r.vlak
    from plek_rye r
    order by r.wyk_id, r.grootte, r.plek
  )
  select pw.muni_kode, pw.wyk_id, pw.plek, pw.vlak from per_wyk pw
  union all
  select distinct on (b.muni_kode) b.muni_kode, null::text, b.naam, 'munisipaliteit'
  from langste b
  where b.is_muni
  order by 1, 2 nulls first;
$$;

revoke all on function public.koppel_nuus(text, text[]) from public, anon, authenticated;
grant execute on function public.koppel_nuus(text, text[]) to service_role;

create or replace function public.plaaslike_nuus_vir_wyk(p_wyk_id text, p_perk integer default 3)
returns table (vlak text, plek text, titel text, bron text, url text, gepubliseer_om timestamptz)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  with muni as (
    select w.muni_kode from public.wyke w where w.wyk_id = p_wyk_id
  ),
  kandidate as (
    select s.vlak, s.plek, n.id, n.titel, n.bron, n.url, n.gepubliseer_om,
           case s.vlak when 'wyk' then 1 when 'dorp' then 2 else 3 end as orde
    from public.plaaslike_nuus_skakel s
    join public.plaaslike_nuus n on n.id = s.nuus_id
    where not n.versteek
      and n.gepubliseer_om > now() - interval '30 days'
      and (s.wyk_id = p_wyk_id
           or (s.vlak = 'munisipaliteit' and s.muni_kode = (select m.muni_kode from muni m)))
  ),
  per_storie as (
    select distinct on (k.id) * from kandidate k order by k.id, k.orde
  ),
  per_opskrif as (
    select distinct on (lower(p.titel)) * from per_storie p
    order by lower(p.titel), p.orde, p.gepubliseer_om desc
  ),
  gerangskik as (
    select e.*, row_number() over (partition by e.vlak order by e.gepubliseer_om desc) as rn
    from per_opskrif e
  )
  select g.vlak, g.plek, g.titel, g.bron, g.url, g.gepubliseer_om
  from gerangskik g
  where g.rn <= least(greatest(p_perk, 1), 10)
  order by g.orde, g.gepubliseer_om desc;
$$;

revoke all on function public.plaaslike_nuus_vir_wyk(text, integer) from public;
grant execute on function public.plaaslike_nuus_vir_wyk(text, integer) to anon, authenticated, service_role;

create or replace function public.plaaslike_nuus_vir_muni(p_kode text, p_perk integer default 6)
returns table (plek text, titel text, bron text, url text, gepubliseer_om timestamptz)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select e.plek, e.titel, e.bron, e.url, e.gepubliseer_om
  from (
    select distinct on (lower(s.titel)) s.*
    from (
      select distinct on (n.id) s.plek, n.titel, n.bron, n.url, n.gepubliseer_om,
             case s.vlak when 'munisipaliteit' then 1 when 'dorp' then 2 else 3 end as orde
      from public.plaaslike_nuus_skakel s
      join public.plaaslike_nuus n on n.id = s.nuus_id
      where s.muni_kode = p_kode
        and not n.versteek
        and n.gepubliseer_om > now() - interval '30 days'
      order by n.id, orde
    ) s
    order by lower(s.titel), s.gepubliseer_om desc
  ) e
  order by e.gepubliseer_om desc
  limit least(greatest(p_perk, 1), 20);
$$;

revoke all on function public.plaaslike_nuus_vir_muni(text, integer) from public;
grant execute on function public.plaaslike_nuus_vir_muni(text, integer) to anon, authenticated, service_role;

-- Clears the rows from the first, looser run so everything is re-matched under this rule.
delete from public.plaaslike_nuus where id > 0;
delete from public.plaaslike_nuus_gesien where url is not null;
