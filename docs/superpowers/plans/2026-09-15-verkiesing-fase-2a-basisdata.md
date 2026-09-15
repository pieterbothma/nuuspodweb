# Verkiesing Fase 2a — base data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Load the Phase 2 base data into Supabase `stg_` tables and produce a check report for Piet: wards, municipalities, voting stations, places and aliases, 2021 council seats, plus a candidate-list parser proven on the 2021 fixture. Stop there. Publishing to `public` and the site pages are Fase 2b.

**Architecture:**
- DDL goes in via Supabase MCP migrations.
- Python loaders in `data/` (run with `uv run --with …`) parse the source files and POST batches to PostgREST using the service secret key. `stg_` tables are RLS-on with no grants, so they're invisible to anon.
- Server-side SQL functions, service-role only, do overlaps, self-tests and the later publish step.

**Tech stack:** Python 3.12 via `uv`, `pdfplumber`, `pyshp`, `shapely` 2, `pyproj`, `httpx`, `pytest`; Supabase Postgres with PostGIS and pg_trgm.

**Spec:** `docs/superpowers/specs/2026-09-15-verkiesing-fase-2-wyksoeker-design.md` (§3–§5, §8, §11). Parent: `docs/superpowers/specs/2026-09-14-verkiesing-2026-design.md`.

**Note on format:** unlike the Drop 1 plan, loaders are specified by contract, fixtures and tests rather than verbatim code. The source files' exact layouts (PDF columns, shapefile fields) must be discovered from the files themselves, and each task's first step does that discovery.

## Global Constraints
- **Supabase project:** `verkiesing-2026`, ref `xxysgvanarnirxoxrbkj`.
- **Credentials:**
  - Loaders read `VERKIESING_SUPABASE_URL` and `VERKIESING_SUPABASE_SECRET_KEY` from `~/nuuspod/.env.local`. Values may be wrapped in double quotes, so strip them.
  - Never print or commit the key. Never write it into `nuuspod-web/.env.local`.
- **No direct Postgres connection.** DDL goes via MCP `apply_migration` (Task 1 only); data goes via PostgREST `POST /rest/v1/stg_*` and `POST /rest/v1/rpc/*` with headers `apikey` + `Authorization: Bearer <secret>`.
- **`stg_` tables:** RLS enabled, no policies, `REVOKE ALL … FROM anon, authenticated`. Server functions are `SECURITY DEFINER`, `SET search_path = public, extensions`, with `EXECUTE` revoked from `PUBLIC, anon, authenticated` and granted to `service_role`.
- **Source files:** in `nuuspod-web/data/bron/` (gitignored):
  - `MDBWards2026.zip`
  - `stemstasies-2026-WC.pdf` (others downloaded in Task 4)
  - `kandidate-2021-WC.pdf`
  - `setelberekening-2021-EC135.pdf`
  - `lge2021_{EC,FS,GP,KN,MP,NC,NP,NW,WP}.csv`
  - `plekke/Subplace.zip`, `plekke/MainPlace.zip`
- **Personal data:** masked ID numbers in candidate PDFs are never parsed into memory structures that get stored or written to disk outputs.
- **Official counts to reconcile:**
  - 4,488 wards (the MDB file has 4,485; 3 Free State wards are missing)
  - 213 municipalities with wards (8 metros + 205 locals), plus 44 districts
  - candidates: 142,072 total, 100,856 ward, 40,241 PR, 975 independent ward (real list only, Fase 2b)
- **Naming:** Afrikaans identifiers, English code comments, Afrikaans commit messages. Trailers:
  ```
  Co-Authored-By: <implementing model> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p
  ```
- **Repo and branch:** `~/projects/nuuspod-web`, branch `verkiesing-fase-2`. Don't push. Explicit `git add` paths.
- **Every loader:**
  - is idempotent: it empties its `stg_` table(s) first via `rpc/stg_leeg`;
  - writes `data/uitvoer/<datastel>-verslag.md`, where `data/uitvoer/` is gitignored;
  - exits non-zero on failure.
- **No site (`app/`) changes in this plan.**

