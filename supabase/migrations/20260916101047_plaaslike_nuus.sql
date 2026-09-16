-- Verkiesing 2026: plaaslike nuus op wyk- en munisipaliteitsblaaie.
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- Headlines from ~125 community outlets are linked to wards by place name. The admin cron
-- (kremetart.com, /api/cron/verkiesing-plaaslik) fetches the feeds and hands every item to
-- neem_plaaslike_nuus_in(); matching happens here, against plek_name.
--
-- Levels (Piet, 2026-09-16):
--   wyk            a place that covers 1–3 wards            → "Uit jou omgewing" on those wards
--   dorp           a place that covers 4+ wards (a town)     → "In <dorp>" on those wards
--   munisipaliteit the municipality itself is named          → municipality page + a short block
--                                                              on every ward of that municipality
-- A place only counts when its municipality is confirmed: it is one of the outlet's home
-- municipalities, or the same text names that municipality. Unconfirmed names are dropped,
-- never guessed (the spike showed "Washington", "Rugby", "Mkhize" landing on SA wards).
--
-- Contains, in this order:
--   1. normaliseer_nuusteks(text)  — normaliseer_soekteks plus every non-alphanumeric → space
--   2. gewone_woorde               — single-word place names that are ordinary words (loaded by
--                                    data/laai_gewone_woorde.py) plus a fixed stoplist
--   3. plek_name + bou_plek_name() — the match index, rebuilt from plekke/plek_aliasse/plek_wyke
--   4. plaaslike_nuus, plaaslike_nuus_skakel, plaaslike_nuus_gesien
--   5. koppel_nuus(teks, munis)    — service_role
--   6. neem_plaaslike_nuus_in(items) — service_role, called by the admin cron
--   7. plaaslike_nuus_vir_wyk / plaaslike_nuus_vir_muni — anon, read by the site

set search_path = public, extensions;

-- ---------------------------------------------------------------------------
-- 1. normaliseer_nuusteks
-- ---------------------------------------------------------------------------

create or replace function public.normaliseer_nuusteks(t text)
returns text
language sql
immutable
strict
parallel safe
set search_path = public, extensions
as $$
  select btrim(regexp_replace(public.normaliseer_soekteks(t), '[^a-z0-9]+', ' ', 'g'));
$$;

revoke all on function public.normaliseer_nuusteks(text) from public;
grant execute on function public.normaliseer_nuusteks(text) to service_role;

-- ---------------------------------------------------------------------------
-- 2. gewone_woorde
-- ---------------------------------------------------------------------------

create table if not exists public.gewone_woorde (
  woord text primary key
);
alter table public.gewone_woorde enable row level security;

-- ---------------------------------------------------------------------------
-- 3. plek_name
-- ---------------------------------------------------------------------------

create table if not exists public.plek_name (
  naam_soek text not null,
  muni_kode text not null,
  naam text not null,
  wyk_ids text[],
  is_muni boolean not null default false,
  gewone_woord boolean not null default false,
  primary key (naam_soek, muni_kode)
);
alter table public.plek_name enable row level security;

