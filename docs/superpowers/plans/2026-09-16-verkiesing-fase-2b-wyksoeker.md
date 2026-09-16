# Verkiesing Fase 2b — wyk-soeker op die werf (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship everything a voter needs to find their ward on nuuspod.co.za — search, ward pages, municipality pages — so that the only remaining step is loading the IEC candidate list and publishing it.

**Architecture:** Fase 2a loaded wards, stations, places, overlaps, aliases and the 2021 council results into `stg_` tables. This phase (1) adds the search, point-lookup and publish RPCs, (2) publishes the base data into the public tables, (3) builds the site: a search combobox in the hero, `/wyk/[wykId]`, `/munisipaliteit/[kode]`, OG cards and the sitemap, and (4) adds the candidate loader and the candidate sections of the check report, so the 16 Sep list is a load-and-publish step rather than a build step.

**Tech Stack:** Next.js 16.2 App Router (React 19, Tailwind v4 `@theme` tokens, `motion`, `next/og`), Vitest, PostgREST over plain `fetch` (`lib/supabase-rest.ts`), Supabase Postgres + PostGIS + pg_trgm, Python 3 loaders (`uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest`), Gemini `gemini-3.5-flash` for Afrikaans copy.

**Spec:** `docs/superpowers/specs/2026-09-15-verkiesing-fase-2-wyksoeker-design.md`
**Fase 2a handoff (decisions + open design items):** `docs/superpowers/plans/2026-09-15-verkiesing-fase-2a-oorhandiging.md`
**Approved design (visual source):** `docs/verkiesing/ontwerp/` (`LEESMY.md` explains each file)

## Global Constraints

- **Supabase project:** `verkiesing-2026`, ref `xxysgvanarnirxoxrbkj`. DDL goes through Supabase MCP `apply_migration`; the migration file name must equal the recorded version (check with `list_migrations` afterwards and rename if needed).
- **Credentials:** loaders and publish scripts read `VERKIESING_SUPABASE_URL` and `VERKIESING_SUPABASE_SECRET_KEY` from `~/nuuspod/.env.local` via `data/lib/omgewing.py` only. The site reads `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` from `nuuspod-web/.env.local`. **Never** cat, grep, echo or log any env file or key value. Never write a secret key into `nuuspod-web/.env.local`.
- **No model-generated claims about candidates or parties.** Every name and number on a page is rendered from a database row.
- **Neutral display:** ordering is alphabetical until the IEC ballot draw (23 Sep), then official ballot order; never by seats or votes. Equal space per candidate. No party colours, logos or photos on ballot, candidate, ward or municipality pages. `docs/verkiesing/partykleure.json` is for results graphics in a later drop — do not import it in this phase.
- **No public launch promises:** no copy anywhere announces a Nuuspod feature or date.
- **Never write "Die Buitelyn".**
- **Personal data:** masked ID numbers are never parsed, stored, logged or written to any output. Geolocation coordinates are never stored or logged (not in route handlers, not in analytics, not in error messages).
- **Piet's approved data decisions (2026-09-15):** publish with 4,485 wards; search groups places per main place/municipality rather than listing sub places; the 3 harbour slivers (`199056003`, `199057014`, `199063016`) are excluded from search; "no majority" is measured against the full 2021 council size including independents; a station with an empty address shows its name only; "Mahikeng" is added as a search alias for Mafikeng (NW383).
- **RLS:** public tables are anon `SELECT` only. New RPCs that anon may call are `security invoker`, `stable`, `EXECUTE` granted to `anon` and `authenticated`. Publish RPCs are `SECURITY DEFINER`, `SET search_path = public, extensions`, `EXECUTE` revoked from `PUBLIC, anon, authenticated` and granted to `service_role`.
- **PostgREST limits:** the authenticator `statement_timeout` is 8s and `safeupdate` is on (a DELETE needs a WHERE). Every bulk server-side step must be chunked.
- **Repo:** `~/projects/nuuspod-web`, branch `verkiesing-fase-2`. Do not push. Explicit `git add` paths. Afrikaans commit messages and identifiers, English code comments. Commit trailers:
  ```
  Co-Authored-By: <implementing model> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p
  ```
- **Tests:** `npm test` (Vitest) for site code; `cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest pytest -q` for loaders. `npx tsc --noEmit` and `npm run build` must pass before a task is done if it touched site code.
- **Afrikaans UI copy** is written by Gemini in Task 9. Until then, components read from `lib/verkiesing/kopie.ts`; add each new slot there with a **draft** value in Task 5–8 and let Task 9 replace the values. No component hardcodes user-visible Afrikaans text.

---

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/<version>_wyksoeker_rpcs.sql` | `normaliseer_soekteks`, `mp_naam_soek` columns + indexes, `soek`, `vind_wyk`, publish RPCs |
| `data/laai_plekke.py` (modify) | fill `mp_naam_soek`; Mahikeng alias row in `data/aliasse.csv` |
| `data/publiseer.py` | chunked stg → public publish, `data_weergawes`, `/api/herlaai` |
| `data/laai_kandidate.py` | IEC candidate list → `stg_partye` + `stg_kandidate` (uses `data/kandidate_ontleder.py`) |
| `data/kontroleer.py` (modify) | candidate sections + hard gates; publish-diff section |
| `lib/verkiesing/wyksoeker.ts` | types + reads for wards, stations, candidates, municipalities |
| `lib/verkiesing/orden.ts` | candidate/party ordering and the 2021 no-majority computation |
| `lib/verkiesing/kopie.ts` (modify) | new copy slots |
| `app/api/soek/route.ts`, `app/api/wyk-by-punt/route.ts` | search and point lookup |
| `app/api/herlaai/route.ts` (modify) | allow the `wyke` and `kandidate` tags |
| `app/_components/verkiesing/wyk-soeker.tsx` | hero search combobox (client) |
| `app/_components/verkiesing/stembriewe.tsx`, `stemlokale-lys.tsx`, `bron-strook.tsx` | ward page blocks |
| `app/_components/verkiesing/raad-2021.tsx`, `wyk-rooster.tsx` | municipality page blocks |
| `app/wyk/[wykId]/page.tsx`, `opengraph-image.tsx` | ward page + share card |
| `app/munisipaliteit/[kode]/page.tsx` | municipality page |
| `app/sitemap.ts`, `app/robots.ts` | sitemap + robots |

---

### Task 1: Search, lookup and publish RPCs (migration)

**Files:**
- Create: `supabase/migrations/<version>_wyksoeker_rpcs.sql`
- Modify: `data/laai_plekke.py` (write `mp_naam_soek`), `data/aliasse.csv` (Mahikeng row)
- Test: `data/tests/test_soek_rpc.py` (calls the RPCs over PostgREST with the secret key; skips with a clear message if the env is missing)

**Interfaces:**
- Produces: `soek(q text)`, `vind_wyk(lat double precision, lng double precision)`, `publiseer_leeg(datastel text)`, `publiseer_tabel(datastel text, van int, tot int)`, `publiseer_afrond(datastelle text[], bron_datum date)`, `normaliseer_soekteks(text)`.
- Consumes: the Fase 2a tables (`wyke`, `plekke`, `plek_wyke`, `plek_aliasse`, `stemstasies`, `munisipaliteite`, `raad_uitslae_2021`, `raad_grootte_2021`, `kandidate`, `partye`, `stembrief_volgorde`, `data_weergawes`) and their `stg_` twins.

- [ ] **Step 1: Read the existing schema before writing SQL**

Read `supabase/migrations/20260915082741*.sql` (base schema, exact column names), `20260915093428*.sql` (`bou_plek_wyke`, the chunking pattern to copy), `20260915123045*.sql` (unique keys) and `data/lib/teks.py` (`normaliseer`, which the SQL function must match).

- [ ] **Step 2: Write the migration**

The migration must contain, in this order:

1. `normaliseer_soekteks(t text) returns text` — `immutable`, `strict`, `parallel safe`, `set search_path = public, extensions`. It must produce exactly what `data/lib/teks.py:normaliseer` produces: lower-case, accents folded, `'` and `-` collapsed to a space, punctuation dropped, whitespace squeezed. Fold accents with `translate()` over the vowel set actually present in the place names (the database has no `unaccent`); do not add an extension.
2. `alter table public.plekke add column if not exists mp_naam_soek text;` and the same for `public.stg_plekke`.
3. Backfill both: `update … set mp_naam_soek = normaliseer_soekteks(regexp_replace(mp_naam, '\s+(NU|SH)$', '')) where mp_naam is not null;` — run it in chunks of 5,000 `sp_kode`s if a single statement risks the 8s timeout, or note in the report that it was applied by the controller via direct SQL.
4. Indexes (`if not exists`): GIN trigram on `plekke.naam_soek`, `plekke.mp_naam_soek`, `plek_aliasse.alias`, `stemstasies.naam`, `stemstasies.adres`; GiST on `wyke.geom`, `plekke.geom`; btree on `plek_wyke.sp_kode`, `plek_wyke.wyk_id`, `stemstasies.wyk_id`, `kandidate.wyk_id`, `kandidate.muni_kode`, `raad_uitslae_2021.muni_kode`. Check which already exist first and don't duplicate.
5. `vind_wyk(lat double precision, lng double precision)`:

