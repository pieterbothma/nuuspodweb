# Verkiesing 2026 — nuuspod.co.za election hub (sub-project A) design

Written 14 September 2026. Approved section by section in a brainstorming session with Piet.
Covers sub-project **A** in full and records the decisions that constrain **B–E**.

## 1. Goal

From 17 September 2026 until after the council coalition window, nuuspod.co.za is the Afrikaans
hub for the Local Government Elections on **Wednesday 4 November 2026**. It must show that Nuuspod
can compete with the big outlets. It does that through depth per ward, Afrikaans, and speed, while
staying strictly neutral.

The current advertiser page moves to `/adverteer` and returns to `/` after the elections.

## 2. Sub-projects

| # | Sub-project | Where | Public? | Dates |
|---|---|---|---|---|
| **A** | Site takeover + wyk-soeker (this spec) | `nuuspod-web` + Supabase + admin crons | Yes | Drop 1 Thu 17 Sep, Drop 2 Fri 25 Sep |
| B | Dorpsbulletins + daily countdown segment | `nuuspod` admin pipeline | Yes | 21 Sep – 10 Oct |
| C | "Vra jou munisipaliteit" (AG reports, IDPs, AFS) | corpus + `nuuspod-web` page | Yes | 1–20 Oct |
| D | Uitslagnag + coalition watch | both | Yes | built by 15 Oct, live 4 Nov |
| E | Voorspel-model: internal election-night nowcast, scored afterwards | `hq` + Supabase `intern` | **Never** | backtested by ~25 Oct |

Scope limits for A: web only, nuuspod.co.za only. No Koedoe, no WhatsApp bot, no public API.

Each of B–E gets its own spec. D and E share one IEC live-results ingest.

## 3. Hard rules

1. **No model-generated claims about named candidates or parties.** Every name comes from IEC data
   rows or a verbatim quote. No generated sentence on the site names a person or party.
2. **Human approval gate on all election content until 4 Nov.** How it applies to A:
   - Explainers and other copy are approved by Piet before publishing.
   - IEC/MDB data goes live only through the stage → check → publish step (§7.3).
   - **Deliberate exception:** the "Wat ander berig" rail auto-publishes verbatim headlines from
     allowlisted outlets (§8.1). Piet has a Telegram "hide" button.
3. **Neutral positioning.**
   - Candidates and parties are ordered alphabetically until the IEC ballot draw (23 Sep), then in
     official ballot order. Never by size or past performance.
   - Every candidate gets equal space.
   - Party rows are plain white or grey text: name plus IEC abbreviation. No party colours, no
     logos, no brand colour.
4. **Never publish unofficial results as official.** Model output, including E, is never shown
   publicly. Exit polls and projections during voting hours are also illegal (Municipal Electoral
   Act s76).
5. **Headlines from other outlets are shown exactly as published.** No translation, shortening,
   truncation or cleanup. English stays English. Only our own labels (source type, relative time)
   are Afrikaans.
6. **No public launch promises.** Nothing on the site announces upcoming Nuuspod features or dates
   (Piet, 14 Sep). Drop dates in this spec are internal targets only.

## 4. Verified facts (corrections to the original brief)

| Fact | Value | Source |
|---|---|---|
| Special vote applications | open Mon 21 Sep, **close Mon 12 Oct 17:00** (not 15 Oct) | IEC gazetted timetable PDF; IEC auto-reply 14 Sep |
| Special voting | Mon 2 & Tue 3 Nov, 08:00–17:00 (home visit or station) | timetable |
| Election day | Wed 4 Nov, 07:00–21:00 | timetable |
| Code of Conduct signing; ballot draw | 23 Sep | timetable / CoGTA |
| Certificates of candidacy | 25 Sep | timetable |
| Parties | **732 registered, 546 contesting** (674 was the 7 Aug figure) | M&G 2 Sep 2026 |
| Candidates / seats | 142,072 candidates (100,856 ward, 40,241 PR, 975 independent ward) for 10,526 seats | IEC via The Citizen |
| Wards | 4,488 (was 4,468 in 2021); boundaries **re-delimited** | IEC/MDB release |
| Travelling vote | **None in LGE.** Vote only in the voting district where registered | IEC auto-reply |
| ID | smartcard or green ID book ("no other ID accepted"; TIC status to confirm) | IEC auto-reply |
| Special vote by SMS | ID number to 32249 (R1.50), voting-station special vote only | IEC auto-reply |
| Seat formula | Municipal Structures Act 117 of 1998, Schedule 1 Part 3 items 12–16; DC seats Schedule 2 | Act |

**Ward ID trap.** Of the 4,430 WardIDs shared between 2021 and 2026, about 2,270 changed area by
more than 5%. **Never join 2021 ward results to 2026 wards on WardID.**

