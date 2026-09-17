import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Kopstuk } from "@/app/_components/verkiesing/kopstuk";
import { vulIn } from "@/app/_components/verkiesing/stembriewe";
import { Voet } from "@/app/_components/verkiesing/voet";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { haalPartyverklaring, paragrawe, partyLogo } from "@/lib/verkiesing/partye";

/**
 * One approved party statement on its own page: logo, party, date, the Afrikaans headline and
 * text at a readable width, then what it is (AI-translated, or published in Afrikaans) with the
 * original headline linked to the party's site. Nuuspod adds no sentence of its own about the
 * party. Only approved statements exist here; anything else is the site's 404.
 */
export const dynamicParams = true;

type Props = { params: Promise<{ id: string }> };

const DATUM = new Intl.DateTimeFormat("af-ZA", {
  timeZone: "Africa/Johannesburg",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const v = await haalPartyverklaring(id);
  if (!v) return { title: KOPIE.nie_gevind_titel, robots: { index: false, follow: true } };
  const titel = vulIn(KOPIE.partye_bladtitel, { q: v.titel_af });
  const beskrywing = vulIn(KOPIE.partye_beskrywing, { q: v.party });
  return {
    title: titel,
    description: beskrywing,
    openGraph: { title: titel, description: beskrywing, url: `https://www.nuuspod.co.za/verklaring/${v.id}` },
  };
}

export default async function VerklaringBladsy({ params }: Props) {
  const { id } = await params;
  const v = await haalPartyverklaring(id);
  if (!v) notFound();
  const logo = partyLogo(v.party);

  return (
    <>
      <Kopstuk />
      <main className="mx-auto max-w-3xl px-5 pt-8 pb-10 sm:px-8 sm:pt-11">
        <nav aria-label={KOPIE.kruimelspoor_etiket} className="text-grys font-sans text-sm">
          <Link href="/" className="text-grys hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi">
            {KOPIE.wyk_kruimel_tuis}
          </Link>{" "}
          ›{" "}
          <Link href="/#wat-die-partye-se" className="text-grys hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi">
            {KOPIE.partye_opskrif.charAt(0) + KOPIE.partye_opskrif.slice(1).toLowerCase()}
          </Link>
        </nav>

        <article className="mt-7">
          <header className="flex items-center gap-4">
            {logo && (
              // eslint-disable-next-line @next/next/no-img-element -- small fixed-size local logo
              <img src={logo} alt={vulIn(KOPIE.partye_logo_alt, { q: v.party })} width={64} height={64} className="size-16 shrink-0 object-contain" />
            )}
            <div className="min-w-0">
              <p className="text-ink font-sans text-sm font-bold tracking-[0.14em] uppercase">{v.party}</p>
              <time dateTime={v.gepubliseer_om} className="text-grys font-sans text-sm">
                {DATUM.format(new Date(v.gepubliseer_om))}
              </time>
            </div>
          </header>

          <h1 className="text-ink mt-6 font-display text-[2rem] leading-[1.1] tracking-[-0.01em] text-balance sm:text-5xl">
            {v.titel_af}
          </h1>

          <div className="text-ink mt-7 grid gap-5 font-sans text-lg leading-relaxed">
            {paragrawe(v.teks_af).map((p, i) => (
              <p key={i} className="break-words whitespace-pre-line">{p}</p>
            ))}
          </div>

          <p data-bron className="border-rand text-grys mt-10 border-t pt-5 font-sans text-sm">
            {v.vertaal ? KOPIE.partye_vertaal_etiket : KOPIE.partye_afrikaans_etiket}{" "}
            <a
              href={v.bron_url}
              target="_blank"
              rel="noopener"
              className="text-ink decoration-rand underline underline-offset-4 hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              {v.titel_oorspronklik} ↗︎
            </a>
          </p>
        </article>

        <p className="mt-8 font-sans text-sm">
          <Link href="/#wat-die-partye-se" className="text-ink font-bold hover:text-rooi focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi">
            ← {KOPIE.partye_terug}
          </Link>
        </p>
      </main>
      <Voet />
    </>
  );
}