```sql
create or replace function public.vind_wyk(lat double precision, lng double precision)
returns table (wyk_id text, wyk_nr int, muni_kode text, muni_naam text)
language sql stable security invoker
set search_path = public, extensions
as $$
  select w.wyk_id, w.wyk_nr, w.muni_kode, m.naam
  from public.wyke w
  join public.munisipaliteite m on m.kode = w.muni_kode
  where w.geom is not null
    and lat between -35.0 and -21.0 and lng between 15.0 and 34.0
    and extensions.ST_Intersects(w.geom, extensions.ST_SetSRID(extensions.ST_MakePoint(lng, lat), 4326))
  limit 1;
$$;
revoke all on function public.vind_wyk(double precision, double precision) from public;
grant execute on function public.vind_wyk(double precision, double precision) to anon, authenticated, service_role;
```

6. `soek(q text)` — `language plpgsql`, `stable`, `security invoker`, `set search_path = public, extensions`, returning:

```sql
returns table (
  soort text,          -- 'plek' | 'stemlokaal'
  etiket text,         -- what the row shows, e.g. 'Brooklyn' or the station name
  muni_kode text,
  muni_naam text,
  wyk_ids text[],      -- sorted
  wyk_nrs int[],       -- same order as wyk_ids
  teiken text,         -- '/wyk/<id>' or '/wyk/<id>#stemlokale' when exactly one ward, else null
  rang int
)
```

Rules, all of which get a test in Step 4:
- `normaliseer_soekteks(q)`; if it is shorter than 2 characters, return no rows.
- Place candidates come from three sources, each carrying a match class: `1` exact, `2` prefix, `3` trigram (`similarity(...) > 0.3`):
  - `plek_aliasse.alias` (normalised on both sides) → its `sp_kode`s;
  - `plekke.naam_soek`;
  - `plekke.mp_naam_soek` (this is what makes "Soweto" work).
- Join `plek_wyke` → `wyke` → `munisipaliteite`, **group by the display label and `muni_kode`**, aggregating `wyk_id`s (`array_agg(distinct …)` ordered). The display label is `plekke.naam` for a name/alias hit and the cleaned `mp_naam` for a main-place hit; when both hit, prefer the sub-place name.
- The municipality always comes from the 2026 ward (`wyke.muni_kode`), never from the 2011 place codes.
- Exclude the 3 harbour `sp_kode`s (`199056003`, `199057014`, `199063016`) and any place with no `plek_wyke` row.
- Station candidates: `stemstasies.naam` or `stemstasies.adres`, same match classes; each row carries its own single ward.
- `rang` orders: match class, then places before stations, then non-rural (`plekke.landelik = false`) before rural, then metro municipalities before local, then `etiket`.
- `limit 20`.
- `revoke all … from public; grant execute … to anon, authenticated, service_role;`

7. Publish RPCs. `PUBLISEERBAAR` is a hard-coded allow-list of dataset names (`munisipaliteite`, `wyke`, `stemstasies`, `plekke`, `plek_wyke`, `plek_aliasse`, `raad_uitslae_2021`, `raad_grootte_2021`, `partye`, `kandidate`, `stembrief_volgorde`); anything else raises. Use `format('%I')` everywhere, never string-concatenated identifiers. All three are `SECURITY DEFINER`, `SET search_path = public, extensions`, revoked from `PUBLIC, anon, authenticated`, granted to `service_role`.
- `publiseer_leeg(datastel text) returns bigint` — `delete from public.<datastel> where true` (safeupdate), returns the deleted count.
- `publiseer_tabel(datastel text, van int, tot int) returns bigint` — inserts `stg_<datastel>` rows whose `row_number() over (order by <the table's own unique key>)` falls in `[van, tot]`, returns the inserted count. Derive the ordering key per dataset from a small `case` mapping (e.g. `wyke` → `wyk_id`, `plek_wyke` → `(sp_kode, wyk_id)`); make it deterministic, because the caller chunks on it. Use `on conflict do nothing` so a retried chunk is idempotent.
- `publiseer_afrond(datastelle text[], bron_datum date) returns void` — one `data_weergawes` row per dataset with `rye` counted from the public table, `bron_datum`, `gelaai_om`, `gepubliseer_om = now()`.

- [ ] **Step 3: Apply the migration and confirm the version**

Apply with Supabase MCP `apply_migration` (name `wyksoeker_rpcs`), then `list_migrations` and rename the repo file so its prefix equals the recorded version. Then verify with read-only SQL: every new function exists with the intended `prosecdef`, `proconfig` and grants; every index exists and is valid.

- [ ] **Step 4: Tests**

`data/tests/test_soek_rpc.py`, calling the RPCs over PostgREST (`POST /rest/v1/rpc/soek`, `{"q": ...}`) with the secret key from `omgewing.lees()`:

