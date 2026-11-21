import type { MetadataRoute } from "next";

import { SITE_URL } from "@/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    { url: `${SITE_URL}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/escaparate`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/escaparate/calendario`, lastModified, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/escaparate/legal`, lastModified, changeFrequency: "yearly", priority: 0.2 },
  ];
}
