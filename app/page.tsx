import { Aftelling } from "./_components/verkiesing/aftelling";
import { GidsKaarte } from "./_components/verkiesing/gids-kaarte";
import { Kopstuk } from "./_components/verkiesing/kopstuk";
import { KontroleerRegistrasie } from "./_components/verkiesing/kontroleer-registrasie";
import { Nuusstroom } from "./_components/verkiesing/nuusstroom";
import { Verkiesingsprogram } from "./_components/verkiesing/verkiesingsprogram";
import { Voet } from "./_components/verkiesing/voet";
import { WatKom } from "./_components/verkiesing/wat-kom";
import { STEMDAG } from "@/lib/verkiesing/datums";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { haalEpisodes, haalStroom } from "@/lib/verkiesing/lees";

export default async function Tuis() {
  const nou = new Date();
  const [stroom, episodes] = await Promise.all([haalStroom(), haalEpisodes()]);

  return (
    <>
      <Kopstuk />
      <main>
        <section className="mx-auto max-w-6xl px-5 pt-8 sm:px-8 sm:pt-11">
          <div className="neon-raam grid gap-8 p-5 sm:p-10 lg:grid-cols-[minmax(0,1fr)_26rem] lg:items-end lg:gap-12 lg:px-12 lg:py-11">
            <div>
              <p className="font-sans text-xs font-bold tracking-[0.22em] text-ink uppercase sm:text-[0.8rem]">
                {KOPIE.held_etiket}
              </p>
              <h1 className="mt-3 font-display text-[3.75rem] leading-[0.9] tracking-[-0.02em] text-ink sm:text-8xl lg:text-[7rem]">
                Verkiesing
                <br />
                <span className="text-rooi">2026</span>
              </h1>
              <p className="mt-3 font-display text-[1.625rem] text-ink sm:text-4xl lg:text-5xl">
                met Izak du Plessis
              </p>
            </div>
            <div className="grid gap-7">
              <Aftelling teikenIso={STEMDAG.toISOString()} nouMs={nou.getTime()} />
              <KontroleerRegistrasie />
            </div>
          </div>
        </section>

        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[1fr_22rem]">
          <div className="grid content-start gap-14">
            <WatKom nou={nou} />
            <Verkiesingsprogram episodes={episodes} />
            <GidsKaarte />
          </div>
          <aside>
            <Nuusstroom items={stroom} nou={nou} />
          </aside>
        </div>
      </main>
      <Voet />
    </>
  );
}