## 5. Site structure

| Route | Drop | Content |
|---|---|---|
| `/` | 1 | Countdown to 4 Nov 07:00; "Hierdie week" timeline (always shows the next deadline); link to the IEC voter lookup (replaced by the wyk-soeker only once it is live); Verkiesingsprogram; explainer cards; "Wat ander berig" rail; Real411 link |
| `/gids/wyk-en-pr-stembrief` | 1 | 2 ballots (metros) vs 3 ballots (local municipalities, incl. DC); seat allocation in plain terms |
| `/gids/spesiale-stemme` | 1 | who, how to apply (online, form, SMS 32249), dates |
| `/gids/wat-om-saam-te-bring` | 1 | valid ID, voters' roll closed, no travelling vote |
| `/gids/waar-stem-ek` | 1 | finding your station, hours, queue at 21:00; IEC lookup |
| `/wyk/[wykId]` | 2 | ward page (§9.1–9.3) |
| `/munisipaliteit/[kode]` | 2 | wards list, official 2021 council result, parties contesting (§9.7) |
| `/adverteer` | 1 | current sales page moved unchanged, plus a footer link |

**Footer on every page:**
- "Bron: Verkiesingskommissie (IEC) · Munisipale Afbakeningsraad" where their data is used
- "Nuuspod is nie aan die IEC of enige party verbonde nie."
- Real411 link
- `/adverteer` link

## 6. Look

- **Full Nuuspod look:** black ground, `#00D2FA → #FA2229` neon border, cyan-over-red headline
  treatment (see the nuuspod house-style memory).
- **Red and cyan appear only in page chrome:** border, headings, logo, countdown. They never touch
  party names, candidate rows or data bars. The EFF uses red.
- **Motion** (via the existing `motion` library) only on the countdown and on the lookup result
  appearing.
- **Phone first:** it must be fast on mobile data.
- **Link previews:** every ward and municipality page has its own Open Graph image (§9.3).

## 7. Data layer

### 7.1 Supabase

Dedicated project `verkiesing-2026` (ref `xxysgvanarnirxoxrbkj`, eu-west-1, org Koedoe, $10/month),
created 14 Sep 2026 with Piet's approval.

| Schema | Tables | Access |
|---|---|---|
| `public` | `munisipaliteite`, `wyke` (PostGIS geometry, reprojected EPSG:3857 → 4326), `stemstasies`, `partye`, `kandidate`, `stembrief_volgorde`, `raad_uitslae_2021`, `plekname`, `nuusstroom`, `episodes`, `terugvoer` | Anon key: `SELECT` via RLS on published rows only; `INSERT` only on `terugvoer` |
| `staging` | mirrors of the IEC/MDB tables | service role only |
| `intern` | `vd_uitslae` (historical voting-district results), `wyk_2021_hertoewysing` (the remap); later E's prediction log | never exposed via the API |

Every `kandidate` and `stemstasies` row stores `bron_lêer` and `bron_ry`, so any displayed row can be
traced back to the IEC PDF. `data_weergawes` records dataset, source URL, source-file date, row
count, loaded_at and published_at.

### 7.2 Lookup (no paid geocoder)

All three searches are Postgres RPC functions:

- **`vind_wyk(lat, lng)`**: browser geolocation ("Gebruik my ligging"), then point-in-polygon on
  `wyke`.
- **`soek_plek(q)`**: trigram search on `plekname` (Stats SA sub-place/main-place names and shapes).
  - Returns each matching place with its municipality, plus the wards overlapping it.
  - Ambiguous names show as a list, e.g. "Brooklyn — Tshwane" and "Brooklyn — Kaapstad".
  - *To verify: current download of the Stats SA place-name layer.*
- **`soek_stemstasie(q)`**: trigram search on station name and address. The station row already
  carries the WardID.

Postcode search is out: there are no official postcode boundaries.

### 7.3 Data pipeline: stage → check → publish

Scripts live in `nuuspod-web/data/`. Python handles the PDF parsing; SQL loads the data.

1. **Parse.**
   - Candidates: per-province IEC PDFs. In 2021 the columns were Municipality, Party,
     "Ward \ List Order", masked ID, Fullname, Surname. That one column holds either a PR list
     position or an 8-digit WardID. Independents appear as `INDEPENDENT`.
   - Voting stations: IEC PDFs (Province, Municipality, Ward, VD, Station, Address).
   - Ward shapes: MDB `MDBWards2026.zip`.
   - Official 2021 council results and seat calculations: IEC results downloads.
2. **Load** into `staging`.
3. **Check report**, one Markdown file per load:
   - totals reconciled against official figures (4,488 wards; 142,072 candidates; per-province
     counts);
   - candidates whose WardID is not in `wyke`;
   - duplicates;
   - wards with no shape (currently 3 in the Free State);
   - stations whose PDF WardID ≠ the ward their location falls in (once station locations exist);
   - a diff against the previous published version.