```python
def test_soek_gee_niks_vir_een_karakter():
    assert roep_soek("B") == []

def test_brooklyn_gee_meer_as_een_munisipaliteit():
    rye = roep_soek("Brooklyn")
    munis = {r["muni_naam"] for r in rye}
    assert "City of Tshwane" in munis and "City of Cape Town" in munis

def test_kaapstad_alias_gee_stad_kaapstad_gegroepeer():
    rye = [r for r in roep_soek("Kaapstad") if r["soort"] == "plek"]
    assert rye and all(r["muni_naam"] == "City of Cape Town" for r in rye)
    assert len(rye) <= 20

def test_soweto_kom_deur_die_hoofplek():
    rye = roep_soek("Soweto")
    assert any(r["muni_naam"] == "City of Johannesburg" for r in rye)

def test_hawe_snippers_kom_nooit_terug_nie():
    assert not [r for r in roep_soek("Habour") if r["soort"] == "plek"]

def test_stemlokaal_gee_een_wyk_en_n_teiken():
    rye = [r for r in roep_soek("Kaya Mandi High") if r["soort"] == "stemlokaal"]
    assert rye and len(rye[0]["wyk_ids"]) == 1 and rye[0]["teiken"].endswith("#stemlokale")

def test_vind_wyk_op_n_punt_binne_stellenbosch():
    ry = roep_vind_wyk(-33.9367, 18.8614)  # Stellenbosch town
    assert ry and ry[0]["muni_kode"] == "WC024"

def test_vind_wyk_buite_die_land_gee_niks():
    assert roep_vind_wyk(51.5, -0.12) == []
```

- [ ] **Step 5: Mahikeng alias and `mp_naam_soek` in the loader**

