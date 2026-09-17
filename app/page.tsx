import { Aftelling } from "./_components/verkiesing/aftelling";
import { GidsKaarte } from "./_components/verkiesing/gids-kaarte";
import { Kopstuk } from "./_components/verkiesing/kopstuk";
import { Nuusstroom } from "./_components/verkiesing/nuusstroom";
import { OvkAksies } from "./_components/verkiesing/ovk-aksies";
import { OvkNuus } from "./_components/verkiesing/ovk-nuus";
import { Partyverklarings } from "./_components/verkiesing/partyverklarings";
import { Verkiesingsprogram } from "./_components/verkiesing/verkiesingsprogram";
import { Voet } from "./_components/verkiesing/voet";
import { WatKom } from "./_components/verkiesing/wat-kom";
import { WykSoeker } from "./_components/verkiesing/wyk-soeker";
import { spesialeStemStatus, STEMDAG } from "@/lib/verkiesing/datums";
import { KOPIE } from "@/lib/verkiesing/kopie";
import { haalEpisodes, haalStroom } from "@/lib/verkiesing/lees";
import { haalOvkNuus } from "@/lib/verkiesing/ovk";
import { haalPartyverklarings } from "@/lib/verkiesing/partye";

export default async function Tuis() {
  const nou = new Date();
  const [stroom, episodes, verklarings, ovkNuus] = await Promise.all([
    haalStroom(),
    haalEpisodes(),
    haalPartyverklarings(),
    haalOvkNuus(),
  ]);
  const spesialeStem = spesialeStemStatus(nou);

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
              <WykSoeker />
            </div>
          </div>
        </section>

        {/* Piet, 2026-09-16: search, then what the parties say. The IEC actions, episodes and
            guides follow; "Wat ander berig" stays beside the main column. Until a statement
            is approved the party block renders nothing and the rest simply moves up. */}
        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="grid min-w-0 content-start gap-14">
            <Partyverklarings verklarings={verklarings} nou={nou} />
            <OvkNuus items={ovkNuus} />
            <WatKom nou={nou} />
          </div>
          <aside>
            <Nuusstroom items={stroom} nou={nou} />
          </aside>
        </div>

        <OvkAksies spesialeStem={spesialeStem} />

        <div className="mx-auto grid max-w-6xl gap-14 px-5 py-12 sm:px-8">
          <Verkiesingsprogram episodes={episodes} />
          <GidsKaarte />
        </div>
      </main>
      <Voet />
    </>
  );
}
