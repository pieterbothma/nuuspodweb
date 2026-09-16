import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BronStrook, haalBronDatum, OVK_LYS_SKAKEL } from "@/app/_components/verkiesing/bron-strook";
import { Kopstuk } from "@/app/_components/verkiesing/kopstuk";
import { Stembriewe, vulIn } from "@/app/_components/verkiesing/stembriewe";
import { StemlokaleLys } from "@/app/_components/verkiesing/stemlokale-lys";
import { Uitslag2021 } from "@/app/_components/verkiesing/uitslag-2021";
import { WykNuus } from "@/app/_components/verkiesing/plaaslike-nuus";
import { haalWykNuus } from "@/lib/verkiesing/plaaslik";
import { Voet } from "@/app/_components/verkiesing/voet";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { muniNaam, provinsieNaam } from "@/lib/verkiesing/name";
import {
  geldigeWykId,
  haalStembriewe,
  haalStemstasies,
  haalWyk,
  haalWykUitslag2021,
} from "@/lib/verkiesing/wyksoeker";

/**
 * The page a voter lands on: their ballots, what a ward councillor does, and their ward's
 * voting stations.
 *
 * 4,485 wards is too many to prerender, so there is no `generateStaticParams`: a ward is
 * built the first time someone asks for it and then cached (the data layer's reads carry
 * `revalidate: 3600` and the `wyke` / `kandidate` tags).
 */
export const dynamicParams = true;

type Props = { params: Promise<{ wykId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { wykId } = await params;
  // An unknown ward renders the site's 404, and a `notFound()` from a dynamic segment keeps
  // whatever title this function returned — so return the 404's own title, not an empty
  // object, which would leave the root layout's homepage title on a 404.
  const nieGevind: Metadata = { title: KOPIE.nie_gevind_titel, robots: { index: false, follow: true } };
  if (!geldigeWykId(wykId)) return nieGevind;
  // The same read the page makes, deduplicated by Next's fetch cache within the request.
  const wyk = await haalWyk(wykId);
  if (!wyk) return nieGevind;
  const waardes = { w: wyk.wyk_nr, q: muniNaam(wyk.muni_kode, wyk.muni_naam) };
  const titel = vulIn(KOPIE.wyk_bladtitel, waardes);
  const beskrywing = vulIn(KOPIE.wyk_beskrywing, waardes);
  return {
    title: titel,
    description: beskrywing,
    openGraph: {
      title: titel,
      description: beskrywing,
      url: `https://www.nuuspod.co.za/wyk/${wyk.wyk_id}`,
    },
  };
}

/** "Wyk {n}" with the number in red — the copy stays one slot, split on its placeholder. */
function WykOpskrif({ wykNr }: { wykNr: number }) {
  const [voor, na] = KOPIE.soek_wyk_nommer.split("{n}");
  return (
    <h1 className="text-ink mt-3.5 font-display text-[4.5rem] leading-[0.9] tracking-[-0.02em] sm:text-8xl lg:text-[7rem]">
      {voor}
      <span className="text-rooi">{wykNr}</span>
      {na}
    </h1>
  );
}

export default async function WykBladsy({ params }: Props) {
  const { wykId } = await params;
  // An id that cannot be a ward is a 404 before any request goes out.
  if (!geldigeWykId(wykId)) notFound();

  const wyk = await haalWyk(wykId);
  if (!wyk) notFound();

  const [stasies, stembriewe, bronDatum, nuus, uitslag2021] = await Promise.all([
    haalStemstasies(wyk.wyk_id),
    haalStembriewe(wyk),
    haalBronDatum(),
    haalWykNuus(wyk.wyk_id),
    haalWykUitslag2021(wyk.wyk_id),
  ]);

  const SKAKEL =
    "text-grys hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi";

  return (
    <>
      <Kopstuk />
      <main className="mx-auto max-w-6xl px-5 pt-8 pb-10 sm:px-8 sm:pt-11">
        <nav aria-label={KOPIE.kruimelspoor_etiket} className="text-grys font-sans text-sm">
          <Link href="/" className={SKAKEL}>
            {KOPIE.wyk_kruimel_tuis}
          </Link>{" "}
          ›{" "}
          <Link href={`/munisipaliteit/${wyk.muni_kode}`} className={SKAKEL}>
            {muniNaam(wyk.muni_kode, wyk.muni_naam)}
          </Link>{" "}
          › <span aria-current="page">{vulIn(KOPIE.soek_wyk_nommer, { n: wyk.wyk_nr })}</span>
        </nav>

        <WykOpskrif wykNr={wyk.wyk_nr} />

        <p className="text-ink mt-3.5 font-sans text-[1.0625rem] sm:text-xl">
          <Link
            href={`/munisipaliteit/${wyk.muni_kode}`}
            className="decoration-rand font-bold underline underline-offset-[5px] hover:decoration-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
          >
            {muniNaam(wyk.muni_kode, wyk.muni_naam)}
          </Link>{" "}
          <span className="text-grys">· {provinsieNaam(wyk.provinsie)}</span>
        </p>

        {/* Phone order: councillor, stations, ballots (the sidebar comes first in the DOM).
            Desktop puts both sidebar blocks in the second column of the same grid row. */}
        <div className="mt-9 grid gap-9 lg:mt-11 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start lg:gap-12">
          <div className="flex flex-col gap-9 lg:col-start-2 lg:row-start-1">
            <section aria-labelledby="raadslid" className="neon-raam-dun p-5 sm:px-6">
              <h2
                id="raadslid"
                className="text-ink font-sans text-xs font-bold tracking-[0.22em] uppercase"
              >
                {KOPIE.wyk_raadslid_opskrif}
              </h2>
              <p className="text-ink mt-2.5 font-sans text-base leading-relaxed">
                {KOPIE.wyk_raadslid_teks}
              </p>
            </section>
            <StemlokaleLys wykNr={wyk.wyk_nr} stasies={stasies} />
          </div>

          <div className="lg:col-start-1 lg:row-start-1">
            <Stembriewe wyk={wyk} stembriewe={stembriewe} />
            <div className="border-rand mt-12 border-t pt-8">
              <Uitslag2021 uitslag={uitslag2021} wykNr={wyk.wyk_nr} muniKode={wyk.muni_kode} />
            </div>
          </div>
        </div>

        <div className="border-rand mt-12 border-t pt-8 lg:mt-14">
          <WykNuus groepe={nuus} muniNaam={muniNaam(wyk.muni_kode, wyk.muni_naam)} nou={new Date()} />
        </div>

        {/* The footer asks the feedback question, so the strip does not: the ward page is the
            most-shared page in this drop and needs the footer's independence line and the
            Real411 link, not two "Het jy gekry wat jy gesoek het?" widgets. */}
        <BronStrook bronDatum={bronDatum} bronSkakel={OVK_LYS_SKAKEL} metTerugvoer={false} />
      </main>
      <Voet />
    </>
  );
}
