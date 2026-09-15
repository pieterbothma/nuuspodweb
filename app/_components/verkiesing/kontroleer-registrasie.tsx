import { KOMMISSIE } from "@/lib/verkiesing/terme";

export function KontroleerRegistrasie() {
  return (
    <div className="neon-raam p-5 sm:p-6">
      <p className="font-sans text-xs font-bold tracking-[0.22em] text-ink uppercase">Waar stem jy?</p>
      <p className="text-ink mt-2 font-display text-2xl text-balance">
        Kontroleer jou registrasie, stemlokaal en wyk met jou ID-nommer.
      </p>
      <a
        href="https://www.elections.org.za/pw/Voter/Voter-Information"
        target="_blank"
        rel="noopener"
        className="mt-4 inline-block font-sans text-sm font-bold tracking-widest text-ink uppercase hover:text-rooi focus-visible:outline-2 focus-visible:outline-rooi"
      >
        Kyk by die {KOMMISSIE} ↗
      </a>
    </div>
  );
}
