import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { checkHealth } from "./health";

describe("checkHealth", () => {
  it("requests the same-origin liveness endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(checkHealth()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/api/healthz", expect.anything());
  });

  it("raises ApiError with the status for non-2xx responses", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response("down", { status: 503 })));

    await expect(checkHealth()).rejects.toMatchObject({ name: "ApiError", status: 503 });
  });

  it("raises ApiError without a status when the network fails", async () => {
    const cause = new TypeError("Failed to fetch");
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(cause));

    const error = await checkHealth().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: undefined, cause });
  });
});
