import Image from "next/image";

const WHATSAPP =
  "https://wa.me/27828385204?text=" +
  encodeURIComponent("Hallo Izak, ek wil graag by Nuuspod adverteer.");
const EPOS = "journozak@gmail.com";
const YOUTUBE = "https://www.youtube.com/@Nuuspod";
const FACEBOOK = "https://www.facebook.com/izak.duplessis.752";
const X = "https://x.com/zakjourno";
const KANAAL_ID = "UC8WVZnhOnCUwSpJaMIhdQcg";

/** Used when the feed cannot be reached, so the page never renders an empty player. */
const TERUGVAL_VIDEO = {
  id: "tH9a5SJywFE",
  title: "Nuusbulletin Maandag 3 Augustus 2026",
};

/**
 * The newest upload, read from the channel's public RSS feed.
 *
 * A hardcoded video id means the page slowly starts advertising last month's
 * news. The feed keeps it current with nothing to maintain.
 */
async function jongsteVideo() {
  try {
    const res = await fetch(
      `https://www.youtube.com/feeds/videos.xml?channel_id=${KANAAL_ID}`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return TERUGVAL_VIDEO;
    const xml = await res.text();
    const id = xml.match(/<yt:videoId>(.*?)<\/yt:videoId>/)?.[1];
    const title = xml.match(/<media:title>(.*?)<\/media:title>/)?.[1];
    return id ? { id, title: title ?? TERUGVAL_VIDEO.title } : TERUGVAL_VIDEO;
  } catch {
    return TERUGVAL_VIDEO;
  }
}

/**
 * The on-air lower third, used as this page's section marker.
 *
 * Taken from the broadcast rather than invented for the web: it is the graphic
 * the audience already associates with the show.
 */
function Chyron({
  kicker,
  children,
}: {
  kicker: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-8 sm:mb-12">
      <div className="flex items-center gap-3">
        <span className="h-5 w-1 bg-rooi" aria-hidden />
        <span className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
          {kicker}
        </span>
      </div>
      <h2 className="text-papier mt-3 font-display text-3xl leading-tight sm:text-4xl md:text-5xl">
        {children}
      </h2>
    </div>
  );
}

const PAKKETTE = [
  {
    naam: "Logo daagliks in program",
    prys: "R5 000",
    per: "per maand",
    wat: "Jou logo op die skerm in elke bulletin, elke weeksdag.",
  },
  {
    naam: "Video en live read daagliks",
    prys: "R10 000",
    per: "per maand",
    wat: "Jou advertensie speel, en Izak lees jou boodskap self voor in die uitsending.",
    uit: true,
  },
  {
    naam: "Logo en kontakbesonderhede op Facebook",
    prys: "R10 000",
    per: "per maand",
    wat: "Eksklusief op elke Facebook-berig, waar die grootste gehoor sit.",
  },
  {
    naam: "Promo onderhoud",
    prys: "R5 000",
    per: "eenmalig",
    wat: "'n Volledige onderhoud oor jou besigheid, gepubliseer op al die kanale.",
  },
  {
    naam: "Promo onderhoudreeks",
    prys: "R20 000",
    per: "per maand",
    wat: "'n Reeks onderhoude wat jou storie oor weke heen bou.",
  },
];

const WAAROM = [
  {
    kop: "Afrikaanse volwassenes",
    lyf: "Mense wat doelbewus vir nuus kom kyk, nie tieners wat verbyrol nie. Dit is die gehoor wat besluite neem oor motors, prokureurs, versekering en dienste.",
  },
  {
    kop: "Elke weeksdag, dieselfde tyd",
    lyf: "'n Bulletin wat elke dag verskyn bou gewoonte. Jou naam word deel van daardie gewoonte, nie 'n advertensie wat een keer verbyflits nie.",
  },
  {
    kop: "Izak lees dit self",
    lyf: "By 'n live read is dit die aanbieder se eie stem wat jou naam sê. Dit is die verskil tussen 'n advertensie en 'n aanbeveling.",
  },
];

const SYFERS = [
  { syfer: "14 miljoen", label: "Facebook-kyke per maand", noot: "gemiddeld" },
  { syfer: "113 000", label: "Volgelinge op Facebook" },
  { syfer: "63 900", label: "Intekenare op YouTube" },
  { syfer: "22 miljoen", label: "Kyke op YouTube", noot: "sedert 2020" },
];

export default async function Tuis() {
  const video = await jongsteVideo();

  return (
    <main>
      {/* Masthead */}
      <header className="border-rand bg-swart/95 sticky top-0 z-20 border-b backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3 sm:px-8">
          <Image
            src="/logo.jpg"
            alt=""
            width={40}
            height={40}
            className="rounded-full"
          />
          <div className="flex-1 leading-none">
            <div className="text-papier font-display text-xl tracking-[0.14em]">
              NUUSPOD
            </div>
            <div className="text-grys mt-1 font-sans text-[0.7rem]">
              met Izak du Plessis
            </div>
          </div>
          <a
            href={WHATSAPP}
            className="bg-rooi text-papier rounded px-4 py-2 font-sans text-xs font-bold tracking-widest uppercase transition-colors hover:bg-[#c62f2c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan"
          >
            WhatsApp
          </a>
        </div>
      </header>

      {/* Hero */}
      <section className="border-rand border-b">
        <div className="mx-auto grid max-w-6xl gap-12 px-5 py-16 sm:px-8 sm:py-24 md:grid-cols-[1.35fr_1fr] md:items-center">
          <div>
            <div className="flex items-center gap-3">
              <span className="bg-rooi h-2 w-2 rounded-full" aria-hidden />
              <span className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
                Elke weeksdag regstreeks
              </span>
            </div>

            <h1 className="text-papier mt-5 font-display text-4xl leading-[1.05] sm:text-6xl md:text-7xl">
              14 miljoen mense sien Nuuspod elke maand.
            </h1>

            <div className="bg-rooi mt-6 h-1 w-40">
              <div className="puls bg-siaan h-full w-full" />
            </div>

            <p className="text-grys mt-6 max-w-xl font-sans text-lg leading-relaxed">
              Hoeveel van hulle ken jou besigheid se naam? Nuuspod is &apos;n
              Afrikaanse nuusbulletin wat elke weeksdag regstreeks uitsaai op
              Facebook en YouTube — en jou advertensie sit binne-in die nuus,
              nie langs dit nie.
            </p>

            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href={WHATSAPP}
                className="bg-rooi text-papier rounded px-6 py-3 font-sans text-sm font-bold tracking-widest uppercase transition-colors hover:bg-[#c62f2c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan"
              >
                WhatsApp Izak
              </a>
              <a
                href="#pakkette"
                className="border-rand text-papier rounded border px-6 py-3 font-sans text-sm font-bold tracking-widest uppercase transition-colors hover:border-siaan focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan"
              >
                Sien die pakkette
              </a>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-xs md:mx-0 md:max-w-sm">
            <div className="bg-paneel absolute -inset-x-3 top-8 bottom-6" aria-hidden />
            <Image
              src="/izak-duim.jpg"
              alt="Izak du Plessis"
              width={342}
              height={584}
              className="relative w-full object-cover"
              priority
            />
            <div className="bg-rooi relative flex items-baseline gap-3 px-4 py-3">
              <span className="text-papier font-display text-lg">
                Izak du Plessis
              </span>
              <span className="text-papier/80 font-sans text-xs tracking-widest uppercase">
                Aanbieder
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* The numbers, as the strip that runs under a broadcast */}
      <section className="border-rand bg-paneel border-b">
        <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
          <div className="flex items-center gap-3">
            <span className="bg-siaan h-5 w-1" aria-hidden />
            <span className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
              Nuuspod bereik
            </span>
          </div>

          <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 md:grid-cols-4">
            {SYFERS.map((s) => (
              <div key={s.label}>
                <dt className="text-papier font-display text-4xl leading-none sm:text-5xl">
                  {s.syfer}
                </dt>
                <dd className="text-grys mt-3 font-sans text-sm leading-snug">
                  {s.label}
                  {s.noot ? (
                    <span className="text-grys/70 block text-xs">{s.noot}</span>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>

          <p className="border-rand text-grys mt-10 border-t pt-6 font-sans text-sm">
            Meer as <strong className="text-papier">10 000 mense</strong> kyk
            elke dag die regstreekse uitsending op YouTube alleen — mense wat
            doelbewus vir nuus kom, nie verbyrol nie.
          </p>
        </div>
      </section>

      {/* The product itself */}
      <section className="border-rand border-b">
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <Chyron kicker="Die jongste bulletin">Kyk waarvoor jy betaal.</Chyron>

          <div className="border-rand bg-paneel overflow-hidden border">
            <div className="relative aspect-video">
              <iframe
                src={`https://www.youtube-nocookie.com/embed/${video.id}`}
                title={video.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="absolute inset-0 h-full w-full"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <span className="text-papier font-sans text-sm">{video.title}</span>
              <a
                href={YOUTUBE}
                className="hover:text-papier font-sans text-xs font-bold tracking-widest text-siaan uppercase"
              >
                Sien die kanaal ↗
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Packages — the one block set on newsprint, like the cards */}
      <section
        id="pakkette"
        className="border-rand bg-papier text-swart scroll-mt-20 border-b"
      >
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <div className="mb-10 sm:mb-14">
            <div className="flex items-center gap-3">
              <span className="bg-rooi h-5 w-1" aria-hidden />
              <span className="font-sans text-xs font-bold tracking-[0.22em] text-[#0a6f88] uppercase">
                Advertensietariewe
              </span>
            </div>
            <h2 className="text-swart mt-3 font-display text-3xl leading-tight sm:text-4xl md:text-5xl">
              Vyf maniere om in die nuus te wees.
            </h2>
          </div>

          <ul className="divide-y divide-[#d8d2c4] border-y border-[#d8d2c4]">
            {PAKKETTE.map((p) => (
              <li
                key={p.naam}
                className="grid gap-2 py-6 sm:grid-cols-[1fr_auto] sm:items-baseline sm:gap-8"
              >
                <div>
                  <h3 className="text-swart font-sans text-lg font-bold">
                    {p.naam}
                    {p.uit ? (
                      <span className="bg-rooi text-papier ml-3 inline-block px-2 py-0.5 align-middle font-sans text-[0.6rem] font-bold tracking-widest uppercase">
                        Gewildste
                      </span>
                    ) : null}
                  </h3>
                  <p className="mt-1 max-w-xl font-sans text-sm leading-relaxed text-[#4a5058]">
                    {p.wat}
                  </p>
                </div>
                <div className="sm:text-right">
                  <span className="text-swart font-display text-3xl">
                    {p.prys}
                  </span>
                  <span className="ml-2 font-sans text-xs tracking-widest text-[#4a5058] uppercase">
                    {p.per}
                  </span>
                </div>
              </li>
            ))}
          </ul>

          <p className="mt-8 font-sans text-sm text-[#4a5058]">
            Wil jy pakkette kombineer, of iets doen wat nie hier staan nie?
            Stuur &apos;n boodskap — ons werk iets uit wat by jou begroting pas.
          </p>
        </div>
      </section>

      {/* Why it works */}
      <section className="border-rand border-b">
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <Chyron kicker="Wie kyk">Nie almal nie. Die regtes.</Chyron>

          <div className="grid gap-10 md:grid-cols-3">
            {WAAROM.map((k) => (
              <div key={k.kop}>
                <div className="bg-rooi h-px w-full" aria-hidden />
                <h3 className="text-papier mt-5 font-display text-2xl">
                  {k.kop}
                </h3>
                <p className="text-grys mt-3 font-sans text-sm leading-relaxed">
                  {k.lyf}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact */}
      <section className="border-rand bg-paneel border-b">
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <div className="grid gap-12 md:grid-cols-[1.2fr_1fr] md:items-center">
            <div>
              <div className="flex items-center gap-3">
                <span className="bg-rooi h-5 w-1" aria-hidden />
                <span className="font-sans text-xs font-bold tracking-[0.22em] text-siaan uppercase">
                  Kom ons praat
                </span>
              </div>
              <h2 className="text-papier mt-3 font-display text-3xl leading-tight sm:text-4xl md:text-5xl">
                Stuur &apos;n boodskap. Izak antwoord self.
              </h2>
              <p className="text-grys mt-5 max-w-lg font-sans text-base leading-relaxed">
                Sê vir ons wat jou besigheid doen en wat jy wil bereik. Ons sê
                vir jou eerlik of Nuuspod die regte plek daarvoor is.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <a
                  href={WHATSAPP}
                  className="bg-rooi text-papier rounded px-6 py-3 font-sans text-sm font-bold tracking-widest uppercase transition-colors hover:bg-[#c62f2c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan"
                >
                  WhatsApp 082 838 5204
                </a>
                <a
                  href={`mailto:${EPOS}?subject=${encodeURIComponent("Adverteer by Nuuspod")}`}
                  className="border-rand text-papier rounded border px-6 py-3 font-sans text-sm font-bold tracking-widest uppercase transition-colors hover:border-siaan focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-siaan"
                >
                  Stuur e-pos
                </a>
              </div>
            </div>

            <div className="mx-auto w-44 md:mx-0 md:w-full md:max-w-[240px]">
              <Image
                src="/izak-kop.jpg"
                alt="Izak du Plessis agter die mikrofoon"
                width={447}
                height={447}
                className="w-full"
              />
              <div className="bg-rooi h-1 w-full" aria-hidden />
            </div>
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="text-grys font-sans text-xs">
            © {new Date().getFullYear()} Nuuspod · Afrikaanse nuus en aktualiteit
          </div>
          <nav className="flex flex-wrap gap-5 font-sans text-xs font-bold tracking-widest uppercase">
            <a href={YOUTUBE} className="text-grys hover:text-siaan">
              YouTube
            </a>
            <a href={FACEBOOK} className="text-grys hover:text-siaan">
              Facebook
            </a>
            <a href={X} className="text-grys hover:text-siaan">
              X
            </a>
            <a href={`mailto:${EPOS}`} className="text-grys hover:text-siaan">
              E-pos
            </a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
