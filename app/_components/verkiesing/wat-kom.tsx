import { komendeMylpale } from "@/lib/verkiesing/datums";
import { KOPIE } from "@/lib/verkiesing/kopie";

export function WatKom({ nou }: { nou: Date }) {
  const items = komendeMylpale(nou);
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="wat-kom">
      <h2 id="wat-kom" className="font-sans text-[0.8125rem] font-black tracking-[0.22em] text-rooi-teks uppercase">
        {KOPIE.watkom_opskrif}
      </h2>
      <ol className="border-rand divide-rand mt-4 divide-y border-y">
        {items.map((m) => (
          <li key={m.id} className="grid gap-1 py-4 sm:grid-cols-[15rem_1fr] sm:gap-6">
            <span className="text-ink font-sans text-sm font-bold">{m.wanneer}</span>
            <span className="text-grys font-sans">{m.wat}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
