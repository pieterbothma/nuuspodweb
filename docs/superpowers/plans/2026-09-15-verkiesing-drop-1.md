# Verkiesing 2026 Drop 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn nuuspod.co.za into the Verkiesing 2026 home page. It carries the countdown, upcoming dates, approved voter explainers, Verkiesings-Vrydag episodes, a verbatim "Wat ander berig" headline rail and a feedback prompt. The advertiser page moves to `/adverteer`.

**Architecture:**
- `nuuspod-web` stays a small Next.js 16 site. It reads a new Supabase project (`verkiesing-2026`) through plain PostgREST `fetch` calls, cached with `next: { revalidate, tags }`. No database client dependency.
- Ingestion runs as two Vercel crons in the `nuuspod` admin repo, which already has RSS parsing, `CRON_SECRET` crons and the Telegram bot. The crons write to Supabase with the secret key.
- A Telegram "Versteek" button hides a headline. It calls a site endpoint that expires the cached rail.

**Tech Stack:**
- Next.js 16.2 (App Router, no `cacheComponents`), React 19, Tailwind v4, `motion`
- Supabase Postgres + PostgREST
- Vitest 4
- `rss-parser` (admin, already installed)
- Telegram Bot API (admin client)

**Spec:** `docs/superpowers/specs/2026-09-14-verkiesing-2026-design.md` (read it with this plan)

## Global Constraints

- **Election day constant:** `2026-11-04T07:00:00+02:00`.
  - Special-vote applications: 21 Sep – 12 Oct 2026 17:00.
  - Special votes: 2–3 Nov 08:00–17:00.
  - Voting: 4 Nov 07:00–21:00.
  - Timezone for every displayed time: `Africa/Johannesburg`.
- **No generated sentence names a party or candidate.** Episode titles are Nuuspod's own journalism and are shown as-is.
- **Headlines are stored and shown exactly as the feed gives them.** Only XML/HTML entity decoding and trimming of leading/trailing whitespace are allowed. No translation, shortening, truncation (`line-clamp`, `…`) or case changes. Feed body text is never stored.
- **No public launch promises:** no copy announcing upcoming Nuuspod features or dates, anywhere.
- **Explainers go live only when Piet approves.** Each has a `gepubliseer` flag that defaults to `false`.
- **Party colours never appear.** Red (`rooi`) and cyan (`siaan`) are for page chrome only.
- **Brand is "Nuuspod", never "Die Buitelyn".** Grep before shipping.
- **Supabase project:** `verkiesing-2026`, ref `xxysgvanarnirxoxrbkj`, URL `https://xxysgvanarnirxoxrbkj.supabase.co`.
  - The publishable key goes in the site only.
  - The secret key goes in the admin only and never in a `NEXT_PUBLIC_*` variable.
- **Site tokens** (`app/globals.css`): `swart`, `paneel`, `rand`, `rooi`, `siaan`, `papier`, `grys`. Fonts `font-display` (DM Serif Display) and `font-sans` (Source Sans 3).
- **Language:**
  - Afrikaans for all on-page copy and all commit messages in both repos.
  - Code identifiers follow each repo's existing Afrikaans naming.
  - Code comments stay English, as the existing files do.
- **The admin repo (`~/nuuspod`) has unrelated uncommitted changes** (`CLAUDE.md`, `scraper/main.py`, `.data/`). Always `git add` explicit paths; never `git add -A` or `git commit -a` there.
- **Branches:**
  - `nuuspod-web`: work on `verkiesing-drop-1`. `main` deploys production.
  - `nuuspod`: work on `verkiesing-drop-1`, merged to `main` in Task 11. Vercel crons only run on production.
- **Every commit ends with:**
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p
  ```

## File map

**nuuspod-web** (paths from `~/projects/nuuspod-web`)

| File | Responsibility |
|---|---|
| `supabase/migrations/20260915000000_verkiesing_drop1.sql` | Drop 1 tables, RLS and grants (record of what was applied) |
| `vitest.config.ts`, `package.json` | Test runner |
| `app/adverteer/page.tsx` | Former home page, moved verbatim + its own metadata |
| `app/layout.tsx` | Site-wide election metadata |
| `lib/supabase-rest.ts` | `lees` (cached GET) and `voegIn` (POST) against PostgREST |
| `lib/verkiesing/datums.ts` (+ test) | Election milestones, `komendeMylpale`, `aftelling` |
| `lib/verkiesing/stroom.ts` (+ test) | `StroomItem`, `balanseer`, `tydEtiket` |
| `lib/verkiesing/lees.ts` | `haalStroom`, `haalEpisodes`, fallback episode |
| `lib/verkiesing/terme.ts` | The one place the commission's name is spelled |
| `lib/verkiesing/gidse/tipes.ts` (+ test) | `Blok`, `GidsBron`, `Gids`, `vetDele`, `mdNaBlokke` |
| `lib/verkiesing/gidse/index.ts` | `GIDSE`, `gepubliseerdeGidse`, `vindGids` |
| `lib/verkiesing/gidse/<slug>.ts` | Generated explainer content (4 files) |
| `docs/verkiesing/konsepte/<slug>.md` | Editor-approved explainer source text |
| `scripts/gids-na-ts.mjs` | Generates `lib/verkiesing/gidse/<slug>.ts` from the Markdown |
| `app/api/herlaai/route.ts` | Secret-guarded on-demand revalidation of `nuusstroom` / `episodes` |
| `app/aksies.ts` | Server action `stuurTerugvoer` |
| `app/_components/verkiesing/*.tsx` | `Kopstuk`, `Aftelling`, `WatKom`, `KontroleerRegistrasie`, `Verkiesingsprogram`, `Nuusstroom`, `GidsKaarte`, `GidsInhoud`, `Terugvoer`, `Voet` |
| `app/page.tsx` | New election home page |
| `app/gids/[onderwerp]/page.tsx` | Explainer pages |
| `next.config.ts` | Allow `i.ytimg.com` thumbnails |

**nuuspod** admin (paths from `~/nuuspod`)

| File | Responsibility |
|---|---|
| `src/lib/verkiesing/bronne.ts` | Headline source allowlist |
| `src/lib/verkiesing/filter.ts` (+ test) | `isVerkiesingStorie` keyword filter |
| `src/lib/verkiesing/titel.ts` (+ test) | `dekodeerTitel` |
| `src/lib/verkiesing/stroom.ts` (+ test) | `naStroomRy` (pure) and `neemStroomIn` (I/O) |
| `src/lib/verkiesing/episodes.ts` (+ test) | Title parsing, `uitFeedXml`, `neemEpisodesIn` |
| `src/lib/verkiesing/db.ts` | `rest` PostgREST helper with the secret key |
| `src/lib/verkiesing/werf.ts` | `herlaaiWerf` calls the site's revalidate endpoint |
| `src/lib/verkiesing/telegram.ts` (+ test) | `stroomBoodskap`, `versteekKnoppie`, `meldNuweStroomItems`, `versteekTerugroep` |
| `src/lib/telegram/keyboard.ts` (+ test) | Add callback namespace `"h"` |
| `src/lib/telegram/handlers/index.ts` | Route `h:` callbacks to `versteekTerugroep` |
| `src/app/api/cron/verkiesing-stroom/route.ts` | Headline cron |
| `src/app/api/cron/verkiesing-episodes/route.ts` | Episode cron |
| `vercel.json` | Two new cron entries |

---

### Task 1: Supabase schema, keys and local env

**Files:**
- Create: `~/projects/nuuspod-web/supabase/migrations/20260915000000_verkiesing_drop1.sql`
- Modify: `~/projects/nuuspod-web/.env.local` (create; gitignored via `.env*`), `~/nuuspod/.env.local`

**Interfaces:**
- Produces:
  - Tables `public.nuusstroom`, `public.episodes`, `public.terugvoer`
  - Env `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `HERLAAI_SECRET` (site)
  - Env `VERKIESING_SUPABASE_URL`, `VERKIESING_SUPABASE_SECRET_KEY`, `NUUSPOD_WEB_HERLAAI_SECRET`, `NUUSPOD_WEB_URL`, `VERKIESING_TELEGRAM_CHAT_ID` (admin)

- [ ] **Step 1: Create the branches**

```bash
cd ~/projects/nuuspod-web && git checkout -b verkiesing-drop-1
cd ~/nuuspod && git checkout -b verkiesing-drop-1
```

- [ ] **Step 2: Write the migration file**

```sql
-- Verkiesing 2026, Drop 1: headline rail, Verkiesings-Vrydag episodes, reader feedback.
-- Applied to project xxysgvanarnirxoxrbkj with the Supabase MCP apply_migration tool.

create table public.nuusstroom (
  id bigint generated always as identity primary key,
  titel text not null check (length(titel) between 1 and 500),
  bron text not null,
  bron_tipe text not null check (bron_tipe in ('nasionaal', 'streek', 'gemeenskap', 'openbare uitsaaier')),
  url text not null unique check (url ~ '^https?://'),
  gepubliseer_om timestamptz not null,
  ingevoeg_om timestamptz not null default now(),
  versteek boolean not null default false
);
create index nuusstroom_sigbaar_idx on public.nuusstroom (gepubliseer_om desc) where not versteek;

create table public.episodes (
  video_id text primary key check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  titel text not null,
  uitsaaidatum date not null,
  gepubliseer_om timestamptz,
  handmatig boolean not null default false,
  versteek boolean not null default false,
  bygewerk_om timestamptz not null default now()
);

create table public.terugvoer (
  id bigint generated always as identity primary key,
  bladsy text not null check (bladsy ~ '^/' and length(bladsy) <= 200),
  gevind boolean not null,
  geskep_om timestamptz not null default now()
);

alter table public.nuusstroom enable row level security;
alter table public.episodes enable row level security;
alter table public.terugvoer enable row level security;

revoke all on public.nuusstroom, public.episodes, public.terugvoer from anon, authenticated;
grant select on public.nuusstroom, public.episodes to anon;
grant insert (bladsy, gevind) on public.terugvoer to anon;

create policy "publiek lees sigbare stroom" on public.nuusstroom
  for select to anon using (not versteek);
create policy "publiek lees sigbare episodes" on public.episodes
  for select to anon using (not versteek);
create policy "publiek stuur terugvoer" on public.terugvoer
  for insert to anon with check (true);
```

- [ ] **Step 3: Apply it**

Call MCP `apply_migration` with project_id `xxysgvanarnirxoxrbkj`, name `verkiesing_drop1` and the SQL above. Then call MCP `get_advisors` (type `security`).
Expected: no ERROR-level advisories for these three tables. Fix any before continuing.

- [ ] **Step 4: Get the keys**

- Publishable key: MCP `get_publishable_keys` for `xxysgvanarnirxoxrbkj`. Use the `sb_publishable_…` key.
- Secret key:
  - Run `supabase projects api-keys --project-ref xxysgvanarnirxoxrbkj`.
  - If the CLI is not logged in, stop and ask Piet to copy the `sb_secret_…` key from Dashboard → Project Settings → API Keys into `~/nuuspod/.env.local` himself.
  - Never paste the secret key into chat.

- [ ] **Step 5: Write the env files**

```bash
HERLAAI=$(openssl rand -hex 32)
cat >> ~/projects/nuuspod-web/.env.local <<EOF
SUPABASE_URL=https://xxysgvanarnirxoxrbkj.supabase.co
SUPABASE_PUBLISHABLE_KEY=<sb_publishable key>
HERLAAI_SECRET=$HERLAAI
EOF
cat >> ~/nuuspod/.env.local <<EOF
VERKIESING_SUPABASE_URL=https://xxysgvanarnirxoxrbkj.supabase.co
VERKIESING_SUPABASE_SECRET_KEY=<sb_secret key>
NUUSPOD_WEB_URL=http://localhost:3001
NUUSPOD_WEB_HERLAAI_SECRET=$HERLAAI
VERKIESING_TELEGRAM_CHAT_ID=<first id from TELEGRAM_ALLOWED_CHAT_IDS in the same file>
EOF
grep -c "^\.env" ~/projects/nuuspod-web/.gitignore
```

Expected: the last command prints `1` (`.env*` is ignored). If it prints `0`, add `.env*.local` to `.gitignore`.

- [ ] **Step 6: Verify the access rules with real requests**

```bash
set -a; source ~/projects/nuuspod-web/.env.local; set +a
B=$SUPABASE_URL/rest/v1
curl -s "$B/nuusstroom?select=id&limit=1" -H "apikey: $SUPABASE_PUBLISHABLE_KEY"; echo
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$B/nuusstroom" -H "apikey: $SUPABASE_PUBLISHABLE_KEY" -H "Content-Type: application/json" -d '{"titel":"x","bron":"x","bron_tipe":"nasionaal","url":"https://x.co","gepubliseer_om":"2026-09-15T00:00:00Z"}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$B/terugvoer" -H "apikey: $SUPABASE_PUBLISHABLE_KEY" -H "Content-Type: application/json" -H "Prefer: return=minimal" -d '{"bladsy":"/toets","gevind":true}'
curl -s -o /dev/null -w "%{http_code}\n" "$B/terugvoer?select=id" -H "apikey: $SUPABASE_PUBLISHABLE_KEY"
```

Expected, in order:
1. `[]`
2. `401` or `403` (anon cannot write the rail)
3. `201` (anon can send feedback)
4. `401` or `403` (anon cannot read feedback)

Then delete the test row: MCP `execute_sql` `delete from public.terugvoer where bladsy = '/toets';`

- [ ] **Step 7: Commit (site repo only; env files are ignored)**

```bash
cd ~/projects/nuuspod-web
git add supabase/migrations/20260915000000_verkiesing_drop1.sql
git commit -m "Verkiesing: databasis vir die nuusstroom, episodes en terugvoer

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 2: Test runner, `/adverteer` move, election metadata

**Files:**
- Create: `vitest.config.ts`
- Modify: `package.json` (script + devDependency)
- Move: `app/page.tsx` → `app/adverteer/page.tsx`
- Modify: `app/layout.tsx:34-49`
- Create: `app/page.tsx` (temporary placeholder, replaced in Task 6)

**Interfaces:**
- Produces: `npm test` runs `lib/**/*.test.ts`. `/adverteer` serves the old sales page unchanged.

- [ ] **Step 1: Install Vitest and add the config**

```bash
cd ~/projects/nuuspod-web && npm install -D vitest@^4.1.9 && npm pkg set scripts.test="vitest run"
```

`vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, ".") } },
  test: { environment: "node", include: ["lib/**/*.test.ts"] },
});
```

- [ ] **Step 2: Move the sales page**

```bash
mkdir -p app/adverteer && git mv app/page.tsx app/adverteer/page.tsx
sed -i '' 's#from "./_components/animasie"#from "../_components/animasie"#' app/adverteer/page.tsx
grep -n '_components/animasie' app/adverteer/page.tsx
```

Expected: one line showing `from "../_components/animasie"`.

Add at the top of `app/adverteer/page.tsx`, below the existing imports:

```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Adverteer by Nuuspod — Afrikaanse nuus, elke weeksdag regstreeks",
  description:
    "Nuuspod met Izak du Plessis bereik gemiddeld 14 miljoen mense per maand op Facebook en YouTube. Sien die advertensiepakkette en tariewe.",
  openGraph: {
    title: "Adverteer by Nuuspod",
    description:
      "Afrikaanse nuusbulletin, elke weeksdag regstreeks. Gemiddeld 14 miljoen kyke per maand.",
    url: "https://nuuspod.co.za/adverteer",
    siteName: "Nuuspod",
    locale: "af_ZA",
    type: "website",
  },
};
```

Also rename the component: `export default async function Tuis()` → `export default async function Adverteer()`.

- [ ] **Step 3: Replace the layout metadata**

In `app/layout.tsx`, replace the whole `export const metadata: Metadata = { … };` block with:

```tsx
export const metadata: Metadata = {
  metadataBase: new URL("https://nuuspod.co.za"),
  title: "Verkiesing 2026 — Nuuspod",
  description:
    "Die plaaslike verkiesing van 4 November 2026 in Afrikaans: belangrike datums, hoe om te stem, en Verkiesings-Vrydag met Izak du Plessis.",
  openGraph: {
    title: "Verkiesing 2026 — Nuuspod",
    description: "Alles wat jy nodig het om op 4 November te stem, in Afrikaans.",
    url: "https://nuuspod.co.za",
    siteName: "Nuuspod",
    locale: "af_ZA",
    type: "website",
  },
};
```

- [ ] **Step 4: Temporary home page so the build passes**

`app/page.tsx`:

```tsx
export default function Tuis() {
  return <main className="p-8 font-display text-3xl">Verkiesing 2026</main>;
}
```

- [ ] **Step 5: Build and check `/adverteer`**

```bash
npm run build && (npx next start -p 3001 & sleep 5; curl -s localhost:3001/adverteer | grep -o "Adverteer by Nuuspod" | head -1; curl -s -o /dev/null -w "%{http_code}\n" localhost:3001/; kill %1)
```

Expected:
- the build succeeds;
- the first curl prints `Adverteer by Nuuspod`;
- the second prints `200`.

- [ ] **Step 6: Commit**

```bash
git add vitest.config.ts package.json package-lock.json app/adverteer/page.tsx app/page.tsx app/layout.tsx
git commit -m "Verkiesing: advertensiebladsy skuif na /adverteer; toetsloper

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 3: Site data libraries (dates, rail, Supabase reads)

