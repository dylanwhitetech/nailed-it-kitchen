import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

function stubHealth(ok: boolean) {
  vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response("{}", { status: ok ? 200 : 503 })));
}

/** Renders the app and waits for the health check to settle, avoiding act() warnings. */
async function renderApp(pathname: string) {
  render(<App pathname={pathname} />);
  await waitFor(() => expect(screen.getByRole("status")).not.toHaveTextContent("Checking"));
}

describe("App shell", () => {
  it("shows the site name as text, the beta identity and a skip link", async () => {
    stubHealth(true);
    await renderApp("/");

    const home = screen.getByRole("link", { name: "Nailed It Kitchen" });
    expect(home).toHaveAttribute("href", "/");
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(await screen.findByText("Recipe service is available.")).toBeInTheDocument();
  });

  it("marks the current page in the main navigation", async () => {
    stubHealth(true);
    await renderApp("/recipes/");

    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Recipes" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("heading", { level: 1, name: "Recipes" })).toBeInTheDocument();
  });

  it("renders a not-found page for unknown paths", async () => {
    stubHealth(true);
    await renderApp("/nope");

    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("reports an unavailable backend without hiding the page", async () => {
    stubHealth(false);
    vi.spyOn(console, "error").mockImplementation(() => {});
    await renderApp("/");

    expect(await screen.findByRole("status")).toHaveTextContent("Recipe service is unavailable");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Welcome to Nailed It Kitchen");
  });
});
