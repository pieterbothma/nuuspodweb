import type { MetadataRoute } from "next";
import { gepubliseerdeGidse } from "@/lib/verkiesing/gidse";
import { haalAlleMuniKodes, haalAlleWykIds } from "@/lib/verkiesing/wyksoeker";

const BASIS = "https://www.nuuspod.co.za";

/**
 * The site's routes that exist independent of the database: the homepage, the ad page and
 * every published explainer. These are always present, even when the database is down —
 * they anchor the "fall back to the static pages" contract below.
 */
function statieseBladsye(): MetadataRoute.Sitemap {
  return [
    { url: `${BASIS}/`, changeFrequency: "daily", priority: 1 },
    { url: `${BASIS}/adverteer`, changeFrequency: "monthly", priority: 0.3 },
    ...gepubliseerdeGidse().map((gids) => ({
      url: `${BASIS}/gids/${gids.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
  ];
}

/**
 * Every ward and municipality page, from the same paged listers the ward finder itself
 * uses. `haalAlleWykIds`/`haalAlleMuniKodes` already degrade a mid-page database outage to
 * a partial (or empty) array rather than throwing — but the whole sitemap must render even
 * if a future change to that contract lets an error through, so an unexpected rejection
 * here still falls back to an empty list instead of taking the static entries down with it.
 */
async function dinamieseBladsye(): Promise<MetadataRoute.Sitemap> {
  const [wyke, munisipaliteite] = await Promise.all([
    haalAlleWykIds().catch(() => []),
    haalAlleMuniKodes().catch(() => []),
  ]);

  return [
    ...wyke.map((w) => ({
      url: `${BASIS}/wyk/${w.wyk_id}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...munisipaliteite.map((m) => ({
      url: `${BASIS}/munisipaliteit/${m.kode}`,
      changeFrequency: "weekly" as const,
      priority: 0.7,
    })),
  ];
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  return [...statieseBladsye(), ...(await dinamieseBladsye())];
}
