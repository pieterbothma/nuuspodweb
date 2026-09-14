import Link from "next/link";
import { gepubliseerdeGidse } from "@/lib/verkiesing/gidse";

export function GidsKaarte() {
  const gidse = gepubliseerdeGidse();
  if (gidse.length === 0) return null;
  return (
    <section id="gidse" aria-labelledby="gidse-kop" className="scroll-mt-24">
      <h2 id="gidse-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Hoe om te stem
      </h2>
      <ul className="border-rand bg-rand mt-4 grid gap-px border sm:grid-cols-2">
        {gidse.map((g) => (
          <li key={g.slug} className="bg-swart">
            <Link href={`/gids/${g.slug}`} className="group block h-full p-5 focus-visible:outline-2 focus-visible:outline-siaan">
              <span className="text-papier group-hover:text-siaan block font-display text-xl text-balance">{g.titel}</span>
              <span className="text-grys mt-2 block font-sans text-sm">{g.opsomming}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
