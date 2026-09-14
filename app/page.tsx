import { Aftelling } from "./_components/verkiesing/aftelling";
import { GidsKaarte } from "./_components/verkiesing/gids-kaarte";
import { Kopstuk } from "./_components/verkiesing/kopstuk";
import { KontroleerRegistrasie } from "./_components/verkiesing/kontroleer-registrasie";
import { Nuusstroom } from "./_components/verkiesing/nuusstroom";
import { Verkiesingsprogram } from "./_components/verkiesing/verkiesingsprogram";
import { Voet } from "./_components/verkiesing/voet";
import { WatKom } from "./_components/verkiesing/wat-kom";
import { STEMDAG } from "@/lib/verkiesing/datums";
import { haalEpisodes, haalStroom } from "@/lib/verkiesing/lees";

export default async function Tuis() {
  const nou = new Date();
  const [stroom, episodes] = await Promise.all([haalStroom(), haalEpisodes()]);

  return (
    <>
      <Kopstuk />
      <main>
        <section className="border-rand border-b">
          <div className="mx-auto grid max-w-6xl gap-10 px-5 py-12 sm:px-8 sm:py-16 md:grid-cols-[1.4fr_1fr] md:items-end">
            <div>
              <p className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
                Plaaslike verkiesing · Woensdag 4 November 2026
              </p>
              <h1 className="text-papier mt-4 font-display text-4xl leading-[1.05] text-balance sm:text-6xl">
                Jou raad. Jou wyk. Jou stem.
              </h1>
              <div className="mt-8">
                <Aftelling teikenIso={STEMDAG.toISOString()} nouMs={nou.getTime()} />
              </div>
            </div>
            <KontroleerRegistrasie />
          </div>
        </section>

        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_22rem]">
          <div className="grid content-start gap-14">
            <WatKom nou={nou} />
            <Verkiesingsprogram episodes={episodes} />
            <GidsKaarte />
          </div>
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <Nuusstroom items={stroom} nou={nou} />
          </aside>
        </div>
      </main>
      <Voet />
    </>
  );
}
