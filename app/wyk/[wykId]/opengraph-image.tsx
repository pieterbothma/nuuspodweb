import fs from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";
import { ImageResponse } from "next/og";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { muniNaam } from "@/lib/verkiesing/name";
import { geldigeWykId, haalStembriewe, haalWyk } from "@/lib/verkiesing/wyksoeker";

/**
 * The ward's share card — `Deelkaart.dc.html` in code: white ground, the neon gradient as an
 * 8 px frame, the masthead, "Wyk N" with the number in red, the municipality, and how many
 * candidates are on the ward ballot.
 *
 * **No party names, logos or colours** ever reach this card: a share image is the one place
 * where a single party could be given free prominence, so it names none.
 *
 * `next/og` cannot fetch the site's own webfonts, so the two faces are read off disk. That
 * needs the Node runtime (the default here — do not switch this route to edge).
 */

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
/** Next only allows a static `alt`, so it describes the card without naming a ward. */
export const alt = KOPIE.og_wyk_alt;

const INK = "#0b0d10";
const ROOI = "#e53935";

function leesLeer(relatief: string): Buffer {
  return fs.readFileSync(path.join(process.cwd(), relatief));
}

/** Satori has no network, so the logo rides along as a data URI. */
function logoUri(): string {
  return `data:image/jpeg;base64,${leesLeer("public/logo.jpg").toString("base64")}`;
}

export default async function DeelKaart({ params }: { params: Promise<{ wykId: string }> }) {
  const { wykId } = await params;
  const wyk = geldigeWykId(wykId) ? await haalWyk(wykId) : null;
  // The card 404s with the page it belongs to: a 200 PNG reading "Wyk" with no number would
  // be a share image for a ward that does not exist.
  if (!wyk) notFound();
  // A ward ballot's candidate count — the figure a reader can check against the page itself.
  const aantal = (await haalStembriewe(wyk)).wyk.length;
  const onderaan = aantal > 0 ? vulIn(KOPIE.og_wyk_sjabloon, { n: aantal }) : KOPIE.og_wyk_geen;
  const [voor] = KOPIE.soek_wyk_nommer.split("{n}");
  const naam = muniNaam(wyk.muni_kode, wyk.muni_naam);

  const display = leesLeer("public/fonts/DMSerifDisplay-Regular.ttf");
  const sansNormaal = leesLeer("public/fonts/SourceSans3-Regular.ttf");
  const sansVet = leesLeer("public/fonts/SourceSans3-Bold.ttf");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#ffffff",
          padding: 28,
        }}
      >
        {/* The gradient sits behind an 8 px inset white panel — the single-element neon
            frame, drawn the way Satori can actually paint it. */}
        <div
          style={{
            display: "flex",
            flex: 1,
            padding: 8,
            background: "linear-gradient(120deg, #00d2fa, #fa2229)",
          }}
        >
          <div
            style={{
              display: "flex",
              flex: 1,
              flexDirection: "column",
              justifyContent: "space-between",
              background: "#ffffff",
              padding: "48px 64px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center" }}>
              {/* Satori renders this itself; next/image has no part in an OG card. */}
              <img src={logoUri()} alt="" width={64} height={64} style={{ borderRadius: 999 }} />
              <div style={{ display: "flex", flexDirection: "column", marginLeft: 16 }}>
                <div
                  style={{
                    fontFamily: "Display",
                    fontSize: 32,
                    letterSpacing: "0.14em",
                    color: INK,
                  }}
                >
                  NUUSPOD
                </div>
                <div
                  style={{
                    fontFamily: "Sans",
                    fontSize: 16,
                    fontWeight: 700,
                    letterSpacing: "0.18em",
                    marginTop: 6,
                    color: INK,
                  }}
                >
                  {KOPIE.og_masthead.toUpperCase()}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column" }}>
              <div
                style={{
                  display: "flex",
                  fontFamily: "Display",
                  fontSize: 150,
                  lineHeight: 0.88,
                  letterSpacing: "-0.02em",
                  color: INK,
                }}
              >
                {/* A trailing ordinary space collapses in Satori's flex row. */}
                <span>{voor.replace(/\s+$/, " ")}</span>
                <span style={{ color: ROOI }}>{wyk.wyk_nr}</span>
              </div>
              {naam && (
                <div
                  style={{
                    fontFamily: "Display",
                    // Long council names would run off a 1,200 px card at 52 px.
                    fontSize: naam.length > 22 ? 40 : 52,
                    // 24, not the mockup's 12: at lineHeight 0.88 the 150 px line above has
                    // no room for its descenders, so 12 px reads as a collision.
                    marginTop: 24,
                    color: INK,
                  }}
                >
                  {naam}
                </div>
              )}
            </div>

            <div style={{ fontFamily: "Sans", fontSize: 26, fontWeight: 700, color: INK }}>
              {onderaan}
            </div>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Display", data: display, weight: 400, style: "normal" },
        { name: "Sans", data: sansNormaal, weight: 400, style: "normal" },
        { name: "Sans", data: sansVet, weight: 700, style: "normal" },
      ],
    }
  );
}