Add `Mahikeng` → the Mafikeng main place to `data/aliasse.csv` (match the file's existing columns), make `laai_plekke.py` write `mp_naam_soek` for new loads, then run `laai_plekke.py --net-aliasse` (it must exit 0 and report 0 unresolved aliases). Do not run the full places reload.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations data/laai_plekke.py data/aliasse.csv data/tests/test_soek_rpc.py
git commit -m "Verkiesing Fase 2b: soek-, punt- en publiseer-RPCs"
```

---

### Task 2: Publish the base data (`data/publiseer.py`)

**Files:**
- Create: `data/publiseer.py`, `data/tests/test_publiseer.py`
- Modify: `app/api/herlaai/route.ts` (add the `wyke` and `kandidate` tags)

**Interfaces:**
- Consumes: Task 1's `publiseer_leeg`, `publiseer_tabel`, `publiseer_afrond`; `data/lib/supabase.py` (`rpc`, `telling`, `kry_alles`, which now requires `orde`).
- Produces: `data/uitvoer/publiseer-verslag.md`; public tables filled; `/api/herlaai` called for the affected tags.

- [ ] **Step 1: Write the failing test**

`data/tests/test_publiseer.py` — pure unit tests, no network:

```python
def test_stukkies_dek_elke_ry():
    assert list(publiseer.stukkies(4485, 2000)) == [(1, 2000), (2001, 4000), (4001, 4485)]

def test_datastel_moet_op_die_witlys_wees():
    with pytest.raises(publiseer.PubliseerFout):
        publiseer.kontroleer_datastelle(["wyke", "geheime_tabel"])

def test_tags_vir_datastelle():
    assert publiseer.tags_vir(["wyke", "stemstasies"]) == ["wyke"]
    assert publiseer.tags_vir(["kandidate", "partye"]) == ["kandidate"]
```

- [ ] **Step 2: Run it and watch it fail**

`cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest pytest tests/test_publiseer.py -q` → fails (module missing).

- [ ] **Step 3: Write `data/publiseer.py`**

CLI: `python publiseer.py --datastelle wyke,stemstasies[,…] [--stukgrootte 2000] [--bron-datum 2026-09-16] [--droogloop] [--aanvaar-verskil "reason"]`.

Behaviour:
1. `kontroleer_datastelle` against the same allow-list as the SQL function (a mismatch is a `PubliseerFout`).
2. For each dataset, in this order — `munisipaliteite`, `wyke`, `stemstasies`, `plekke`, `plek_wyke`, `plek_aliasse`, `raad_uitslae_2021`, `raad_grootte_2021`, `partye`, `kandidate`, `stembrief_volgorde` (skip any not requested, and any whose `stg_` table is empty, which is logged as skipped):
   - read the `stg_` count;
   - `publiseer_leeg`;
   - `publiseer_tabel` per chunk, retrying a chunk up to 3 times and halving it on a timeout (copy the pattern in `laai_plekke.py`);
   - verify the public count equals the `stg_` count; a mismatch aborts unless `--aanvaar-verskil` is given, and the reason is recorded.
3. `publiseer_afrond(datastelle, bron_datum)`.
4. POST `/api/herlaai` once per affected tag with `NUUSPOD_WEB_HERLAAI_SECRET`-equivalent: read `HERLAAI_SECRET` from `nuuspod-web/.env.local` through a small helper in `data/lib/omgewing.py` (never print it), to `https://www.nuuspod.co.za/api/herlaai` (www, `redirect="manual"`). A failed herlaai is a warning, not a failure — the report says so.
5. Write `data/uitvoer/publiseer-verslag.md`: per dataset the stg count, published count, duration, and the herlaai results. Exit non-zero on any hard failure, after writing the report.
6. `--droogloop` does everything except the writes, and prints the plan.

- [ ] **Step 4: Run the tests to green**

Same command as Step 2 → 3 passed.

- [ ] **Step 5: Extend the herlaai allowlist**

In `app/api/herlaai/route.ts`: `const TAGS = new Set(["nuusstroom", "episodes", "wyke", "kandidate"]);`

- [ ] **Step 6: Publish the base data for real**

Piet approved the data (15 Sep). Run:

```bash
cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest python publiseer.py \
  --datastelle munisipaliteite,wyke,stemstasies,plekke,plek_wyke,plek_aliasse,raad_uitslae_2021,raad_grootte_2021 \
  --bron-datum 2026-09-16
```

Expected published counts: `munisipaliteite` 257, `wyke` 4485, `stemstasies` 23696, `plekke` 22196, `plek_wyke` 35582, `plek_aliasse` 519 (518 + Mahikeng), `raad_uitslae_2021` 2789, `raad_grootte_2021` 213. Candidates and ballot order stay empty. Record the actual numbers in the report.

- [ ] **Step 7: Verify anon can read and cannot write**

With read-only checks from the repo's publishable key (site `.env.local`): `GET /rest/v1/wyke?limit=1` and `POST /rest/v1/rpc/soek` succeed; `GET /rest/v1/stg_wyke?limit=1` returns no rows or a permission error; a `POST /rest/v1/wyke` insert attempt is refused. Never print the key.

- [ ] **Step 8: Commit**

```bash
git add data/publiseer.py data/tests/test_publiseer.py data/lib/omgewing.py app/api/herlaai/route.ts
git commit -m "Verkiesing Fase 2b: publiseer-skrif en basisdata in publieke tabelle"
```

---

### Task 3: Site data layer and ordering (`lib/verkiesing/`)

**Files:**
- Create: `lib/verkiesing/wyksoeker.ts`, `lib/verkiesing/orden.ts`, `lib/verkiesing/__tests__/orden.test.ts`, `lib/verkiesing/__tests__/wyksoeker.test.ts`
- Read for patterns: `lib/verkiesing/lees.ts`, `lib/supabase-rest.ts`

**Interfaces:**
- Produces, for Tasks 4–8:
  ```ts
  export type Wyk = { wyk_id: string; wyk_nr: number; muni_kode: string; muni_naam: string; muni_tipe: "metro" | "plaaslik" | "distrik"; distrik_kode: string | null; distrik_naam: string | null; provinsie: string };
  export type Stemstasie = { vd_nommer: string; naam: string; adres: string | null };
  export type Kandidaat = { volle_naam: string; van: string; party_naam: string | null; onafhanklik: boolean; lys_posisie: number | null };
  export type PartyLys = { party_naam: string; posisie: number | null; kandidate: Kandidaat[] };
  export type Stembriewe = { wyk: Kandidaat[]; pv_plaaslik: PartyLys[]; pv_distrik: PartyLys[]; volgorde: "alfabeties" | "stembrief" };
  export type MuniOpsomming = { kode: string; naam: string; tipe: string; provinsie: string; distrik_naam: string | null; wyke: { wyk_id: string; wyk_nr: number }[]; partye: string[]; raad2021: Raad2021 | null };
  export type Raad2021 = { raadsgrootte: number; onafhanklike_setels: number; rye: { party_naam: string; setels_wyk: number; setels_pv: number; setels_totaal: number }[]; geenMeerderheid: boolean };

  export async function haalWyk(wykId: string): Promise<Wyk | null>;
  export async function haalStemstasies(wykId: string): Promise<Stemstasie[]>;
  export async function haalStembriewe(wyk: Wyk): Promise<Stembriewe>;
  export async function haalMuni(kode: string): Promise<MuniOpsomming | null>;
  export async function haalAlleWykIds(): Promise<{ wyk_id: string }[]>;      // sitemap
  export async function haalAlleMuniKodes(): Promise<{ kode: string }[]>;     // sitemap
  ```
- Every read uses `lees()` from `lib/supabase-rest.ts` with `{ tags: ["wyke"] }` or `{ tags: ["kandidate"] }` and `revalidate: 3600`, so a database outage renders a fallback rather than an error page (`lees` returns `null`).

- [ ] **Step 1: Write the failing tests for `orden.ts`**

```ts
import { describe, expect, it } from "vitest";
import { geenMeerderheid, sorteerKandidate, sorteerPartyLyste } from "../orden";

describe("sorteerKandidate", () => {
  it("sorteer alfabeties op van, dan volle naam, met Afrikaanse kollasie", () => {
    const uit = sorteerKandidate([
      { volle_naam: "Zani", van: "ZULU", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Anna", van: "ÅBERG", party_naam: "P", onafhanklik: false, lys_posisie: null },
      { volle_naam: "Bea", van: "BOTHA", party_naam: null, onafhanklik: true, lys_posisie: null },
    ]);
    expect(uit.map((k) => k.van)).toEqual(["ÅBERG", "BOTHA", "ZULU"]);
  });
  it("gebruik lys_posisie wanneer dit die stembriefvolgorde is", () => {
    const uit = sorteerKandidate(
      [
        { volle_naam: "B", van: "B", party_naam: "P", onafhanklik: false, lys_posisie: 2 },
        { volle_naam: "A", van: "A", party_naam: "P", onafhanklik: false, lys_posisie: 1 },
      ],
      "stembrief"
    );
    expect(uit.map((k) => k.van)).toEqual(["A", "B"]);
  });
});

describe("sorteerPartyLyste", () => {
  it("sorteer alfabeties sonder volgorde-data", () => {
    expect(sorteerPartyLyste([{ party_naam: "ZZZ", posisie: null, kandidate: [] }, { party_naam: "AAA", posisie: null, kandidate: [] }]).map((p) => p.party_naam)).toEqual(["AAA", "ZZZ"]);
  });
  it("sorteer op posisie sodra die trekking gebeur het", () => {
    expect(sorteerPartyLyste([{ party_naam: "AAA", posisie: 2, kandidate: [] }, { party_naam: "ZZZ", posisie: 1, kandidate: [] }]).map((p) => p.party_naam)).toEqual(["ZZZ", "AAA"]);
  });
  it("sorteer nooit op setels of lysgrootte nie", () => {
    const groot = { party_naam: "ZZZ", posisie: null, kandidate: [1, 2, 3].map(() => ({ volle_naam: "x", van: "x", party_naam: "ZZZ", onafhanklik: false, lys_posisie: null })) };
    const klein = { party_naam: "AAA", posisie: null, kandidate: [] };
    expect(sorteerPartyLyste([groot, klein]).map((p) => p.party_naam)).toEqual(["AAA", "ZZZ"]);
  });
});

describe("geenMeerderheid", () => {
  it("meet teen die volle raadsgrootte, insluitend onafhanklikes", () => {
    // 11-seat council: biggest party 5 → no majority
    expect(geenMeerderheid({ raadsgrootte: 11, onafhanklike_setels: 1, rye: [{ party_naam: "A", setels_wyk: 3, setels_pv: 2, setels_totaal: 5 }, { party_naam: "B", setels_wyk: 2, setels_pv: 3, setels_totaal: 5 }] })).toBe(true);
  });
  it("is vals wanneer een party meer as die helfte het", () => {
    expect(geenMeerderheid({ raadsgrootte: 45, onafhanklike_setels: 0, rye: [{ party_naam: "DA", setels_wyk: 19, setels_pv: 9, setels_totaal: 28 }, { party_naam: "ANC", setels_wyk: 4, setels_pv: 4, setels_totaal: 8 }] })).toBe(false);
  });
});
```

- [ ] **Step 2: Run them and watch them fail**

`npm test -- lib/verkiesing/__tests__/orden.test.ts` → FAIL (module not found).

- [ ] **Step 3: Implement `orden.ts`**

```ts
const KOLLASIE = new Intl.Collator("af-ZA", { sensitivity: "base", numeric: true });

export function sorteerKandidate(kandidate: Kandidaat[], volgorde: "alfabeties" | "stembrief" = "alfabeties"): Kandidaat[] {
  // Ordering is neutral: alphabetical until the IEC draw, then the official ballot position.
  // It must never consider seats, votes or list length.
  return [...kandidate].sort((a, b) =>
    volgorde === "stembrief" && a.lys_posisie != null && b.lys_posisie != null
      ? a.lys_posisie - b.lys_posisie
      : KOLLASIE.compare(a.van, b.van) || KOLLASIE.compare(a.volle_naam, b.volle_naam)
  );
}
```

`sorteerPartyLyste` sorts by `posisie` when every entry has one, otherwise by `party_naam` with the same collator. `geenMeerderheid({raadsgrootte, onafhanklike_setels, rye})` returns `true` when `max(setels_totaal) * 2 <= raadsgrootte` (note: strictly more than half is a majority; 6 of 11 is a majority, 5 of 11 is not) and `raadsgrootte > 0`; it returns `false` when `raadsgrootte` is 0 or missing.

- [ ] **Step 4: Run the tests to green**

- [ ] **Step 5: Implement `wyksoeker.ts`**

PostgREST paths (embed with `select=` so each page is one request):
- `haalWyk`: `wyke?wyk_id=eq.<id>&select=wyk_id,wyk_nr,muni_kode,munisipaliteite!inner(naam,tipe,distrik_kode,provinsie)` → map to `Wyk`, then a second read for `distrik_naam` when `distrik_kode` is set (or embed the district through a second `munisipaliteite` select if PostgREST allows the self-relation; if it doesn't, do the second read and say so in a code comment).
- `haalStemstasies`: `stemstasies?wyk_id=eq.<id>&select=vd_nommer,naam,adres&order=naam.asc`.
- `haalStembriewe`: candidates for the ward (`kandidate?wyk_id=eq.<id>&stembrief=eq.wyk&select=volle_naam,van,onafhanklik,lys_posisie,partye(naam)`), the local PR lists (`kandidate?muni_kode=eq.<muni>&stembrief=eq.pv_plaaslik&…`), and the district PR lists when `distrik_kode` is set (`kandidate?muni_kode=eq.<distrik_kode>&stembrief=eq.pv_distrik&…`), plus `stembrief_volgorde` for that municipality. `volgorde` is `"stembrief"` only when `stembrief_volgorde` has rows for that municipality and ballot, else `"alfabeties"`. Group PR candidates per party into `PartyLys` and sort with Task 3's helpers.
- `haalMuni`: the municipality row, its wards (`wyke?muni_kode=eq.<kode>&select=wyk_id,wyk_nr&order=wyk_nr.asc`), the distinct party names contesting it (from `kandidate`, empty until the list is loaded), and `raad_uitslae_2021` + `raad_grootte_2021` assembled into `Raad2021` with `geenMeerderheid`.
- `haalAlleWykIds` / `haalAlleMuniKodes`: paged reads (PostgREST caps at 1,000 rows) with a stable `order`, used by the sitemap.
- Validate ids before any request: `wyk_id` must match `/^\d{8}$/`, `muni_kode` must match `/^[A-Z]{2,3}\d{0,3}$/`. An invalid id returns `null` without calling the database.

- [ ] **Step 6: Tests for `wyksoeker.ts`**

`lib/verkiesing/__tests__/wyksoeker.test.ts` — `vi.stubGlobal("fetch", …)` to assert: an invalid `wyk_id` never calls fetch and returns `null`; `haalStembriewe` groups PR rows per party and applies ballot order when `stembrief_volgorde` has rows; a `null` from `lees` (database down) yields empty arrays rather than a throw; the tags and `revalidate` passed to fetch are the intended ones.

- [ ] **Step 7: Commit**

```bash
git add lib/verkiesing/wyksoeker.ts lib/verkiesing/orden.ts lib/verkiesing/__tests__
git commit -m "Verkiesing Fase 2b: datalaag en neutrale ordening vir die wyk-soeker"
```

---

### Task 4: `/api/soek` and `/api/wyk-by-punt`

**Files:**
- Create: `app/api/soek/route.ts`, `app/api/wyk-by-punt/route.ts`, `app/api/__tests__/soek.test.ts`, `app/api/__tests__/wyk-by-punt.test.ts`
- Read for patterns: `app/api/herlaai/route.ts`, `lib/supabase-rest.ts`

**Interfaces:**
- Produces: `GET /api/soek?q=…` → `{ resultate: SoekRy[] }` where `SoekRy` is the `soek` RPC's row shape (`soort`, `etiket`, `muni_kode`, `muni_naam`, `wyk_ids`, `wyk_nrs`, `teiken`); `GET /api/wyk-by-punt?lat=&lng=` → `{ wyk: { wyk_id, wyk_nr, muni_kode, muni_naam } | null }`.
- Consumes: Task 1's RPCs. Also export the `SoekRy` type from `lib/verkiesing/wyksoeker.ts` so Task 5 can import it.

- [ ] **Step 1: Write the failing tests**

```ts
// soek
it("gee 400 vir 'n navraag korter as 2 karakters", async () => { … expect(res.status).toBe(400); });
it("gee 'n leë lys sonder om die databasis te roep", …);
it("stuur die navraag na die soek-RPC en gee die rye terug", …);   // fetch stubbed
it("gee 'n leë lys wanneer die databasis stukkend is", …);          // fetch throws → 200 + { resultate: [] }

// wyk-by-punt
it("gee 400 vir nie-numeriese of ontbrekende koördinate", …);
it("gee 400 vir koördinate buite Suid-Afrika", …);
it("log nooit die koördinate nie", async () => {
  const spioen = vi.spyOn(console, "error");
  … // force an error path
  expect(spioen.mock.calls.flat().join(" ")).not.toContain("-33.9");
});
it("gee { wyk: null } wanneer die punt buite elke wyk val", …);
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Implement the routes**

Both are `export const dynamic = "force-static"`-free plain GET handlers using `fetch` against `${SUPABASE_URL}/rest/v1/rpc/<fn>` with `apikey: SUPABASE_PUBLISHABLE_KEY`, `Content-Type: application/json`, `method: "POST"`, body `{ q }` / `{ lat, lng }`.
- `/api/soek`: trim `q`, reject <2 characters with 400, cache with `next: { revalidate: 3600, tags: ["soek"] }` (the URL includes `q`, so each query caches separately), and return `{ resultate: [] }` with status 200 on any upstream failure. Never echo the raw `q` into a log line longer than 80 characters.
- `/api/wyk-by-punt`: parse `lat`/`lng` with `Number.parseFloat`, require finite numbers inside `lat ∈ [-35, -21]`, `lng ∈ [15, 34]`, use `cache: "no-store"`, and **log nothing that contains a coordinate** — error logs say only `"[wyk-by-punt] opsoek misluk"` plus the HTTP status.

- [ ] **Step 4: Run the tests to green, then `npx tsc --noEmit`**

- [ ] **Step 5: Commit**

```bash
git add app/api/soek app/api/wyk-by-punt app/api/__tests__ lib/verkiesing/wyksoeker.ts
git commit -m "Verkiesing Fase 2b: soek- en wyk-by-punt-roetes"
```

---

### Task 5: The hero search (`wyk-soeker.tsx`)

**Files:**
- Create: `app/_components/verkiesing/wyk-soeker.tsx`, `app/_components/verkiesing/__tests__/wyk-soeker.test.tsx`
- Modify: `app/page.tsx` (hero: search replaces `KontroleerRegistrasie`), `app/_components/verkiesing/kopstuk.tsx` (nav link), `lib/verkiesing/kopie.ts` (draft copy slots)
- Visual source: `docs/verkiesing/ontwerp/Main.dc.html`, `SoekFoon.dc.html`, `SoekToestande.dc.html`

**Interfaces:**
- Consumes: `GET /api/soek`, `GET /api/wyk-by-punt`, `SoekRy` from `lib/verkiesing/wyksoeker.ts`.
- Produces: `<WykSoeker />`, rendered in the hero box with `id="vind-jou-wyk"`.

- [ ] **Step 1: Add the draft copy slots**

In `lib/verkiesing/kopie.ts` (values are drafts; Task 9 replaces them): `soek_etiket`, `soek_titel`, `soek_plekhouer`, `soek_ligging_knoppie`, `soek_ligging_besig`, `soek_groep_plekke`, `soek_groep_stemlokale`, `soek_geen`, `soek_ligging_geweier`, `soek_ligging_buite`, `soek_wyke_kies`, `soek_resultate_telling`, `soek_registrasie_skakel`, `nav_vind_wyk`.

- [ ] **Step 2: Write the failing component tests**

Using the repo's existing Vitest + React Testing Library setup (check `vitest.config.*`; if RTL is not yet a dependency, add `@testing-library/react` and `@testing-library/user-event` as devDependencies and a jsdom environment for this test file only):

```tsx
it("soek nie voor 2 karakters nie", …);                    // fetch not called for "B"
it("ontdop 250 ms en doen een versoek vir vinnige tikwerk", …);  // fake timers
it("wys plekke en stemlokale in aparte groepe", …);
it("wys 'n kiesstrook wanneer 'n plek oor meer as een wyk val", …);
it("navigeer na die teiken met Enter", …);                 // router.push stubbed
it("hanteer pyltjies en Escape volgens die combobox-patroon", …);
it("wys die geweier-boodskap wanneer ligging geweier word", …);   // geolocation stubbed
it("stuur nooit koördinate na /api/soek nie", …);
it("wys die geen-resultate-boodskap", …);
```

- [ ] **Step 3: Run them and watch them fail**

- [ ] **Step 4: Implement the component**

- Structure and spacing follow `Main.dc.html`: the label, the `text-balance` display title, a `type="search"` input 48 px high with the search icon, the results popover with `Plekke` / `Stemlokale` group labels, and the "Gebruik my ligging" outline button plus the small "Sien meer ↓" registration link below it.
- ARIA combobox: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `role="listbox"`/`option`, `aria-live="polite"` count line, Escape clears, ArrowUp/Down move, Enter follows `teiken` or opens the ward chooser, focus rings via `focus-visible:outline-2 focus-visible:outline-rooi` like the rest of the site.
- Debounce 250 ms, minimum 2 characters, `AbortController` cancels the previous request, and results are keyed by the query so a late response for an old query is dropped.
- Location: `navigator.geolocation.getCurrentPosition` with `timeout: 8000`, `enableHighAccuracy: false`; on success call `/api/wyk-by-punt` and `router.push` the ward; on denial or failure show the copy slot message; a `{ wyk: null }` answer shows the "outside a ward" message. Coordinates are held in a local variable only — never logged, never put in a query string beyond this request, never stored.
- Respect `prefers-reduced-motion` for any transition (the site uses `motion`; a popover fade is enough).

- [ ] **Step 5: Wire it into the hero and the nav**

In `app/page.tsx`, replace `<KontroleerRegistrasie />` in the hero grid with `<WykSoeker />`, keep `<Aftelling />` above it, and keep the OVK section below unchanged. `KontroleerRegistrasie` stays in the repo only if something still renders it; if nothing does, delete the file and its import. In `kopstuk.tsx` prepend `{ href: "/#vind-jou-wyk", teks: KOPIE.nav_vind_wyk }` to `skakels`.

- [ ] **Step 6: Tests green, `npx tsc --noEmit`, `npm run build`**

- [ ] **Step 7: Commit**

```bash
git add app/_components/verkiesing/wyk-soeker.tsx app/_components/verkiesing/__tests__ app/page.tsx app/_components/verkiesing/kopstuk.tsx lib/verkiesing/kopie.ts
git commit -m "Verkiesing Fase 2b: wyk-soeker in die heldblok"
```

---

### Task 6: `/wyk/[wykId]` and its share card

**Files:**
- Create: `app/wyk/[wykId]/page.tsx`, `app/wyk/[wykId]/opengraph-image.tsx`, `app/_components/verkiesing/stembriewe.tsx`, `app/_components/verkiesing/stemlokale-lys.tsx`, `app/_components/verkiesing/bron-strook.tsx`, `app/wyk/__tests__/wyk.test.tsx`
- Modify: `lib/verkiesing/kopie.ts` (draft slots)
- Visual source: `docs/verkiesing/ontwerp/Wyk.dc.html`, `WykFoon.dc.html`, `Deelkaart.dc.html`

**Interfaces:**
- Consumes: `haalWyk`, `haalStemstasies`, `haalStembriewe`, `sorteerKandidate`, `sorteerPartyLyste` (Task 3); `KOPIE`.
- Produces: the ward page; `<BronStrook bronDatum={…} bronSkakel={…} />` reused by Task 7.

- [ ] **Step 1: Draft copy slots**

`wyk_raadslid_opskrif`, `wyk_raadslid_teks`, `wyk_stemlokale_opskrif`, `wyk_stemlokale_nota`, `wyk_stembriewe_opskrif`, `stembrief_wyk`, `stembrief_wyk_uitleg`, `stembrief_pv`, `stembrief_pv_uitleg`, `stembrief_distrik`, `stembrief_distrik_uitleg`, `volgorde_alfabeties`, `volgorde_stembrief`, `onafhanklik`, `wys_lys`, `versteek_lys`, `laas_bygewerk`, `bron_ovk`, `kandidate_nog_nie_gelaai`, `og_wyk_sjabloon`.

`wyk_raadslid_teks` must be fact-checked against the Municipal Structures Act in Task 9; the draft is a placeholder marked `[konsep]`.

- [ ] **Step 2: Write the failing page tests**

`app/wyk/__tests__/wyk.test.tsx` (render the page's exported component with stubbed data-layer functions):

```tsx
it("gee 404 vir 'n onbekende of ongeldige wyk-id", …);            // notFound() called
it("wys 3 stembriefblokke vir 'n plaaslike munisipaliteit", …);
it("wys 2 stembriefblokke vir 'n metro", …);
it("wys 'n stasie sonder adres met net sy naam", …);
it("wys die kandidate-nog-nie-gelaai-boodskap wanneer daar geen kandidate is nie", …);
it("gebruik geen partykleur- of rooi-klasse op kandidaat- of partyrye nie", …);  // assert className strings
it("wys 'Alfabeties' sonder stembriefvolgorde en 'Volgorde soos op die stembrief' daarmee", …);
```

- [ ] **Step 3: Run them and watch them fail**

- [ ] **Step 4: Implement the page and components**

- `export const dynamicParams = true;` and no `generateStaticParams` (4,485 pages are built on demand and then cached). `params` is a Promise in Next 16 — `const { wykId } = await params;`.
- `notFound()` when the id fails `/^\d{8}$/` or `haalWyk` returns `null`.
- Layout: desktop `grid-cols-[minmax(0,1fr)_22rem]` with the ballots left and the councillor box + stations right; phone stacks councillor, stations, ballots (as in the mockups). Breadcrumb, `Wyk <nr>` with the number in `text-rooi`, the municipality linked to `/munisipaliteit/<kode>`, province in grey.
- `stembriewe.tsx`: one bordered block per ballot, each with a `Stembrief N van {aantal}` label, the title, the explanation, and the order chip; ward candidates as equal-height rows (name bold, party or `KOPIE.onafhanklik` in grey); PR parties as rows with a "Wys lys / Versteek lys" disclosure (a client component using `useState`, or `<details>` if that keeps it server-rendered — prefer `<details>` with styled `<summary>`), listing `lys_posisie`-ordered names inside. No colour tokens beyond `text-ink` / `text-grys` / `border-rand` on these rows.
- Empty candidates (before the list is loaded): render `KOPIE.kandidate_nog_nie_gelaai` inside the ballot block instead of rows. It states a fact about the IEC's publication, never a Nuuspod promise.
- `stemlokale-lys.tsx`: `id="stemlokale"`, count in the heading, name + address rows, name only when `adres` is null/empty.
- `bron-strook.tsx`: attribution line ("Bron: OVK (IEC) · Munisipale Afbakeningsraad · Statistiek Suid-Afrika, Sensus 2011 (eie verwerking)"), `laas bygewerk` from `data_weergawes.bron_datum` (read it once per page through the data layer), a link to the IEC source page (`target="_blank" rel="noopener"`), and `<Terugvoer />`.
- `generateMetadata`: title `Wyk {nr} · {munisipaliteit} — Verkiesing 2026`, description from a copy slot, and OG url. `opengraph-image.tsx` uses `next/og` with `size = { width: 1200, height: 630 }`, the `Deelkaart.dc.html` composition (white ground, neon gradient border, logo, `Wyk {nr}` with the number in red, municipality, then `{n} kandidate · Stem op 4 November` from `KOPIE.og_wyk_sjabloon`). **No party names on the card.** Load the local fonts with `fs.readFileSync` from `public/fonts` as `next/og` requires.

- [ ] **Step 5: Tests green, `npx tsc --noEmit`, `npm run build`**

- [ ] **Step 6: Verify one page in a browser**

Run `npm run dev`, open `/wyk/<a real Stellenbosch ward id>` at 400 px and 1280 px, confirm: no horizontal scroll, the 3 ballot blocks, the stations, the source strip, and `/wyk/12345678` → 404. Also open `/wyk/<id>/opengraph-image` and confirm the card renders.

- [ ] **Step 7: Commit**

```bash
git add app/wyk app/_components/verkiesing/stembriewe.tsx app/_components/verkiesing/stemlokale-lys.tsx app/_components/verkiesing/bron-strook.tsx lib/verkiesing/kopie.ts
git commit -m "Verkiesing Fase 2b: wykblad met stembriewe, stemlokale en deelkaart"
```

---

### Task 7: `/munisipaliteit/[kode]`

**Files:**
- Create: `app/munisipaliteit/[kode]/page.tsx`, `app/_components/verkiesing/wyk-rooster.tsx`, `app/_components/verkiesing/raad-2021.tsx`, `app/munisipaliteit/__tests__/munisipaliteit.test.tsx`
- Modify: `lib/verkiesing/kopie.ts`
- Visual source: `docs/verkiesing/ontwerp/Munisipaliteit.dc.html`

- [ ] **Step 1: Draft copy slots**

`muni_wyke_opskrif`, `muni_partye_opskrif`, `muni_2021_opskrif`, `muni_2021_geen_meerderheid`, `muni_2021_kolom_party`, `muni_2021_kolom_wyk`, `muni_2021_kolom_pv`, `muni_2021_kolom_totaal`, `muni_2021_wys_sonder_setels`, `muni_2021_versteek_sonder_setels`, `muni_2021_sortering`, `muni_partye_nog_nie_gelaai`.

- [ ] **Step 2: Write the failing tests**

```tsx
it("gee 404 vir 'n onbekende kode", …);
it("wys elke wyk as 'n skakel", …);                       // 23 links for WC024
it("sorteer die 2021-tabel op partynaam, nie op setels nie", …);
it("versteek partye sonder setels totdat jy hulle wys", …);
it("wys die geen-meerderheid-reël net wanneer dit waar is", …);
it("wys geen distriksafdeling vir 'n metro nie", …);
```

- [ ] **Step 3: Run them and watch them fail**

- [ ] **Step 4: Implement**

Header (`Plaaslike munisipaliteit` / `Metro` / `Distriksraad` label, name in display type, district + province + ward count), `wyk-rooster.tsx` (a responsive grid of bordered ward links, 6 columns on desktop, 3 on phone), the contesting parties list (alphabetical, with `muni_partye_nog_nie_gelaai` until candidates are loaded), and `raad-2021.tsx`: a table of party · ward seats · PR seats · total sorted by party name, with parties on 0 seats behind a `<details>` toggle that names the count, the council size beside the heading, the independents row when `onafhanklike_setels > 0`, and `KOPIE.muni_2021_geen_meerderheid` rendered only when `geenMeerderheid` is true. `tabular-nums` on every number column. The table sits in an `overflow-x-auto` container. Then `<BronStrook />`.

- [ ] **Step 5: Tests green, `npx tsc --noEmit`, `npm run build`**

- [ ] **Step 6: Commit**

```bash
git add app/munisipaliteit app/_components/verkiesing/wyk-rooster.tsx app/_components/verkiesing/raad-2021.tsx lib/verkiesing/kopie.ts
git commit -m "Verkiesing Fase 2b: munisipaliteitsblad met 2021-raad"
```

---

### Task 8: Sitemap and robots

**Files:**
- Create: `app/sitemap.ts`, `app/robots.ts`, `app/__tests__/sitemap.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it("lys die tuisblad, elke gids, elke wyk en elke munisipaliteit", async () => {
  // data layer stubbed with 2 wards and 2 municipalities
  const uit = await sitemap();
  expect(uit.map((u) => u.url)).toEqual(expect.arrayContaining([
    "https://www.nuuspod.co.za/",
    "https://www.nuuspod.co.za/adverteer",
    "https://www.nuuspod.co.za/wyk/19100055",
    "https://www.nuuspod.co.za/munisipaliteit/WC024",
  ]));
});
it("val terug na die statiese blaaie wanneer die databasis stil is", …);
```

- [ ] **Step 2: Run it and watch it fail**

- [ ] **Step 3: Implement**

`app/sitemap.ts` uses `haalAlleWykIds` and `haalAlleMuniKodes`, plus `/`, `/adverteer` and every published explainer from `gepubliseerdeGidse()`. A `null` from the data layer degrades to the static entries. `app/robots.ts` allows everything and points at the sitemap.

- [ ] **Step 4: Tests green, then commit**

```bash
git add app/sitemap.ts app/robots.ts app/__tests__/sitemap.test.ts
git commit -m "Verkiesing Fase 2b: sitemap en robots met wyk- en munisipaliteitsblaaie"
```

---

### Task 9: Gemini writes the Afrikaans copy

**Files:**
- Create: `scripts/verkiesing-kopie-2b.mjs`, `docs/verkiesing/ui-kopie-2b.json`
- Modify: `lib/verkiesing/kopie.ts`, `docs/verkiesing/ui-kopie-wysigings.md`

- [ ] **Step 1: Read the Drop 1 precedent**

Read `docs/verkiesing/ui-kopie.json` and `docs/verkiesing/ui-kopie-wysigings.md` to copy the format, the voice brief and the fact list style.

- [ ] **Step 2: Write the generator**

`scripts/verkiesing-kopie-2b.mjs`: reads `GEMINI_API_KEY` from `~/nuuspod/.env.local` (**strip surrounding quotes**; never print the value), posts one request to `gemini-3.5-flash` with `responseMimeType: "application/json"`, and writes `docs/verkiesing/ui-kopie-2b.json`. The prompt carries:
- the same voice brief as Drop 1 (direct, warm, everyday South African Afrikaans, "jy", no exclamation marks, no emoji, not translated English);
- the rules: use only the given facts; never name a party or candidate; never promise a Nuuspod feature or date; keep each slot within its word limit; write ordinary sentence case;
- the facts: election day 4 Nov 2026 07:00–21:00; you may only vote at the station where you are registered; final candidate lists 16 Sep; ballot draw 23 Sep; a ward councillor represents the ward in the municipal council, and the party lists fill the proportional seats (checked against the Municipal Structures Act); voters in a local municipality get 3 ballots (ward, local PR, district PR) and metro voters get 2; the source of the data is the IEC, the Municipal Demarcation Board and Stats SA Census 2011;
- one brief per slot, for every slot added in Tasks 5–8.

- [ ] **Step 3: Run it, then fact-check every line yourself**

Check each returned line against the facts above: no invented numbers or dates, no party or candidate names, no promises, word limits respected, and `wyk_raadslid_teks` factually correct about what a ward councillor does. Fix anything wrong by hand and log the change.

- [ ] **Step 4: Merge into `kopie.ts` and log the edits**

Replace the draft values with the approved lines, keeping the keys. Append a Fase 2b section to `docs/verkiesing/ui-kopie-wysigings.md`: each slot, Gemini's line, your edit, and why.

- [ ] **Step 5: Tests green (`npm test`), `npm run build`, then commit**

```bash
git add scripts/verkiesing-kopie-2b.mjs docs/verkiesing/ui-kopie-2b.json docs/verkiesing/ui-kopie-wysigings.md lib/verkiesing/kopie.ts
git commit -m "Verkiesing Fase 2b: Gemini se Afrikaanse kopie vir die wyk-soeker"
```

---

### Task 10: Candidate loader and the candidate half of the check report

**Files:**
- Create: `data/laai_kandidate.py`, `data/tests/test_laai_kandidate.py`
- Modify: `data/kontroleer.py`
- Read: `data/kandidate_ontleder.py` (the Fase 2a parser, with its runtime ID guard), `data/laai_uitslae_2021.py` (loader shape to copy)

**Interfaces:**
- Produces: `stg_partye` and `stg_kandidate` rows, `data/uitvoer/kandidate-verslag.md`, and the candidate sections and gates in `kontroleer.py`.
- Consumes: `kandidate_ontleder.ontleed_lys(pad)` (confirm the real function name and return shape before writing).

- [ ] **Step 1: Write the failing tests**

Pure tests against the 2021 WC fixture already in the repo:

```python
def test_party_ids_is_stabiel_oor_twee_lopies():
    # the same party name must map to the same id when the loader runs twice
def test_stembrief_afleiding():
    # an 8-digit ward id → 'wyk'; a list position in a local municipality → 'pv_plaaslik';
    # a list position in a district municipality → 'pv_distrik'
def test_onafhanklike_kandidaat_kry_geen_party_id():
def test_geen_id_nommer_beland_in_n_ry_nie():
    # no field of any produced row contains a 6+ digit run
def test_wyk_id_moet_in_stg_wyke_bestaan():
    # unknown ward ids are reported and the loader exits non-zero
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Implement `data/laai_kandidate.py`**

CLI: `python laai_kandidate.py --bron bron/kandidate-2026-*.pdf [--net-ontleed]`.
1. Parse every source file with `kandidate_ontleder`; abort on any parse error.
2. Build `stg_partye`: distinct party names, ids assigned deterministically (sorted by name, 1-based) so a re-run is stable; `afkorting` stays null unless the source has one.
3. Build `stg_kandidate`: `muni_kode`, `stembrief`, `wyk_id`, `lys_posisie`, `party_id`, `onafhanklik`, `volle_naam`, `van`, `bron_lêer`, `bron_ry`. Never carry an ID number; re-assert the parser's guard on the rows about to be sent.
4. Validate before writing: every `muni_kode` exists in `stg_munisipaliteite`; every `wyk_id` exists in `stg_wyke`; no duplicate `(muni_kode, stembrief, wyk_id, volle_naam, van, party_id)`; counts per ballot type and per province. Any failure exits non-zero with the reason in the report, before `stg_leeg`.
5. `stg_leeg` both tables, then batch-insert with the existing helper; write `data/uitvoer/kandidate-verslag.md` with the counts, the per-province table, the ballot-type split, and the parse rules that were confirmed against the real file.
6. `--net-ontleed` parses and reports without touching the database.

- [ ] **Step 4: Tests to green**

- [ ] **Step 5: Extend `data/kontroleer.py`**

Add, using the existing `veilig()` per-section pattern so a failure still writes the report:
- a candidates section: totals vs the IEC's published 142,072 (100,856 ward · 40,241 PR · 975 independent ward), per province, per ballot type, plus parties count;
- candidates whose `wyk_id` is not in `stg_wyke`, duplicates, empty names, and any field containing a 6+ digit run (this must be 0);
- a "wards with no ward candidates" count, listed by municipality if small;
- hard gates: a candidate `wyk_id` not in `stg_wyke` > 0, any ID-shaped field > 0, or duplicates > 0 fail the run; a total that differs from the IEC figures is reported as a **decision** (not an automatic failure), because the IEC corrects its list until 25 Sep;
- extend the existing "not yet loaded" section so it drops candidates once they are loaded and keeps ballot order until 23 Sep;
- extend the publish-diff section to compare each `stg_` table against its public table (rows added, removed, changed), which is now meaningful because Task 2 published the base data.

- [ ] **Step 6: Run the full check report**

`python kontroleer.py` must exit 0 with candidates still empty (the candidate section says "nog nie gelaai nie"), and the diff section must show the base tables in sync.

- [ ] **Step 7: Commit**

```bash
git add data/laai_kandidate.py data/tests/test_laai_kandidate.py data/kontroleer.py
git commit -m "Verkiesing Fase 2b: kandidaatlaaier en kandidaat-afdelings in die kontroleverslag"
```

---

### Task 11: Neutrality, brand and promise checks, and full verification

**Files:**
- Create: `app/__tests__/neutraliteit.test.ts`, `scripts/kontroleer-kopie.mjs`
- Modify: `package.json` (a `kontroleer:kopie` script if the repo has a scripts block for this)

- [ ] **Step 1: Write the failing tests**

```ts
it("geen kandidaat- of partyry gebruik 'n kleurtoken nie", …);
// render the ballot and 2021 components and assert no className contains rooi/neon/bg-[#
it("die deelkaart bevat geen partynaam nie", …);
it("geen komponent voer partykleure.json in nie", …);   // grep the source tree
it("ordening gebruik nooit setels of stemme nie", …);   // grep orden.ts for 'setels' outside geenMeerderheid
```

- [ ] **Step 2: Run them and watch them fail, then implement `scripts/kontroleer-kopie.mjs`**

The script greps the built output and the source for: "Die Buitelyn"; launch-promise patterns (`kom binnekort`, `binnekort beskikbaar`, `vanaf \d`, `word gelaai op`, an upcoming-feature date); and any `\d{6,}` inside `lib/verkiesing/kopie.ts`. It exits non-zero with the offending file and line.

- [ ] **Step 3: Full verification**

Run and paste the output into the report: `npm test`, `npx tsc --noEmit`, `npm run build`, `node scripts/kontroleer-kopie.mjs`, and `cd data && … pytest -q`.

- [ ] **Step 4: Browser verification**

With `npm run dev`: search "Brooklyn" and pick a ward; search a station name; run the location flow with mocked coordinates in Stellenbosch; keyboard-only search (Tab, arrows, Enter); a ward page and a municipality page at 400 px and 1280 px; check no horizontal scroll and visible focus rings. Record what you saw.

- [ ] **Step 5: Commit**

```bash
git add app/__tests__/neutraliteit.test.ts scripts/kontroleer-kopie.mjs package.json
git commit -m "Verkiesing Fase 2b: neutraliteits- en kopiekontroles"
```

---

## Out of scope for this plan

- Loading the real candidate list (that is the load-and-publish step this plan prepares for) and the ballot-order loader after 23 Sep.
- Results night, the prediction model, party colours in graphics, maps of ward boundaries, candidate photos or biographies.
- Deploying to production: the branch stays local until Piet approves a preview.
