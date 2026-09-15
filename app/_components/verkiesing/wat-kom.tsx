import { komendeMylpale } from "@/lib/verkiesing/datums";

export function WatKom({ nou }: { nou: Date }) {
  const items = komendeMylpale(nou);
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="wat-kom">
      <h2 id="wat-kom" className="font-sans text-xs font-bold tracking-[0.22em] text-ink uppercase">
        Wat kom
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
