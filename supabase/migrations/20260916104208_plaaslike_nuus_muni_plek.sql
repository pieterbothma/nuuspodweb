-- Verkiesing 2026: plaaslike_nuus_vir_muni gee plek = null vir 'n storie wat net die
-- munisipaliteit self noem. Toegepas met die Supabase MCP apply_migration-hulpmiddel.
--
-- On a municipality's own page a label like "Joburg" or "Cape Town" next to each headline is
-- noise (and sometimes a nickname of the page's own heading); a town or suburb label stays.

set search_path = public, extensions;

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
      select distinct on (n.id)
             case when s.vlak = 'munisipaliteit' then null else s.plek end as plek,
             n.titel, n.bron, n.url, n.gepubliseer_om,
             case s.vlak when 'dorp' then 1 when 'wyk' then 2 else 3 end as orde
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