4. **Piet approves**, then `publish` swaps staging into `public` in one transaction, writes
   `data_weergawes`, and calls on-demand revalidation for the affected site paths.

The same steps handle every IEC correction round.

### 7.4 Site reads

Next.js server components query Supabase server-side, with ISR caching. Pages are revalidated when
data is published, or hourly for the rail and episodes. On a traffic spike the site serves cached
pages. Only new searches hit the database.

## 8. Ingest jobs (Vercel crons in the `nuuspod` admin)

### 8.1 "Wat ander berig" (every 15 min)

- **Sources:** reuse `src/lib/rss-sources.ts` and the per-source modules (Maroela, Daily Maverick,
  Citizen, PoliticsWeb, SABC, M&G, The South African). News24/Netwerk24 (Railway scraper) join later.
  - Media24 and Maroela Media permissions are handled by Piet.
  - An outlet only goes live on the rail once Piet has cleared it.
- **Allowlist:** one file in the admin repo.
  - Only Press Council of SA members and BCCSA broadcasters are eligible.
  - Each source is labelled by type: `nasionaal · streek · gemeenskap · openbare uitsaaier`.
  - No left/right bias labels.
- **Filter:** bilingual keyword match only, no model, on title + categories + the first 300
  characters of the description. Terms include verkiesing/election, IEC/VKK, ward councillor,
  by-election, special votes, coalition, candidate lists. Municipality names alone are excluded:
  they would pull in every Cape Town or Tshwane story. Items older than 7 days are skipped.
- **Stored per item:** `titel` exactly as in the feed (entities decoded, nothing else), `bron`,
  `bron_tipe`, `url` (unique), `gepubliseer_om`, `versteek` (default false). Feed bodies (Citizen and
  SABC include full text) are discarded before insert.
- **Display:** newest first, in `HH:MM · Bron · headline ↗` form, with no images or snippets.
  - Long headlines wrap, never truncate.
  - At most 3 visible items per source in the top 15, so no single outlet dominates.
- **Hide:** a Telegram message per new item with a "Versteek" button, sent through the existing
  Nuuspod bot. It sets `versteek = true`.

### 8.2 Verkiesingsprogram episodes (hourly)