create or replace function public.bou_plek_name()
returns integer
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  n integer;
begin
  delete from public.plek_name where naam_soek is not null;

  -- Municipality names and the everyday names people use for them.
  insert into public.plek_name (naam_soek, muni_kode, naam, is_muni)
  select distinct on (naam_soek, kode) naam_soek, kode, vertoon, true
  from (
    select public.normaliseer_nuusteks(v) as naam_soek, m.kode, v as vertoon
    from public.munisipaliteite m,
    lateral (values
      (regexp_replace(regexp_replace(m.naam, '^(City of|Local of|The)\s+', ''),
                      '\s+(Metropolitan|Local)?\s*Municipality$', ''))
    ) as x(v)
    where m.tipe <> 'distrik'
    union all
    select public.normaliseer_nuusteks(b.naam), b.kode, b.naam
    from (values
      ('Joburg', 'JHB'), ('Jozi', 'JHB'), ('Johannesburg', 'JHB'),
      ('Pretoria', 'TSH'), ('Tshwane', 'TSH'),
      ('Durban', 'ETH'), ('eThekwini', 'ETH'),
      ('Gqeberha', 'NMA'), ('Port Elizabeth', 'NMA'), ('Nelson Mandela Bay', 'NMA'),
      ('East London', 'BUF'), ('Buffalo City', 'BUF'),
      ('Bloemfontein', 'MAN'), ('Mangaung', 'MAN'),
      ('Cape Town', 'CPT'), ('Kaapstad', 'CPT'),
      ('Mbombela', 'MP326'), ('Nelspruit', 'MP326'),
      ('Pietermaritzburg', 'KZN225'), ('Msunduzi', 'KZN225'),
      ('Kimberley', 'NC091'), ('Polokwane', 'LIM354'),
      ('Mahikeng', 'NW383'), ('Mafikeng', 'NW383')
    ) as b(naam, kode)
  ) bron
  where length(naam_soek) >= 4
  order by naam_soek, kode, vertoon;

  -- Places (sub places and main places, without the NU/SH suffix) and aliases, per
  -- municipality, with every ward they overlap. A place whose name is also the
  -- municipality's own name (or a "City of ..." sub place) is left to the municipality row.
  insert into public.plek_name (naam_soek, muni_kode, naam, wyk_ids, gewone_woord)
  select p.naam_soek, p.muni_kode, min(p.naam), array_agg(distinct p.wyk_id order by p.wyk_id),
         bool_or(g.woord is not null)
  from (
    select public.normaliseer_nuusteks(regexp_replace(pl.naam, '\s+(NU|SH)$', '')) as naam_soek,
           regexp_replace(pl.naam, '\s+(NU|SH)$', '') as naam, w.muni_kode, pw.wyk_id
    from public.plekke pl
    join public.plek_wyke pw on pw.sp_kode = pl.sp_kode
    join public.wyke w on w.wyk_id = pw.wyk_id
    union all
    select public.normaliseer_nuusteks(regexp_replace(pl.mp_naam, '\s+(NU|SH)$', '')),
           regexp_replace(pl.mp_naam, '\s+(NU|SH)$', ''), w.muni_kode, pw.wyk_id
    from public.plekke pl
    join public.plek_wyke pw on pw.sp_kode = pl.sp_kode
    join public.wyke w on w.wyk_id = pw.wyk_id
    where pl.mp_naam is not null
    union all
    select public.normaliseer_nuusteks(a.alias), a.alias, w.muni_kode, pw.wyk_id
    from public.plek_aliasse a
    join public.plek_wyke pw on pw.sp_kode = a.sp_kode
    join public.wyke w on w.wyk_id = pw.wyk_id and w.muni_kode = a.muni_kode
  ) p
  left join public.gewone_woorde g on g.woord = p.naam_soek
  where length(p.naam_soek) >= 4
    and p.naam_soek !~ '^[0-9 ]+$'
    and p.naam_soek !~ '^city of '
    and not exists (
      select 1 from public.plek_name m
      where m.is_muni and m.naam_soek = p.naam_soek and m.muni_kode = p.muni_kode
    )
  group by p.naam_soek, p.muni_kode;

  select count(*) into n from public.plek_name;
  return n;
end;
$$;

revoke all on function public.bou_plek_name() from public, anon, authenticated;
grant execute on function public.bou_plek_name() to service_role;

-- ---------------------------------------------------------------------------
-- 4. Nuus-tabelle
-- ---------------------------------------------------------------------------

create table if not exists public.plaaslike_nuus (
  id bigint generated always as identity primary key,
  titel text not null check (length(titel) between 1 and 500),
  bron text not null,
  url text not null unique check (url ~ '^https?://'),
  gepubliseer_om timestamptz not null,
  ingevoeg_om timestamptz not null default now(),
  versteek boolean not null default false
);
create index if not exists plaaslike_nuus_datum_idx on public.plaaslike_nuus (gepubliseer_om desc) where not versteek;

create table if not exists public.plaaslike_nuus_skakel (
  nuus_id bigint not null references public.plaaslike_nuus (id) on delete cascade,
  muni_kode text not null,
  wyk_id text,
  plek text not null,
  vlak text not null check (vlak in ('wyk', 'dorp', 'munisipaliteit')),
  check ((vlak = 'munisipaliteit') = (wyk_id is null)),
  unique nulls not distinct (nuus_id, muni_kode, wyk_id)
);
create index if not exists plaaslike_nuus_skakel_wyk_idx on public.plaaslike_nuus_skakel (wyk_id) where wyk_id is not null;
create index if not exists plaaslike_nuus_skakel_muni_idx on public.plaaslike_nuus_skakel (muni_kode, vlak);

-- Every URL the matcher has looked at, matched or not, so a feed item is matched once.
create table if not exists public.plaaslike_nuus_gesien (
  url text primary key,
  gesien_om timestamptz not null default now()
);

alter table public.plaaslike_nuus enable row level security;
alter table public.plaaslike_nuus_skakel enable row level security;
alter table public.plaaslike_nuus_gesien enable row level security;

drop policy if exists "publiek lees sigbare plaaslike nuus" on public.plaaslike_nuus;
create policy "publiek lees sigbare plaaslike nuus" on public.plaaslike_nuus
  for select to anon, authenticated using (not versteek);
drop policy if exists "publiek lees plaaslike nuus-skakels" on public.plaaslike_nuus_skakel;
create policy "publiek lees plaaslike nuus-skakels" on public.plaaslike_nuus_skakel
  for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------
