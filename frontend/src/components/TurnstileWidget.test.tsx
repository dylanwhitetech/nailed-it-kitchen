import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TurnstileWidget } from "./TurnstileWidget";

afterEach(() => {
  delete window.turnstile;
});

describe("TurnstileWidget", () => {
  it("renders with the site key, forwards tokens and clears them on expiry", async () => {
    type Api = NonNullable<Window["turnstile"]>;
    let options: Parameters<Api["render"]>[1] | undefined;
    const remove = vi.fn<Api["remove"]>();
    window.turnstile = {
      render: vi.fn<Api["render"]>((_container, opts) => {
        options = opts;
        return "widget-1";
      }),
      remove,
    };
    const onToken = vi.fn<(token: string | null) => void>();

    const { unmount } = render(<TurnstileWidget siteKey="site-key" onToken={onToken} />);
    await act(async () => {});

    expect(options?.sitekey).toBe("site-key");
    options?.callback("token-1");
    options?.["expired-callback"]();
    options?.["error-callback"]();
    expect(onToken.mock.calls).toEqual([["token-1"], [null], [null]]);

    unmount();
    expect(remove).toHaveBeenCalledWith("widget-1");
  });
});
