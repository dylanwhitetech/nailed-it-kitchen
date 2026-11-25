import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SubmissionAvailability } from "./SubmissionAvailability";

function renderNotice() {
  render(<SubmissionAvailability>{(siteKey) => <p>Form for {siteKey}</p>}</SubmissionAvailability>);
}

describe("SubmissionAvailability", () => {
  it("renders the submission UI with the site key while open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json({ enabled: true, turnstile_site_key: "site-key" })),
    );
    renderNotice();

    expect(await screen.findByText("Form for site-key")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("explains paused submissions without rendering the form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json({ enabled: false, turnstile_site_key: null })),
    );
    renderNotice();

    expect(await screen.findByText(/submissions are paused/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Browsing and searching recipes still work");
    expect(screen.queryByText(/Form for/)).not.toBeInTheDocument();
  });

  it("treats a failed check as unavailable, not open", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response("down", { status: 503 })));
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderNotice();

    expect(await screen.findByText(/couldn't check whether recipe submissions are open/)).toBeInTheDocument();
    expect(screen.queryByText(/Form for/)).not.toBeInTheDocument();
  });
});