**Files:**
- Create: `lib/verkiesing/datums.ts`, `lib/verkiesing/datums.test.ts`
- Create: `lib/verkiesing/stroom.ts`, `lib/verkiesing/stroom.test.ts`
- Create: `lib/supabase-rest.ts`, `lib/verkiesing/lees.ts`, `lib/verkiesing/terme.ts`

**Interfaces:**
- Produces:
  - `STEMDAG: Date`
  - `interface Mylpaal { id: string; wanneer: string; wat: string; einde: string }`
  - `MYLPALE: Mylpaal[]`
  - `komendeMylpale(nou: Date, aantal?: number): Mylpaal[]`
  - `aftelling(nou: Date, teiken?: Date): { dae: number; ure: number; minute: number; verby: boolean }`
  - `interface StroomItem { id: number; titel: string; bron: string; bron_tipe: string; url: string; gepubliseer_om: string }`
  - `balanseer(items: StroomItem[], top?: number, perBron?: number): StroomItem[]`
  - `tydEtiket(iso: string, nou: Date): string`
  - `lees<T>(pad: string, opts: { tags: string[]; revalidate: number }): Promise<T[] | null>`
  - `voegIn(tabel: string, ry: Record<string, unknown>): Promise<boolean>`
  - `interface Episode { video_id: string; titel: string; uitsaaidatum: string }`
  - `TERUGVAL_EPISODE: Episode`
  - `haalStroom(): Promise<StroomItem[]>`
  - `haalEpisodes(): Promise<Episode[]>`
  - `KOMMISSIE: string`

- [ ] **Step 1: Write the failing tests**

`lib/verkiesing/datums.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { aftelling, komendeMylpale, STEMDAG } from "./datums";

describe("aftelling", () => {
  it("counts whole days, hours and minutes to 07:00 on election day", () => {
    expect(aftelling(new Date("2026-09-14T20:00:00+02:00"))).toEqual({
      dae: 50,
      ure: 11,
      minute: 0,
      verby: false,
    });
  });

  it("reports verby once voting has opened", () => {
    expect(aftelling(STEMDAG).verby).toBe(true);
  });
});

describe("komendeMylpale", () => {
  it("drops milestones whose end has passed and keeps list order", () => {
    const ids = komendeMylpale(new Date("2026-09-17T12:00:00+02:00")).map((m) => m.id);
    expect(ids).toEqual(["spesiale-aansoeke", "trekking", "spesiale-stemme"]);
  });

  it("keeps the special-vote window visible until 17:00 on 12 October", () => {
    const voor = komendeMylpale(new Date("2026-10-12T16:59:00+02:00"), 1);
    const na = komendeMylpale(new Date("2026-10-12T17:01:00+02:00"), 1);
    expect(voor[0].id).toBe("spesiale-aansoeke");
    expect(na[0].id).toBe("spesiale-stemme");
  });

  it("is empty after voting closes", () => {
    expect(komendeMylpale(new Date("2026-11-04T21:01:00+02:00"))).toEqual([]);
  });
});
```

`lib/verkiesing/stroom.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { balanseer, tydEtiket, type StroomItem } from "./stroom";

const item = (id: number, bron: string): StroomItem => ({
  id,
  titel: `Opskrif ${id}`,
  bron,
  bron_tipe: "nasionaal",
  url: `https://voorbeeld.co.za/${id}`,
  gepubliseer_om: "2026-09-15T08:00:00Z",
});

describe("balanseer", () => {
  it("allows at most three items per source, in the given order", () => {
    const items = [1, 2, 3, 4].map((id) => item(id, "A")).concat(item(5, "B"));
    expect(balanseer(items).map((i) => i.id)).toEqual([1, 2, 3, 5]);
  });

  it("stops at the top limit", () => {
    const items = Array.from({ length: 40 }, (_, i) => item(i, `bron-${i}`));
    expect(balanseer(items)).toHaveLength(15);
  });
});

