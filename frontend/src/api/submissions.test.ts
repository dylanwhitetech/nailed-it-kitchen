import { describe, expect, it, vi } from "vitest";
import { fetchSubmissionAvailability, postSubmission } from "./submissions";

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

describe("postSubmission", () => {
  const recipe = { title: "Toast", ingredients: ["bread"], instructions: ["Toast it."] };

  it("posts JSON and returns the pull request URL", async () => {
    const fetchMock = stubJson(
      { status: "submitted", pull_request_url: "https://github.com/owner/repo/pull/12" },
      201,
    );

    await expect(postSubmission(recipe, "token")).resolves.toEqual({
      status: "submitted",
      pullRequestUrl: "https://github.com/owner/repo/pull/12",
    });
    const [path, init] = fetchMock.mock.calls[0] ?? [];
    expect(path).toBe("/api/submissions");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ recipe, turnstile_token: "token" });
  });

  it.each(["javascript:alert(1)", "https://evil.example/owner/repo/pull/1", "https://github.com/o/r/issues/1"])(
    "does not trust a success URL of %j",
    async (url) => {
      stubJson({ status: "submitted", pull_request_url: url }, 201);

      await expect(postSubmission(recipe, "token")).resolves.toMatchObject({
        status: "error",
        code: "unexpected_response",
        retryable: false,
      });
    },
  );

  it("returns field errors from the server", async () => {
    stubJson(
      { detail: { code: "invalid_recipe", message: "Check the recipe.", errors: ["recipe.title: too long", 3] } },
      422,
    );

    await expect(postSubmission(recipe, "token")).resolves.toEqual({
      status: "error",
      code: "invalid_recipe",
      message: "Check the recipe.",
      errors: ["recipe.title: too long"],
      retryable: false,
      retryAfterSeconds: null,
      httpStatus: 422,
    });
  });

  it("reads Retry-After when rate limited", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ detail: { code: "rate_limited", message: "Slow down." } }), {
          status: 429,
          headers: { "Retry-After": "120" },
        }),
      ),
    );

    await expect(postSubmission(recipe, "token")).resolves.toMatchObject({
      code: "rate_limited",
      retryable: true,
      retryAfterSeconds: 120,
    });
  });

  it("keeps the server's retryable flag for publish failures", async () => {
    stubJson({ detail: { code: "publish_failed", message: "Not now.", retryable: false } }, 502);

    await expect(postSubmission(recipe, "token")).resolves.toMatchObject({ code: "publish_failed", retryable: false });
  });

  it("reports network failures without throwing", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline")));
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(postSubmission(recipe, "token")).resolves.toMatchObject({
      code: "network_error",
      retryable: true,
      httpStatus: null,
    });
  });
});