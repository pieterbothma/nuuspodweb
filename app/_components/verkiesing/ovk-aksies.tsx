import { KOPIE } from "@/lib/verkiesing/kopie";
import type { SpesialeStemStatus } from "@/lib/verkiesing/datums";

const ETIKET = "font-sans text-xs font-bold tracking-[0.18em] text-grys uppercase";
const KNOPPIE_BASIS =
  "mt-auto flex min-h-11 items-center justify-between gap-2 px-4 py-3 font-sans text-xs font-bold tracking-widest uppercase focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rooi";
const KNOPPIE_PRIMER = `${KNOPPIE_BASIS} bg-ink text-white hover:bg-rooi`;
const KNOPPIE_SEKONDER = `${KNOPPIE_BASIS} border border-ink hover:border-rooi hover:text-rooi`;

function WhatsappIkoon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 20l1.3-3.9A8 8 0 1 1 8 19z" />
      <path d="M9 10h.01M12 10h.01M15 10h.01" />
    </svg>
  );
}

function SmsIkoon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="6" y="2.5" width="12" height="19" rx="2" />
      <path d="M10.5 18.5h3" />
    </svg>
  );
}

function AanlynIkoon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </svg>
  );
}

function BelIkoon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
    </svg>
  );
}

/** Decorative smart-ID drawing: grey card with a photo block and two text lines. */
function SlimkaartTekening() {
  return (
    <div aria-hidden className="flex h-14 items-center gap-2.5 border border-rand bg-paneel px-3">
      <div className="h-9 w-[30px] shrink-0 bg-rand" />
      <div className="flex flex-1 flex-col gap-1.5">
        <div className="h-[5px] bg-[#d4d4d4]" />
        <div className="h-[5px] w-[70%] bg-[#d4d4d4]" />
      </div>
    </div>
  );
}

/** Decorative green ID book drawing: pale green block with a centred strip. */
function BoekieTekening() {
  return (
    <div aria-hidden className="flex h-14 items-center justify-center border border-[#cfdccf] bg-[#e8f0e8]">
      <div className="h-[6px] w-11 bg-[#b9c9b9]" />
    </div>
  );
}