-- 5. koppel_nuus
-- ---------------------------------------------------------------------------

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
  ),
  -- The longest name wins where names overlap ("Pretoria North" over "Pretoria").
  langste as (
    select * from treffers a
    where not exists (
      select 1 from treffers b
      where b.n > a.n and b.s <= a.s and a.s + a.n <= b.s + b.n
    )
  ),
  genoem as (
    select distinct l.muni_kode from langste l where l.is_muni
  ),
  bevestig as (
    select * from langste l
    where l.muni_kode = any (munis)
       or l.muni_kode in (select g.muni_kode from genoem g)
  ),
  plek_rye as (
    select b.muni_kode, u.wyk_id, b.naam as plek,
           case when cardinality(b.wyk_ids) <= 3 then 'wyk' else 'dorp' end as vlak,
           cardinality(b.wyk_ids) as grootte
    from bevestig b, unnest(b.wyk_ids) as u(wyk_id)
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
  from bevestig b
  where b.is_muni
  order by 1, 2 nulls first;
$$;

revoke all on function public.koppel_nuus(text, text[]) from public, anon, authenticated;
grant execute on function public.koppel_nuus(text, text[]) to service_role;

-- ---------------------------------------------------------------------------
-- 6. neem_plaaslike_nuus_in
--
-- items: [{titel, bron, url, gepubliseer_om, teks, munis: [..]}]. Items already in
-- plaaslike_nuus_gesien are skipped; the rest are matched, and only matched items are
-- stored. Returns how many were new, how many matched.
-- ---------------------------------------------------------------------------

create or replace function public.neem_plaaslike_nuus_in(items jsonb)
returns table (nuut integer, gekoppel integer)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  it jsonb;
  v_munis text[];
  v_id bigint;
  v_nuut integer := 0;
  v_gekoppel integer := 0;
begin
  delete from public.plaaslike_nuus_gesien where gesien_om < now() - interval '21 days';

  for it in select * from jsonb_array_elements(items)
  loop
    insert into public.plaaslike_nuus_gesien (url) values (it->>'url')
    on conflict (url) do nothing;
    if not found then
      continue;
    end if;
    v_nuut := v_nuut + 1;
    -- RETURNING INTO leaves the variable untouched when ON CONFLICT skips the row.
    v_id := null;

    select coalesce(array_agg(x), '{}') into v_munis
    from jsonb_array_elements_text(coalesce(it->'munis', '[]'::jsonb)) as x;

    create temp table if not exists _koppel (muni_kode text, wyk_id text, plek text, vlak text) on commit drop;
    delete from _koppel where true;
    insert into _koppel select * from public.koppel_nuus(it->>'teks', v_munis);
    if not exists (select 1 from _koppel) then
      continue;
    end if;

    insert into public.plaaslike_nuus (titel, bron, url, gepubliseer_om)
    values (it->>'titel', it->>'bron', it->>'url', (it->>'gepubliseer_om')::timestamptz)
    on conflict (url) do nothing
    returning id into v_id;
    if v_id is null then
      continue;
    end if;

    insert into public.plaaslike_nuus_skakel (nuus_id, muni_kode, wyk_id, plek, vlak)
    select v_id, k.muni_kode, k.wyk_id, k.plek, k.vlak from _koppel k
    on conflict do nothing;
    v_gekoppel := v_gekoppel + 1;
  end loop;

  return query select v_nuut, v_gekoppel;
end;
$$;

revoke all on function public.neem_plaaslike_nuus_in(jsonb) from public, anon, authenticated;
grant execute on function public.neem_plaaslike_nuus_in(jsonb) to service_role;

-- ---------------------------------------------------------------------------
-- 7. Leesfunksies vir die werf
-- ---------------------------------------------------------------------------

-- One ward: up to p_perk stories per level, newest first, last 30 days. A story appears
-- once, at its narrowest level for this ward.
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
  eens as (
    select distinct on (k.id) * from kandidate k order by k.id, k.orde
  ),
  gerangskik as (
    select e.*, row_number() over (partition by e.vlak order by e.gepubliseer_om desc) as rn
    from eens e
  )
  select g.vlak, g.plek, g.titel, g.bron, g.url, g.gepubliseer_om
  from gerangskik g
  where g.rn <= least(greatest(p_perk, 1), 10)
  order by g.orde, g.gepubliseer_om desc;
$$;

revoke all on function public.plaaslike_nuus_vir_wyk(text, integer) from public;
grant execute on function public.plaaslike_nuus_vir_wyk(text, integer) to anon, authenticated, service_role;

-- One municipality: every story linked to it at any level, once each, newest first.
create or replace function public.plaaslike_nuus_vir_muni(p_kode text, p_perk integer default 6)
returns table (plek text, titel text, bron text, url text, gepubliseer_om timestamptz)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select e.plek, e.titel, e.bron, e.url, e.gepubliseer_om
  from (
    select distinct on (n.id) s.plek, n.titel, n.bron, n.url, n.gepubliseer_om,
           case s.vlak when 'munisipaliteit' then 1 when 'dorp' then 2 else 3 end as orde
    from public.plaaslike_nuus_skakel s
    join public.plaaslike_nuus n on n.id = s.nuus_id
    where s.muni_kode = p_kode
      and not n.versteek
      and n.gepubliseer_om > now() - interval '30 days'
    order by n.id, orde
  ) e
  order by e.gepubliseer_om desc
  limit least(greatest(p_perk, 1), 20);
$$;

revoke all on function public.plaaslike_nuus_vir_muni(text, integer) from public;
grant execute on function public.plaaslike_nuus_vir_muni(text, integer) to anon, authenticated, service_role;