## File map
| File | Responsibility |
|---|---|
| `supabase/migrations/20260915100000_verkiesing_fase2_basis.sql` | Record of the applied migration |
| `data/README.md` | How to run each loader and the tests |
| `data/lib/omgewing.py` | Read env from `~/nuuspod/.env.local` |
| `data/lib/supabase.py` | `plaas_bondels(tabel, rye, grootte)`, `rpc(naam, args)`, retry and backoff |
| `data/lib/geo.py` | Reproject 3857→4326, to MultiPolygon, EWKT |
| `data/lib/teks.py` | Name normalisation (`normaliseer`), cp1252 decode helpers |
| `data/laai_wyke.py` | MDB wards → `stg_wyke`, `stg_munisipaliteite` |
| `data/laai_stemstasies.py` | IEC station PDFs → `stg_stemstasies` |
| `data/laai_plekke.py` | SP/MP → `stg_plekke`; `rpc/bou_plek_wyke`; aliases → `stg_plek_aliasse` |
| `data/aliasse.csv` | Hand-curated Afrikaans/English aliases |
| `data/laai_uitslae_2021.py` | 2021 seats → `stg_raad_uitslae_2021` |
| `data/kandidate_ontleder.py` | Candidate PDF parser (pure; no DB) |
| `data/kontroleer.py` | Combined `data/uitvoer/kontroleverslag.md` |
| `data/tests/test_*.py` | pytest for pure functions and parsers |

---

### Task 1: Schema, staging, server functions

**Files:** `supabase/migrations/20260915100000_verkiesing_fase2_basis.sql`

**Requirements:**
- `create extension if not exists postgis with schema extensions; create extension if not exists pg_trgm with schema extensions;` Check with MCP `list_extensions` first. If postgis is already in `public`, leave it there.
- **Public tables** (spec §4): `munisipaliteite`, `wyke`, `stemstasies`, `partye`, `kandidate`, `stembrief_volgorde`, `raad_uitslae_2021`, `plekke`, `plek_wyke`, `plek_aliasse`, `data_weergawes`.
  - Columns and types exactly as spec §4, plus sensible NOT NULL and CHECK constraints: `wyk_id ~ '^\d{8}$'`, `stembrief in ('wyk','pv_plaaslik','pv_distrik')`, `tipe in ('metro','plaaslik','distrik')`.
  - Geometry columns: `geometry(MultiPolygon,4326)`.
  - Add foreign keys where cheap (e.g. `wyke.muni_kode → munisipaliteite.kode`). `plek_wyke.wyk_id → wyke.wyk_id` stays **without** FK on stg.
- **Staging tables:** `stg_<name>` for each of the above except `data_weergawes`, created `LIKE <public> INCLUDING DEFAULTS INCLUDING CONSTRAINTS` but with no foreign keys.
- **RLS:**
  - Public tables: anon `SELECT` granted with policy `using (true)`. No writes for anon or authenticated.
  - `stg_*` tables: RLS on, no policies, all privileges revoked from anon and authenticated.
  - `data_weergawes`: anon may select.
- **Indexes:** GiST on `wyke.geom`, `plekke.geom`, `stg_wyke.geom`, `stg_plekke.geom`; GIN `gin_trgm_ops` on `plekke.naam_soek`, `plek_aliasse.alias`, `stemstasies.naam`, `stemstasies.adres`.
- **Server functions** (all service-role only as in Global Constraints):
  - `stg_leeg(tabel text)`: `TRUNCATE` one `stg_` table after validating the name against an allowlist.
  - `bou_plek_wyke()`:
    - Deletes `stg_plek_wyke`.
    - Inserts rows for every `stg_plekke` × `stg_wyke` intersection where `ST_Area(ST_Intersection)` on geography ≥ 5 % of the place area or ≥ 10,000 m².
    - Stores `oorvleueling = intersection/place area` (0–1).
    - Returns the inserted count.
  - `kontroleer_wyke()`: returns `table(wyke_totaal int, met_geom int, sonder_geom int, selftoets_geslaag int, selftoets_gefaal int, gefaalde_ids text[])`. The self-test checks `ST_Contains(w.geom, ST_PointOnSurface(w.geom))` resolves via a point-in-polygon query back to the same `wyk_id` and exactly one ward, over `stg_wyke`.
- **Record keeping:** apply with MCP `apply_migration` (name `verkiesing_fase2_basis`), save the identical SQL in the file, then run MCP `get_advisors` (security) and resolve anything ERROR-level caused by these objects.

