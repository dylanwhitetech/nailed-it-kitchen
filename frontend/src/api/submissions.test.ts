import { describe, expect, it, vi } from "vitest";
import { fetchSubmissionAvailability } from "./submissions";

function stubJson(body: unknown, status = 200) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("fetchSubmissionAvailability", () => {
  it("maps an open response with its site key", async () => {
    const fetchMock = stubJson({ enabled: true, turnstile_site_key: "site-key" });

    await expect(fetchSubmissionAvailability()).resolves.toEqual({ enabled: true, turnstileSiteKey: "site-key" });
    expect(fetchMock).toHaveBeenCalledWith("/api/submissions/availability", expect.anything());
  });

  it("maps a paused response", async () => {
    stubJson({ enabled: false, turnstile_site_key: null });

    await expect(fetchSubmissionAvailability()).resolves.toEqual({ enabled: false, turnstileSiteKey: null });
  });

  it.each([{ enabled: true, turnstile_site_key: null }, { enabled: "yes" }, null])(
    "rejects an unexpected shape %j",
    async (body) => {
      stubJson(body);

      await expect(fetchSubmissionAvailability()).rejects.toMatchObject({ name: "ApiError" });
    },
  );
});
