# Verkiesing Fase 2a — handoff to Fase 2b

Status 2026-09-15: Fase 2a (base data in `stg_`) is complete. All 8 tasks passed review, plus a final whole-branch review and a fix round (206 tests). `data/kontroleer.py` exits 0 with the hard gates in place. Nothing is published yet, and there are no site changes.

## Loaded (stg)
| Table | Rows |
|---|---:|
| stg_munisipaliteite | 213 + 44 districts |
| stg_wyke | 4,485 (incl. the 15 NC451 wards, recovered from the IEC NC PDF) |
| stg_stemstasies | 23,696 |
| stg_plekke | 22,196 |
| stg_plek_wyke | 35,582 |
| stg_plek_aliasse | 518 |
| stg_raad_uitslae_2021 | 2,789 |
| stg_raad_grootte_2021 | 213 |

Run order and reload caveats: `data/README.md`.

## Owner decisions (Piet, 2026-09-15: "good on decisions you suggested")
1. Publish with 4,485 wards. Ask the IEC/MDB about the 3 missing Free State wards (they have no stations either).
2. Alias fan-out (Kaapstad → 126 sub places): search groups results per main place / municipality instead of listing sub places.
3. Harbour slivers 199056003, 199057014 and 199063016 (no ward): exclude from search.
4. 2021 "no majority" is measured against the full council size, independents included: 70 councils.
5. The 2 KZN285 stations with an empty address: show the station name only.
6. Mahikeng: add a search alias → Mafikeng (NW383). The municipality display name should also read Mahikeng.
7. Soweto-type queries: search must match the main place (`mp_naam`), not only the sub place name. See Fase 2b design item B.
8. Pretoria-Oos, Johannesburg-Suid and Kaapse Vlakte aliases are removed for now. Curated suburb lists come later, if wanted.

## Fase 2b design items (from the final review)
- **A. Publish vs the 8s PostgREST timeout.** A one-transaction copy of 22k places, 35k overlaps and 23.7k stations into indexed public tables will time out. Choose between a table swap, chunked copies or an MCP/direct-SQL runbook.
- **B. Main-place search.** Add a normalised `mp_naam_soek` column with a trigram index (strip the " NU"/" SH" suffixes, keep the Stats SA "Port Elizaberth" spelling behind aliases), or generate main-place alias rows. Normalise both sides of the alias search.
- **C. Party/candidate IDs.** `partye.id` and `kandidate.id` are identity columns, but the stg copies have no ID generation. Pick client-assigned IDs (OVERRIDING SYSTEM VALUE) or natural keys that stay stable across IEC correction reloads.
- **D. Ranking.** Rank ward matches by overlap share. Stellenbosch currently also returns City of Cape Town and Drakenstein via ≥1 ha slivers.
- **E. 2021 results display.** 1,496 of the 2,789 seat rows are 0-seat parties; decide whether to list them. Districts have no 2021 council result. Show 2021 as council totals only, never next to 2026 wards (42 municipalities changed ward counts).
- **F. The 4 rural places** (Mnquma/"Mnquna", Ngquza Hill, Nyandeni, Thulamela, 156 rows) need direct SQL after any full places reload. The ranged delete-first `bou_plek_wyke` has not run live yet; its first chunked run is its test.

## Deferred minors
- `plaas_bondels` retries 5xx. With the unique keys, a server-committed batch that the client saw as a 502 now fails loudly with the table partly loaded; rerun the loader.
- The full-load second alias guard in `laai_plekke.py` fires after `stg_leeg` (unreachable in practice; `kontroleer.py` catches empty aliases).
- Supabase default privileges still grant anon/authenticated rights on sequences created later; revoke them on new sequences.
- `bron_ry` is encoded as page×1000 for stations but page×10000 for candidates.
- The REST client code is partly duplicated in `laai_plekke.py` and `kontroleer.py`.
- Non-network exceptions outside `veilig()` in `kontroleer.py` still crash before the report is written.
- The "excess seat" flag in the 2021 seats is stripped, not stored.
- `data/uitvoer/plekke-verslag.md` is stale; older plan docs cite the pre-rename migration filenames.
- Candidate parser: blank muni/party cells raise; empty `volle_naam`/`van` cells are not yet guarded. Revisit on the real 2026 list (16 Sep).
