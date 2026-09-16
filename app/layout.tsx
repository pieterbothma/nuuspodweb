import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const dmSerifDisplay = localFont({
  src: [
    {
      path: "../public/fonts/DMSerifDisplay-Regular.ttf",
      weight: "400",
      style: "normal",
    },
  ],
  variable: "--font-display",
  display: "swap",
});

const sourceSans = localFont({
  src: [
    {
      path: "../public/fonts/SourceSans3-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "../public/fonts/SourceSans3-Bold.ttf",
      weight: "700",
      style: "normal",
    },
    {
      // Section headings only (text-rooi-teks eyebrows). Subset to Latin, like the other cuts.
      path: "../public/fonts/SourceSans3-Black.ttf",
      weight: "900",
      style: "normal",
    },
  ],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://www.nuuspod.co.za"),
  title: "Verkiesing 2026 — Nuuspod",
  description:
    "Die plaaslike verkiesing van 4 November 2026 in Afrikaans: belangrike datums, hoe om te stem, en Verkiesings-Vrydag met Izak du Plessis.",
  openGraph: {
    title: "Verkiesing 2026 — Nuuspod",
    description: "Alles wat jy nodig het om op 4 November te stem, in Afrikaans.",
    url: "https://nuuspod.co.za",
    siteName: "Nuuspod",
    locale: "af_ZA",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="af"
      className={`${dmSerifDisplay.variable} ${sourceSans.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}
