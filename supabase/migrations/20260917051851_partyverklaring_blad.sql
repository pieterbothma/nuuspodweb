-- Each approved party statement gets its own page (Piet, 2026-09-17: opening in place read
-- badly). The list function now returns the id to link to, and a second function returns one
-- approved statement by id. Both expose public columns of approved rows only.

drop function if exists public.partyverklarings_nuutste(integer);

create function public.partyverklarings_nuutste(p_dae integer default 30)
returns table (
  id bigint,
  party text,
  bron_url text,
  titel_oorspronklik text,
  titel_af text,
  teks_af text,
  vertaal boolean,
  gepubliseer_om timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select e.id, e.party, e.bron_url, e.titel_oorspronklik, e.titel_af, e.teks_af, e.vertaal, e.gepubliseer_om
  from (
    select distinct on (v.party) v.*
    from public.partyverklarings v
    where v.status = 'goedgekeur'
      and v.titel_af is not null
      and v.teks_af is not null
      and v.gepubliseer_om > now() - make_interval(days => least(greatest(p_dae, 1), 90))
    order by v.party, v.gepubliseer_om desc
  ) e
  order by e.party;
$$;

revoke all on function public.partyverklarings_nuutste(integer) from public;
grant execute on function public.partyverklarings_nuutste(integer) to anon, authenticated, service_role;

-- One approved statement. No date window: a shared link keeps working after the statement
-- has left the home page.
create or replace function public.partyverklaring(p_id bigint)
returns table (
  id bigint,
  party text,
  bron_url text,
  titel_oorspronklik text,
  titel_af text,
  teks_af text,
  vertaal boolean,
  gepubliseer_om timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select v.id, v.party, v.bron_url, v.titel_oorspronklik, v.titel_af, v.teks_af, v.vertaal, v.gepubliseer_om
  from public.partyverklarings v
  where v.id = p_id
    and v.status = 'goedgekeur'
    and v.titel_af is not null
    and v.teks_af is not null;
$$;

revoke all on function public.partyverklaring(bigint) from public;
grant execute on function public.partyverklaring(bigint) to anon, authenticated, service_role;
