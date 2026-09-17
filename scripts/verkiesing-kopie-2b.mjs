// Fase 2b: Gemini writes the Afrikaans UI copy for the ward finder, the ward page, the
// municipality page and the 404 page. Provenance for the values in lib/verkiesing/kopie.ts.
//
// Run: node scripts/verkiesing-kopie-2b.mjs
// Writes docs/verkiesing/ui-kopie-2b.json. Reads GEMINI_API_KEY from ~/nuuspod/.env.local
// (surrounding quotes stripped) and never prints it.
//
// The slots are read from kopie.ts itself (everything after the "Wyk-soeker" marker), so
// the request always covers exactly the slots the components use. After the response
// arrives the script checks every slot mechanically — present, placeholders and "\n"
// preserved, within its word limit, no digits beyond the ones the facts allow — and exits
// non-zero on any failure. The human fact-check comes after that.

import { readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const MODEL = "gemini-3.5-flash";
const WORTEL = new URL("..", import.meta.url).pathname;
// `--plaaslik` rewrites only the local-news slots and writes their own provenance file.
const PLAASLIK = process.argv.includes("--plaaslik");
// `--uitslag2021` rewrites only the 2021 ward-result slots.
const UITSLAG2021 = process.argv.includes("--uitslag2021");
// `--kandidaat` rewrites only the nameless-candidate placeholder.
const KANDIDAAT = process.argv.includes("--kandidaat");
// `--uitvou` rewrites only the show/hide button labels for long lists.
const UITVOU = process.argv.includes("--uitvou");
// `--partye` rewrites only the "Wat die partye sê" block's labels.
const PARTYE = process.argv.includes("--partye");
const UIT = join(
  WORTEL,
  PLAASLIK
    ? "docs/verkiesing/ui-kopie-plaaslik.json"
    : UITSLAG2021
      ? "docs/verkiesing/ui-kopie-uitslag2021.json"
      : KANDIDAAT
        ? "docs/verkiesing/ui-kopie-kandidaat.json"
        : UITVOU
          ? "docs/verkiesing/ui-kopie-uitvou.json"
          : PARTYE
            ? "docs/verkiesing/ui-kopie-partye.json"
            : "docs/verkiesing/ui-kopie-2b.json"
);

function sleutel() {
  const env = readFileSync(join(homedir(), "nuuspod/.env.local"), "utf8");
  const ry = env.split("\n").find((r) => r.startsWith("GEMINI_API_KEY="));
  if (!ry) throw new Error("GEMINI_API_KEY ontbreek in ~/nuuspod/.env.local");
  return ry.slice("GEMINI_API_KEY=".length).trim().replace(/^["']|["']$/g, "");
}

/** Every `key: "value"` after the Wyk-soeker marker, values unescaped via JSON. */
function leesGleuwe() {
  const bron = readFileSync(join(WORTEL, "lib/verkiesing/kopie.ts"), "utf8");
  const begin = bron.indexOf("// --- Wyk-soeker");
  if (begin < 0) throw new Error("Wyk-soeker-merker nie in kopie.ts gevind nie");
  const deel = bron.slice(begin);
  const gleuwe = {};
  // Drop 1's slots (dates, rail, footer) sit between the 2b sections; they are already
  // Gemini-written (ui-kopie.json), so only the slots briefed below are rewritten.
  for (const m of deel.matchAll(/^\s+([a-z0-9_]+):\s*\n?\s*("(?:[^"\\]|\\.)*")\s*,/gm)) {
    if (m[1] in aktieweBriewe()) gleuwe[m[1]] = JSON.parse(m[2]);
  }
  return gleuwe;
}

const BRIEWE_UITSLAG2021 = {
  uitslag2021_opskrif: "Klein etiket in HOOFLETTERS bo die 2021-wykuitslag op 'n wykblad.",
  uitslag2021_onderskrif: "Een of twee sinne: dit is die OVK se amptelike uitslag van die wykstembrief in die plaaslike verkiesing van 2021, en hierdie wyk bestaan uit presies dieselfde stemdistrikte as toe (dus dieselfde gebied).",
  uitslag2021_hernommer: "Kort sin wanneer die wyk hernommer is: in 2021 was hierdie selfde gebied wyk {n}.",
  uitslag2021_kolom_party: "Tabelkolom: party.",
  uitslag2021_kolom_stemme: "Tabelkolom: stemme.",
  uitslag2021_kolom_persent: "Tabelkolom: persentasie (kort, bv. '%').",
  uitslag2021_onafhanklik: "Etiket vir die ry van onafhanklike kandidate op die wykstembrief (die OVK tel moontlik meer as een saam).",
  uitslag2021_geregistreer: "Etiket: aantal geregistreerde kiesers.",
  uitslag2021_stemdeelname: "Etiket: stemdeelname (persentasie van geregistreerde kiesers wat gestem het).",
  uitslag2021_bedorwe: "Etiket: bedorwe stemme.",
  uitslag2021_verander: "Een sin: hierdie wyk se grense het sedert 2021 verander, daarom pas geen 2021-wykuitslag presies nie. (Word gevolg deur 'n skakel.)",
  uitslag2021_verander_skakel: "Kort skakelteks na die munisipale raad se amptelike uitslag van 2021.",
  uitslag2021_bron: "Bronvermelding: die OVK se amptelike uitslae per stemdistrik van 2021, opgetel vir hierdie wyk.",
  uitslag2021_wys_klein: "Knoppie wat partye met minder as 1% van die stemme wys; {n} = hoeveel partye.",
  uitslag2021_versteek_klein: "Knoppie wat daardie partye weer versteek.",
};

const BRIEWE_KANDIDAAT = {
  kandidaat_sonder_naam: "Kort plekhouer op 'n stembrief waar die OVK 'n kandidaat se reël sonder naam gepubliseer het: die kandidaat bestaan, maar die OVK-lys noem geen naam nie. Geen skuld of spekulasie nie.",
};

const BRIEWE_UITVOU = {
  uitvou_wys_kandidate: "Kort knoppie wat 'n stembrief se volledige kandidaatlys oopmaak; {n} = hoeveel kandidate. Tot 5 woorde.",
  uitvou_wys_partye: "Kort knoppie wat die volledige lys partye (op 'n stembrief of in 'n munisipaliteit) oopmaak; {n} = hoeveel partye.",
  uitvou_wys_berigte: "Kort knoppie wat 'n lys plaaslike nuusopskrifte oopmaak; {n} = hoeveel berigte.",
  uitvou_wys_stemlokale: "Kort knoppie wat die lys stemlokale in 'n wyk oopmaak; {n} = hoeveel stemlokale.",
  uitvou_wys_uitslag: "Kort knoppie wat die tabel met die 2021-uitslag oopmaak (die opskrif daarbo noem reeds 2021).",
  uitvou_versteek: "Een woord op dieselfde knoppie wanneer die lys oop is: maak dit weer toe.",
};

const BRIEWE_PARTYE = {
  partye_opskrif: "Klein etiket in HOOFLETTERS bo 'n blok op die tuisblad met die amptelike verklarings van politieke partye.",
  partye_onderskrif: "Een of twee sinne wat die leser moet weet om die blok te vertrou: dit is elke party in die Parlement se jongste amptelike verklaring (een per party), in alfabetiese volgorde; Nuuspod vertaal dit met KI in Afrikaans en 'n mens kontroleer dit voordat dit verskyn. Geen party word genoem nie.",
  partye_lees: "Kort skakelteks op 'n kaart wat na die blad met die hele vertaalde verklaring gaan.",
  partye_bladtitel: "Blaaiertitel van die blad met een verklaring. {q} = die Afrikaanse opskrif van die verklaring. Eindig met ' — Verkiesing 2026'.",
  partye_beskrywing: "Meta-beskrywing vir soekenjins en deelkaarte: dit is die party se amptelike verklaring, met KI in Afrikaans vertaal. {q} = die party se naam. Geen ander bewering nie.",
  partye_logo_alt: "Alt-teks vir die party se logo. {q} = die party se naam.",
  partye_terug: "Skakel onderaan 'n verklaring terug na die tuisblad se blok met die partye se verklarings.",
  partye_vertaal_etiket: "Kort etiket voor 'n skakel na die oorspronklike Engelse verklaring: die teks hierbo is met KI uit Engels vertaal.",
  partye_afrikaans_etiket: "Kort etiket voor 'n skakel na die oorspronklike: hierdie party het die verklaring self in Afrikaans gepubliseer (dus nie vertaal nie).",
};

const aktieweBriewe = () =>
  PLAASLIK ? BRIEWE_PLAASLIK : UITSLAG2021 ? BRIEWE_UITSLAG2021 : KANDIDAAT ? BRIEWE_KANDIDAAT : UITVOU ? BRIEWE_UITVOU : PARTYE ? BRIEWE_PARTYE : BRIEWE;

const plekhouers = (s) => (s.match(/\{[a-z]\}/g) ?? []).sort().join(",");
const woorde = (s) => s.split(/\s+/).filter(Boolean).length;
const woordLimiet = (konsep) => Math.max(3, Math.ceil(woorde(konsep) * 1.3) + 2);

// What each slot is for, where the draft alone does not say enough.
const BRIEWE = {
  nav_vind_wyk: "Navigasieskakel in die kopstuk na die wyk-soeker.",
  soek_etiket: "Klein etiket in HOOFLETTERS bo die soekblok in die tuisblad se heldblok.",
  soek_titel: "Opskrif van die soekblok: jy vind hier jou wyk, stemlokaal en kandidate.",
  soek_plekhouer: "Plekhouer in die soekveld; sê wat jy kan intik.",
  soek_ligging_knoppie: "Knoppie wat die leser se huidige ligging gebruik om die wyk te vind.",
  soek_ligging_besig: "Kort statusteks terwyl die ligging gesoek word; eindig met 'n ellips (…).",
  soek_groep_plekke: "Groepopskrif in die aftreklys: plekke (voorstede, dorpe).",
  soek_groep_stemlokale: "Groepopskrif in die aftreklys: stemlokale.",
  soek_resultate_telling: "Skermleser-aankondiging van die aantal resultate. {n} = aantal, {q} = soekterm.",
  soek_resultate_telling_een: "Enkelvoud van die vorige; {q} = soekterm.",
  soek_wyk_nommer: "Etiket vir 'n wyk; {n} = wyknommer.",
  soek_wyk_aantal: "Hoeveel wyke 'n plek oorspan; {n} = aantal.",
  soek_wyke_kies: "'n Plek val oor meer as een wyk en die leser moet sy wyk kies. {q} = die plek se naam, {n} = aantal wyke.",
  soek_geen: "Geen resultate. Reël 1: stelling met {q} = soekterm. '\\n' en dan reël 2: raad (probeer die stemlokaal se naam of gebruik jou ligging).",
  soek_ligging_geweier: "Ligging kon nie verkry word nie. Reël 1: stelling. '\\n' en dan reël 2: raad (tik eerder voorstad, dorp of stemlokaal).",
  soek_ligging_buite: "Die ligging val in geen wyk nie. Reël 1: stelling. '\\n' en dan reël 2: waarom dit gebeur (naby die see of op 'n grens) en raad om eerder op stemlokaal te soek.",
  soek_registrasie_skakel: "Skakel na die afdeling oor hoe om registrasie by die OVK na te gaan.",
  wyk_kruimel_tuis: "Eerste skakel in die kruimelspoor, na die verkiesingstuisblad. Behou 'Verkiesing 2026' presies.",
  wyk_bladtitel: "Blaaiertitel. {w} = wyknommer, {q} = munisipaliteit. Eindig met ' — Verkiesing 2026'.",
  wyk_beskrywing: "Meta-beskrywing vir soekenjins en deelkaarte. {w}, {q} soos hierbo. Noem 4 November 2026.",
  wyk_raadslid_opskrif: "Opskrif van 'n kort verduideliking van wat 'n wyksraadslid doen.",
  wyk_raadslid_teks: "Twee of drie sinne, slegs uit die feite: wat 'n wyksraadslid doen. Geen bewerings buite die feite nie.",
  wyk_stemlokale_opskrif: "Opskrif bo die lys stemlokale. {n} = aantal, {w} = wyknommer.",
  wyk_stemlokale_opskrif_een: "Enkelvoud van die vorige; {w} = wyknommer.",
  wyk_stemlokale_nota: "Herinnering: jy stem net by die stemlokaal waar jy geregistreer is.",
  wyk_stemlokale_geen: "Daar is geen stemlokale vir die wyk om te wys nie.",
  wyk_stembriewe_opskrif: "Opskrif bo die leser se stembriewe.",
  stembrief_teller: "Klein teller op elke stembriefkaart. {n} = watter een, {m} = hoeveel.",
  stembrief_wyk: "Naam van die wykstembrief.",
  stembrief_wyk_uitleg: "Een sin: op hierdie stembrief kies jy een kandidaat as wyksraadslid vir wyk {w}.",
  stembrief_pv: "Naam van die plaaslike raad se proporsionele stembrief; {q} = raad se naam.",
  stembrief_pv_uitleg: "Een sin: jy stem vir 'n party; die setels word uit die partye se lyste gevul (proporsioneel).",
  stembrief_distrik: "Naam van die distriksraad se proporsionele stembrief; {q} = distrik se naam.",
  stembrief_distrik_uitleg: "Een sin: jy stem vir 'n party in die distriksraad.",
  volgorde_alfabeties: "Klein kenteken: die lys is alfabeties gesorteer.",
  volgorde_stembrief: "Klein kenteken: die lys volg die volgorde op die stembrief.",
  onafhanklik: "Etiket vir 'n onafhanklike kandidaat (geen party nie).",
  wys_lys: "Knoppie wat 'n party se kandidaatlys oopmaak.",
  versteek_lys: "Knoppie wat die lys weer toemaak.",
  kandidate_nog_nie_gelaai: "Daar is nog geen kandidate om te wys nie. Mag noem dat die OVK die finale kandidaatlyste op 16 September 2026 publiseer. Beloof NIKS oor Nuuspod nie.",
  laas_bygewerk: "Wanneer die data laas bygewerk is; {q} = 'n datum.",
  bron_ovk: "Bronvermelding. Behou die eiename presies: OVK (IEC), Munisipale Afbakeningsraad, Statistiek Suid-Afrika, Sensus 2011, en 'eie verwerking'.",
  bron_ovk_skakel: "Skakel na die OVK se eie lys.",
  og_wyk_sjabloon: "Kort reël op 'n deelkaart. {n} = aantal wykkandidate; noem stemdag 4 November.",
  og_wyk_geen: "Kort reël op 'n deelkaart sonder kandidate; noem stemdag 4 November.",
  og_masthead: "Deelkaart se kopreël. Behou 'Verkiesing 2026' presies.",
  og_wyk_alt: "Alt-teks vir die deelkaart; generies (noem geen wyk nie).",
  kruimelspoor_etiket: "Skermleser-etiket vir die kruimelspoor-navigasie.",
  bron_nota_setels_2021: "Nota: die 2021-setels kom uit die OVK se amptelike uitslae.",
  muni_tipe_plaaslik: "Tipe-etiket: plaaslike munisipaliteit.",
  muni_tipe_metro: "Tipe-etiket: metropolitaanse munisipaliteit (kort).",
  muni_tipe_distrik: "Tipe-etiket: distriksraad / distriksmunisipaliteit.",
  muni_bladtitel: "Blaaiertitel; {q} = munisipaliteit. Eindig met ' — Verkiesing 2026'.",
  muni_beskrywing: "Meta-beskrywing; {q} = munisipaliteit. Wyke, partye op die stembrief, die raad ná 2021; noem 4 November 2026.",
  muni_onderskrif_distrik: "Onderskrif-deel; {q} = distrik se naam, bv. '{q}-distrik'.",
  muni_wyke_aantal: "{n} = aantal wyke.",
  muni_wyke_aantal_een: "Enkelvoud: een wyk.",
  muni_wyke_opskrif: "Opskrif bo die wykrooster.",
  muni_geen_wyke: "Een sin op 'n distriksraad se blad: hierdie raad het nie sy eie wyke nie. Niks meer nie.",
  muni_partye_opskrif: "Opskrif bo die lys partye wat in die munisipaliteit meeding.",
  muni_partye_nog_nie_gelaai: "Daar is nog geen partye om te wys nie. Mag noem dat die OVK die finale kandidaatlyste op 16 September 2026 publiseer. Beloof NIKS oor Nuuspod nie.",
  muni_2021_opskrif: "Opskrif: die raad se samestelling ná die 2021-verkiesing, amptelike uitslae.",
  muni_2021_raadsgrootte: "{n} = totale aantal setels in die raad.",
  muni_2021_geen_meerderheid: "Een sin: geen party het ná 2021 'n meerderheid in hierdie raad gehad nie.",
  muni_2021_kolom_party: "Tabelkolom: party.",
  muni_2021_kolom_wyk: "Tabelkolom: wyksetels.",
  muni_2021_kolom_pv: "Tabelkolom: PV-setels (proporsionele verteenwoordiging).",
  muni_2021_kolom_totaal: "Tabelkolom: totaal.",
  muni_2021_onafhanklikes: "Tabelry: onafhanklike raadslede.",
  muni_2021_geen_data: "Skermleser-teks vir 'n sel sonder data.",
  muni_2021_wys_sonder_setels: "Knoppie; {n} = aantal partye sonder setels wat versteek is.",
  muni_2021_versteek_sonder_setels: "Knoppie wat daardie partye weer versteek.",
  muni_2021_sortering: "Klein kenteken: die tabel is op partynaam gesorteer.",
  nie_gevind_titel: "Blaaiertitel van die 404-blad. Eindig met ' — Verkiesing 2026'.",
  nie_gevind_opskrif: "Opskrif: bladsy nie gevind nie.",
  nie_gevind_teks: "Een sin: die blad bestaan nie, of die wyk- of munisipaliteitskode in die adres is verkeerd.",
  nie_gevind_tuis: "Skakel terug na die tuisblad.",
  nie_gevind_soek: "Skakel na die wyk-soeker.",
};

const BRIEWE_PLAASLIK = {
  plaaslik_opskrif: "Klein etiket in HOOFLETTERS bo 'n blok plaaslike nuusopskrifte op 'n wyk- of munisipaliteitsblad.",
  plaaslik_onderskrif: "Een sin: dit is opskrifte presies soos plaaslike (gemeenskaps)koerante dit gepubliseer het, met skakels na die oorspronklike berigte. Geen belofte nie.",
  plaaslik_omgewing: "Kort opskrif vir nuus uit die leser se eie buurt/voorstad (1–3 wyke).",
  plaaslik_dorp: "Kort opskrif vir nuus uit 'n groter dorp of gebied; {q} = die dorp se naam, bv. 'In {q}'.",
  plaaslik_munisipaliteit: "Kort opskrif vir nuus oor die hele munisipaliteit; {q} = munisipaliteit se naam.",
  plaaslik_muni_opskrif: "Klein etiket in HOOFLETTERS of kort opskrif bo plaaslike nuus op 'n munisipaliteitsblad; {q} = munisipaliteit se naam.",
};

const FEITE = [
  "Die plaaslike verkiesing is op Woensdag 4 November 2026; stemlokale is oop van 07:00 tot 21:00.",
  "Jy mag net stem by die stemlokaal waar jy geregistreer is.",
  "Die OVK publiseer die finale kandidaatlyste op 16 September 2026.",
  "Die trekking op 23 September 2026 bepaal die volgorde van partye op die stembriewe.",
  "'n Wyksraadslid word deur die kiesers van een wyk verkies, verteenwoordig daardie wyk in die munisipale raad, en is die voorsitter van die wykkomitee wat die gemeenskap se sienings na die raad bring.",
  "In elke munisipaliteit met wyke word ongeveer die helfte van die raad as wyksraadslede verkies; die res van die setels word uit partye se lyste gevul (proporsionele verteenwoordiging), sodat die raad as geheel die partye se steun weerspieël.",
  "Kiesers in 'n plaaslike munisipaliteit kry 3 stembriewe: wyk, die plaaslike raad se PV-stembrief, en die distriksraad se PV-stembrief. Kiesers in 'n metro kry 2: wyk en die metroraad se PV-stembrief.",
  "Die vorige plaaslike verkiesing was op 1 November 2021; die OVK publiseer amptelike uitslae per stemdistrik.",
  "Die data kom van die OVK (IEC), die Munisipale Afbakeningsraad en Statistiek Suid-Afrika (Sensus 2011), met Nuuspod se eie verwerking.",
  "Die tuisblad wys die amptelike persverklarings van die partye met setels in die Nasionale Vergadering (die Parlement): per party net die jongste een, in alfabetiese volgorde van die partyname. Engelse verklarings word met KI in Afrikaans vertaal; 'n redakteur by Nuuspod keur elke verklaring goed voordat dit verskyn. Party wat self in Afrikaans publiseer, word nie vertaal nie.",
];

function prompt(gleuwe) {
  const lys = Object.entries(gleuwe).map(([k, konsep]) => ({
    sleutel: k,
    doel: aktieweBriewe()[k] ?? "",
    konsep,
    plekhouers: plekhouers(konsep) || "geen",
    maks_woorde: woordLimiet(konsep),
  }));
  return `Jy skryf die Afrikaanse koppelvlakteks vir Nuuspod se webwerf oor die Suid-Afrikaanse plaaslike verkiesing van 2026: 'n wyk-soeker, 'n wykblad, 'n munisipaliteitsblad, 'n 404-blad en 'n blok plaaslike nuusopskrifte uit gemeenskapskoerante.

STEM
- Direk, warm, alledaagse Suid-Afrikaanse Afrikaans. Spreek die leser aan as "jy".
- Geen uitroeptekens, geen emoji. Nie vertaalde Engels nie; skryf soos 'n Afrikaanse redakteur.
- Gewone sinsbou-hoofletters (net die eerste woord en eiename), behalwe waar die konsep HOOFLETTERS gebruik vir 'n etiket.
- Gebruik korrekte Afrikaanse spelling en samestellings.

REËLS
- Gebruik NET die feite hieronder. Moenie getalle, datums, wette of bewerings uitdink nie.
- Noem nooit 'n party of kandidaat nie.
- Beloof nooit 'n Nuuspod-funksie of -datum nie (bv. nooit "kom binnekort" of "word later bygevoeg" nie).
- Behou elke plekhouer ({n}, {m}, {q}, {w}) presies soos gegee, en voeg geen nuwes by nie.
- Waar die konsep "\\n" bevat, behou presies een "\\n" tussen die twee reëls.
- Bly binne maks_woorde vir elke gleuf.
- Behou eiename presies: OVK, IEC, "Verkiesing 2026", Munisipale Afbakeningsraad, Statistiek Suid-Afrika, Sensus 2011.
- Die konsep is 'n rigtingwyser, nie heilig nie: verbeter dit waar jy kan, maar hou die betekenis.

FEITE
${FEITE.map((f) => `- ${f}`).join("\n")}

GLEUWE (JSON)
${JSON.stringify(lys, null, 2)}

Gee 'n JSON-objek terug met presies hierdie sleutels (${lys.length}), elke waarde die finale teks as 'n string.`;
}

function kontroleer(gleuwe, uit) {
  const foute = [];
  for (const [k, konsep] of Object.entries(gleuwe)) {
    const w = uit[k];
    if (typeof w !== "string" || !w.trim()) { foute.push(`${k}: ontbreek`); continue; }
    if (plekhouers(w) !== plekhouers(konsep)) foute.push(`${k}: plekhouers ${plekhouers(w)} ≠ ${plekhouers(konsep)}`);
    if ((w.match(/\n/g) ?? []).length !== (konsep.match(/\n/g) ?? []).length) foute.push(`${k}: reëlbreuke verskil`);
    if (woorde(w) > woordLimiet(konsep)) foute.push(`${k}: ${woorde(w)} woorde > ${woordLimiet(konsep)}`);
    if (/!/.test(w)) foute.push(`${k}: uitroepteken`);
    if (/Die Buitelyn/.test(w)) foute.push(`${k}: "Die Buitelyn"`);
    if (/binnekort|later bygevoeg|kom op \d/i.test(w)) foute.push(`${k}: klink na 'n belofte`);
  }
  for (const k of Object.keys(uit)) if (!(k in gleuwe)) foute.push(`${k}: onbekende sleutel`);
  return foute;
}

async function hoof() {
  const gleuwe = leesGleuwe();
  const nieGevind = Object.keys(aktieweBriewe()).filter((k) => !(k in gleuwe));
  if (nieGevind.length) throw new Error(`Nie in kopie.ts nie: ${nieGevind.join(", ")}`);

  const antwoord = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": sleutel() },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt(gleuwe) }] }],
        generationConfig: {
          responseMimeType: "application/json",
          // Pinned keys: without a schema Gemini "corrects" kandidate_… to kandidates_….
          responseSchema: {
            type: "OBJECT",
            properties: Object.fromEntries(Object.keys(gleuwe).map((k) => [k, { type: "STRING" }])),
            required: Object.keys(gleuwe),
            propertyOrdering: Object.keys(gleuwe),
          },
          temperature: 0.4,
        },
      }),
    }
  );
  if (!antwoord.ok) throw new Error(`Gemini ${antwoord.status}: ${(await antwoord.text()).slice(0, 300)}`);
  const data = await antwoord.json();
  const teks = data.candidates?.[0]?.content?.parts?.map((p) => p.text ?? "").join("") ?? "";
  const uit = JSON.parse(teks);

  const geordend = Object.fromEntries(Object.keys(gleuwe).map((k) => [k, uit[k]]));
  writeFileSync(UIT, JSON.stringify(geordend, null, 2) + "\n");
  const foute = kontroleer(gleuwe, uit);
  console.log(`${Object.keys(gleuwe).length} gleuwe → ${UIT}`);
  if (foute.length) {
    console.error(`${foute.length} kontrolefout(e):\n- ${foute.join("\n- ")}`);
    process.exit(1);
  }
  console.log("Meganiese kontroles: alles geslaag.");
}

hoof().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
