import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { mockApi, recipePage } from "./testing/mockApi";

/** Stubs health plus empty recipe reads; `ok=false` makes every API call fail with 503. */
function stubApi(ok: boolean) {
  mockApi((url) => {
    if (!ok) return new Response("down", { status: 503 });
    if (url.pathname === "/api/recipes") return recipePage([]);
    if (url.pathname === "/api/most-viewed") return Response.json([]);
    return undefined;
  });
}

/** Renders the app and waits for the health check to settle, avoiding act() warnings. */
async function renderApp(pathname: string) {
  render(<App pathname={pathname} />);
  await waitFor(() => expect(screen.getByRole("status")).not.toHaveTextContent("Checking"));
}

describe("App shell", () => {
  it("shows the site name as text, the beta identity and a skip link", async () => {
    stubApi(true);
    await renderApp("/");

    const home = screen.getByRole("link", { name: "Nailed It Kitchen" });
    expect(home).toHaveAttribute("href", "/");
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(await screen.findByText("Recipe service is available.")).toBeInTheDocument();
  });

  it("marks the current page in the main navigation", async () => {
    stubApi(true);
    await renderApp("/recipes/");

    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Recipes" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("heading", { level: 1, name: "Recipes" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search recipes" })).toBeInTheDocument();
  });

  it("renders a not-found page for unknown paths", async () => {
    stubApi(true);
    await renderApp("/nope");

    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("routes recipe slugs to the recipe page", async () => {
    mockApi((url) =>
      url.pathname === "/api/recipes/tomato-soup"
        ? Response.json({ slug: "tomato-soup", title: "Tomato soup", ingredients: ["Tomatoes"], instructions: ["Cook."] })
        : undefined,
    );
    await renderApp("/recipes/tomato-soup");
    expect(await screen.findByRole("heading", { level: 1, name: "Tomato soup" })).toBeInTheDocument();
  });

  it("does not treat nested recipe paths as recipes", async () => {
    stubApi(true);
    await renderApp("/recipes/a/b");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("reports an unavailable backend without hiding the page", async () => {
    stubApi(false);
    vi.spyOn(console, "error").mockImplementation(() => {});
    await renderApp("/");

    expect(await screen.findByRole("status")).toHaveTextContent("Recipe service is unavailable");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Welcome to Nailed It Kitchen");
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
  });
});

describe("Home page", () => {
  it("shows a bounded most-viewed section separate from the A-Z list", async () => {
    const fetchMock = mockApi((url) => {
      if (url.pathname === "/api/most-viewed") {
        return Response.json([
          { slug: "pancakes", title: "Pancakes" },
          { slug: "chili", title: "Chili" },
        ]);
      }
      if (url.pathname === "/api/recipes") return recipePage(["Apple pie", "Chili", "Pancakes"]);
      return undefined;
    });
    await renderApp("/");

    const popular = await screen.findByRole("list", { name: "Most viewed recipes" });
    expect(popular.tagName).toBe("OL");
    expect(within(popular).getAllByRole("link").map((link) => link.textContent)).toEqual(["Pancakes", "Chili"]);
    const az = await screen.findByRole("list", { name: "Recipes A to Z" });
    expect(within(az).getAllByRole("link").map((link) => link.textContent)).toEqual(["Apple pie", "Chili", "Pancakes"]);
    expect(screen.getByRole("heading", { level: 2, name: "Most viewed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Recipes A–Z" })).toBeInTheDocument();
    const mostViewedCall = fetchMock.mock.calls.find(([input]) => String(input).startsWith("/api/most-viewed"));
    expect(String(mostViewedCall?.[0])).toBe("/api/most-viewed?limit=5");
  });
});
