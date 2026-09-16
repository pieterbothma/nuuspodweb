-- Verkiesing 2026, Fase 2b, Task 1 — herstelrondte 2: laat val die ongebruikte
-- rou-kolom-trigram-indekse op stemstasies. Toegepas op projek xxysgvanarnirxoxrbkj met
-- die Supabase MCP apply_migration-hulpmiddel.
--
-- `stemstasies_naam_trgm` en `stemstasies_adres_trgm` kom uit die Fase 2a-basisskema en
-- staan op die ROU `naam`/`adres`-kolomme. Sedert 20260916065118_stemstasies_soekkolomme
-- vergelyk soek() net teen die gestoorde `naam_soek`/`adres_soek`-kolomme (elk met sy eie
-- GIN-trigram- en btree-voorvoegselindeks), so hierdie twee word deur geen navraag in
-- hierdie stelsel meer gebruik nie — hulle is net ~15 MB (7 064 kB + 8 576 kB) en 'n
-- skryfkoste op elke publisering. pg_stat_user_indexes wys `stemstasies_adres_trgm` op 0
-- skanderings en `stemstasies_naam_trgm` op 2 (albei van 'n diagnostiese navraag wat ek
-- self voor die gestoorde kolomme gedoen het, nie van soek() nie), teenoor 219 elk op die
-- twee `_soek`-indekse.
--
-- Die rou kolomme self bly (soek() gee `stemstasies.naam` as die etiket en `adres` as die
-- stemlokaal se adres terug); net die indekse verdwyn.

set search_path = public, extensions;

drop index if exists public.stemstasies_naam_trgm;
drop index if exists public.stemstasies_adres_trgm;
