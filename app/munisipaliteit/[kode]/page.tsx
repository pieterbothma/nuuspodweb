import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BronStrook, haalBronDatum, OVK_LYS_SKAKEL } from "@/app/_components/verkiesing/bron-strook";
import { Kopstuk } from "@/app/_components/verkiesing/kopstuk";
import { Raad2021Tabel } from "@/app/_components/verkiesing/raad-2021";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";
import { Voet } from "@/app/_components/verkiesing/voet";
import { WykRooster } from "@/app/_components/verkiesing/wyk-rooster";
import { MuniNuus } from "@/app/_components/verkiesing/plaaslike-nuus";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { haalMuniNuus } from "@/lib/verkiesing/plaaslik";
import { distrikNaam, muniNaam, provinsieNaam } from "@/lib/verkiesing/name";
import { vergelykNaam, type Volgorde } from "@/lib/verkiesing/orden";
import { geldigeMuniKode, haalMuni, type MuniOpsomming } from "@/lib/verkiesing/wyksoeker";

/**
 * A municipality: the wards a reader can pick theirs from, the parties contesting it, and
 * how its council looked after 2021. `Munisipaliteit.dc.html` in code.
 *
 * Three shapes have to read sensibly, because all three are real rows:
 *  - a **local municipality** (WC024): district + province + ward count, wards, 2021 council;
 *  - a **metro** (TSH): no district anywhere on the page;
 *  - a **district council** (DC2): no wards of its own and no 2021 council result of its own,
 *    so the ward grid becomes one sentence and the 2021 section is simply not rendered —
 *    better than a heading over an empty table.
 *
 * As with the ward page there is no `generateStaticParams`: the page is built on demand and
 * the data layer's reads carry the caching (`revalidate: 3600`, tags `wyke` / `kandidate`).
 */
export const dynamicParams = true;

type Props = { params: Promise<{ kode: string }> };

/** "Cape Winelands-distrik · Wes-Kaap · 23 wyke" — each clause only when it applies. */
function onderskrif(muni: MuniOpsomming): string[] {
  const dele: string[] = [];
  if (muni.distrik_naam) {
    const q = distrikNaam(muni.distrik_kode ?? "", muni.distrik_naam);
    dele.push(vulIn(KOPIE.muni_onderskrif_distrik, { q }));
  }
  dele.push(provinsieNaam(muni.provinsie));
  if (muni.wyke.length === 1) dele.push(KOPIE.muni_wyke_aantal_een);
  else if (muni.wyke.length > 1) dele.push(vulIn(KOPIE.muni_wyke_aantal, { n: muni.wyke.length }));
  return dele;
}

/**
 * A district council is a row in `munisipaliteite` too, so its own page's heading goes
 * through the district map rather than the metro map.
 */
function vertoonNaam(muni: MuniOpsomming): string {
  return muni.tipe === "distrik"
    ? distrikNaam(muni.kode, muni.naam)
    : muniNaam(muni.kode, muni.naam);
}

function tipeEtiket(tipe: string): string {
  if (tipe === "metro") return KOPIE.muni_tipe_metro;
  if (tipe === "distrik") return KOPIE.muni_tipe_distrik;
  return KOPIE.muni_tipe_plaaslik;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { kode } = await params;
  // An unknown code renders the site's 404, and a `notFound()` from a dynamic segment keeps
  // whatever title this function returned — so return the 404's own title, not an empty
  // object, which would leave the root layout's homepage title on a 404.
  const nieGevind: Metadata = {
    title: KOPIE.nie_gevind_titel,
    robots: { index: false, follow: true },
  };
  if (!geldigeMuniKode(kode)) return nieGevind;
  // The same read the page makes, deduplicated by Next's fetch cache within the request.
  const muni = await haalMuni(kode);
  if (!muni) return nieGevind;
  const naam = vertoonNaam(muni);
  const titel = vulIn(KOPIE.muni_bladtitel, { q: naam });
  const beskrywing = vulIn(KOPIE.muni_beskrywing, { q: naam });
  return {
    title: titel,
    description: beskrywing,
    openGraph: {
      title: titel,
      description: beskrywing,
      url: `https://www.nuuspod.co.za/munisipaliteit/${muni.kode}`,
    },
  };
}

/**
 * The contesting parties with equal space each and no colour or logo: alphabetical before the
 * ballot draw, in drawn ballot order after it. The chip is a claim about what the reader is
 * looking at, so before the draw this component sorts itself rather than trusting its input.
 */
