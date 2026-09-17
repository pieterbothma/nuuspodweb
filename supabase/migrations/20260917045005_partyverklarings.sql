-- "Wat die partye sê": official statements of the parties in Parliament, translated to
-- Afrikaans and published only after a human taps Goedkeur in Telegram.
-- Spec: docs/superpowers/specs/2026-09-17-partyverklarings-design.md

create table if not exists public.partyverklarings (
  id bigint generated always as identity primary key,
  party text not null,
  bron_url text not null unique,
  titel_oorspronklik text not null,
  teks_oorspronklik text not null,
  gepubliseer_om timestamptz not null,
  titel_af text,
  teks_af text,
  -- false where the party already publishes in Afrikaans (VF+): shown as published.
  vertaal boolean not null default true,
  kontrole jsonb,
  status text not null default 'wag'
    check (status in ('basislyn', 'wag', 'goedgekeur', 'verwerp', 'fout')),
  besluit_deur text,
  besluit_om timestamptz,
  -- Telegram chat id -> message id, so every approver's message can be updated.
  telegram jsonb not null default '{}'::jsonb,
  geskep_om timestamptz not null default now()
);

create index if not exists partyverklarings_party_idx
  on public.partyverklarings (party, gepubliseer_om desc) where status = 'goedgekeur';
create index if not exists partyverklarings_status_idx on public.partyverklarings (status);

-- No anon policy on the table: it holds unapproved text, check results and chat ids.
-- The site reads only through the function below.
alter table public.partyverklarings enable row level security;

-- The latest approved statement per party, public columns only. The site sorts the parties
-- itself with the shared Afrikaans collator, so the order here is only a convenience.
create or replace function public.partyverklarings_nuutste(p_dae integer default 30)
returns table (
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
  select e.party, e.bron_url, e.titel_oorspronklik, e.titel_af, e.teks_af, e.vertaal, e.gepubliseer_om
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