describe("tydEtiket", () => {
  const nou = new Date("2026-09-14T18:00:00Z"); // 20:00 SAST

  it("shows SAST clock time for today's items", () => {
    expect(tydEtiket("2026-09-14T12:20:00Z", nou)).toBe("14:20");
  });

  it("shows day and Afrikaans month for older items", () => {
    expect(tydEtiket("2026-09-12T09:00:00Z", nou)).toBe("12 Sep");
    expect(tydEtiket("2026-10-03T09:00:00Z", new Date("2026-10-20T09:00:00Z"))).toBe("3 Okt");
  });

  it("uses the SAST date, not the UTC date, to decide what is today", () => {
    // 23:30 UTC on the 13th is 01:30 SAST on the 14th.
    expect(tydEtiket("2026-09-13T23:30:00Z", nou)).toBe("01:30");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npm test`
Expected: FAIL. `Cannot find module './datums'` and `'./stroom'`.

- [ ] **Step 3: Implement**

`lib/verkiesing/datums.ts`:

```ts
/** Voting opens at 07:00 SAST on Wednesday 4 November 2026 (gazetted timetable). */
export const STEMDAG = new Date("2026-11-04T07:00:00+02:00");

export interface Mylpaal {
  id: string;
  /** Afrikaans date label as shown on the page. */
  wanneer: string;
  /** Afrikaans description as shown on the page. */
  wat: string;
  /** ISO instant after which the milestone is no longer upcoming. */
  einde: string;
}

// Dates verified against the IEC's gazetted LGE 2026 timetable (spec §4). Neutral facts only.
export const MYLPALE: Mylpaal[] = [
  {
    id: "kandidaatlyste",
    wanneer: "Woensdag 16 September",
    wat: "Die finale kandidaatlyste word gepubliseer.",
    einde: "2026-09-16T23:59:59+02:00",
  },
  {
    id: "spesiale-aansoeke",
    wanneer: "21 September tot 12 Oktober, 17:00",
    wat: "Doen aansoek om 'n spesiale stem as jy nie op stemdag by jou stemlokaal kan stem nie.",
    einde: "2026-10-12T17:00:00+02:00",
  },
  {
    id: "trekking",
    wanneer: "Woensdag 23 September",
    wat: "Die trekking bepaal die volgorde van partye op die stembriewe.",
    einde: "2026-09-23T23:59:59+02:00",
  },
  {
    id: "spesiale-stemme",
    wanneer: "Maandag 2 en Dinsdag 3 November",
    wat: "Spesiale stemme, 08:00 tot 17:00.",
    einde: "2026-11-03T17:00:00+02:00",
  },
  {
    id: "stemdag",
    wanneer: "Woensdag 4 November",
    wat: "Stemdag. Stemlokale is oop van 07:00 tot 21:00.",
    einde: "2026-11-04T21:00:00+02:00",
  },
];

export function komendeMylpale(nou: Date, aantal = 3): Mylpaal[] {
  return MYLPALE.filter((m) => new Date(m.einde).getTime() > nou.getTime()).slice(0, aantal);
}

export function aftelling(nou: Date, teiken: Date = STEMDAG) {
  const ms = teiken.getTime() - nou.getTime();
  if (ms <= 0) return { dae: 0, ure: 0, minute: 0, verby: true };
  const totaal = Math.floor(ms / 60_000);
  return {
    dae: Math.floor(totaal / 1440),
    ure: Math.floor((totaal % 1440) / 60),
    minute: totaal % 60,
    verby: false,
  };
}
```

Note: `komendeMylpale` filters by end time but keeps list order, so the list must stay in the order readers should see it. The test at 17 Sep expects `spesiale-aansoeke, trekking, spesiale-stemme`.

`lib/verkiesing/stroom.ts`:

```ts
export interface StroomItem {
  id: number;
  titel: string;
  bron: string;
  bron_tipe: string;
  url: string;
  gepubliseer_om: string;
}

/** Newest-first input; no single outlet may dominate the visible rail. */
export function balanseer(items: StroomItem[], top = 15, perBron = 3): StroomItem[] {
  const tel = new Map<string, number>();
  const uit: StroomItem[] = [];
  for (const item of items) {
    const n = tel.get(item.bron) ?? 0;
    if (n >= perBron) continue;
    tel.set(item.bron, n + 1);
    uit.push(item);
    if (uit.length === top) break;
  }
  return uit;
}

const MAANDE = ["Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"];

function sast(d: Date) {
  const dele = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Africa/Johannesburg",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(d)
      .map((p) => [p.type, p.value])
  );
  return { datum: `${dele.year}-${dele.month}-${dele.day}`, maand: Number(dele.month), dag: Number(dele.day), tyd: `${dele.hour}:${dele.minute}` };
}

/** "14:20" for today (SAST), otherwise "12 Sep". Month names are fixed so ICU data can't change them. */
export function tydEtiket(iso: string, nou: Date): string {
  const item = sast(new Date(iso));
  return item.datum === sast(nou).datum ? item.tyd : `${item.dag} ${MAANDE[item.maand - 1]}`;
}
```

`lib/supabase-rest.ts`:

```ts
/**
 * PostgREST over plain fetch, so Next's fetch cache (revalidate + tags) applies and the site needs
 * no database client. Reads use the publishable key; row access is enforced by RLS.
 */
function konfig() {
  const url = process.env.SUPABASE_URL;
  const sleutel = process.env.SUPABASE_PUBLISHABLE_KEY;
  return url && sleutel ? { url, sleutel } : null;
}

/** Returns null (never throws) so a database outage renders fallbacks instead of an error page. */
export async function lees<T>(
  pad: string,
  opts: { tags: string[]; revalidate: number }
): Promise<T[] | null> {
  const k = konfig();
  if (!k) return null;
  try {
    const res = await fetch(`${k.url}/rest/v1/${pad}`, {
      headers: { apikey: k.sleutel },
      next: { tags: opts.tags, revalidate: opts.revalidate },
    });
    if (!res.ok) {
      console.error(`[supabase] GET ${pad}: ${res.status}`);
      return null;
    }
    return (await res.json()) as T[];
  } catch (err) {
    console.error(`[supabase] GET ${pad}:`, err);
    return null;
  }
}

export async function voegIn(tabel: string, ry: Record<string, unknown>): Promise<boolean> {
  const k = konfig();
  if (!k) return false;
  try {
    const res = await fetch(`${k.url}/rest/v1/${tabel}`, {
      method: "POST",
      headers: { apikey: k.sleutel, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify(ry),
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}
```

`lib/verkiesing/lees.ts`:

```ts
import { lees } from "@/lib/supabase-rest";
import { balanseer, type StroomItem } from "./stroom";

export interface Episode {
  video_id: string;
  titel: string;
  uitsaaidatum: string;
}

/** The first Verkiesings-Vrydag, shown if the episodes table is empty or unreachable. */
export const TERUGVAL_EPISODE: Episode = {
  video_id: "Y9HiKkP7Rmo",
  titel: "Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag 11 September 2026",
  uitsaaidatum: "2026-09-11",
};

export async function haalStroom(): Promise<StroomItem[]> {
  const rye = await lees<StroomItem>(
    "nuusstroom?select=id,titel,bron,bron_tipe,url,gepubliseer_om&order=gepubliseer_om.desc&limit=60",
    { tags: ["nuusstroom"], revalidate: 300 }
  );
  return balanseer(rye ?? []);
}

export async function haalEpisodes(): Promise<Episode[]> {
  const rye = await lees<Episode>(
    "episodes?select=video_id,titel,uitsaaidatum&order=uitsaaidatum.desc&limit=12",
    { tags: ["episodes"], revalidate: 3600 }
  );
  return rye && rye.length > 0 ? rye : [TERUGVAL_EPISODE];
}
```

`lib/verkiesing/terme.ts`:

```ts
/** How the site names the Electoral Commission: "OVK" (Piet, 14 Sep). Change it here only. */
export const KOMMISSIE = "OVK";
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: PASS, 10 tests. If the `stemdag` milestone order causes the 17 Sep test to fail, the list order is wrong. Fix the order, never the test.

- [ ] **Step 5: Commit**

```bash
git add lib/
git commit -m "Verkiesing: datums, aftelling, nuusstroom-balans en Supabase-lees

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 4: Explainer content pipeline and `/gids/[onderwerp]`

**Files:**
- Create: `docs/verkiesing/konsepte/{wyk-en-pr-stembrief,spesiale-stemme,wat-om-saam-te-bring,waar-stem-ek}.md`
- Create: `lib/verkiesing/gidse/tipes.ts`, `lib/verkiesing/gidse/tipes.test.ts`, `lib/verkiesing/gidse/index.ts`
- Create: `scripts/gids-na-ts.mjs`, `lib/verkiesing/gidse/<slug>.ts` (generated ×4)
- Create: `app/_components/verkiesing/gids-inhoud.tsx`, `app/gids/[onderwerp]/page.tsx`

**Interfaces:**
- Consumes: `Kopstuk` and `Voet` from Task 6. **Build this page after Task 6**, or stub both as `() => null` until then.
- Produces:
  - `type Blok = { tipe: "p"; teks: string } | { tipe: "h2"; teks: string } | { tipe: "ul"; items: string[] }`
  - `interface GidsBron { slug: string; titel: string; lyf: string; bronne: string[]; nagegaan: string; gepubliseer: boolean }`
  - `interface Gids extends GidsBron { blokke: Blok[]; opsomming: string }`
  - `vetDele(teks: string): { teks: string; vet: boolean }[]`
  - `mdNaBlokke(md: string): Blok[]`
  - `GIDSE: Gids[]`
  - `gepubliseerdeGidse(): Gids[]`
  - `vindGids(slug: string): Gids | undefined`

- [ ] **Step 1: Confirm the drafts are in the repo**

The four drafts were committed on 14 Sep (`5fd59f4`) with all of Piet's editor decisions applied:
- ID wording follows the IEC email;
- "OVK" throughout;
- "R1,50 per SMS";
- the reg 23B address rule is added;
- "Voter Information" appears in quotes;
- Gemini's titles are kept;
- the wyk-soeker date line is removed.

```bash
ls docs/verkiesing/konsepte/
```

Expected: `spesiale-stemme.md  waar-stem-ek.md  wat-om-saam-te-bring.md  wyk-en-pr-stembrief.md`. Apply any later change by editing only these files, and log it under `## Wysigings ná Gemini`.

- [ ] **Step 2: Write the failing tests**

`lib/verkiesing/gidse/tipes.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { mdNaBlokke, vetDele } from "./tipes";

describe("vetDele", () => {
  it("splits bold runs from plain text", () => {
    expect(vetDele("**Stemdag:** Woensdag 4 November 2026.")).toEqual([
      { teks: "Stemdag:", vet: true },
      { teks: " Woensdag 4 November 2026.", vet: false },
    ]);
  });

  it("leaves text without markers alone, including a lone pair of asterisks", () => {
    expect(vetDele("Geen ** hier")).toEqual([{ teks: "Geen ** hier", vet: false }]);
  });

  it("returns nothing for an empty string", () => {
    expect(vetDele("")).toEqual([]);
  });
});

describe("mdNaBlokke", () => {
  it("reads paragraphs, headings and bullet lists", () => {
    const md = [
      "Eerste sin.",
      "",
      "## Wie kan aansoek doen?",
      "",
      "Jy moet geregistreer wees.",
      "* **Huisbesoek:** As jy nie kan reis nie.",
      "* **Stemlokaalbesoek:** As jy vooraf wil stem.",
      "",
      "Slot.",
    ].join("\n");
    expect(mdNaBlokke(md)).toEqual([
      { tipe: "p", teks: "Eerste sin." },
      { tipe: "h2", teks: "Wie kan aansoek doen?" },
      { tipe: "p", teks: "Jy moet geregistreer wees." },
      {
        tipe: "ul",
        items: ["**Huisbesoek:** As jy nie kan reis nie.", "**Stemlokaalbesoek:** As jy vooraf wil stem."],
      },
      { tipe: "p", teks: "Slot." },
    ]);
  });

  it("does not mistake a bold paragraph for a bullet", () => {
    expect(mdNaBlokke("**Let wel:** dit is vet.")).toEqual([{ tipe: "p", teks: "**Let wel:** dit is vet." }]);
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npm test`
Expected: FAIL. `Cannot find module './tipes'`.

- [ ] **Step 4: Implement the types, parser and index**

`lib/verkiesing/gidse/tipes.ts`:

```ts
export type Blok =
  | { tipe: "p"; teks: string }
  | { tipe: "h2"; teks: string }
  | { tipe: "ul"; items: string[] };

/** Generated from docs/verkiesing/konsepte/<slug>.md; `lyf` is the approved Markdown body verbatim. */
export interface GidsBron {
  slug: string;
  titel: string;
  lyf: string;
  bronne: string[];
  nagegaan: string;
  gepubliseer: boolean;
}

export interface Gids extends GidsBron {
  blokke: Blok[];
  opsomming: string;
}

export function vetDele(teks: string): { teks: string; vet: boolean }[] {
  const dele: { teks: string; vet: boolean }[] = [];
  let laaste = 0;
  for (const m of teks.matchAll(/\*\*(.+?)\*\*/g)) {
    const begin = m.index ?? 0;
    if (begin > laaste) dele.push({ teks: teks.slice(laaste, begin), vet: false });
    dele.push({ teks: m[1], vet: true });
    laaste = begin + m[0].length;
  }
  if (laaste < teks.length) dele.push({ teks: teks.slice(laaste), vet: false });
  return dele;
}

/** The explainers use only paragraphs, `## ` headings and `* ` bullets; nothing else is supported. */
export function mdNaBlokke(md: string): Blok[] {
  const blokke: Blok[] = [];
  let para: string[] = [];
  let lys: string[] | null = null;
  const spoelPara = () => {
    if (para.length) blokke.push({ tipe: "p", teks: para.join(" ") });
    para = [];
  };
  const spoelLys = () => {
    if (lys) blokke.push({ tipe: "ul", items: lys });
    lys = null;
  };
  for (const rou of md.split("\n")) {
    const reël = rou.trim();
    if (reël === "") {
      spoelPara();
      spoelLys();
      continue;
    }
    if (reël.startsWith("## ")) {
      spoelPara();
      spoelLys();
      blokke.push({ tipe: "h2", teks: reël.slice(3).trim() });
      continue;
    }
    const item = reël.match(/^[*-]\s+(.*)$/);
    if (item) {
      spoelPara();
      (lys ??= []).push(item[1]);
      continue;
    }
    spoelLys();
    para.push(reël);
  }
  spoelPara();
  spoelLys();
  return blokke;
}
```

`scripts/gids-na-ts.mjs`:

```js
// Usage: node scripts/gids-na-ts.mjs <slug> [--gepubliseer]
// Regenerate after every edit to docs/verkiesing/konsepte/<slug>.md. Never hand-edit the output.
import { readFileSync, writeFileSync } from "node:fs";

const slug = process.argv[2];
const gepubliseer = process.argv.includes("--gepubliseer");
if (!slug) throw new Error("Gee 'n slug, bv. spesiale-stemme");

const rou = readFileSync(`docs/verkiesing/konsepte/${slug}.md`, "utf8");
const [artikel, bylae = ""] = rou.split("\n---\n");
const titel = artikel.match(/^# (.+)$/m)?.[1].trim();
if (!titel) throw new Error(`Geen '# titel' in ${slug}.md nie`);
const lyf = artikel.replace(/^# .+\n/, "").trim();
const feite = bylae.split(/^## /m).find((s) => s.startsWith("Feite en bronne")) ?? "";
const bronne = [
  ...new Set([...feite.matchAll(/https?:\/\/[^\s|;)]+/g)].map((m) => m[0].replace(/[.,]+$/, ""))),
];
const naam = slug.replace(/-(\w)/g, (_, c) => c.toUpperCase());
const data = { slug, titel, lyf, bronne, nagegaan: "2026-09-14", gepubliseer };

writeFileSync(
  `lib/verkiesing/gidse/${slug}.ts`,
  `// Generated from docs/verkiesing/konsepte/${slug}.md by scripts/gids-na-ts.mjs. Do not edit.\n` +
    `import type { GidsBron } from "./tipes";\n\nexport const ${naam}: GidsBron = ${JSON.stringify(data, null, 2)};\n`
);
console.log(`lib/verkiesing/gidse/${slug}.ts`, gepubliseer ? "(gepubliseer)" : "(konsep)");
```

Generate all four as drafts:

```bash
for s in wyk-en-pr-stembrief spesiale-stemme wat-om-saam-te-bring waar-stem-ek; do node scripts/gids-na-ts.mjs $s; done
```

Expected: four `lib/verkiesing/gidse/<slug>.ts` lines, each ending `(konsep)`.

`lib/verkiesing/gidse/index.ts`:

```ts
import { mdNaBlokke, type Gids, type GidsBron } from "./tipes";
import { spesialeStemme } from "./spesiale-stemme";
import { waarStemEk } from "./waar-stem-ek";
import { watOmSaamTeBring } from "./wat-om-saam-te-bring";
import { wykEnPrStembrief } from "./wyk-en-pr-stembrief";

function bou(bron: GidsBron): Gids {
  const blokke = mdNaBlokke(bron.lyf);
  const lede = blokke.find((b) => b.tipe === "p");
  return { ...bron, blokke, opsomming: lede?.tipe === "p" ? lede.teks.replace(/\*\*/g, "") : "" };
}

export const GIDSE: Gids[] = [wykEnPrStembrief, spesialeStemme, watOmSaamTeBring, waarStemEk].map(bou);

export function gepubliseerdeGidse(): Gids[] {
  return GIDSE.filter((g) => g.gepubliseer);
}

export function vindGids(slug: string): Gids | undefined {
  return gepubliseerdeGidse().find((g) => g.slug === slug);
}
```

- [ ] **Step 5: Run the tests**

Run: `npm test`
Expected: PASS (15 tests).

- [ ] **Step 6: Page and renderer**

`app/_components/verkiesing/gids-inhoud.tsx`:

```tsx
import { vetDele, type Blok } from "@/lib/verkiesing/gidse/tipes";

function Teks({ teks }: { teks: string }) {
  return (
    <>
      {vetDele(teks).map((d, i) =>
        d.vet ? (
          <strong key={i} className="text-papier font-bold">
            {d.teks}
          </strong>
        ) : (
          <span key={i}>{d.teks}</span>
        )
      )}
    </>
  );
}

export function GidsInhoud({ blokke }: { blokke: Blok[] }) {
  return (
    <div className="text-papier/90 grid gap-5 font-sans text-lg leading-relaxed">
      {blokke.map((b, i) => {
        if (b.tipe === "h2")
          return (
            <h2 key={i} className="text-papier mt-4 font-display text-2xl text-balance">
              {b.teks}
            </h2>
          );
        if (b.tipe === "ul")
          return (
            <ul key={i} className="grid list-disc gap-2 pl-6 marker:text-siaan">
              {b.items.map((it, j) => (
                <li key={j}>
                  <Teks teks={it} />
                </li>
              ))}
            </ul>
          );
        return (
          <p key={i}>
            <Teks teks={b.teks} />
          </p>
        );
      })}
    </div>
  );
}
```

`app/gids/[onderwerp]/page.tsx`:

```tsx
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { GidsInhoud } from "@/app/_components/verkiesing/gids-inhoud";
import { Kopstuk } from "@/app/_components/verkiesing/kopstuk";
import { Voet } from "@/app/_components/verkiesing/voet";
import { gepubliseerdeGidse, vindGids } from "@/lib/verkiesing/gidse";

type Props = { params: Promise<{ onderwerp: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return gepubliseerdeGidse().map((g) => ({ onderwerp: g.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const gids = vindGids((await params).onderwerp);
  if (!gids) return {};
  return {
    title: `${gids.titel} — Nuuspod`,
    description: gids.opsomming,
    openGraph: { title: gids.titel, description: gids.opsomming, url: `https://nuuspod.co.za/gids/${gids.slug}` },
  };
}

export default async function GidsBladsy({ params }: Props) {
  const gids = vindGids((await params).onderwerp);
  if (!gids) notFound();

  return (
    <>
      <Kopstuk />
      <main className="mx-auto max-w-2xl px-5 py-12 sm:px-8 sm:py-16">
        <Link href="/#gidse" className="font-sans text-xs font-bold tracking-widest text-siaan uppercase hover:text-papier">
          ← Hoe om te stem
        </Link>
        <h1 className="text-papier mt-6 font-display text-4xl leading-tight text-balance sm:text-5xl">{gids.titel}</h1>
        <div className="mt-8">
          <GidsInhoud blokke={gids.blokke} />
        </div>
        <section className="border-rand mt-12 border-t pt-6" aria-labelledby="bronne">
          <h2 id="bronne" className="text-grys font-sans text-xs font-bold tracking-[0.2em] uppercase">
            Amptelike bronne · nagegaan {gids.nagegaan}
          </h2>
          <ul className="text-grys mt-3 grid gap-2 font-sans text-sm">
            {gids.bronne.map((u) => (
              <li key={u} className="break-all">
                <a href={u} className="hover:text-siaan">
                  {new URL(u).hostname + new URL(u).pathname}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <Voet />
    </>
  );
}
```

- [ ] **Step 7: Verify draft explainers are NOT reachable**

(After Task 6 exists) `npm run build && (npx next start -p 3001 & sleep 5; curl -s -o /dev/null -w "%{http_code}\n" localhost:3001/gids/spesiale-stemme; kill %1)`
Expected: `404`, because every explainer is still a draft.

- [ ] **Step 8: Commit**

```bash
git add lib/verkiesing/gidse scripts/gids-na-ts.mjs app/_components/verkiesing/gids-inhoud.tsx "app/gids/[onderwerp]/page.tsx"
git commit -m "Verkiesing: gidse uit goedgekeurde Markdown, eers as konsepte

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 5: Revalidate endpoint, feedback action, thumbnail config

**Files:**
- Create: `app/api/herlaai/route.ts`, `app/aksies.ts`
- Modify: `next.config.ts`

**Interfaces:**
- Consumes: `voegIn` (Task 3)
- Produces:
  - `POST /api/herlaai` with header `Authorization: Bearer $HERLAAI_SECRET` and body `{ "tag": "nuusstroom" | "episodes" }` → `200 { ok: true, tag }`
  - `stuurTerugvoer(bladsy: string, gevind: boolean): Promise<boolean>`

- [ ] **Step 1: Route**

`app/api/herlaai/route.ts`:

```ts
import { revalidateTag } from "next/cache";

const TAGS = new Set(["nuusstroom", "episodes"]);

/** Called by the admin when Piet hides a headline or a new episode lands. */
export async function POST(req: Request) {
  const geheim = process.env.HERLAAI_SECRET;
  if (!geheim || req.headers.get("authorization") !== `Bearer ${geheim}`) {
    return Response.json({ fout: "Nie gemagtig nie" }, { status: 401 });
  }
  const { tag } = (await req.json().catch(() => ({}))) as { tag?: string };
  if (!tag || !TAGS.has(tag)) {
    return Response.json({ fout: "Onbekende tag" }, { status: 400 });
  }
  // expire: 0 so a hidden headline is gone on the next request, not after a stale window.
  revalidateTag(tag, { expire: 0 });
  return Response.json({ ok: true, tag });
}
```

Check the second argument against `node_modules/next/dist/docs/01-app/03-api-reference/04-functions/revalidateTag.md` before relying on `{ expire: 0 }`. If that page says the profile object is not accepted in route handlers, use `revalidateTag(tag, "max")` and accept up to one stale request.

- [ ] **Step 2: Server action**

`app/aksies.ts`:

```ts
"use server";

import { voegIn } from "@/lib/supabase-rest";

/** Anonymous yes/no only: the page path and the answer, nothing that identifies the reader. */
export async function stuurTerugvoer(bladsy: string, gevind: boolean): Promise<boolean> {
  if (typeof bladsy !== "string" || !bladsy.startsWith("/") || bladsy.length > 200) return false;
  if (typeof gevind !== "boolean") return false;
  return voegIn("terugvoer", { bladsy, gevind });
}
```

- [ ] **Step 3: Thumbnails**

`next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "i.ytimg.com", pathname: "/vi/**" }],
  },
};

export default nextConfig;
```

- [ ] **Step 4: Verify the route rejects and accepts correctly**

```bash
set -a; source .env.local; set +a
npm run build && (npx next start -p 3001 & sleep 5
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3001/api/herlaai -d '{"tag":"nuusstroom"}'
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:3001/api/herlaai -H "Authorization: Bearer $HERLAAI_SECRET" -d '{"tag":"iets"}'
curl -s -X POST localhost:3001/api/herlaai -H "Authorization: Bearer $HERLAAI_SECRET" -d '{"tag":"nuusstroom"}'; echo
kill %1)
```

Expected: `401`, `400`, `{"ok":true,"tag":"nuusstroom"}`.

- [ ] **Step 5: Commit**

```bash
git add app/api/herlaai/route.ts app/aksies.ts next.config.ts
git commit -m "Verkiesing: herlaai-eindpunt, terugvoer-aksie en YouTube-duimnaels

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 6: Election home page and shared chrome

**Files:**
- Create in `app/_components/verkiesing/`: `kopstuk.tsx`, `aftelling.tsx`, `wat-kom.tsx`, `kontroleer-registrasie.tsx`, `verkiesingsprogram.tsx`, `nuusstroom.tsx`, `gids-kaarte.tsx`, `terugvoer.tsx`, `voet.tsx`
- Replace: `app/page.tsx`

**Interfaces:**
- Consumes:
  - `STEMDAG`, `komendeMylpale`, `aftelling`, `tydEtiket`, `StroomItem`, `haalStroom`, `haalEpisodes`, `Episode`, `KOMMISSIE` (Task 3)
  - `gepubliseerdeGidse` (Task 4)
  - `stuurTerugvoer` (Task 5)
- Produces: `Kopstuk()`, `Voet()` (used by Task 4's page)

- [ ] **Step 1: Chrome**

`kopstuk.tsx`:

```tsx
import Image from "next/image";
import Link from "next/link";

const SKAKELS = [
  { href: "/#gidse", teks: "Hoe om te stem" },
  { href: "/#program", teks: "Verkiesings-Vrydag" },
  { href: "/#wat-ander-berig", teks: "Wat ander berig" },
];

export function Kopstuk() {
  return (
    <header className="border-rand bg-swart/95 sticky top-0 z-20 border-b backdrop-blur">
      <div className="h-[3px] bg-linear-to-r from-siaan to-rooi" aria-hidden />
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3 sm:px-8">
        <Link href="/" className="flex flex-1 items-center gap-3">
          <Image src="/logo.jpg" alt="" width={40} height={40} className="rounded-full" />
          <span className="leading-none">
            <span className="text-papier block font-display text-xl tracking-[0.14em]">NUUSPOD</span>
            <span className="mt-1 block font-sans text-[0.7rem] font-bold tracking-[0.18em] text-siaan uppercase">
              Verkiesing 2026
            </span>
          </span>
        </Link>
        <nav aria-label="Afdelings" className="hidden gap-6 font-sans text-xs font-bold tracking-widest uppercase md:flex">
          {SKAKELS.map((s) => (
            <a key={s.href} href={s.href} className="text-grys hover:text-papier focus-visible:outline-2 focus-visible:outline-siaan">
              {s.teks}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
```

`terugvoer.tsx`:

```tsx
"use client";

import { usePathname } from "next/navigation";
import { useState, useTransition } from "react";
import { stuurTerugvoer } from "@/app/aksies";

const KNOPPIE =
  "border-rand text-papier rounded border px-4 py-2 font-sans text-xs font-bold tracking-widest uppercase hover:border-siaan focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan disabled:opacity-50";

export function Terugvoer() {
  const pad = usePathname();
  const [gestuur, setGestuur] = useState(false);
  const [besig, begin] = useTransition();

  if (gestuur) {
    return (
      <p role="status" className="text-grys font-sans text-sm">
        Dankie, dit help ons om die bladsy beter te maak.
      </p>
    );
  }

  const stuur = (gevind: boolean) =>
    begin(async () => {
      await stuurTerugvoer(pad, gevind);
      setGestuur(true);
    });

  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-papier font-sans text-sm">Het jy gekry wat jy soek?</p>
      <button type="button" disabled={besig} onClick={() => stuur(true)} className={KNOPPIE}>
        Ja
      </button>
      <button type="button" disabled={besig} onClick={() => stuur(false)} className={KNOPPIE}>
        Nee
      </button>
    </div>
  );
}
```

`voet.tsx`:

```tsx
import Link from "next/link";
import { Terugvoer } from "./terugvoer";

export function Voet() {
  return (
    <footer className="border-rand mt-16 border-t">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:px-8">
        <Terugvoer />
        <div className="text-grys grid gap-2 font-sans text-sm">
          <p>Bron van verkiesingsinligting: die OVK (IEC).</p>
          <p>Nuuspod is nie aan die OVK of enige party verbonde nie.</p>
          <p>
            Sien jy vals verkiesingsinligting?{" "}
            <a href="https://www.real411.org" className="text-siaan hover:text-papier">
              Rapporteer dit by Real411 ↗
            </a>
          </p>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 font-sans text-xs font-bold tracking-widest uppercase">
          <a href="https://www.youtube.com/@Nuuspod" className="text-grys hover:text-siaan">YouTube</a>
          <a href="https://www.facebook.com/izak.duplessis.752" className="text-grys hover:text-siaan">Facebook</a>
          <a href="https://x.com/zakjourno" className="text-grys hover:text-siaan">X</a>
          <Link href="/adverteer" className="text-grys hover:text-siaan">Adverteer by Nuuspod</Link>
        </div>
      </div>
    </footer>
  );
}
```

Before shipping, check that `https://www.real411.org` resolves to the Real411 complaints site: `curl -sI https://www.real411.org | head -3`.

- [ ] **Step 2: Countdown (the one animated element)**

`aftelling.tsx`:

```tsx
"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { aftelling } from "@/lib/verkiesing/datums";

/** Server passes its own clock so the first client render matches the HTML exactly. */
export function Aftelling({ teikenIso, nouMs }: { teikenIso: string; nouMs: number }) {
  const [nou, setNou] = useState(nouMs);
  const min = useReducedMotion();

  useEffect(() => {
    setNou(Date.now());
    const t = setInterval(() => setNou(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);

  const a = aftelling(new Date(nou), new Date(teikenIso));
  if (a.verby) {
    return <p className="text-papier font-display text-4xl">Stemdag is Woensdag 4 November.</p>;
  }

  const dele = [
    { waarde: a.dae, etiket: a.dae === 1 ? "dag" : "dae" },
    { waarde: a.ure, etiket: "uur" },
    { waarde: a.minute, etiket: a.minute === 1 ? "minuut" : "minute" },
  ];

  return (
    <div role="timer" aria-label={`Nog ${a.dae} dae, ${a.ure} uur en ${a.minute} minute tot stemdag`} className="flex gap-6 sm:gap-10">
      {dele.map((d, i) => (
        <div key={i} className="flex flex-col" aria-hidden>
          <span className="text-papier relative block overflow-hidden font-display text-5xl leading-none tabular-nums sm:text-7xl">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={d.waarde}
                className="block"
                initial={min ? false : { y: "55%", opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={min ? { opacity: 0 } : { y: "-55%", opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              >
                {d.waarde}
              </motion.span>
            </AnimatePresence>
          </span>
          <span className="text-grys mt-2 font-sans text-xs font-bold tracking-[0.2em] uppercase">{d.etiket}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Content blocks**

`wat-kom.tsx`:

```tsx
import { komendeMylpale } from "@/lib/verkiesing/datums";

export function WatKom({ nou }: { nou: Date }) {
  const items = komendeMylpale(nou);
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="wat-kom">
      <h2 id="wat-kom" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Wat kom
      </h2>
      <ol className="border-rand divide-rand mt-4 divide-y border-y">
        {items.map((m) => (
          <li key={m.id} className="grid gap-1 py-4 sm:grid-cols-[15rem_1fr] sm:gap-6">
            <span className="text-papier font-sans text-sm font-bold">{m.wanneer}</span>
            <span className="text-grys font-sans">{m.wat}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
```

`kontroleer-registrasie.tsx` (links out to the commission and promises nothing of ours):

```tsx
import { KOMMISSIE } from "@/lib/verkiesing/terme";

export function KontroleerRegistrasie() {
  return (
    <div className="border-rand bg-paneel border p-5 sm:p-6">
      <p className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">Waar stem jy?</p>
      <p className="text-papier mt-2 font-display text-2xl text-balance">
        Kontroleer jou registrasie, stemlokaal en wyk met jou ID-nommer.
      </p>
      <a
        href="https://www.elections.org.za/pw/Voter/Voter-Information"
        className="mt-4 inline-block font-sans text-sm font-bold tracking-widest text-siaan uppercase hover:text-papier"
      >
        Kyk by die {KOMMISSIE} ↗
      </a>
    </div>
  );
}
```

`verkiesingsprogram.tsx`:

```tsx
import Image from "next/image";
import type { Episode } from "@/lib/verkiesing/lees";

export function Verkiesingsprogram({ episodes }: { episodes: Episode[] }) {
  const [nuutste, ...vorige] = episodes;
  return (
    <section id="program" aria-labelledby="program-kop" className="scroll-mt-24">
      <h2 id="program-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Verkiesings-Vrydag
      </h2>
      <p className="text-papier mt-2 font-display text-3xl">Elke Vrydag regstreeks.</p>
      <div className="border-rand bg-paneel mt-6 overflow-hidden border">
        <div className="relative aspect-video">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${nuutste.video_id}`}
            title={nuutste.titel}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 h-full w-full"
          />
        </div>
        <p className="text-papier px-5 py-4 font-sans text-sm">{nuutste.titel}</p>
      </div>
      {vorige.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          {vorige.map((e) => (
            <li key={e.video_id}>
              <a href={`https://www.youtube.com/watch?v=${e.video_id}`} target="_blank" rel="noopener noreferrer" className="group block">
                <Image src={`https://i.ytimg.com/vi/${e.video_id}/mqdefault.jpg`} alt="" width={320} height={180} className="border-rand w-full border" />
                <span className="text-grys group-hover:text-papier mt-2 block font-sans text-sm">{e.titel}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
```

`nuusstroom.tsx`:

```tsx
import { tydEtiket, type StroomItem } from "@/lib/verkiesing/stroom";

const TIPE: Record<string, string> = {
  nasionaal: "Nasionaal",
  streek: "Streek",
  gemeenskap: "Gemeenskap",
  "openbare uitsaaier": "Openbare uitsaaier",
};

/** Headlines render exactly as stored: never clamp, truncate or restyle their case. */
export function Nuusstroom({ items, nou }: { items: StroomItem[]; nou: Date }) {
  return (
    <section id="wat-ander-berig" aria-labelledby="stroom-kop" className="scroll-mt-24">
      <h2 id="stroom-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Wat ander berig
      </h2>
      <p className="text-grys mt-1 font-sans text-xs">Opskrifte soos gepubliseer, met skakels na die oorspronklike berigte.</p>
      {items.length === 0 ? (
        <p className="text-grys mt-4 font-sans text-sm">Nog geen berigte nie.</p>
      ) : (
        <ol className="border-rand divide-rand mt-4 divide-y border-y">
          {items.map((i) => (
            <li key={i.id}>
              <a href={i.url} target="_blank" rel="noopener noreferrer" className="group block py-3 focus-visible:outline-2 focus-visible:outline-siaan">
                <span className="text-grys flex flex-wrap items-baseline gap-x-2 font-sans text-xs tabular-nums">
                  <span>{tydEtiket(i.gepubliseer_om, nou)}</span>
                  <span aria-hidden>·</span>
                  <span className="text-papier font-bold">{i.bron}</span>
                  <span>{TIPE[i.bron_tipe] ?? i.bron_tipe}</span>
                </span>
                <span className="text-papier group-hover:text-siaan mt-1 block font-sans text-[0.95rem] leading-snug break-words">
                  {i.titel}
                  <span aria-hidden className="text-grys"> ↗</span>
                </span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
```

`gids-kaarte.tsx`:

```tsx
import Link from "next/link";
import { gepubliseerdeGidse } from "@/lib/verkiesing/gidse";

export function GidsKaarte() {
  const gidse = gepubliseerdeGidse();
  if (gidse.length === 0) return null;
  return (
    <section id="gidse" aria-labelledby="gidse-kop" className="scroll-mt-24">
      <h2 id="gidse-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Hoe om te stem
      </h2>
      <ul className="border-rand bg-rand mt-4 grid gap-px border sm:grid-cols-2">
        {gidse.map((g) => (
          <li key={g.slug} className="bg-swart">
            <Link href={`/gids/${g.slug}`} className="group block h-full p-5 focus-visible:outline-2 focus-visible:outline-siaan">
              <span className="text-papier group-hover:text-siaan block font-display text-xl text-balance">{g.titel}</span>
              <span className="text-grys mt-2 block font-sans text-sm">{g.opsomming}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Home page**

`app/page.tsx`:

```tsx
import { Aftelling } from "./_components/verkiesing/aftelling";
import { GidsKaarte } from "./_components/verkiesing/gids-kaarte";
import { Kopstuk } from "./_components/verkiesing/kopstuk";
import { KontroleerRegistrasie } from "./_components/verkiesing/kontroleer-registrasie";
import { Nuusstroom } from "./_components/verkiesing/nuusstroom";
import { Verkiesingsprogram } from "./_components/verkiesing/verkiesingsprogram";
import { Voet } from "./_components/verkiesing/voet";
import { WatKom } from "./_components/verkiesing/wat-kom";
import { STEMDAG } from "@/lib/verkiesing/datums";
import { haalEpisodes, haalStroom } from "@/lib/verkiesing/lees";

export default async function Tuis() {
  const nou = new Date();
  const [stroom, episodes] = await Promise.all([haalStroom(), haalEpisodes()]);

  return (
    <>
      <Kopstuk />
      <main>
        <section className="border-rand border-b">
          <div className="mx-auto grid max-w-6xl gap-10 px-5 py-12 sm:px-8 sm:py-16 md:grid-cols-[1.4fr_1fr] md:items-end">
            <div>
              <p className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
                Plaaslike verkiesing · Woensdag 4 November 2026
              </p>
              <h1 className="text-papier mt-4 font-display text-4xl leading-[1.05] text-balance sm:text-6xl">
                Jou raad. Jou wyk. Jou stem.
              </h1>
              <div className="mt-8">
                <Aftelling teikenIso={STEMDAG.toISOString()} nouMs={nou.getTime()} />
              </div>
            </div>
            <KontroleerRegistrasie />
          </div>
        </section>

        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_22rem]">
          <div className="grid content-start gap-14">
            <WatKom nou={nou} />
            <Verkiesingsprogram episodes={episodes} />
            <GidsKaarte />
          </div>
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <Nuusstroom items={stroom} nou={nou} />
          </aside>
        </div>
      </main>
      <Voet />
    </>
  );
}
```

The hero line "Jou raad. Jou wyk. Jou stem." and every label are draft copy for Piet to approve at Task 12.

- [ ] **Step 5: Lint, build and run locally**

```bash
npm run lint && npm test && npm run build && npx next start -p 3001
```

Expected: lint clean, tests pass, build succeeds.
- `localhost:3001` shows the countdown, "Wat kom", the Y9HiKkP7Rmo episode (fallback) and "Nog geen berigte nie."
- No explainer cards appear, since all are drafts.

Stop the server.

- [ ] **Step 6: Commit**

```bash
git add app/page.tsx app/_components/verkiesing/
git commit -m "Verkiesing: tuisblad met aftelling, wat kom, Verkiesings-Vrydag en nuusstroom

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 7: Admin pure logic (sources, filter, titles, episodes)

**Files (all under `~/nuuspod`):**
- Create: `src/lib/verkiesing/bronne.ts`
- Create: `src/lib/verkiesing/filter.ts`, `filter.test.ts`
- Create: `src/lib/verkiesing/titel.ts`, `titel.test.ts`
- Create: `src/lib/verkiesing/episodes.ts`, `episodes.test.ts`
- Create: `src/lib/verkiesing/stroom.ts` (pure part), `stroom.test.ts`

**Interfaces:**
- Produces:
  - `type BronTipe = "nasionaal" | "streek" | "gemeenskap" | "openbare uitsaaier"`
  - `interface StroomBron { naam: string; feedUrl: string; tipe: BronTipe; aktief: boolean }`
  - `STROOM_BRONNE: StroomBron[]`
  - `isVerkiesingStorie(teks: string): boolean`
  - `dekodeerTitel(rou: string): string`
  - `interface StroomRy { titel: string; bron: string; bron_tipe: BronTipe; url: string; gepubliseer_om: string }`
  - `interface StroomItemIn { title?: string; link?: string; pubDate?: string; isoDate?: string; contentSnippet?: string; categories?: unknown[] }`
  - `naStroomRy(item: StroomItemIn, bron: StroomBron, nou: Date): StroomRy | null`
  - `NUUSPOD_KANAAL_ID`
  - `isVerkiesingsVrydag(titel: string): boolean`
  - `datumUitTitel(titel: string): string | null`
  - `sastDatum(iso: string): string`
  - `interface EpisodeRy { video_id: string; titel: string; uitsaaidatum: string; gepubliseer_om: string }`
  - `uitFeedXml(xml: string): EpisodeRy[]`

- [ ] **Step 1: Verify the feeds before listing them**

```bash
for u in https://www.dailymaverick.co.za/rss/ https://mg.co.za/feed/ https://www.sabcnews.com/sabcnews/feed/ https://www.citizen.co.za/feed/ https://www.thesouthafrican.com/feed/ https://www.politicsweb.co.za/rss.xml https://www.citizen.co.za/lowvelder/feed/ https://www.citizen.co.za/rekord/feed/ https://maroelamedia.co.za/feed/; do
  printf "%s " "$u"; curl -sL -A "Mozilla/5.0" --max-time 20 "$u" | grep -c "<item" ; done
```

Expected: a count above 0 per feed. Set `aktief: false` for any feed that returns 0 and note it in the commit message.

- [ ] **Step 2: Write `bronne.ts`**

```ts
export type BronTipe = "nasionaal" | "streek" | "gemeenskap" | "openbare uitsaaier";

export interface StroomBron {
  naam: string;
  feedUrl: string;
  tipe: BronTipe;
  /** Only outlets Piet has cleared appear on the rail (spec §8.1). */
  aktief: boolean;
}

// Allowlist for "Wat ander berig": Press Council members and BCCSA broadcasters only.
// Media24 and Maroela Media stay inactive until Piet has spoken to them.
export const STROOM_BRONNE: StroomBron[] = [
  { naam: "Daily Maverick", feedUrl: "https://www.dailymaverick.co.za/rss/", tipe: "nasionaal", aktief: true },
  { naam: "Mail & Guardian", feedUrl: "https://mg.co.za/feed/", tipe: "nasionaal", aktief: true },
  { naam: "SABC News", feedUrl: "https://www.sabcnews.com/sabcnews/feed/", tipe: "openbare uitsaaier", aktief: true },
  { naam: "The Citizen", feedUrl: "https://www.citizen.co.za/feed/", tipe: "nasionaal", aktief: true },
  { naam: "The South African", feedUrl: "https://www.thesouthafrican.com/feed/", tipe: "nasionaal", aktief: true },
  { naam: "Politicsweb", feedUrl: "https://www.politicsweb.co.za/rss.xml", tipe: "nasionaal", aktief: true },
  { naam: "Lowvelder", feedUrl: "https://www.citizen.co.za/lowvelder/feed/", tipe: "gemeenskap", aktief: true },
  { naam: "Rekord", feedUrl: "https://www.citizen.co.za/rekord/feed/", tipe: "gemeenskap", aktief: true },
  { naam: "Maroela Media", feedUrl: "https://maroelamedia.co.za/feed/", tipe: "nasionaal", aktief: false },
];
```

**Before Task 11, Piet must confirm the `aktief: true` set.** Press Council membership of The South African and Politicsweb is unverified; flag both when asking.

- [ ] **Step 3: Write the failing tests**

`src/lib/verkiesing/filter.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { isVerkiesingStorie } from "./filter";

describe("isVerkiesingStorie", () => {
  it.each([
    "IEC confirms 546 parties will contest the local government elections",
    "Spesiale stemme: só doen jy aansoek",
    "By-election results: ward 12 changes hands",
    "Coalition talks stall in Tshwane council",
    "Munisipale verkiesing: kandidaatlyste vrygestel",
    "What voters in Gqeberha want from their ward councillor",
    "Tussenverkiesing in Stellenbosch",
  ])("accepts %s", (titel) => {
    expect(isVerkiesingStorie(titel)).toBe(true);
  });

  it.each([
    "Springboks beat All Blacks in Wellington",
    "Cape Town water tariffs rise in July",
    "Load shedding suspended for the weekend",
  ])("rejects %s", (titel) => {
    expect(isVerkiesingStorie(titel)).toBe(false);
  });
});
```

`src/lib/verkiesing/titel.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { dekodeerTitel } from "./titel";

describe("dekodeerTitel", () => {
  it("decodes numeric and named entities once", () => {
    expect(dekodeerTitel("Ramaphosa&#8217;s plan")).toBe("Ramaphosa’s plan");
    expect(dekodeerTitel("M&amp;G: &quot;Vote&quot;")).toBe('M&G: "Vote"');
    expect(dekodeerTitel("A &#x2014; B")).toBe("A — B");
  });

  it("only trims the ends and keeps everything else exactly", () => {
    expect(dekodeerTitel("  IEC says ALL votes count…  ")).toBe("IEC says ALL votes count…");
  });

  it("leaves unknown entities untouched", () => {
    expect(dekodeerTitel("Tom &unknown; Jerry")).toBe("Tom &unknown; Jerry");
  });
});
```

`src/lib/verkiesing/stroom.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import type { StroomBron } from "./bronne";
import { naStroomRy } from "./stroom";

const bron: StroomBron = { naam: "SABC News", feedUrl: "https://x", tipe: "openbare uitsaaier", aktief: true };
const nou = new Date("2026-09-15T08:00:00Z");

describe("naStroomRy", () => {
  it("keeps the title verbatim (decoded) and drops the body", () => {
    const ry = naStroomRy(
      {
        title: "IEC&#8217;s final candidate list is out",
        link: "https://www.sabcnews.com/a ",
        isoDate: "2026-09-15T06:00:00.000Z",
        contentSnippet: "Long body text that must never be stored",
      },
      bron,
      nou
    );
    expect(ry).toEqual({
      titel: "IEC’s final candidate list is out",
      bron: "SABC News",
      bron_tipe: "openbare uitsaaier",
      url: "https://www.sabcnews.com/a",
      gepubliseer_om: "2026-09-15T06:00:00.000Z",
    });
  });

  it("matches on categories and the start of the description, not only the title", () => {
    const ry = naStroomRy(
      { title: "What Soweto wants", link: "https://x/b", isoDate: "2026-09-15T06:00:00Z", categories: ["Elections 2026"] },
      bron,
      nou
    );
    expect(ry?.titel).toBe("What Soweto wants");
  });

  it("ignores an election word deep in a full-text body", () => {
    const lyf = "a ".repeat(400) + "election";
    expect(naStroomRy({ title: "Weather", link: "https://x/c", isoDate: "2026-09-15T06:00:00Z", contentSnippet: lyf }, bron, nou)).toBeNull();
  });

  it("skips items older than 7 days, and items without title or link", () => {
    expect(naStroomRy({ title: "IEC update", link: "https://x/d", isoDate: "2026-09-07T00:00:00Z" }, bron, nou)).toBeNull();
    expect(naStroomRy({ title: "IEC update", isoDate: "2026-09-15T06:00:00Z" }, bron, nou)).toBeNull();
  });

  it("falls back to now for an unparseable date", () => {
    const ry = naStroomRy({ title: "IEC update", link: "https://x/e", pubDate: "not a date" }, bron, nou);
    expect(ry?.gepubliseer_om).toBe(nou.toISOString());
  });
});
```

`src/lib/verkiesing/episodes.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { datumUitTitel, isVerkiesingsVrydag, sastDatum, uitFeedXml } from "./episodes";

const FEED = `<?xml version="1.0"?>
<feed><title>NUUSPOD</title>
<entry><yt:videoId>Y9HiKkP7Rmo</yt:videoId><title>Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag 11 September 2026</title>
<published>2026-09-10T07:02:50+00:00</published><media:group><media:title>Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag 11 September 2026</media:title></media:group></entry>
<entry><yt:videoId>abcdefghijk</yt:videoId><title>Nuusbulletin Vrydag 11 September 2026</title>
<published>2026-09-11T06:24:10+00:00</published><media:group><media:title>Nuusbulletin Vrydag 11 September 2026</media:title></media:group></entry>
</feed>`;

describe("episodes", () => {
  it("recognises the title prefix only at the start", () => {
    expect(isVerkiesingsVrydag("Verkiesings-Vrydag: Iets")).toBe(true);
    expect(isVerkiesingsVrydag("Nuusbulletin oor Verkiesings-Vrydag")).toBe(false);
  });

  it("reads the air date from the Afrikaans date in the title", () => {
    expect(datumUitTitel("Verkiesings-Vrydag: X Vrydag 11 September 2026")).toBe("2026-09-11");
    expect(datumUitTitel("Verkiesings-Vrydag: X Vrydag 2 Oktober 2026")).toBe("2026-10-02");
    expect(datumUitTitel("Verkiesings-Vrydag sonder datum")).toBeNull();
  });

  it("converts an instant to its SAST calendar date", () => {
    expect(sastDatum("2026-09-10T23:30:00Z")).toBe("2026-09-11");
  });

  it("keeps only election episodes from the channel feed, dated by title not by <published>", () => {
    expect(uitFeedXml(FEED)).toEqual([
      {
        video_id: "Y9HiKkP7Rmo",
        titel: "Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag 11 September 2026",
        uitsaaidatum: "2026-09-11",
        gepubliseer_om: "2026-09-10T07:02:50.000Z",
      },
    ]);
  });
});
```

- [ ] **Step 4: Run to verify failure**

Run: `npx vitest run src/lib/verkiesing`
Expected: FAIL. The modules are not found.

- [ ] **Step 5: Implement**

`src/lib/verkiesing/filter.ts`:

```ts
// Keyword filter for the headline rail. No model: a regex can't rewrite or misread a headline.
// Municipality names alone are deliberately absent, since they would match every Cape Town story.
const PATRONE: RegExp[] = [
  /\bverkiesing/i,
  /\btussenverkiesing/i,
  /\belection/i,
  /\bby-?election/i,
  /\bIEC\b/,
  /\bVKK\b/,
  /\bOVK\b/,
  /\bstembus/i,
  /\bkiesers?\b/i,
  /\bvoters?\b/i,
  /\bward councillors?\b/i,
  /\bwyksraadsl/i,
  /\bspecial votes?\b/i,
  /\bspesiale stem/i,
  /\bcoalitions?\b/i,
  /\bkoalisie/i,
  /\bcandidate lists?\b/i,
  /\bkandidaatlys/i,
];

export function isVerkiesingStorie(teks: string): boolean {
  return PATRONE.some((p) => p.test(teks));
}
```

`src/lib/verkiesing/titel.ts`:

```ts
const BENOEMD: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

/**
 * The only transformation a rail headline may undergo: one pass of entity decoding (WordPress
 * feeds double-escape curly quotes) and trimming the ends. Case, punctuation and wording stay.
 */
export function dekodeerTitel(rou: string): string {
  return rou
    .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (heel, kern: string) => {
      if (kern.startsWith("#")) {
        const n = kern[1].toLowerCase() === "x" ? parseInt(kern.slice(2), 16) : parseInt(kern.slice(1), 10);
        return Number.isFinite(n) ? String.fromCodePoint(n) : heel;
      }
      return BENOEMD[kern.toLowerCase()] ?? heel;
    })
    .trim();
}
```

`src/lib/verkiesing/stroom.ts` (pure part; Task 8 appends `neemStroomIn`):

```ts
import type { BronTipe, StroomBron } from "./bronne";
import { isVerkiesingStorie } from "./filter";
import { dekodeerTitel } from "./titel";

export interface StroomRy {
  titel: string;
  bron: string;
  bron_tipe: BronTipe;
  url: string;
  gepubliseer_om: string;
}

export interface StroomItemIn {
  title?: string;
  link?: string;
  pubDate?: string;
  isoDate?: string;
  contentSnippet?: string;
  categories?: unknown[];
}

const MAKS_OUDERDOM_MS = 7 * 24 * 60 * 60 * 1000;

export function naStroomRy(item: StroomItemIn, bron: StroomBron, nou: Date): StroomRy | null {
  if (!item.title || !item.link) return null;

  const kategorieë = (item.categories ?? []).filter((k): k is string => typeof k === "string").join(" ");
  // Citizen and SABC feeds carry full articles; only the opening decides relevance.
  const soek = `${item.title} ${kategorieë} ${(item.contentSnippet ?? "").slice(0, 300)}`;
  if (!isVerkiesingStorie(soek)) return null;

  const datum = new Date(item.isoDate ?? item.pubDate ?? nou.toISOString());
  const gepubliseer = Number.isNaN(datum.getTime()) ? nou : datum;
  if (nou.getTime() - gepubliseer.getTime() > MAKS_OUDERDOM_MS) return null;

  return {
    titel: dekodeerTitel(item.title),
    bron: bron.naam,
    bron_tipe: bron.tipe,
    url: item.link.trim(),
    gepubliseer_om: gepubliseer.toISOString(),
  };
}
```

`src/lib/verkiesing/episodes.ts` (pure part; Task 8 appends `neemEpisodesIn`):

```ts
import { dekodeerTitel } from "./titel";

export const NUUSPOD_KANAAL_ID = "UC8WVZnhOnCUwSpJaMIhdQcg";
export const EPISODE_VOORVOEGSEL = "Verkiesings-Vrydag";

const MAANDE = ["januarie", "februarie", "maart", "april", "mei", "junie", "julie", "augustus", "september", "oktober", "november", "desember"];

export interface EpisodeRy {
  video_id: string;
  titel: string;
  uitsaaidatum: string;
  gepubliseer_om: string;
}

export function isVerkiesingsVrydag(titel: string): boolean {
  return titel.trim().startsWith(EPISODE_VOORVOEGSEL);
}

/** Nuuspod titles end in the air date ("… Vrydag 11 September 2026"). */
export function datumUitTitel(titel: string): string | null {
  const m = titel.match(new RegExp(`(\\d{1,2})\\s+(${MAANDE.join("|")})\\s+(\\d{4})\\s*$`, "i"));
  if (!m) return null;
  const maand = MAANDE.indexOf(m[2].toLowerCase()) + 1;
  return `${m[3]}-${String(maand).padStart(2, "0")}-${m[1].padStart(2, "0")}`;
}

export function sastDatum(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Johannesburg",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

/**
 * <published> is when a livestream was SCHEDULED (Monday's show carries Friday's date), so the
 * air date comes from the title and <published> is only the fallback.
 */
export function uitFeedXml(xml: string): EpisodeRy[] {
  const rye: EpisodeRy[] = [];
  for (const [, inskrywing] of xml.matchAll(/<entry>([\s\S]*?)<\/entry>/g)) {
    const id = inskrywing.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1];
    const rou = inskrywing.match(/<media:title>([^<]*)<\/media:title>/)?.[1] ?? inskrywing.match(/<title>([^<]*)<\/title>/)?.[1];
    const gepubliseer = inskrywing.match(/<published>([^<]+)<\/published>/)?.[1];
    if (!id || !rou || !gepubliseer) continue;
    const titel = dekodeerTitel(rou);
    if (!isVerkiesingsVrydag(titel)) continue;
    rye.push({
      video_id: id,
      titel,
      uitsaaidatum: datumUitTitel(titel) ?? sastDatum(gepubliseer),
      gepubliseer_om: new Date(gepubliseer).toISOString(),
    });
  }
  return rye;
}
```

- [ ] **Step 6: Run the tests**

Run: `npx vitest run src/lib/verkiesing`
Expected: PASS, all tests. If "What voters in Gqeberha want from their ward councillor" fails, `/\bvoters?\b/i` or `/\bward councillors?\b/i` is missing.

- [ ] **Step 7: Commit (explicit paths only)**

```bash
cd ~/nuuspod
git add src/lib/verkiesing/bronne.ts src/lib/verkiesing/filter.ts src/lib/verkiesing/filter.test.ts src/lib/verkiesing/titel.ts src/lib/verkiesing/titel.test.ts src/lib/verkiesing/stroom.ts src/lib/verkiesing/stroom.test.ts src/lib/verkiesing/episodes.ts src/lib/verkiesing/episodes.test.ts
git commit -m "Verkiesing: bronne, sleutelwoordfilter, opskrifte woordeliks en episode-herkenning

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 8: Admin ingestion and crons

**Files (under `~/nuuspod`):**
- Create: `src/lib/verkiesing/db.ts`, `src/lib/verkiesing/werf.ts`
- Modify: `src/lib/verkiesing/stroom.ts` (append), `src/lib/verkiesing/episodes.ts` (append)
- Create: `src/app/api/cron/verkiesing-stroom/route.ts`, `src/app/api/cron/verkiesing-episodes/route.ts`
- Modify: `vercel.json`

**Interfaces:**
- Consumes: Task 7 exports. Env from Task 1.
- Produces:
  - `rest(pad: string, init?: RequestInit & { prefer?: string }): Promise<Response>`
  - `herlaaiWerf(tag: "nuusstroom" | "episodes"): Promise<void>`
  - `interface GestoordeStroomRy { id: number; titel: string; bron: string; url: string }`
  - `neemStroomIn(nou?: Date): Promise<{ nuut: GestoordeStroomRy[]; mislukteBronne: string[] }>`
  - `neemEpisodesIn(): Promise<{ gevind: number }>`

- [ ] **Step 1: DB and site helpers**

`src/lib/verkiesing/db.ts`:

```ts
/** PostgREST on the verkiesing-2026 project with the SECRET key. Server-only; never import from client code. */
export async function rest(pad: string, init: RequestInit & { prefer?: string } = {}): Promise<Response> {
  const url = process.env.VERKIESING_SUPABASE_URL;
  const sleutel = process.env.VERKIESING_SUPABASE_SECRET_KEY;
  if (!url || !sleutel) throw new Error("VERKIESING_SUPABASE_URL of VERKIESING_SUPABASE_SECRET_KEY ontbreek");

  const { prefer, headers, ...res } = init;
  const antwoord = await fetch(`${url}/rest/v1/${pad}`, {
    ...res,
    cache: "no-store",
    headers: {
      apikey: sleutel,
      "Content-Type": "application/json",
      ...(prefer ? { Prefer: prefer } : {}),
      ...headers,
    },
  });
  if (!antwoord.ok) {
    throw new Error(`Supabase ${init.method ?? "GET"} ${pad}: ${antwoord.status} ${await antwoord.text()}`);
  }
  return antwoord;
}
```

`src/lib/verkiesing/werf.ts`:

```ts
/** Expires nuuspod.co.za's cached rail or episodes. Failure is logged, never thrown: the site self-refreshes. */
export async function herlaaiWerf(tag: "nuusstroom" | "episodes"): Promise<void> {
  const basis = process.env.NUUSPOD_WEB_URL;
  const geheim = process.env.NUUSPOD_WEB_HERLAAI_SECRET;
  if (!basis || !geheim) {
    console.warn("[verkiesing] NUUSPOD_WEB_URL of NUUSPOD_WEB_HERLAAI_SECRET ontbreek; werf herlaai op sy eie skedule");
    return;
  }
  try {
    const res = await fetch(`${basis}/api/herlaai`, {
      method: "POST",
      headers: { Authorization: `Bearer ${geheim}`, "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    });
    if (!res.ok) console.error(`[verkiesing] herlaai ${tag}: ${res.status}`);
  } catch (err) {
    console.error(`[verkiesing] herlaai ${tag}:`, err);
  }
}
```

- [ ] **Step 2: Append ingestion**

Append to `src/lib/verkiesing/stroom.ts`:

```ts
import Parser from "rss-parser";
import { STROOM_BRONNE } from "./bronne";
import { rest } from "./db";

export interface GestoordeStroomRy {
  id: number;
  titel: string;
  bron: string;
  url: string;
}

export async function neemStroomIn(nou = new Date()): Promise<{ nuut: GestoordeStroomRy[]; mislukteBronne: string[] }> {
  const parser = new Parser({ timeout: 15_000 });
  const aktief = STROOM_BRONNE.filter((b) => b.aktief);
  const uitslae = await Promise.allSettled(
    aktief.map(async (bron) => {
      const feed = await parser.parseURL(bron.feedUrl);
      return (feed.items ?? []).slice(0, 40).map((i) => naStroomRy(i, bron, nou));
    })
  );

  const perUrl = new Map<string, StroomRy>();
  const mislukteBronne: string[] = [];
  uitslae.forEach((u, i) => {
    if (u.status === "rejected") {
      mislukteBronne.push(aktief[i].naam);
      console.error(`[verkiesing-stroom] ${aktief[i].naam}:`, u.reason);
      return;
    }
    for (const ry of u.value) if (ry && !perUrl.has(ry.url)) perUrl.set(ry.url, ry);
  });

  if (perUrl.size === 0) return { nuut: [], mislukteBronne };

  // ignore-duplicates + return=representation returns only rows that were actually inserted.
  const res = await rest("nuusstroom?on_conflict=url&select=id,titel,bron,url", {
    method: "POST",
    body: JSON.stringify([...perUrl.values()]),
    prefer: "resolution=ignore-duplicates,return=representation",
  });
  return { nuut: (await res.json()) as GestoordeStroomRy[], mislukteBronne };
}
```

Move the three new `import` lines to the top of the file with the existing imports. Imports must not sit mid-file.

Append to `src/lib/verkiesing/episodes.ts` (and move the imports to the top):

```ts
import { rest } from "./db";
import { herlaaiWerf } from "./werf";

export async function neemEpisodesIn(): Promise<{ gevind: number }> {
  const res = await fetch(`https://www.youtube.com/feeds/videos.xml?channel_id=${NUUSPOD_KANAAL_ID}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`YouTube-voer: ${res.status}`);
  const rye = uitFeedXml(await res.text());
  if (rye.length > 0) {
    // merge-duplicates updates titel/datum only; versteek and handmatig are never sent, so Piet's overrides stay.
    await rest("episodes?on_conflict=video_id", {
      method: "POST",
      body: JSON.stringify(rye.map((r) => ({ ...r, bygewerk_om: new Date().toISOString() }))),
      prefer: "resolution=merge-duplicates,return=minimal",
    });
    await herlaaiWerf("episodes");
  }
  return { gevind: rye.length };
}
```

- [ ] **Step 3: Cron routes**

`src/app/api/cron/verkiesing-stroom/route.ts`:

```ts
import { NextResponse } from "next/server";
import { neemStroomIn } from "@/lib/verkiesing/stroom";
import { meldNuweStroomItems } from "@/lib/verkiesing/telegram";

export const runtime = "nodejs";
export const maxDuration = 120;

/**
 * Every 15 minutes (vercel.json). Guarded by CRON_SECRET like the other crons.
 * `?stil=1` skips the Telegram messages. Use it for the first seeding run so Piet isn't flooded.
 */
export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return NextResponse.json({ error: "CRON_SECRET ontbreek" }, { status: 500 });
  if (req.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Nie gemagtig nie" }, { status: 401 });
  }
  try {
    const { nuut, mislukteBronne } = await neemStroomIn();
    if (new URL(req.url).searchParams.get("stil") !== "1") await meldNuweStroomItems(nuut);
    console.log("[verkiesing-stroom]", nuut.length, "nuut; misluk:", mislukteBronne);
    return NextResponse.json({ nuut: nuut.length, mislukteBronne });
  } catch (err) {
    console.error("[verkiesing-stroom] misluk:", err);
    return NextResponse.json({ error: String((err as Error)?.message ?? err) }, { status: 500 });
  }
}
```

`src/app/api/cron/verkiesing-episodes/route.ts`:

```ts
import { NextResponse } from "next/server";
import { neemEpisodesIn } from "@/lib/verkiesing/episodes";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Hourly (vercel.json). Picks up every "Verkiesings-Vrydag" upload from the channel feed. */
export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return NextResponse.json({ error: "CRON_SECRET ontbreek" }, { status: 500 });
  if (req.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Nie gemagtig nie" }, { status: 401 });
  }
  try {
    const uitslag = await neemEpisodesIn();
    console.log("[verkiesing-episodes]", uitslag);
    return NextResponse.json(uitslag);
  } catch (err) {
    console.error("[verkiesing-episodes] misluk:", err);
    return NextResponse.json({ error: String((err as Error)?.message ?? err) }, { status: 500 });
  }
}
```

(`meldNuweStroomItems` is created in Task 9. Implement Task 9 before running this route.)

- [ ] **Step 4: Cron schedule**

Add these two objects to the `crons` array in `vercel.json`:

```json
    {
      "path": "/api/cron/verkiesing-stroom",
      "schedule": "*/15 * * * *"
    },
    {
      "path": "/api/cron/verkiesing-episodes",
      "schedule": "7 * * * *"
    }
```

- [ ] **Step 5: Run locally against the real database (after Task 9 exists)**

```bash
cd ~/nuuspod && npx tsc --noEmit && npx vitest run src/lib/verkiesing src/lib/telegram
npm run dev   # separate terminal, port 3000
set -a; source .env.local; set +a
curl -s "localhost:3000/api/cron/verkiesing-episodes" -H "Authorization: Bearer $CRON_SECRET"; echo
curl -s "localhost:3000/api/cron/verkiesing-stroom?stil=1" -H "Authorization: Bearer $CRON_SECRET"; echo
```

Expected:
- Episodes returns `{"gevind":1}` or more.
- Stroom returns `{"nuut":N,"mislukteBronne":[]}` with N ≥ 0. Any source listed in `mislukteBronne` must be investigated.

Then check the rows with MCP `execute_sql`:

```sql
select video_id, uitsaaidatum from episodes;
select bron, count(*) from nuusstroom group by bron;
```

Expected: `Y9HiKkP7Rmo | 2026-09-11`, and per-source counts.

**Verbatim check:** for three random rows, open the URL and confirm the page's headline matches `titel` character for character.

- [ ] **Step 6: Commit (after Task 9 passes too)**

```bash
git add src/lib/verkiesing/db.ts src/lib/verkiesing/werf.ts src/lib/verkiesing/stroom.ts src/lib/verkiesing/episodes.ts src/app/api/cron/verkiesing-stroom/route.ts src/app/api/cron/verkiesing-episodes/route.ts vercel.json
git commit -m "Verkiesing: crons vir die nuusstroom en Verkiesings-Vrydag-episodes

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

---

### Task 9: Telegram "Versteek" button

**Files (under `~/nuuspod`):**
- Create: `src/lib/verkiesing/telegram.ts`, `src/lib/verkiesing/telegram.test.ts`
- Modify: `src/lib/telegram/keyboard.ts` (the `Namespace` type and `NAMESPACES` array)
- Modify: `src/lib/telegram/keyboard.test.ts` (add a test)
- Modify: `src/lib/telegram/handlers/index.ts` (`hanteerTerugroep`, before `const flow = await loadFlow(chatId);`)

**Interfaces:**
- Consumes:
  - `enkodeer`, `dekodeer` (keyboard.ts)
  - `sendMessage(chatId, text, keyboard?)`, `editMessageText(chatId, messageId, text, keyboard?)` (client.ts)
  - `rest`, `herlaaiWerf`, `GestoordeStroomRy`
- Produces:
  - `stroomBoodskap(ry: { bron: string; titel: string; url: string }): string`
  - `versteekKnoppie(id: number): InlineKeyboardMarkup`
  - `meldNuweStroomItems(rye: GestoordeStroomRy[]): Promise<void>`
  - `versteekTerugroep(chatId: number, arg: string | undefined, messageId: number | undefined, teks: string | undefined): Promise<void>`

- [ ] **Step 1: Failing tests**

Append to `src/lib/telegram/keyboard.test.ts`:

```ts
describe("namespace h (verkiesing-stroom)", () => {
  it("round-trips a hide payload with a numeric id", () => {
    expect(dekodeer(enkodeer({ ns: "h", op: "v", arg: "123456" }))).toEqual({ ns: "h", op: "v", arg: "123456" });
  });
});
```

`src/lib/verkiesing/telegram.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { stroomBoodskap, versteekKnoppie } from "./telegram";

describe("verkiesing telegram", () => {
  it("shows source, verbatim headline and link", () => {
    expect(stroomBoodskap({ bron: "SABC News", titel: "IEC's list is out", url: "https://s/a" })).toBe(
      "Wat ander berig · SABC News\nIEC's list is out\nhttps://s/a"
    );
  });

  it("builds one Versteek button carrying the row id", () => {
    expect(versteekKnoppie(42)).toEqual({ inline_keyboard: [[{ text: "Versteek", callback_data: "h:v:42" }]] });
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/telegram/keyboard.test.ts src/lib/verkiesing/telegram.test.ts`
Expected: FAIL. The keyboard test fails because `dekodeer` returns `null` for unknown namespace `h`, and `./telegram` is not found.

- [ ] **Step 3: Implement**

In `src/lib/telegram/keyboard.ts`, change:

```ts
export type Namespace = "b" | "v" | "k" | "c" | "n";
```

to

```ts
export type Namespace = "b" | "v" | "k" | "c" | "n" | "h";
```

and change

```ts
const NAMESPACES: Namespace[] = ["b", "v", "k", "c", "n"];
```

to

```ts
const NAMESPACES: Namespace[] = ["b", "v", "k", "c", "n", "h"];
```

`src/lib/verkiesing/telegram.ts`:

```ts
import { editMessageText, sendMessage } from "@/lib/telegram/client";
import { enkodeer } from "@/lib/telegram/keyboard";
import type { InlineKeyboardMarkup } from "@/lib/telegram/types";
import { rest } from "./db";
import type { GestoordeStroomRy } from "./stroom";
import { herlaaiWerf } from "./werf";

export function stroomBoodskap(ry: { bron: string; titel: string; url: string }): string {
  return `Wat ander berig · ${ry.bron}\n${ry.titel}\n${ry.url}`;
}

/** Row ids are bigints well under 20 digits, so "h:v:<id>" stays far below the 64-byte cap. */
export function versteekKnoppie(id: number): InlineKeyboardMarkup {
  return { inline_keyboard: [[{ text: "Versteek", callback_data: enkodeer({ ns: "h", op: "v", arg: String(id) }) }]] };
}

export async function meldNuweStroomItems(rye: GestoordeStroomRy[]): Promise<void> {
  const chat = Number(process.env.VERKIESING_TELEGRAM_CHAT_ID);
  if (!Number.isFinite(chat) || chat === 0) {
    console.warn("[verkiesing] VERKIESING_TELEGRAM_CHAT_ID ontbreek; geen Versteek-knoppies gestuur nie");
    return;
  }
  for (const ry of rye) {
    await sendMessage(chat, stroomBoodskap(ry), versteekKnoppie(ry.id));
  }
}

export async function versteekTerugroep(
  chatId: number,
  arg: string | undefined,
  messageId: number | undefined,
  teks: string | undefined
): Promise<void> {
  const id = Number(arg);
  if (!Number.isSafeInteger(id) || id <= 0) return;
  await rest(`nuusstroom?id=eq.${id}`, {
    method: "PATCH",
    body: JSON.stringify({ versteek: true }),
    prefer: "return=minimal",
  });
  await herlaaiWerf("nuusstroom");
  if (messageId) await editMessageText(chatId, messageId, `${teks ?? ""}\n\nVersteek van nuuspod.co.za.`);
}
```

In `src/lib/telegram/handlers/index.ts`:
1. Add `import { versteekTerugroep } from "@/lib/verkiesing/telegram";` to the imports.
2. Insert directly above `const flow = await loadFlow(chatId);`:

```ts
  // Hide a "Wat ander berig" headline. Stateless: the row id rides in the button.
  if (cb.ns === "h" && cb.op === "v") {
    await versteekTerugroep(chatId, cb.arg, messageId, query.message?.text);
    return;
  }
```

- [ ] **Step 4: Run the tests**

Run: `npx vitest run src/lib/telegram src/lib/verkiesing && npx tsc --noEmit`
Expected: PASS, no type errors. If the `switch (cb.ns)` below the insert fails exhaustiveness checks, add `case "h": return;`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/verkiesing/telegram.ts src/lib/verkiesing/telegram.test.ts src/lib/telegram/keyboard.ts src/lib/telegram/keyboard.test.ts src/lib/telegram/handlers/index.ts
git commit -m "Verkiesing: Versteek-knoppie in Telegram vir die nuusstroom

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

Then do Task 8 Steps 5–6.

---

### Task 10: Hide flow end-to-end (local)

**Files:** none (verification only)

- [ ] **Step 1: Run both apps locally**

Site on 3001 with `.env.local`. Admin dev on 3000 with `NUUSPOD_WEB_URL=http://localhost:3001`.

- [ ] **Step 2: Seed one visible item and send its button**

MCP `execute_sql`: `select id, titel from nuusstroom where not versteek order by gepubliseer_om desc limit 1;`

Then, from `~/nuuspod`:

```bash
npx tsx -e 'import("./src/lib/verkiesing/telegram").then(m => m.meldNuweStroomItems([{ id: <ID>, titel: "<TITEL>", bron: "toets", url: "https://example.com" }]))'
```

Expected: a Telegram message with a "Versteek" button arrives in Piet's chat.

- [ ] **Step 3: Tap Versteek**

This needs the production webhook, so do it after Task 11. Locally, simulate the tap instead:

```bash
npx tsx -e 'import("./src/lib/verkiesing/telegram").then(m => m.versteekTerugroep(Number(process.env.VERKIESING_TELEGRAM_CHAT_ID), "<ID>", undefined, undefined))'
curl -s localhost:3001 | grep -c "<TITEL first 20 chars>"
```

Expected: the row has `versteek = true` in SQL, and the grep prints `0`. The headline is gone from the rendered page.

- [ ] **Step 4: Un-hide the test row**

MCP `execute_sql`: `update nuusstroom set versteek = false where id = <ID>;`

---

### Task 11: Admin to production

**Files:** none (deploy + env)

- [ ] **Step 1: Piet confirms the allowlist**

Show him `STROOM_BRONNE`: which outlets are `aktief: true`, and that Press Council membership is unverified for The South African and Politicsweb. Adjust per his answer and commit.

- [ ] **Step 2: Production env for the admin (Vercel project `nuuspod`)**

```bash
cd ~/nuuspod
for v in VERKIESING_SUPABASE_URL VERKIESING_SUPABASE_SECRET_KEY NUUSPOD_WEB_HERLAAI_SECRET VERKIESING_TELEGRAM_CHAT_ID; do
  grep "^$v=" .env.local | cut -d= -f2- | vercel env add $v production; done
printf "https://nuuspod.co.za" | vercel env add NUUSPOD_WEB_URL production
```

Expected: five "Added Environment Variable" lines.

- [ ] **Step 3: Merge and deploy**

```bash
git checkout main && git merge --no-ff verkiesing-drop-1 -m "Verkiesing Drop 1: nuusstroom- en episode-crons

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p" && git push origin main
```

Wait for the production deployment to show READY (`vercel ls nuuspod | head -5`).

- [ ] **Step 4: Seed silently, then confirm the cron schedule**

```bash
curl -s "https://www.kremetart.com/api/cron/verkiesing-stroom?stil=1" -H "Authorization: Bearer $CRON_SECRET"; echo
curl -s "https://www.kremetart.com/api/cron/verkiesing-episodes" -H "Authorization: Bearer $CRON_SECRET"; echo
```

Expected: JSON with counts and no `error`. Within 20 minutes a scheduled run should log `[verkiesing-stroom]` (check with `vercel logs` or MCP `get_runtime_logs`). New items after the seed produce Telegram messages.

Until the site ships (Task 12), `herlaaiWerf` calls to nuuspod.co.za return 404. That is harmless and logged.

---

### Task 12: Site preview, browser verification, Piet's approval, production

**Files:**
- Modify: `lib/verkiesing/gidse/<slug>.ts` (regenerate with `--gepubliseer` per approved explainer)
- Modify: `lib/verkiesing/terme.ts` (if Piet chose "Verkiesingskommissie")

- [ ] **Step 1: Publish the approved explainers**

For each explainer Piet approved on the review page:

```bash
node scripts/gids-na-ts.mjs <slug> --gepubliseer
```

Unapproved explainers stay drafts. The home page shows only published cards; the rest are added as he approves them.

Commit:

```bash
git add lib/verkiesing/gidse lib/verkiesing/terme.ts docs/verkiesing
git commit -m "Verkiesing: goedgekeurde gidse gepubliseer

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p"
```

- [ ] **Step 2: Pre-flight checks**

```bash
cd ~/projects/nuuspod-web
grep -rn "Die Buitelyn" app lib docs/verkiesing || echo "brand ok"
grep -rniE "kom op|binnekort|launch|bekendstel" app lib/verkiesing/datums.ts lib/verkiesing/terme.ts || echo "no launch promises"
grep -rn "line-clamp\|truncate" app/_components/verkiesing || echo "no truncation"
npm run lint && npm test && npm run build
```

Expected: `brand ok`, `no launch promises`, `no truncation`; lint, tests and build all pass.

- [ ] **Step 3: Site env on Vercel and a preview deploy**

1. Find the project that serves the domain: `vercel domains inspect nuuspod.co.za`.
2. Link to it: `vercel link --yes --project <name>`.
3. Add the variables:

```bash
for v in SUPABASE_URL SUPABASE_PUBLISHABLE_KEY HERLAAI_SECRET; do
  grep "^$v=" .env.local | cut -d= -f2- | vercel env add $v production
  grep "^$v=" .env.local | cut -d= -f2- | vercel env add $v preview
done
git push -u origin verkiesing-drop-1
```

Expected: a preview deployment URL (from the push output or `vercel ls`).

- [ ] **Step 4: Verify in a real browser**

Use the `verify-frontend-change` skill on the preview URL at ~400px and at desktop width. Check each item:
- countdown ticks, and has no animation with reduced motion on;
- "Wat kom" shows the next three milestones;
- the Verkiesings-Vrydag embed plays;
- the rail shows headlines with source and time, no headline is truncated, and links open the original;
- `/adverteer` is unchanged;
- `/gids/<approved slug>` renders and a draft slug returns 404;
- Ja/Nee inserts a `terugvoer` row (check in SQL);
- no horizontal scroll on phone width.

- [ ] **Step 5: Piet approves**

Send Piet the preview URL. His explicit approval of the page and its copy (hero line, labels, footer) is required before production. That is rule 2 of the spec.

- [ ] **Step 6: Production**

```bash
git checkout main && git merge --no-ff verkiesing-drop-1 -m "Verkiesing 2026 Drop 1 op nuuspod.co.za

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018wH6Bu4k15uURamW4fV68p" && git push origin main
```

When the deployment is READY:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nuuspod.co.za/
curl -s -o /dev/null -w "%{http_code}\n" https://nuuspod.co.za/adverteer
set -a; source .env.local; set +a
curl -s -X POST https://nuuspod.co.za/api/herlaai -H "Authorization: Bearer $HERLAAI_SECRET" -d '{"tag":"nuusstroom"}'; echo
```

Expected: `200`, `200`, `{"ok":true,"tag":"nuusstroom"}`.

Finally, tap "Versteek" on one real Telegram message. Confirm that headline disappears from nuuspod.co.za on reload, then un-hide it in SQL.