export function OvkAksies({ spesialeStem }: { spesialeStem: SpesialeStemStatus }) {
  const spesiaalDele = KOPIE.spesiaal_teks.split("32249");

  return (
    <section id="registrasie" className="scroll-mt-24 mx-auto max-w-6xl px-5 sm:px-8 pt-14">
      <p className="font-sans text-[0.8125rem] font-black tracking-[0.22em] text-rooi-teks uppercase">{KOPIE.ovk_etiket}</p>
      <h2 className="mt-3 font-display text-3xl text-balance text-ink sm:text-5xl">{KOPIE.ovk_opskrif}</h2>
      <p className="text-grys mt-3 max-w-[60ch] font-sans">{KOPIE.ovk_inleiding}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="neon-raam-dun flex flex-col gap-3.5 p-6">
          <span className="text-ink"><WhatsappIkoon /></span>
          <span className={ETIKET}>{KOPIE.whatsapp_etiket}</span>
          <p className="font-display text-xl text-balance text-ink">{KOPIE.whatsapp_titel}</p>
          <p className="font-sans text-xl font-bold tabular-nums text-ink">0600 88 0000</p>
          <a
            href="https://wa.me/27600880000?text=Hi"
            target="_blank"
            rel="noopener"
            aria-label={`${KOPIE.whatsapp_knoppie}: 0600 88 0000`}
            className={KNOPPIE_PRIMER}
          >
            <span>{KOPIE.whatsapp_knoppie}</span>
            <span aria-hidden>↗︎</span>
          </a>
        </div>

        <div className="flex flex-col gap-3.5 border border-rand p-6">
          <span className="text-ink"><SmsIkoon /></span>
          <span className={ETIKET}>{KOPIE.sms_etiket}</span>
          <p className="font-display text-xl text-balance text-ink">{KOPIE.sms_titel}</p>
          <p className="font-sans text-xl font-bold tabular-nums text-ink">32810</p>
          <p className="text-grys font-sans text-sm">{KOPIE.sms_nota}</p>
          <a href="sms:32810" aria-label={`${KOPIE.sms_knoppie}: 32810`} className={KNOPPIE_SEKONDER}>
            <span>{KOPIE.sms_knoppie}</span>
            <span aria-hidden>→</span>
          </a>
        </div>

        <div className="flex flex-col gap-3.5 border border-rand p-6">
          <span className="text-ink"><AanlynIkoon /></span>
          <span className={ETIKET}>{KOPIE.aanlyn_etiket}</span>
          <p className="font-display text-xl text-balance text-ink">{KOPIE.aanlyn_titel}</p>
          <p className="text-grys font-sans text-sm">{KOPIE.aanlyn_nota}</p>
          <a
            href="https://www.elections.org.za/pw/Voter/Voter-Information"
            target="_blank"
            rel="noopener"
            aria-label={`${KOPIE.aanlyn_knoppie}: ${KOPIE.aanlyn_titel}`}
            className={KNOPPIE_SEKONDER}
          >
            <span>{KOPIE.aanlyn_knoppie}</span>
            <span aria-hidden>↗︎</span>
          </a>
        </div>

        <div className="flex flex-col gap-3.5 border border-rand p-6">
          <span className="text-ink"><BelIkoon /></span>
          <span className={ETIKET}>{KOPIE.bel_etiket}</span>
          <p className="font-display text-xl text-balance text-ink">{KOPIE.bel_titel}</p>
          <p className="font-sans text-xl font-bold tabular-nums text-ink">0800 11 8000</p>
          <p className="text-grys font-sans text-sm">{KOPIE.bel_nota}</p>
          <a href="tel:0800118000" aria-label={`${KOPIE.bel_knoppie}: 0800 11 8000`} className={KNOPPIE_SEKONDER}>
            <span>{KOPIE.bel_knoppie}</span>
            <span aria-hidden>→</span>
          </a>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.25fr_1fr_1fr]">
        <div className="flex flex-col gap-4 border border-rand p-6">
          <span className={ETIKET}>{KOPIE.id_etiket}</span>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2.5 border border-ink p-3">
              <SlimkaartTekening />
              <p className="font-sans text-base font-bold text-ink">{KOPIE.id_slimkaart}</p>
            </div>
            <div className="flex flex-col gap-2.5 border border-ink p-3">
              <BoekieTekening />
              <p className="font-sans text-base font-bold text-ink">{KOPIE.id_boekie}</p>
            </div>
          </div>
          <p className="text-grys font-sans text-sm">{KOPIE.id_nota}</p>
        </div>

        <div className="flex flex-col gap-3 border border-rand p-6">
          <span className={ETIKET}>{KOPIE.spesiaal_etiket}</span>
          <p className="font-display text-2xl text-balance text-ink">{KOPIE.spesiaal_titel}</p>
          <p className="text-grys font-sans text-sm">
            {spesiaalDele[0]}
            <b className="text-ink">32249</b>
            {spesiaalDele[1]}
          </p>
          {spesialeStem === "oop" ? (
            <a href="sms:32249" aria-label={`${KOPIE.spesiaal_knoppie_oop}: 32249`} className={`${KNOPPIE_SEKONDER} mt-auto`}>
              <span>{KOPIE.spesiaal_knoppie_oop}</span>
              <span aria-hidden>→</span>
            </a>
          ) : (
            <p className="mt-auto flex min-h-11 items-center border border-dashed border-rand px-4 py-3 font-sans text-xs font-bold tracking-widest text-grys uppercase">
              {spesialeStem === "toe" ? KOPIE.spesiaal_knoppie_toe : KOPIE.spesiaal_knoppie_verby}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3 border border-rand p-6">
          <span className={ETIKET}>{KOPIE.onthou_etiket}</span>
          <p className="font-display text-2xl text-balance text-ink">{KOPIE.onthou_titel}</p>
          <p className="text-grys font-sans text-sm">{KOPIE.onthou_teks}</p>
        </div>
      </div>
    </section>
  );
}
