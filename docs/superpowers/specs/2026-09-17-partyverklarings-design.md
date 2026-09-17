# "Wat die partye sê" — party statements on the home page

Date: 2026-09-17. Decisions by Piet on 2026-09-16 (questions in session). Builds on the
election design spec (`2026-09-14-verkiesing-2026-design.md`), whose hard rules still apply.

## 1. Goal

Fresh, automated election news that doesn't compete with other media: the official press
statements of the parties in Parliament, in faithful Afrikaans, on a more focused home page.
Press statements are written to be republished, so no outlet's work is taken.

## 2. Rulings

| Topic | Ruling |
|---|---|
| Which parties | The 18 parties with National Assembly seats. Neutral, checkable line. |
| Sources | Party websites first (free). X later, for parties without a working newsroom, once Piet buys X API credits. |
| When | Hourly, 06:00–21:00 SAST. |
| Afrikaans | Faithful full translation by Gemini, never a summary. VF+ publishes in Afrikaans already: shown as published. |
| Approval | Nothing goes live without a tap. Each new statement goes to the Nuuspod Telegram bot (`TELEGRAM_ALLOWED_CHAT_IDS`, Piet and Izak) with **Goedkeur / Verwerp**. First tap wins; the other chat's message updates. |
| Balance | One card per party (its latest approved statement). Cards in alphabetical party order, never newest-first, so publishing volume buys no prominence. |
| Labels | Every card: party name, Afrikaans headline and text, "Persverklaring van {party}, deur KI in Afrikaans vertaal" (or "soos gepubliseer" for VF+), date, original headline verbatim with a link. |
| Home page | Countdown + ward search on top, then "Wat die partye sê" as the main column. IEC actions, episodes, guides and "Wat ander berig" move below / aside. |

How this squares with the hard rules (§3 of the election spec):
- Rule 1 (no model-generated claims about parties): the text is the party's own statement,
  translated, labelled as AI-translated, linked to the original, and approved by a human.
  No Nuuspod-written sentence about a party is added.
- Rule 2 (human gate): kept — the Telegram tap.
- Rule 3 (neutral positioning): alphabetical cards, one per party, no colours or logos.
- Rule 5 (headlines verbatim): the original headline is shown verbatim next to the translation.

## 3. Sources (verified 2026-09-16)

| Party | Adapter | URL |
|---|---|---|
| ActionSA | rss (excerpt → fetch full text) | actionsa.org.za/feed/ |
| ACDP | rss (full) | acdp.org.za/category/statements/feed/ |
| Al Jama-ah | rss (full) | aljama.co.za/category/press-release/feed/ |
| ANC | wp-json pages, filtered to statement URLs | anc1912.org.za/wp-json/wp/v2/pages?orderby=date |
| BOSA | wp-json posts | bosa.co.za/wp-json/wp/v2/posts |
| DA | sitemap (dated /YYYY/MM/ URLs) + page text | da.org.za/sitemap.xml |
| EFF | rss (full) | effonline.org/feed/ |
| GOOD | wp-json posts | forgood.org.za/wp-json/wp/v2/posts |
| IFP | rss (excerpt → fetch full text) | ifp.org.za/category/press-releases/feed/ |
| MK | rss (full) | mkparty.org.za/category/media-and-press/press-release/feed/ |
| UDM | html listing | udm.org.za/udm-statements |
| VF+ | rss, Afrikaans, no translation | vfplus.org.za/af/feed/ |

No usable newsroom (X later): PA, ATM, PAC, Rise Mzansi, NCC, UAT. Each adapter is verified
against the live site during the build; one that can't be made reliable is left out and
reported, never guessed.

First run: a baseline. Everything already published is stored as `basislyn` and never sent
for approval, so Telegram isn't flooded with weeks of old statements. Only statements that
appear after the baseline are translated and sent.

## 4. Data (verkiesing-2026 Supabase)

`partyverklarings`:
- `id` bigint pk; `party` text (display name as in §3); `bron_url` text unique;
- `titel_oorspronklik`, `teks_oorspronklik` text; `gepubliseer_om` timestamptz;
- `titel_af`, `teks_af` text null; `vertaal` boolean (false for VF+);
- `kontrole` jsonb (translation check results);
- `status` text: `basislyn` | `wag` | `goedgekeur` | `verwerp` | `fout`;
- `besluit_deur` text null, `besluit_om` timestamptz null;
- `telegram` jsonb (chat id → message id, to update every approver's message);
- `geskep_om` timestamptz default now().

RLS: anon may `SELECT` only `status = 'goedgekeur'` rows, only the public columns. The site
reads a view or RPC that returns the latest approved row per party. Writes only with the
secret key (admin app).

## 5. Pipeline (admin app `~/nuuspod`)

Vercel cron `/api/cron/verkiesing-partye`, schedule `5 4-19 * * *` (UTC = 06:05–21:05 SAST),
`CRON_SECRET` like the other crons.

1. Fetch every adapter (browser UA, `--compressed`-equivalent, 25 s timeout, one failing
   source never stops the rest).
2. Normalise to `{party, url, titel, teks, gepubliseer_om}`; strip HTML to paragraphs.
   Skip items older than 3 days or already in the table (by `bron_url`).
3. Insert new rows (`wag`, or `basislyn` on a party's first run).
4. For each `wag` row without a translation: Gemini (`gemini-3.5-flash`, JSON schema
   `{titel, teks}`), instruction: faithful translation, keep every name, number, date and quote,
   add nothing, drop nothing.
5. Mechanical check, stored in `kontrole`: same set of numbers; every capitalised name of 2+
   words in the original still present; same count of quoted passages; length ratio within
   0.7–1.6. A failed check doesn't block — the Telegram message says what failed, in bold.
6. Send to every allowed chat: party, original headline, Afrikaans headline + text, check
   result, link, buttons `p:ok:<id>` / `p:nee:<id>`.

Callback (`ns = "p"`, stateless): update status, `besluit_deur`, `besluit_om`; edit every
approver's message to "Goedgekeur deur X" / "Verwerp deur X" without buttons; on approve,
`herlaaiWerf("partye")`. A second tap on a decided row only shows who decided.

## 6. Site (`nuuspod-web`)

- `lib/verkiesing/partye.ts`: `haalPartyverklarings()` — latest approved statement per party,
  cached with tag `partye`, `revalidate: 3600`. `/api/herlaai` accepts `partye`.
- `app/_components/verkiesing/partyverklarings.tsx`: section "Wat die partye sê", cards in
  alphabetical party order; each card collapsed to headline + first paragraph with
  "Lees die hele verklaring" (`<details>`, no JS), label, date, original headline + link ↗.
  Renders nothing when no statement is approved yet.
- Home page order: hero (countdown + search) → Wat die partye sê → IEC actions → Wat kom /
  episodes / guides, with "Wat ander berig" in the aside.
- All copy via `KOPIE`, written by Gemini (`--partye` mode), logged in `ui-kopie-wysigings.md`.

## 7. Tests

- Admin: each adapter parses a saved fixture; baseline run inserts nothing as `wag`; the check
  flags a dropped number and a dropped name; callback payload fits 64 bytes; a second tap
  doesn't change a decided row; the allowlist still guards callbacks.
- Site: cards alphabetical regardless of input order; one card per party; no party colours or
  red inside cards; nothing renders for an empty list; unapproved rows are never requested
  (the query filters on status).

## 8. Out of scope (for now)

X ingestion (later, Piet buys credits); editing a translation from Telegram before approving
(Verwerp and let it be); parties outside Parliament.
