import { KOMMISSIE } from "@/lib/verkiesing/terme";

export function KontroleerRegistrasie() {
  return (
    <div className="border-rand bg-paneel border p-5 sm:p-6">
      <p className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">Waar stem jy?</p>
      <p className="text-papier mt-2 font-display text-2xl text-balance">
        Kontroleer jou registrasie, stemlokaal en wyk met jou ID-nommer.
      </p>
      <a
        href="https://www.elections.org.za/pw/Voter/Voter-Information"
        className="mt-4 inline-block font-sans text-sm font-bold tracking-widest text-siaan uppercase hover:text-papier focus-visible:outline-2 focus-visible:outline-siaan"
      >
        Kyk by die {KOMMISSIE} ↗
      </a>
    </div>
  );
}
