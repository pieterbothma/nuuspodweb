import Link from "next/link";
import { Terugvoer } from "./terugvoer";

export function Voet() {
  return (
    <footer className="border-rand mt-16 border-t">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:px-8">
        <Terugvoer />
        <div className="text-grys grid gap-2 font-sans text-sm">
          <p>Bron van verkiesingsinligting: die OVK (IEC).</p>
          <p>Nuuspod is nie aan die OVK of enige party verbonde nie.</p>
          <p>
            Sien jy vals verkiesingsinligting?{" "}
            <a href="https://www.real411.org" className="text-siaan hover:text-papier">
              Rapporteer dit by Real411 ↗
            </a>
          </p>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 font-sans text-xs font-bold tracking-widest uppercase">
          <a href="https://www.youtube.com/@Nuuspod" className="text-grys hover:text-siaan">YouTube</a>
          <a href="https://www.facebook.com/izak.duplessis.752" className="text-grys hover:text-siaan">Facebook</a>
          <a href="https://x.com/zakjourno" className="text-grys hover:text-siaan">X</a>
          <Link href="/adverteer" className="text-grys hover:text-siaan">Adverteer by Nuuspod</Link>
        </div>
      </div>
    </footer>
  );
}
