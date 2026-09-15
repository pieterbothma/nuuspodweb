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

## Running the tests

```sh
cd data && uv run --with pytest,shapely,pyproj,pyshp,httpx pytest -q
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
