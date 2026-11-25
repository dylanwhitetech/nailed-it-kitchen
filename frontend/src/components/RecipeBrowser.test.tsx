import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockApi, recipePage } from "../testing/mockApi";
import { RecipeBrowser } from "./RecipeBrowser";

afterEach(() => window.history.replaceState(null, "", "/"));

function titles(prefix: string, count: number) {
  return Array.from({ length: count }, (_, index) => `${prefix} ${String(index + 1).padStart(2, "0")}`);
}

describe("RecipeBrowser", () => {
  it("pages through the A-Z list with load more, moving focus to the first new recipe", async () => {
    const fetchMock = mockApi((url) => {
      if (url.pathname !== "/api/recipes") return undefined;
      return url.searchParams.get("offset") === "0" ? recipePage(titles("Apple", 20), 20) : recipePage(["Zucchini bread"]);
    });
    const user = userEvent.setup();
    render(<RecipeBrowser />);

    const list = await screen.findByRole("list", { name: "Recipes A to Z" });
    expect(within(list).getAllByRole("link")).toHaveLength(20);
    expect(within(list).getByRole("link", { name: "Apple 01" })).toHaveAttribute("href", "/recipes/apple-01");
    expect(screen.getByText("Showing 20 recipes so far.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Load more recipes" }));

    const next = await screen.findByRole("link", { name: "Zucchini bread" });
    await waitFor(() => expect(next).toHaveFocus());
    expect(screen.getByText("Showing 21 recipes.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more recipes" })).not.toBeInTheDocument();
    const second = new URL(String(fetchMock.mock.calls[1]?.[0]), "http://localhost");
    expect(second.searchParams.get("offset")).toBe("20");
    expect(second.searchParams.get("limit")).toBe("20");
  });

  it("debounces keyword search, mirrors it in the URL and restarts pagination", async () => {
    const fetchMock = mockApi((url) => {
      if (url.pathname !== "/api/recipes") return undefined;
      const q = url.searchParams.get("q");
      if (q === "soup") return recipePage(["Tomato soup"]);
      return recipePage(titles("Apple", 20), 20);
    });
    const user = userEvent.setup();
    render(<RecipeBrowser />);
    await screen.findByRole("list", { name: "Recipes A to Z" });

    await user.type(screen.getByRole("searchbox", { name: "Search recipes" }), "soup");

    expect(await screen.findByRole("link", { name: "Tomato soup" })).toBeInTheDocument();
    expect(screen.getByText("Showing 1 recipe matching “soup”.")).toBeInTheDocument();
    expect(window.location.search).toBe("?q=soup");
    const searches = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), "http://localhost"))
      .filter((url) => url.searchParams.has("q"));
    expect(searches).toHaveLength(1);
    expect(searches[0]?.searchParams.get("offset")).toBe("0");
    expect(screen.queryByRole("button", { name: "Load more recipes" })).not.toBeInTheDocument();
  });

  it("restores the query from the URL and shows an empty result", async () => {
    window.history.replaceState(null, "", "/recipes?q=nothing");
    mockApi((url) => (url.pathname === "/api/recipes" && url.searchParams.get("q") === "nothing" ? recipePage([]) : undefined));
    render(<RecipeBrowser />);

    expect(await screen.findByText("No recipes match “nothing”.")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search recipes" })).toHaveValue("nothing");
  });

  it("ignores a slower response for an older query", async () => {
    let releaseOld: (response: Response) => void = () => {};
    mockApi((url) => {
      if (url.pathname !== "/api/recipes") return undefined;
      const q = url.searchParams.get("q");
      if (q === "old") return new Promise<Response>((resolve) => (releaseOld = resolve));
      if (q === "new") return recipePage(["New stew"]);
      return recipePage([]);
    });
    const user = userEvent.setup();
    render(<RecipeBrowser />);
    const search = screen.getByRole("searchbox", { name: "Search recipes" });

    await user.type(search, "old{Enter}");
    await user.clear(search);
    await user.type(search, "new{Enter}");
    expect(await screen.findByRole("link", { name: "New stew" })).toBeInTheDocument();

    releaseOld(recipePage(["Old stew"]));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole("link", { name: "Old stew" })).not.toBeInTheDocument();
  });

  it("reports an unavailable service and retries", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let fail = true;
    mockApi((url) => {
      if (url.pathname !== "/api/recipes") return undefined;
      return fail ? new Response("down", { status: 503 }) : recipePage(["Pancakes"]);
    });
    const user = userEvent.setup();
    render(<RecipeBrowser />);

    expect(await screen.findByRole("alert")).toHaveTextContent("The recipe service is unavailable right now");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: "Pancakes" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