**Verification:**
- With the publishable key, `GET /rest/v1/stg_wyke?select=wyk_id&limit=1` returns 401/403 or an empty or permission error (never rows).
- `GET /rest/v1/wyke?select=wyk_id&limit=1` returns `[]`.
- With the secret key, `POST /rest/v1/rpc/stg_leeg` `{"tabel":"stg_wyke"}` returns 200/204.
- With the publishable key, the same call is refused.
- Commit: `Verkiesing Fase 2: skema, stg_-tabelle en bedienerfunksies`.

### Task 2: Loader library + tests

**Files:** `data/lib/{__init__,omgewing,supabase,geo,teks}.py`, `data/tests/test_teks.py`, `data/tests/test_geo.py`, `data/README.md`, `.gitignore` (add `/data/uitvoer/`)

**Requirements:**
- `omgewing.lees()`: returns `{url, sleutel}` from `~/nuuspod/.env.local`, with quotes stripped. Raises a clear error if either is missing.
- `supabase.plaas_bondels(tabel, rye, grootte=500)`:
  - POSTs JSON batches with `Prefer: return=minimal`.
  - On 413 it halves the batch and retries.
  - On 429/5xx it retries 3× with exponential backoff.
  - Any other failure raises with the response text truncated to 500 chars, never including headers.
  - Returns the rows sent.
- `supabase.rpc(naam, args)`: POST `rpc/<naam>`, returns the parsed JSON.
- `geo.na_ewkt_4326(shape, bron_epsg)`:
  - Converts pyshp or shapely geometry to MultiPolygon.
  - Reprojects with pyproj `Transformer.from_crs(bron_epsg, 4326, always_xy=True)` when needed.
  - Fixes invalid geometry with `shapely.make_valid` and keeps polygonal parts.
  - Returns `"SRID=4326;" + wkt` with rounding to 6 decimals.
- `teks.normaliseer(s)`: lowercase, strip accents (é→e, ë→e, ô→o), hyphens and apostrophes → space, collapse spaces. Examples: "Pretoria-Oos" → "pretoria oos", "Môrelig" → "morelig".
- `teks.skoon_plek_naam(naam)`:
  - Strips a trailing " SP", returning `(naam, landelik=False)`.
  - " NU" or " SH" → stripped with `landelik=True`.
  - Trims whitespace.

**Tests (pytest, RED then GREEN):**
- normaliseer examples above plus "Die Boord" → "die boord".
- skoon_plek_naam: "Stellenbosch SP" → ("Stellenbosch", False); "Paarl NU" → ("Paarl", True).
- na_ewkt_4326: a small 3857 square near Cape Town (build it in the test) returns EWKT starting `SRID=4326;MULTIPOLYGON` with longitude ≈ 18.4 and latitude ≈ −33.9.

**Run:** `cd data && uv run --with pytest,shapely,pyproj,pyshp,httpx pytest -q`.

**Commit:** `Verkiesing Fase 2: laaibiblioteek met toetse`.

### Task 3: Wards and municipalities

**Files:** `data/laai_wyke.py`

**Steps:**
1. **Discover:**
   - Unzip `data/bron/MDBWards2026.zip` into `data/bron/wyke/`.
   - Print the `.prj` and fields.
   - Confirm WardID, WardNo, CAT_B, MUNICNAME, DISTRICT, Province, the record count (expect 4,485) and the CRS (expect 3857). Record these in the verslag.
2. **`stg_munisipaliteite`:** one row per distinct CAT_B.
   - `tipe = 'metro'` if the code is one of BUF, CPT, EKU, ETH, JHB, MAN, NMA, TSH; otherwise `plaaslik`.
   - `distrik_kode` from the DISTRICT field when present.
   - Add one `distrik` row per distinct DISTRICT code, with the name from any available field. If no district name field exists, use the code and note it.
   - Province as given.
3. **`stg_wyke`:** `wyk_id` = WardID as 8-digit text, `wyk_nr` = WardNo, `muni_kode` = CAT_B, `geom` = `geo.na_ewkt_4326(shape, 3857)`. Batch size 25 because polygons are large; let the 413 halving handle outliers.
4. Call `rpc/kontroleer_wyke`.
5. **Verslag:**
   - counts: wards (expect 4,485), municipalities with wards (expect 213) and the metros list, districts;
   - the self-test result (expect 4,485 pass or explain failures);
   - per-province ward counts vs the IEC table (Free State 308 vs 311).

**Commit:** `Verkiesing Fase 2: wyke en munisipaliteite na stg`.

### Task 4: Voting stations