- **Rule:** any upload on the Nuuspod channel (`UC8WVZnhOnCUwSpJaMIhdQcg`) whose title starts with
  **"Verkiesings-Vrydag"** is an election episode.
  - First episode: 11 Sep 2026, `Y9HiKkP7Rmo` ("Verkiesings-Vrydag: Die DA se skynheiligheid Vrydag
    11 September 2026", 2h01m live).
  - Remaining Fridays before the vote: 18, 25 Sep; 2, 9, 16, 23, 30 Oct.
- **Detection:** channel RSS titles only. No YouTube API key is needed.
  - Do **not** use the RSS `<published>` date for the air date. Scheduled livestreams are dated when
    scheduled: Monday 14 Sep's show carries 11 Sep.
  - Sort by the date inside the title, falling back to `<published>`.
- **Display:** the title is shown **as-is**, like the bulletin on the current site (Piet, 14 Sep).
  Episodes are Nuuspod's own human journalism, so rule 1 does not apply to them. The neutrality
  constraints in §3 apply to the data and explainer blocks.
- **Storage:** detected episodes go into `episodes` and stay there permanently. The RSS feed only
  holds the latest 15 uploads.
- **Manual override:** a row with `handmatig = true` always wins over detection.

### 8.3 Timeline

The `Hierdie week` items are a static, typed list in the site repo, taken from §4. Each is shown
from its "show from" date and hidden after its end date.

## 9. Signature features

| # | Feature | Drop |
|---|---|---|
| 9.1 | **Ward page**, modelled on WhoCanIVoteFor: ward number and municipality, "Wat doen 'n raadslid?", voting stations in the ward, every candidate (ward ballot) with equal space, the municipality's PR list parties, link to the IEC source PDF, "Laas bygewerk: [datum] · Bron: IEC-kandidaatlys" | 2 |
| 9.2 | **"Jou stembrief"**: after the 23 Sep draw, the ward's 2 or 3 ballots in official order, text only, no logos or photos. *To verify: how the IEC publishes ballot order (draw decides the first party, rest alphabetical?).* | 2 |
| 9.3 | **Shareable ward card / OG image**: "Wyk 12 · Stellenbosch · 9 kandidate · Stem 4 Nov". **Rendered in code from data** (e.g. `next/og`), never AI-generated, because the figures must be exact | 2 |
| 9.4 | **Verkiesingsprogram**: this week's episode large, archive row below, each card links to the wyk-soeker | 1 |
| 9.5 | **"Wat ander berig" river** (§8.1) | 1 |
| 9.6 | **Countdown + "Hierdie week" timeline** (§8.3) | 1 |
| 9.7 | **Municipality 2021 baseline**: official seats per party (Schedule 1 seat calc report) and a "no party had a majority" flag computed from those seats. No "who governs now" claims; there is no structured source for that | 2 |
| 9.8 | **Real411 link + "Het jy gekry wat jy soek?"** (ja/nee + page into `terugvoer`, no personal data), which gives measured usefulness numbers for `/adverteer` later | 1 |

These move to D: the "how results night works" explainer, provisional/declared status labels, and
the results pages.

## 10. Launch plan

| Drop | Date | Contents | Blocking inputs |
|---|---|---|---|
| 1 | **Thu 17 Sep** | `/`, countdown and timeline, 4 explainers, `/adverteer`, rail, episodes, feedback, Supabase project | Explainer drafts ready Tue 15 Sep evening → Piet reviews Wed 16 Sep; Supabase project created (`verkiesing-2026`, ref `xxysgvanarnirxoxrbkj`) |
| 2 | **Fri 25 Sep** | wyk-soeker, `/wyk/*`, `/munisipaliteit/*`, ballots, ward cards | IEC final candidate list (16 Sep) parsed and reconciled; ballot draw (23 Sep); Stats SA place names |

If an explainer isn't approved in time, Drop 1 goes live without it, and each explainer is added as
it gets approved.

## 11. Failure handling

| Situation | Behaviour |
|---|---|
| Suburb matches several places | List with municipality for each |
| Geolocation denied | Quiet fallback to the search box |
| Ward has no shape (3 FS wards) | Station search still works; note "grens nog nie beskikbaar nie" |
| IEC corrections | Re-run pipeline → check report → publish; ward pages show source-file date |
| Supabase down | Cached pages keep serving; search shows a friendly error |
| A news feed dies | Rail shows the remaining sources; ingest logs the failure |
| Episode misdetected | Manual override row |
| YouTube feed unavailable | Episode block shows the last stored episode |

## 12. Testing

- **Parser:**
  - Fixture = 2021 WC candidate PDF (already downloaded). The totals must reproduce the known 2021
    figures.
  - On the 16th, reconciliation against 142,072 must pass before publish.
- **Lookup:** a set of known point → ward pairs, plus station WardID vs polygon cross-check in the
  check report.
- **Neutrality as tests:**
  - ordering function (alphabetical / ballot order, never by votes);
  - party row component uses no colour tokens;
  - rail `titel` byte-equal to the feed title after entity decoding;
  - no rail item stores feed body text.
- **Real browser:** each drop is verified at ~400px and desktop before promotion (a clean build is
  not verification).
- **Brand grep:** no "Die Buitelyn" in deliverables.

## 13. Permissions and dependencies

| Party | Status (14 Sep) | Blocks |
|---|---|---|
| IEC API credentials + written OK to store/display with Afrikaans labels, ad-supported site | Sent to webmaster@elections.org.za; auto-reply only. Suggested: forward to spokesperson@elections.org.za | D, E (not A) |
| MDB: ward shapes on an ad-supported site; missing FS wards; 2016/2021 layers | Sent to info@demarcation.org.za | A Drop 2 (licence clarity) |
| Media24, Maroela Media: headlines on the rail | Piet handles in person | those sources on the rail |

## 14. Constraints recorded for later sub-projects

- **E (Voorspel-model):**
  - CSIR-style fuzzy clustering of ~23k voting districts on LGE 2021 PR shares + NPE 2024
    provincial shares, with by-election swings. MK's baseline is NPE 2024.
  - Aggregate to municipalities, then apply the Schedule 1 seat formula.
  - Backtest on 2021/2024 with a simulated reporting order.
  - **Poll the IEC feed every few minutes on 4–5 Nov and store every snapshot.** That builds the
    first real arrival-order dataset.
  - Every prediction is timestamped and immutable.
  - Runs on `hq`.
- **Internal remap:** 2021 voting-district results onto 2026 wards, for E and analysis only, never
  public.
- **D:**
  - "Voorlopig · X% getel · bygewerk HH:MM · Bron: IEC" until the IEC declares, then "Verklaar".
  - Always keep the last good snapshot. In 2024 the IEC dashboard reset to zero mid-count.

## 15. Open questions

1. TIC (temporary identity certificate): accepted for LGE 2026? The IEC auto-reply says smartcard or
   green book only.
2. Stats SA place-name layer: which vintage (2011 SP/MP vs 2022), and where to download it.
3. IEC ballot-order publication format after the 23 Sep draw.
4. Whether the permission emails should come from Izak / a Nuuspod address rather than Piet.
