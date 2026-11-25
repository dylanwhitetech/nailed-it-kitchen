import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { mockApi } from "../testing/mockApi";
import { RecipePage } from "./RecipePage";

const recipe = {
  id: 1,
  slug: "tomato-soup",
  title: "Tomato <b>soup</b>",
  view_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ingredients: ["4 tomatoes", "1 onion <script>alert(1)</script>"],
  instructions: ["Chop everything.", "Simmer for 20 minutes.\nStir now and then."],
  source: null,
  notes: null,
};

describe("RecipePage", () => {
  it("renders the title, ingredients then numbered instructions as escaped text", async () => {
    const fetchMock = mockApi((url) => (url.pathname === "/api/recipes/tomato-soup" ? Response.json(recipe) : undefined));
    const { container } = render(<RecipePage slug="tomato-soup" />);

    expect(await screen.findByRole("heading", { level: 1, name: "Tomato <b>soup</b>" })).toBeInTheDocument();
    expect(container.querySelector("b, script")).toBeNull();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(headings).toEqual(["Ingredients", "Instructions"]);
    expect(screen.getByText("1 onion <script>alert(1)</script>")).toBeInTheDocument();
    const steps = screen.getAllByRole("listitem").filter((item) => item.closest("ol"));
    expect(steps.map((step) => step.textContent)).toEqual(["Chop everything.", "Simmer for 20 minutes.\nStir now and then."]);
    await waitFor(() => expect(document.title).toBe("Tomato <b>soup</b> | Nailed It Kitchen"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("encodes the slug in the API path", async () => {
    const fetchMock = mockApi(() => new Response("{}", { status: 404 }));
    render(<RecipePage slug="a/b c" />);
    await screen.findByRole("heading", { name: "Recipe not found" });
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/recipes/a%2Fb%20c");
  });

  it("shows a not-found page for an unknown slug", async () => {
    mockApi(() => Response.json({ detail: "Recipe was not found" }, { status: 404 }));
    render(<RecipePage slug="missing" />);

    expect(await screen.findByRole("heading", { level: 1, name: "Recipe not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse all recipes" })).toHaveAttribute("href", "/recipes");
    await waitFor(() => expect(document.title).toBe("Recipe not found | Nailed It Kitchen"));
  });

  it("shows a retryable error without a success-shaped fallback", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let fail = true;
    mockApi(() => (fail ? new Response("boom", { status: 500 }) : Response.json(recipe)));
    const user = userEvent.setup();
    render(<RecipePage slug="tomato-soup" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong loading this recipe (HTTP 500).");
    expect(screen.queryByRole("heading", { name: "Ingredients" })).not.toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Ingredients" })).toBeInTheDocument();
  });
});