**Files:** `data/laai_stemstasies.py`, `data/tests/test_stemstasies.py`, `data/tests/fixtures/` (a 1–2 page PDF extract is **not** committed; tests read `data/bron/stemstasies-2026-WC.pdf` and skip if missing)

**Steps:**
1. **Discover:**
   - Fetch https://www.elections.org.za/pw/Elections-And-Results/Voting-Stations-LGE-2026 (curl; the site may block WebFetch).
   - Find the nine per-province PDF links and download them to `data/bron/stemstasies-2026-<PROV>.pdf`. Keep WC if it's already there.
   - Open WC with pdfplumber: detect table columns (spec lists Province, Municipality, Ward, VD, Station name, Address) and repeated headers.
2. **Parser `ontleed(pdf_pad) -> list[dict]`:** keys `vd_nommer` (text, as printed), `naam`, `adres`, `wyk_id` (8 digits), `muni_kode` (derived from the municipality column: the code if printed, else a mapping from name to CAT_B via `stg_munisipaliteite` names loaded in Task 3), `bron_lêer`, `bron_ry` (page:row).
   - Joins wrapped multi-line cells.
   - Skips header and footer rows.
   - Mobile-station route rows, if present, go into the verslag rather than the table.
3. **Tests:**
   - WC parse: ≥ 1,600 rows (the research counted 1,623).
   - Every `wyk_id` matches `^\d{8}$` and starts with a WC municipality code prefix.
   - No duplicate `vd_nommer`.
4. **Load** all provinces → `stg_stemstasies` (batch 500).
5. **Verslag:**
   - rows per province;
   - stations whose `wyk_id` isn't in `stg_wyke` (fetch the ward ids via REST);
   - municipality names that couldn't be mapped;
   - duplicate VDs.

**Commit:** `Verkiesing Fase 2: stemlokale na stg`.

### Task 5: Places, overlaps, aliases

**Files:** `data/laai_plekke.py`, `data/aliasse.csv`, `data/tests/test_plekke.py`

**Steps:**
1. **Discover:** unzip both place files into `data/bron/plekke/`. Confirm SP fields (SP_CODE, SP_NAME, MP_NAME, MN_NAME), the CRS (expect EPSG:4148/WGS84-equivalent, so treat as 4326), the cp1252 encoding (`shapefile.Reader(..., encoding="cp1252")`), and the count of 22,196.
2. **`stg_plekke`:**
   - `sp_kode` = SP_CODE as text;
   - `naam` and `landelik` via `skoon_plek_naam(SP_NAME)`;
   - `naam_soek` = `normaliseer(naam)`;
   - `mp_naam` = MP_NAME;
   - `geom` EWKT (no reprojection).
   - Batch 200.
