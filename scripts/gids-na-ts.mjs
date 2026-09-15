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
