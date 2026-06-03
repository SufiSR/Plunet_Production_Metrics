/** Query param for minimal chrome on analytics routes, e.g. `?style=embed`. */
export const ANALYTICS_STYLE_QUERY = "style";
export const ANALYTICS_EMBED_STYLE = "embed";

export function isAnalyticsEmbedStyle(
  searchParams: Pick<URLSearchParams, "get"> | { get: (key: string) => string | null },
): boolean {
  return searchParams.get(ANALYTICS_STYLE_QUERY) === ANALYTICS_EMBED_STYLE;
}

/** Appends `style=embed` to internal analytics links while preserving existing query params. */
export function appendAnalyticsEmbedStyle(href: string, embed = true): string {
  if (!embed) return href;
  if (href.startsWith("http://") || href.startsWith("https://")) {
    const url = new URL(href);
    url.searchParams.set(ANALYTICS_STYLE_QUERY, ANALYTICS_EMBED_STYLE);
    return url.toString();
  }
  const [pathAndQuery, hash = ""] = href.split("#");
  const [pathname, query = ""] = pathAndQuery.split("?");
  const params = new URLSearchParams(query);
  params.set(ANALYTICS_STYLE_QUERY, ANALYTICS_EMBED_STYLE);
  const queryString = params.toString();
  return `${pathname}${queryString ? `?${queryString}` : ""}${hash ? `#${hash}` : ""}`;
}
