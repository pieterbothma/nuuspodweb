import Image from "next/image";
import type { Episode } from "@/lib/verkiesing/lees";

export function Verkiesingsprogram({ episodes }: { episodes: Episode[] }) {
  const [nuutste, ...vorige] = episodes;
  return (
    <section id="program" aria-labelledby="program-kop" className="scroll-mt-24">
      <h2 id="program-kop" className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
        Verkiesings-Vrydag
      </h2>
      <p className="text-papier mt-2 font-display text-3xl">Elke Vrydag regstreeks.</p>
      <div className="border-rand bg-paneel mt-6 overflow-hidden border">
        <div className="relative aspect-video">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${nuutste.video_id}`}
            title={nuutste.titel}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 h-full w-full"
          />
        </div>
        <p className="text-papier px-5 py-4 font-sans text-sm">{nuutste.titel}</p>
      </div>
      {vorige.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          {vorige.map((e) => (
            <li key={e.video_id}>
              <a href={`https://www.youtube.com/watch?v=${e.video_id}`} target="_blank" rel="noopener noreferrer" className="group block focus-visible:outline-2 focus-visible:outline-siaan">
                <Image
                  src={`https://i.ytimg.com/vi/${e.video_id}/mqdefault.jpg`}
                  alt=""
                  width={320}
                  height={180}
                  unoptimized
                  className="border-rand w-full border"
                />
                <span className="text-grys group-hover:text-papier mt-2 block font-sans text-sm">{e.titel}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
