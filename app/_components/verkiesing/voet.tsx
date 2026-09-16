import Link from "next/link";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { Terugvoer } from "./terugvoer";

export function Voet() {
  return (
    <footer className="border-rand mt-16 border-t">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:px-8">
        <Terugvoer />
        <div className="text-grys grid gap-2 font-sans text-sm">
          <p>{KOPIE.voet_bron}</p>
          <p>{KOPIE.voet_onafhanklik}</p>
          <p>
            {KOPIE.voet_real411_vraag}{" "}
            <a
              href="https://real411.org.za"
              target="_blank"
              rel="noopener"
              className="text-ink underline decoration-rand underline-offset-4 hover:decoration-rooi focus-visible:outline-2 focus-visible:outline-rooi"
            >
              {KOPIE.voet_real411_skakel} ↗︎
            </a>
          </p>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 font-sans text-xs font-bold tracking-widest uppercase">
          <a href="https://www.youtube.com/@Nuuspod" target="_blank" rel="noopener" className="font-bold text-ink hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi">YouTube</a>
          <a href="https://www.facebook.com/izak.duplessis.752" target="_blank" rel="noopener" className="font-bold text-ink hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi">Facebook</a>
          <a href="https://x.com/zakjourno" target="_blank" rel="noopener" className="font-bold text-ink hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi">X</a>
          <Link href="/adverteer" className="font-bold text-ink hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi">Adverteer by Nuuspod</Link>
        </div>
      </div>
    </footer>
  );
}
