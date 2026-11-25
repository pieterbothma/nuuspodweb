import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Verkiesing 2026 pages are gone (2026-11-25); old links land on the ad page.
  async redirects() {
    return ["/adverteer", "/gids/:pad*", "/wyk/:pad*", "/munisipaliteit/:pad*", "/verklaring/:pad*"].map(
      (source) => ({ source, destination: "/", permanent: true }),
    );
  },
};

export default nextConfig;
