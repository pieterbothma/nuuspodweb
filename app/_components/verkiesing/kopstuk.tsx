import Image from "next/image";
import Link from "next/link";
import { gepubliseerdeGidse } from "@/lib/verkiesing/gidse";

export function Kopstuk() {
  const skakels = [
    ...(gepubliseerdeGidse().length > 0 ? [{ href: "/#gidse", teks: "Hoe om te stem" }] : []),
    { href: "/#program", teks: "Verkiesings-Vrydag" },
    { href: "/#wat-ander-berig", teks: "Wat ander berig" },
  ];
  return (
    <header className="border-rand bg-grond/95 sticky top-0 z-20 border-b backdrop-blur">
      <div className="h-[3px] bg-linear-to-r from-neon-siaan to-neon-rooi" aria-hidden />
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3 sm:px-8">
        <Link href="/" className="flex flex-1 items-center gap-3">
          <Image src="/logo.jpg" alt="" width={40} height={40} className="rounded-full" />
          <span className="leading-none">
            <span className="text-ink block font-display text-xl tracking-[0.14em]">NUUSPOD</span>
            <span className="mt-1 block font-sans text-[0.7rem] font-bold tracking-[0.18em] text-ink uppercase">
              Verkiesing 2026
            </span>
          </span>
        </Link>
        <nav aria-label="Afdelings" className="hidden gap-6 font-sans text-xs font-bold tracking-widest uppercase md:flex">
          {skakels.map((s) => (
            <a key={s.href} href={s.href} className="text-grys hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi">
              {s.teks}
            </a>
          ))}
        </nav>
        <Link
          href="/adverteer"
          className="bg-rooi text-white hover:bg-[#c62f2c] px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi"
        >
          Adverteer
        </Link>
      </div>
    </header>
  );
}
