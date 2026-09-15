import { KOPIE } from "@/lib/verkiesing/kopie";

export function KontroleerRegistrasie() {
  return (
    <div className="neon-raam-dun p-5 sm:p-6">
      <p className="font-sans text-xs font-bold tracking-[0.22em] text-ink uppercase">{KOPIE.held_boks_etiket}</p>
      <p className="text-ink mt-2 font-display text-2xl text-balance">{KOPIE.held_boks_titel}</p>
      <a
        href="#registrasie"
        className="mt-4 inline-block font-sans text-sm font-bold tracking-widest text-ink uppercase hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi"
      >
        {KOPIE.held_boks_skakel} ↓
      </a>
    </div>
  );
}
