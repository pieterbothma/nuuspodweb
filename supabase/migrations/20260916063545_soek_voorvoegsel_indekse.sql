-- Verkiesing 2026, Fase 2b, Task 1 — herstel-rondte 3: btree-voorvoegselindekse vir soek().
-- Toegepas op projek xxysgvanarnirxoxrbkj met die Supabase MCP apply_migration-hulpmiddel.
--
-- Measured on the published data (22 196 plekke, 23 696 stemstasies) against anon's 3s
-- statement_timeout:
--
--   soek('Brooklyn')  48 ms
--   soek('ka')      1 549 ms
--   soek('ma')      1 705 ms
--   soek('st')      1 866 ms
--
-- A GIN trigram index cannot serve `LIKE 'ka%'`, because a two-character pattern yields
-- no full trigram key, so every short query — exactly what a search box sends on the
-- second keystroke — fell back to a sequential scan that had to call
-- normaliseer_soekteks four times per station row. Under 3s, but with too little margin
-- to sit in front of a live site.
--
-- A btree index with the text_pattern_ops operator class has no minimum pattern length,
-- so it serves the class-1 (exact) and class-2 (prefix) tests directly; the GIN trigram
-- indexes stay for the class-3 `%` test. The two stemstasies ones are expression indexes
-- on normaliseer_soekteks, so they join the existing pair in needing a REINDEX if that
-- function's body ever changes.

set search_path = public, extensions;

create index if not exists plekke_naam_soek_voorvoegsel
  on public.plekke (naam_soek text_pattern_ops);

create index if not exists plekke_mp_naam_soek_voorvoegsel
  on public.plekke (mp_naam_soek text_pattern_ops);

create index if not exists stemstasies_naam_soek_voorvoegsel
  on public.stemstasies (public.normaliseer_soekteks(naam) text_pattern_ops);

create index if not exists stemstasies_adres_soek_voorvoegsel
  on public.stemstasies (public.normaliseer_soekteks(adres) text_pattern_ops);