function KontesterendePartye({ partye, volgorde }: { partye: string[]; volgorde: Volgorde }) {
  const gesorteer = volgorde === "stembrief" ? partye : [...partye].sort(vergelykNaam);
  return (
    <section aria-labelledby="partye-opskrif" className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h2
          id="partye-opskrif"
          className="text-rooi-teks flex-1 font-sans text-xs font-bold tracking-[0.22em] uppercase"
        >
          {KOPIE.muni_partye_opskrif}
        </h2>
        <span className="border-rand text-grys shrink-0 border px-2.5 py-1 font-sans text-[0.6875rem] font-bold tracking-[0.16em] whitespace-nowrap uppercase">
          {volgorde === "stembrief" ? KOPIE.volgorde_stembrief : KOPIE.volgorde_alfabeties}
        </span>
      </div>
      {gesorteer.length === 0 ? (
        // The same sentence covers "not loaded yet" and "database unreachable": the data
        // layer returns the same empty list for both, so this states what is on the page.
        <p className="text-grys font-sans text-[0.9375rem]">{KOPIE.muni_partye_nog_nie_gelaai}</p>
      ) : (
        // Every party is listed. The mockup's "+ 14 meer" truncation is not implemented:
        // equal space per party beats hiding some of them behind a count.
        <ul className="border-rand border-b">
          {gesorteer.map((p) => (
            <li
              key={p}
              data-kontesterende-party
              className="border-rand text-ink border-t py-3 font-sans text-[0.9375rem] font-bold"
            >
              {p}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default async function MuniBladsy({ params }: Props) {
  const { kode } = await params;
  // A code that cannot be a municipality is a 404 before any request goes out.
  if (!geldigeMuniKode(kode)) notFound();

  const muni = await haalMuni(kode);
  if (!muni) notFound();

  const [bronDatum, nuus] = await Promise.all([haalBronDatum(), haalMuniNuus(muni.kode)]);
  const naam = vertoonNaam(muni);

  return (
    <>
      <Kopstuk />
      <main className="mx-auto max-w-6xl px-5 pt-8 pb-10 sm:px-8 sm:pt-11">
        <nav aria-label={KOPIE.kruimelspoor_etiket} className="text-grys font-sans text-sm">
          <Link
            href="/"
            className="text-grys hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
          >
            {KOPIE.wyk_kruimel_tuis}
          </Link>{" "}
          › <span aria-current="page">{naam}</span>
        </nav>

        <p className="text-ink mt-4.5 font-sans text-xs font-bold tracking-[0.22em] uppercase">
          {tipeEtiket(muni.tipe)}
        </p>

        <h1 className="text-ink mt-2.5 font-display text-[3.25rem] leading-[0.92] tracking-[-0.02em] text-balance sm:text-7xl lg:text-8xl">
          {naam}
        </h1>

        <p data-onderskrif className="text-grys mt-3.5 font-sans text-[1.0625rem] sm:text-xl">
          {onderskrif(muni).map((deel, i) => (
            <span key={deel} {...(i === 0 && muni.distrik_naam ? { "data-distrik": "" } : {})}>
              {i > 0 ? " · " : ""}
              {deel}
            </span>
          ))}
        </p>

        <div className="mt-9 grid gap-9 lg:mt-12 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start lg:gap-12">
          {/* min-w-0: without it the grid item's automatic minimum is the 2021 table's
              min-width, and the whole page scrolls sideways on a phone instead of the
              table scrolling inside its own container. */}
          <div className="flex min-w-0 flex-col gap-9 lg:gap-12">
            <WykRooster wyke={muni.wyke} />
            {/* No 2021 row for this council (a district, or a newly demarcated one): the
                section is absent rather than empty. */}
            {muni.raad2021 && (
              <div className="border-rand border-t pt-8">
                <Raad2021Tabel raad={muni.raad2021} />
              </div>
            )}
          </div>
          <KontesterendePartye partye={muni.partye} volgorde={muni.volgorde} />
        </div>

        <div className="border-rand mt-12 border-t pt-8 lg:mt-14">
          <MuniNuus stories={nuus} muniNaam={naam} nou={new Date()} />
        </div>

        {/* The footer asks the feedback question, so the strip does not — the reader is
            asked once. The strip's second line qualifies the 2021 seat figures above it. */}
        <BronStrook
          bronDatum={bronDatum}
          bronSkakel={OVK_LYS_SKAKEL}
          nota={KOPIE.bron_nota_setels_2021}
          metTerugvoer={false}
        />
      </main>
      <Voet />
    </>
  );
}
