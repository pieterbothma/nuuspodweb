# Verkiesing 2026 — Phase 2 (Drop 2): wyk-soeker design

Written 15 September 2026, after Drop 1 went live on www.nuuspod.co.za (site `main` 6fa97a8).
Builds on `2026-09-14-verkiesing-2026-design.md` (the parent spec). Its hard rules, Lig-neon look and neutrality rules
all still apply. This spec covers sub-project A's second drop only. Results night (D) and the prediction model (E)
get their own specs.

## 1. Goal

A voter types a suburb, town or voting station, or taps "Gebruik my ligging", and within a few seconds sees their
2026 ward:
- the ward's voting stations;
- every candidate on their ballots;
- the municipality's official 2021 council result.

Everything comes from structured public data and nothing is generated. The internal target date is Friday 25 September.
Nothing on the site announces a date (parent rule 6).

## 2. Constraints carried into Phase 2

- **No model-generated claims about candidates or parties.** Every name and number is rendered from IEC or MDB rows.
- **Human approval gate:** no data reaches `public` without Piet approving the check report (§5.3).
- **Neutral ordering and display:**
  - Ordering: alphabetical until the IEC ballot draw (23 Sep), then official ballot order. Never by size or 2021 result.
  - Every candidate gets equal space.
  - No party colours, logos or photos.
- **Official data only on public pages.** The 2021 result is shown per municipality only. The ward-level 2021 remap stays internal.
- **Copy:** all new Afrikaans UI copy is written by Gemini (house rule), fact-checked, and added to `lib/verkiesing/kopie.ts`.
- **No personal data beyond what the IEC publishes for display.** The masked ID numbers in the candidate list are
  never parsed into the database. Geolocation coordinates are never stored or logged.
- **The site carries no advertising** (Piet, 15 Sep). If that changes, re-check IEC website clause 2.2 and the MDB
  licence first. Izak is pursuing IEC contact and consent this week.
- **No IEC API dependency.** Phase 2 runs entirely on published downloads.

## 3. Data sources

| Dataset | Source | Status (15 Sep) | Processing |
|---|---|---|---|
| Ward boundaries 2026 | MDB `MDBWards2026.zip` (Spatial Knowledge Hub) | Available: 4,485 polygons, EPSG:3857 | Reproject to 4326; fields WardID, WardNo, CAT_B, MUNICNAME, Province |
| Voting stations | IEC per-province PDFs (published 13 Aug) | Available | Parse: Province, Municipality, Ward (8-digit), VD number, station name, address |
| Candidates | IEC final candidate list | **Due 16 Sep.** Format unconfirmed; 2021 was per-province PDFs printed from Excel | Parse: Municipality, Party, "Ward \ List Order", Fullname, Surname. The masked ID column is dropped at parse time |
| Place names | Stats SA Census 2011 Sub Place (`SP_SA_2011`, 22,196 polygons) + Main Place (`MP_SA_2011`) | Downloaded and verified (mirror: github.com/j-norwood-young/SA-Maps) | Windows-1252 → UTF-8; strip trailing " SP"; " NU"/" SH" → flag `landelik`; overlap with 2026 wards |
| Afrikaans aliases | Own table (e.g. Kaapstad→Cape Town, Pretoria-Oos→Pretoria East) | To build | Hand-curated seed. GeoNames alternate names optional (CC BY 4.0) |
| 2021 council results | IEC results downloads / seat calculation reports per municipality | Available | Seats per party per municipality; "no majority" computed |
| Ballot order | IEC ballot draw | **23 Sep.** Publication format unknown | Party order per municipality and ballot, if published in usable form |

**Attribution** (on ward and municipality pages): "Bron: OVK (IEC) · Munisipale Afbakeningsraad · Statistiek Suid-Afrika,
Sensus 2011 (eie verwerking)", plus "© GeoNames" if its aliases are used.

## 4. Database (Supabase `verkiesing-2026`, ref `xxysgvanarnirxoxrbkj`)

