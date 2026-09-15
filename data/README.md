# Verkiesing Fase 2 — data loaders

Python library used by the base-data loaders (Task 3+) for the `verkiesing-2026`
Supabase project. No project-level Python config exists here on purpose — everything
runs through `uv run --with ...` so there's nothing to install or activate.

## Layout

- `lib/omgewing.py` — reads `VERKIESING_SUPABASE_URL` / `VERKIESING_SUPABASE_SECRET_KEY`
  from `~/nuuspod/.env.local` (quotes stripped). Raises `omgewing.OmgewingFout` naming
  only the missing key(s), never a value.
- `lib/supabase.py` — `plaas_bondels(tabel, rye, grootte=500)` (batched
  `POST /rest/v1/<tabel>` with `Prefer: return=minimal`, halves the batch on 413, retries
  3× with exponential backoff on 429/5xx, raises `supabase.SupabaseFout` — response text
  truncated to 500 chars, never headers — on any other failure) and
  `rpc(naam, args)` (`POST /rest/v1/rpc/<naam>`, returns parsed JSON or `None` on 204).
  Both accept an optional `klient=` (an `httpx.Client`) for dependency injection in tests;
  by default they build one from `omgewing.lees()`.
- `lib/geo.py` — `na_ewkt_4326(shape, bron_epsg)` converts a pyshp or shapely geometry to
  `"SRID=4326;" + WKT` (MultiPolygon), reprojecting with pyproj when `bron_epsg != 4326`,
  repairing invalid geometry with `shapely.make_valid` (keeping only polygonal parts), and
  rounding coordinates to 6 decimals.
- `lib/teks.py` — `normaliseer(s)` (lowercase, strip accents, fold hyphens/apostrophes to
  spaces, collapse whitespace) and `skoon_plek_naam(naam)` (strips the MDB Subplace/
  MainPlace type suffix — `" SP"` is urban, `" NU"`/`" SH"` are rural — returning
  `(naam, landelik)`).
- `tests/` — pytest suite, no network (Supabase calls are tested with
  `httpx.MockTransport`; `omgewing` is tested against temp files).
- `bron/` — source files for the loaders (gitignored, see the plan's global constraints).
- `uitvoer/` — loader run-reports (gitignored; each loader writes
  `uitvoer/<datastel>-verslag.md`).

## Loader run order

Every loader reads credentials via `lib.omgewing.lees()`, empties its own `stg_` table(s)
first, writes `uitvoer/<datastel>-verslag.md`, and exits non-zero on failure. Run from
`data/` with
`uv run --with pdfplumber,pyshp,shapely,pyproj,httpx python <script>`:

1. `laai_wyke.py` — `stg_munisipaliteite` (213 councils + 44 districts) and `stg_wyke`.
   It recovers NC451 (Joe Morolong)'s 15 wards itself from
   `bron/stemstasies-2026-NC.pdf` (the MDB shapefile gives them non-numeric WardIDs), so
   this script alone yields all 4,485 wards. Any NC451 mapping gap is a hard failure
   before any write. `--net-ontleed` parses and prints counts without touching Supabase.
2. `laai_stemstasies.py` — `stg_stemstasies` (needs step 1; it no longer writes wards).
3. `laai_plekke.py` — `stg_plekke`, `stg_plek_wyke` (chunked `rpc/bou_plek_wyke`),
   `stg_plek_aliasse` (needs step 1). An alias row in `aliasse.csv` that resolves to 0
   sub places is a hard failure. `--net-aliasse` reloads only the aliases (cheap).
4. `laai_uitslae_2021.py` — `stg_raad_uitslae_2021` + `stg_raad_grootte_2021` (needs
   step 1; exits non-zero and writes nothing unless all 213 councils parse).
5. `kontroleer.py` — read-only; writes `uitvoer/kontroleverslag.md` and exits 1 if any
   hard gate fails (counts, unknown wards, places without a ward, duplicate keys,
   empty aliases).

`kandidate_ontleder.py` is a pure parser (no DB yet).

### The 4 rural places after a full places reload

A full `laai_plekke.py` run (no flags) empties `stg_plek_wyke` and recomputes overlaps
through PostgREST, where the `authenticator` role's 8 s `statement_timeout` applies.
Four very large rural sub places never finish within 8 s, even one at a time:

| sp_kode | Place |
|---|---|
| 271002001 | Mnquna (spelled "Mnquma" elsewhere) |
| 290003001 | Ngquza Hill |
| 292002001 | Nyandeni |
| 966002001 | Thulamela |

After a full places reload their `stg_plek_wyke` rows (156 in the 2026-09-15 load) must be
recomputed with **direct SQL** (Supabase SQL editor / MCP `execute_sql`, no 8 s limit),
one place per call, using the row number of each sp_kode in `stg_plekke` ordered by
sp_kode:

```sql
with n as (select sp_kode, row_number() over (order by sp_kode) as rn
           from stg_plekke where geom is not null)
select sp_kode, rn from n
where sp_kode in ('271002001', '290003001', '292002001', '966002001');
-- then, for each rn:
select bou_plek_wyke(<rn>, <rn>);
```

The ranged `bou_plek_wyke(van, tot)` deletes the range's existing rows first, so a retry
never duplicates. `kontroleer.py` fails if any of the four has 0 wards or if more than
the 3 known harbour slivers have no ward.

## Running the tests

```sh
cd data && uv run --with pdfplumber,pyshp,shapely,pyproj,httpx,pytest pytest -q
```

`conftest.py` at the top of `data/` puts `data/` on `sys.path` so tests (and future loader
scripts) can `import lib.xxx` regardless of pytest's import-mode.

## Using the library from a loader script

```sh
cd data && uv run --with shapely,pyproj,pyshp,httpx python your_loader.py
```

```python
from lib import omgewing, supabase, geo, teks

waardes = omgewing.lees()  # {"url": ..., "sleutel": ...}
supabase.rpc("stg_leeg", {"tabel": "stg_wyke"})
supabase.plaas_bondels("stg_wyke", ry_lys, grootte=500)
```

## Smoke-testing credentials

A single harmless real call proves the env + auth wiring works without touching real data
(`stg_wyke` is empty at this point in the plan):

```sh
cd data && uv run --with httpx python -c "
from lib import supabase
print(supabase.rpc('stg_leeg', {'tabel': 'stg_wyke'}))
"
```

Expect `None` (PostgREST returns 204 for this RPC) and no error.