3. **`rpc/bou_plek_wyke`** (run after Task 3's wards are loaded). Record the returned count and the elapsed time.
   - If the RPC times out (PostgREST statement timeout), split the work: add an optional `(van int, tot int)` range over a row number of `stg_plekke` to the function via a follow-up migration, and loop.
4. **`data/aliasse.csv`** (columns `alias,naam,mp_naam,munisipaliteit_naam`) with at least these rows:
   - `Kaapstad` → Cape Town (Cape Town main place)
   - `Pretoria-Oos`, `Pretoria-Noord`, `Pretoria-Wes` → Pretoria places, where the sub-place names exist; otherwise map to the Pretoria main place
   - `Johannesburg-Suid` → Johannesburg South
   - `Oos-Londen` → East London
   - `Port Elizabeth` / `Gqeberha` → both directions as they exist in the data
   - `Bloemfontein` → Bloemfontein
   - `Durban` / `eThekwini`
   - `Die Strand` → Strand
   - `Kaapse Vlakte` → Cape Flats, if it exists as a place

   **Only include aliases whose target resolves** to one or more `sp_kode`. The loader resolves each by name (+ mp_naam if given) and inserts `stg_plek_aliasse(alias, sp_kode)` for every match. Unresolved rows are listed in the verslag, not guessed.
5. **Tests** (pure; reading the SP dbf only, no DB):
   - "Brooklyn" appears in ≥ 4 records across ≥ 3 distinct MN_NAME;
   - a record with "Waterkloof" exists with MN_NAME containing Tshwane;
   - `skoon_plek_naam` is applied correctly to 3 real records.
6. **Verslag:**
   - place count;
   - `plek_wyke` count;
   - places with 0 wards (expect some coastal/sea slivers; list the first 20);
   - top 10 places by ward count;
   - alias resolution table;
   - smoke queries via REST on stg for "brooklyn", "waterkloof", "stellenbosch", "kaapstad" (alias), "moreleta park", each showing municipality (via the 2026 ward → `stg_munisipaliteite`) and ward ids.

**Commit:** `Verkiesing Fase 2: plekke, oorvleuelings en aliasse na stg`.

### Task 6: 2021 council seats

**Files:** `data/laai_uitslae_2021.py`, `data/tests/test_uitslae_2021.py`

**Steps:**
1. **Discover the cleanest official source for seats per party per municipality for LGE 2021**, in this order:
   - a. an IEC results download listing seat allocation per municipality (results.elections.org.za/home/Downloads/ME-Results), Excel or CSV;
   - b. the per-municipality "Seat Calculation Detail" PDFs (pattern seen: `https://results.elections.org.za/home/LGEPublicReports/1091/Seat%20Calculation%20Detail/EC/EC135.pdf`; fixture `data/bron/setelberekening-2021-EC135.pdf`) for all municipal councils.

   Record the chosen source and URL list in the verslag. Don't compute seats from the VD CSVs (those are votes, not declared seats).
2. **Parser:** returns rows `muni_kode, party_naam, setels_wyk, setels_pv, setels_totaal`.
   - Test against the EC135 fixture: the totals must equal the council size printed in the PDF, and per-party ward + PR = total.
3. **Map to 2026 codes:** every 2021 municipality code must exist in `stg_munisipaliteite`. List any mismatch; outer boundaries were unchanged, so expect none.
4. **Load** `stg_raad_uitslae_2021`.
5. **Verslag:**
   - municipalities covered (expect all 213 local and metro councils; district PR seats are out of scope unless the source includes them cleanly);
   - councils where no party has > 50 % of seats (count and list);
   - any parse anomalies.

**Commit:** `Verkiesing Fase 2: amptelike raadsetels 2021 na stg`.

### Task 7: Candidate-list parser (fixture only)

**Files:** `data/kandidate_ontleder.py`, `data/tests/test_kandidate_ontleder.py`

**Steps:**
1. **Discover** the 2021 WC PDF layout with pdfplumber: columns Municipality, Party, "Ward \ List Order", IDNumber (masked), Fullname, Surname; header repeats; wrapped cells.
2. **`ontleed(pdf_pad) -> Iterator[Kandidaat]`** (dataclass): `muni_naam`, `muni_kode` (if printed), `party_naam`, `onafhanklik` (party == "INDEPENDENT"), `stembrief`, `wyk_id`, `lys_posisie`, `volle_naam`, `van`, `bron_lêer`, `bron_ry`.
   - Rule: an 8-digit value in the Ward/List column → `stembrief='wyk'`, `wyk_id`; a small integer → PR list with `lys_posisie`. `pv_distrik` applies when the municipality is a district (name starts with "DC" or contains "District"); otherwise `pv_plaaslik`.
   - The ID column is read positionally and discarded **before** building the dataclass. It never appears in any object, log or output.
3. **Tests:**
   - total rows > 0;
   - every row has either `wyk_id` or `lys_posisie`, never both;
   - independents only on `wyk` rows;
   - no field contains a digit run of ≥ 6 other than `wyk_id` (guards against the ID leaking);
   - counts by stembrief printed.
   - If the IEC publishes 2021 WC totals, assert them; otherwise record the counts in the verslag.
4. **Verslag** `kandidate-2021-fixture-verslag.md`: counts per municipality and stembrief, and 10 sample rows **without** ID numbers.

**Commit:** `Verkiesing Fase 2: kandidaatlys-ontleder, getoets op 2021`.

### Task 8: Combined check report

**Files:** `data/kontroleer.py`

**Requirements:**
- Reads the stg tables via REST and the verslag files.
- Writes `data/uitvoer/kontroleverslag.md` with every §5.3 item available at this stage: wards, municipalities, stations, places, overlaps, aliases, 2021 seats, the ward self-test and the place-search smoke tests.
- Adds a clear **"Nog nie gelaai nie: kandidate (16 Sep), stembriefvolgorde (23 Sep)"** section.
- Adds a **"Besluite nodig"** list of anomalies needing Piet's call.

No publish step in this plan.

**Commit:** `Verkiesing Fase 2: gekombineerde kontroleverslag`.
