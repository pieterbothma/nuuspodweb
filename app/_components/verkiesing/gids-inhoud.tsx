import { vetDele, type Blok } from "@/lib/verkiesing/gidse/tipes";

function Teks({ teks }: { teks: string }) {
  return (
    <>
      {vetDele(teks).map((d, i) =>
        d.vet ? (
          <strong key={i} className="text-ink font-bold">
            {d.teks}
          </strong>
        ) : (
          <span key={i}>{d.teks}</span>
        )
      )}
    </>
  );
}

export function GidsInhoud({ blokke }: { blokke: Blok[] }) {
  return (
    <div className="text-ink/90 grid gap-5 font-sans text-lg leading-relaxed">
      {blokke.map((b, i) => {
        if (b.tipe === "h2")
          return (
            <h2 key={i} className="text-ink mt-4 font-display text-2xl text-balance">
              {b.teks}
            </h2>
          );
        if (b.tipe === "ul")
          return (
            <ul key={i} className="grid list-disc gap-2 pl-6 marker:text-grys">
              {b.items.map((it, j) => (
                <li key={j}>
                  <Teks teks={it} />
                </li>
              ))}
            </ul>
          );
        return (
          <p key={i}>
            <Teks teks={b.teks} />
          </p>
        );
      })}
    </div>
  );
}
