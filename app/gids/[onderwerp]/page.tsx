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
