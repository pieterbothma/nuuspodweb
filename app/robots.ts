import type { MetadataRoute } from "next";

const BASIS = "https://www.nuuspod.co.za";

// Nothing on the site is gated (no candidate/ID data lives behind a route), so every page
// is crawlable; the sitemap is the one thing worth pointing crawlers at directly.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${BASIS}/sitemap.xml`,
  };
}
