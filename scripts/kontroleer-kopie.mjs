// Brand, promise and personal-data checks over the site's source and its built pages.
//
// Run: node scripts/kontroleer-kopie.mjs   (after `npm run build` to include the built pages)
//
// Fails (exit 1) with file:line for:
//   - "Die Buitelyn" anywhere (the brand is "Buitelyn");
//   - launch-promise wording: the site never announces an upcoming Nuuspod feature or date;
//   - any 6+ digit run in lib/verkiesing/kopie.ts (an ID number must never be in copy).
// Tests and this script are skipped: they contain the patterns on purpose.

import fs from "node:fs";
import path from "node:path";

const WORTEL = path.resolve(new URL("..", import.meta.url).pathname);

const REËLS = [
  { naam: "Die Buitelyn", patroon: /Die Buitelyn/ },
  {
    naam: "lanseerbelofte",
    patroon: /kom binnekort|binnekort beskikbaar|vanaf \d(?!\d?:\d\d)|word gelaai op|word later bygevoeg|kom op \d{1,2} (Januarie|Februarie|Maart|April|Mei|Junie|Julie|Augustus|September|Oktober|November|Desember)/i,
  },
];

function lêers(gids, pas) {
  const volle = path.join(WORTEL, gids);
  if (!fs.existsSync(volle)) return [];
  const uit = [];
  for (const e of fs.readdirSync(volle, { withFileTypes: true })) {
    const rel = path.join(gids, e.name);
    if (e.isDirectory()) {
      if (e.name === "node_modules" || e.name === "__tests__" || e.name === "cache") continue;
      uit.push(...lêers(rel, pas));
    } else if (pas.test(e.name) && !/\.test\.tsx?$/.test(e.name)) {
      uit.push(rel);
    }
  }
  return uit;
}

const bron = [
  ...lêers("app", /\.(tsx?|mdx?|json)$/),
  ...lêers("lib", /\.(tsx?|json)$/),
  ...lêers("content", /\.(mdx?|json)$/),
  ...lêers("docs/verkiesing", /^ui-kopie.*\.json$/),
];
// The rendered HTML and RSC payloads Next wrote for the prerendered pages.
const gebou = lêers(".next/server/app", /\.(html|rsc|body)$/);

const foute = [];
for (const rel of [...bron, ...gebou]) {
  const reëls = fs.readFileSync(path.join(WORTEL, rel), "utf8").split("\n");
  reëls.forEach((reël, i) => {
    for (const { naam, patroon } of REËLS) {
      const m = reël.match(patroon);
      if (m) foute.push(`${rel}:${i + 1}: ${naam} — "${m[0]}"`);
    }
  });
}

const kopie = "lib/verkiesing/kopie.ts";
fs.readFileSync(path.join(WORTEL, kopie), "utf8")
  .split("\n")
  .forEach((reël, i) => {
    if (/\d{6,}/.test(reël)) foute.push(`${kopie}:${i + 1}: 6+-syferreeks (moontlike ID-nommer)`);
  });

console.log(`${bron.length} bronlêers, ${gebou.length} geboude lêers nagegaan.`);
if (gebou.length === 0) console.log("Let wel: geen .next-uitset nie — hardloop eers `npm run build` om die geboude blaaie te dek.");
if (foute.length) {
  console.error(`${foute.length} fout(e):\n${foute.join("\n")}`);
  process.exit(1);
}
console.log("Geen fout nie.");
