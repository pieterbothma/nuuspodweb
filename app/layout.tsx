import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
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
  ],
  variable: "--font-sans",
  display: "swap",
});

const GA_ID = "G-MKXWBN2L9W";

export const metadata: Metadata = {
  metadataBase: new URL("https://nuuspod.co.za"),
  title: "Adverteer by Nuuspod — Afrikaanse nuus, elke weeksdag regstreeks",
  description:
    "Nuuspod met Izak du Plessis bereik gemiddeld 14 miljoen mense per maand op Facebook en YouTube. Sien die advertensiepakkette en tariewe.",
  openGraph: {
    title: "Adverteer by Nuuspod",
    description:
      "Afrikaanse nuusbulletin, elke weeksdag regstreeks. Gemiddeld 14 miljoen kyke per maand.",
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
      <body className="min-h-full">
        {children}
        <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
        <Script id="google-analytics" strategy="afterInteractive">
          {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
        </Script>
      </body>
    </html>
  );
}