Extensions: `postgis`, `pg_trgm`.

| Table (`public`, each mirrored as `stg_<name>` in `public`, service-role only) | Key columns |
|---|---|
| `munisipaliteite` | `kode` pk (e.g. `WC024`, `CPT`), `naam`, `tipe` (`metro` / `plaaslik` / `distrik`), `distrik_kode`, `provinsie` |
| `wyke` | `wyk_id` text pk (8-digit), `wyk_nr` int, `muni_kode`, `geom` MultiPolygon 4326 **nullable** (3 Free State wards are missing from the MDB file) |
| `stemstasies` | `vd_nommer` pk, `naam`, `adres`, `wyk_id`, `muni_kode`, `bron_lêer`, `bron_ry` |
| `partye` | `id`, `naam` (as in the IEC list), `afkorting` nullable |
| `kandidate` | `id`, `muni_kode`, `stembrief` (`wyk` / `pv_plaaslik` / `pv_distrik`), `wyk_id` nullable, `lys_posisie` nullable, `party_id` nullable, `onafhanklik` bool, `volle_naam`, `van`, `bron_lêer`, `bron_ry` |
| `stembrief_volgorde` | `muni_kode`, `stembrief`, `party_id`, `posisie` |
| `raad_uitslae_2021` | `muni_kode`, `party_naam`, `setels_wyk`, `setels_pv`, `setels_totaal` |
| `plekke` | `sp_kode` pk, `naam`, `naam_soek` (normalised), `mp_naam`, `landelik`, `geom` |
| `plek_wyke` | `sp_kode`, `wyk_id`, `oorvleueling` (share of the place's area). Keep a row if ≥ 5 % of the place or ≥ 1 ha |
| `plek_aliasse` | `alias`, `sp_kode` |
| `data_weergawes` | `datastel`, `bron_url`, `bron_datum`, `rye`, `gelaai_om`, `gepubliseer_om` |

**Access:** anon gets read-only `SELECT` on the `public` tables via RLS. `stg_` tables are not exposed to anon.

**Indexes:** GIN trigram on `plekke.naam_soek`, `plek_aliasse.alias`, `stemstasies.naam` and `stemstasies.adres`;
GiST on `wyke.geom` and `plekke.geom`.

**RPCs** (`security invoker`, `stable`, `EXECUTE` granted to anon):
- `vind_wyk(lat double precision, lng double precision) → table(wyk_id, wyk_nr, muni_kode, muni_naam)`
  - point-in-polygon on `wyke`
- `soek(q text) → table(soort, etiket, muni_naam, wyk_ids text[], teiken)`
  - `soort` is `plek` or `stemlokaal`
  - Plekke come through alias or name trigram, grouped with their municipality (from the 2026 ward, never from the 2011 codes) and overlapping ward ids.
  - Stemlokale are matched on name or address.
  - Results are ranked: exact before prefix before trigram, and metro or larger town before rural. Maximum 20.
  - Input shorter than 2 characters returns nothing.

## 5. Pipeline (`nuuspod-web/data/`)

### 5.1 Tools
- Python scripts run with `uv run --with pdfplumber,pyshp,shapely,httpx`.
- **No direct Postgres connection** (Piet, 15 Sep). DDL (tables, RLS, functions) is applied as migrations via the Supabase MCP. Data loads through PostgREST with the existing secret key (`VERKIESING_SUPABASE_URL` / `VERKIESING_SUPABASE_SECRET_KEY` in `~/nuuspod/.env.local`), batched with retries.
- **Staging tables** live in `public` with a `stg_` prefix, because PostgREST exposes only `public`. They get RLS enabled, no policies and no anon grants, so they are invisible to the site. The service role bypasses RLS.
- **Geometry** is sent as EWKT text (`SRID=4326;MULTIPOLYGON(...)`) from shapely and cast by PostGIS on insert. Reprojection from EPSG:3857 is done in Python (pyproj or shapely transform) before sending.
- **Server-side steps** — overlaps, checks and the staging → public swap — are SQL functions called via RPC. They are `SECURITY DEFINER`, with `EXECUTE` revoked from `public`, `anon` and `authenticated`, and granted to `service_role` only.
- **Large source files** go in `data/bron/`, which is gitignored.

### 5.2 Scripts (each idempotent; each writes `data/uitvoer/<datastel>-verslag.md`)
1. `laai_wyke.py`: MDB shapefile → `stg_wyke` + `stg_munisipaliteite`.
2. `laai_stemstasies.py`: IEC station PDFs → `stg_stemstasies`.
3. `laai_plekke.py`: SP/MP shapefiles → `stg_plekke`, then SQL builds `stg_plek_wyke`; seeds `plek_aliasse` from `data/aliasse.csv`.
4. `laai_uitslae_2021.py`: IEC 2021 seat data → `staging.raad_uitslae_2021`, mapped to 2026 municipality codes (outer boundaries unchanged; verify every code matches).
5. `laai_kandidate.py`: IEC final list → `stg_kandidate` + `stg_partye`.
   - Developed against the 2021 WC PDF fixture on 15 Sep, run on the real list on 16 Sep.
   - Rows with a list-order number go to `pv_plaaslik`, or to `pv_distrik` when the municipality is a district.
   - Rows with an 8-digit ward id go to `wyk`, and `Party = INDEPENDENT` sets `onafhanklik`.
   - The exact rules are confirmed against the real file on 16 Sep and written into the verslag.
6. `laai_stembrief_volgorde.py`: after 23 Sep, only if the IEC publishes the order in a parseable form.

### 5.3 Check report → approval → publish
`data/kontroleer.py` writes one combined `data/uitvoer/kontroleverslag.md` covering:
- Ward count vs 4,488, and wards without geometry, listed.
- Candidates vs 142,072 in total and per ballot type (100,856 ward · 40,241 PR · 975 independent ward), plus per-province counts.
- Candidates whose `wyk_id` is not in `wyke`, duplicates, and empty names.
- Stations per province, and stations whose `wyk_id` is not in `wyke`.
- The ward self-test (§8).
- Place search smoke results: Brooklyn, Waterkloof, Stellenbosch, Kaapstad, Moreleta Park.
- A diff against the currently published version (rows added, removed, changed).

Piet reads the report and says "publiseer". `data/publiseer.py` then:
1. Calls the `publiseer_fase2(datastelle text[])` RPC, which swaps each `stg_` table into its public table in one transaction.
2. Writes `data_weergawes`.
3. POSTs `/api/herlaai` for the tags `wyke` and `kandidate`. The route's allowlist is extended.

IEC correction rounds (until 25 Sep) re-run steps 5 → report → approval → publish.

## 6. Site

### 6.1 Wyk-soeker in the hero box
The neon box beside "Verkiesing 2026" becomes the search (it replaces "Bevestig jou status"; the OVK section stays below):
- **Label and input.** A label and one text input (`type="search"`, `inputMode="search"`, placeholder from copy),
  plus a secondary button "Gebruik my ligging".
- **Typing** (debounced 250 ms, min 2 characters) calls `GET /api/soek?q=`. The route handler calls the `soek` RPC with the
  publishable key and caches per `q` for an hour. Results appear in a listbox grouped into **Plekke** and
  **Stemlokale**:
  - Plek, one ward: "Brooklyn — Stad Tshwane · Wyk 81" → `/wyk/<id>`.
  - Plek, several wards: "Brooklyn — Stad Kaapstad · 3 wyke" → an inline chooser listing those wards (links).
  - Stemlokaal: "Laerskool Eikestad — Stellenbosch · Wyk 12" → `/wyk/<id>#stemlokale`.
  - No results: a short hint to try the station name or use location (copy slot).
- **"Gebruik my ligging":** browser geolocation, then `GET /api/wyk-by-punt?lat&lng` (`vind_wyk`), then navigate.
  - The route handler neither logs nor stores coordinates.
  - Denied or failed: an inline message (copy slot).
  - A point outside every ward (sea, or the missing FS wards): message plus a hint to search by station.
- **Keyboard and screen reader:** combobox pattern (arrow keys, Enter, Escape), `aria-live` result count, visible focus.
- **Home page `KontroleerRegistrasie`:** retired from the hero. The "Sien meer" link to `#registrasie` moves under the search as a small secondary link.

### 6.2 `/wyk/[wykId]`
ISR: no static params at build, `dynamicParams` true, cached with tags `wyke` / `kandidate`. Unknown or invalid ids return 404.
- **Header:** "Wyk {nr}", municipality (linked to its page), province.
- **"Wat doen 'n wyksraadslid?":** two or three sentences (Gemini copy, fact-checked against the Municipal Structures Act).
- **Stemlokale** (`#stemlokale`): name + address per station, sorted by name.
- **"Jou stembriewe"**, one block per ballot the voter receives:
  - **Wykstembrief:** every ward candidate — full name, then party name, or "Onafhanklik". Ordered alphabetically by surname until the draw, then by the party's ballot position (independents per the IEC order if published, else alphabetical after parties).
  - **PV-stembrief (plaaslike raad or metro):** the parties contesting, each expandable to its list in `lys_posisie` order.
  - **Distriksraad-stembrief:** only for wards in local municipalities, the parties on the district PR ballot, expandable the same way.
  - Order label shown: "Alfabeties" until the draw, "Volgorde soos op die stembrief" after (copy slots).
- **Footer strip:** attribution, "Laas bygewerk: {bron_datum}", link to the IEC source page, feedback prompt.
- **Metadata + Open Graph image** via `next/og`, code-rendered from data: "Wyk {nr} · {munisipaliteit} · {n} kandidate · Stem op 4 November" (template copy from Gemini). No party names on the card.

### 6.3 `/munisipaliteit/[kode]`
- Name, type, district, province.
- All wards as a compact grid of links.
- Parties contesting (alphabetical / ballot order).
- **"Raad ná 2021 (amptelik)":** table of party · ward seats · PR seats · total, sorted by party name (not seats), plus the computed line "Geen party het in 2021 'n meerderheid gehad nie" when true (copy slot).
- Attribution + data date.

### 6.4 Also
- `app/sitemap.ts` lists `/`, `/gids/*`, every `/wyk/*` and every `/munisipaliteit/*` from the database.
- `robots` allows all.
- The header nav gains "Vind jou wyk" (anchor to the hero search).

## 7. Copy (Gemini, fact-checked, added to `lib/verkiesing/kopie.ts`)

New slots:
- **Search:**
  - `soek_etiket`, `soek_plekhouer`, `soek_ligging_knoppie`
  - `soek_groep_plekke`, `soek_groep_stemlokale`
  - `soek_geen`, `soek_ligging_geweier`, `soek_ligging_buite`
  - `soek_wyke_kies`
- **Ward page:**
  - `wyk_raadslid_opskrif`, `wyk_raadslid_teks`
  - `wyk_stemlokale_opskrif`, `wyk_stembriewe_opskrif`
  - `stembrief_wyk`, `stembrief_pv`, `stembrief_distrik`
  - `volgorde_alfabeties`, `volgorde_stembrief`
  - `onafhanklik`, `laas_bygewerk`, `wys_lys`, `versteek_lys`
- **Municipality page:**
  - `muni_wyke_opskrif`, `muni_partye_opskrif`
  - `muni_2021_opskrif`, `muni_2021_geen_meerderheid`
  - the three table column headings
- **Header and share card:**
  - `nav_vind_wyk`
  - `og_wyk_sjabloon`

Same process as 15 Sep: verified facts plus slot briefs go to `gemini-3.5-flash`; Claude checks every line against the facts; edits are logged in `docs/verkiesing/ui-kopie-wysigings.md`.

## 8. Testing

- **Parsers:**
  - Unit tests on the 2021 WC candidate PDF fixture: column detection, ward vs list-order split, independents, and that the ID column is dropped.
  - Station PDF fixture: row count for WC.
- **Ward self-test (in the check report):** for every ward with geometry, `vind_wyk` at `ST_PointOnSurface(geom)` must return that ward. Expect 4,485 / 4,485.
- **Place search tests (SQL, in the report):**
  - "Brooklyn" returns ≥ 2 municipalities, including Tshwane and Cape Town.
  - "Kaapstad" returns Cape Town places via the alias.
  - "Waterkloof" includes Tshwane.
  - A 1-character query returns nothing.
- **Reconciliation:** the totals in §5.3 must match the IEC's published figures before publish is allowed. The script refuses to publish on a mismatch unless run with `--aanvaar-verskil` and a reason, which is recorded in `data_weergawes`.
- **Site unit tests (Vitest):**
  - candidate ordering (alphabetical vs ballot order)
  - the 2021 "no majority" computation
  - search result grouping and labels
  - OG template text
- **Neutrality tests:**
  - ordering never uses seats or votes
  - no colour tokens on party or candidate rows
  - no party names on the OG card
- **Browser (real):**
  - search by suburb, by station, and with location (mocked geolocation);
  - the ward page at 400 px and 1280 px;
  - a municipality page;
  - keyboard-only search;
  - no horizontal scroll.
- **Brand and promise grep:** as in Drop 1.

## 9. Failure handling

| Situation | Behaviour |
|---|---|
| Candidate list isn't a parseable PDF (image scan, new format) | Parser fails loudly in the verslag. Fall back to per-province manual extraction for the ~15–20 key municipalities first; the wyk-soeker ships with stations + wards and a "kandidate word gelaai" state (copy slot) only if Piet approves that |
| IEC corrections after 16 Sep | Re-run → report → approval → publish; pages show the source date |
| Ballot order not published in usable form | Alphabetical stays, labelled "Alfabeties" |
| Suburb not in the 2011 layer (new estate) | "Geen plek gevind" hint → station search / location |
| Ward without geometry (3 FS) | Still reachable via station search and municipality page; location lookup can't resolve it (message) |
| Supabase down | Cached ward pages keep serving; search shows a friendly error |
| Location denied | Inline message, search stays usable |

## 10. Build order (internal)

1. **15–16 Sep:** extensions + schema + RLS; wards, stations, places, aliases, 2021 results loaded to `stg_` tables; candidate parser built on the 2021 fixture.
2. **16–18 Sep:** real candidate list parsed and reconciled; first check report → Piet → publish.
3. **18–23 Sep:** RPCs, `/api/soek`, `/api/wyk-by-punt`, hero search, ward and municipality pages, OG cards, sitemap, Gemini copy.
4. **23–24 Sep:** ballot order (if usable), IEC corrections, final report → publish.
5. **24–25 Sep:** preview → browser verification → Piet's approval → production.

## 11. Dependencies and open questions

1. ~~Postgres connection string~~ — not needed (loads go via PostgREST + secret key, 15 Sep).
2. **Real format of the 16 Sep candidate list:** PDF or Excel/CSV, and how district PR lists and independents appear.
3. **Ballot-order publication after the 23 Sep draw.**
4. **Party abbreviations:** is there an IEC list of contesting parties with abbreviations? If not, show full names only.
5. **MDB reply on the 3 missing Free State wards.**
6. **IEC written consent** (Izak, this week) — not a build blocker.

## 12. Out of scope

- Maps and ward boundary drawings on pages.
- Candidate biographies or photos.
- Ward-level 2021 results (internal remap only).
- WhatsApp or Telegram lookups.
- Results night (D), prediction model (E), dorpsbulletins (B), municipal RAG (C).
