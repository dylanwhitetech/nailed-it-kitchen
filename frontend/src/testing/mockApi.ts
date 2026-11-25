import { vi } from "vitest";

/**
 * Stubs `fetch` with a handler that sees each request as a URL. Unhandled paths fail the test loudly;
 * `/api/healthz` answers 200 by default so the footer status settles.
 */
export function mockApi(handler: (url: URL) => Response | Promise<Response> | undefined) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = new URL(String(input), "http://localhost");
    const response = await handler(url);
    if (response) return response;
    if (url.pathname === "/api/healthz") return new Response("{}", { status: 200 });
    throw new Error(`Unexpected request in test: ${url.pathname}${url.search}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Builds an A-Z page response from titles; slugs are derived from titles. */
export function recipePage(titles: string[], nextOffset: number | null = null) {
  return Response.json({
    items: titles.map((title, index) => ({
      id: index + 1,
      slug: title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      title,
      view_count: 0,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    })),
    next_offset: nextOffset,
  });
}
