import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PASTE_TEMPLATE } from "../submission/recipeText";
import { SubmitPage } from "./SubmitPage";

type Api = NonNullable<Window["turnstile"]>;
let turnstile: Parameters<Api["render"]>[1] | undefined;
let renders = 0;

beforeEach(() => {
  renders = 0;
  window.turnstile = {
    render: (_container, options) => {
      turnstile = options;
      renders += 1;
      return `widget-${renders}`;
    },
    remove: () => undefined,
  };
});

afterEach(() => {
  delete window.turnstile;
  turnstile = undefined;
});

const PASTED = `Toast <b>deluxe</b>
Source: Grandma

Ingredients
- 2 slices bread

Instructions
1. Toast the bread.`;

function stubApi(submit: () => Response | Promise<Response>, enabled = true) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    if (String(input) === "/api/submissions/availability") {
      return Response.json(enabled ? { enabled: true, turnstile_site_key: "site-key" } : { enabled: false });
    }
    return submit();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function previewRecipe(text: string) {
  const user = userEvent.setup();
  render(<SubmitPage />);
  const pasteBox = await screen.findByLabelText("Your filled-in recipe");
  await user.click(pasteBox);
  await user.paste(text);
  await user.click(screen.getByRole("button", { name: "Preview recipe" }));
  return user;
}

async function readyToSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("checkbox", { name: /my recipe will be public/ }));
  await act(async () => turnstile?.callback("token-1"));
}

const VALID = PASTED.replace(" <b>deluxe</b>", "");

describe("SubmitPage", () => {
  it("explains paused submissions without the form", async () => {
    stubApi(() => new Response(null, { status: 500 }), false);
    render(<SubmitPage />);

    expect(await screen.findByText(/submissions are paused/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Your filled-in recipe")).not.toBeInTheDocument();
  });

  it("copies the template and falls back to manual copy", async () => {
    stubApi(() => new Response(null, { status: 500 }));
    const user = userEvent.setup();
    render(<SubmitPage />);
    const button = await screen.findByRole("button", { name: "Copy template" });
    const writeText = vi.spyOn(navigator.clipboard, "writeText");

    await user.click(button);
    expect(writeText).toHaveBeenCalledWith(PASTE_TEMPLATE);
    expect(screen.getByText("Template copied.")).toBeInTheDocument();

    writeText.mockRejectedValueOnce(new Error("denied"));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await user.click(button);
    expect(screen.getByText(/Select the template text and copy it manually/)).toBeInTheDocument();
  });

  it("lists parse problems", async () => {
    stubApi(() => new Response(null, { status: 500 }));
    await previewRecipe("Toast\n\nIngredients\n- bread");

    expect(screen.getByRole("alert")).toHaveTextContent("Instructions");
    expect(screen.queryByRole("heading", { name: "3. Review and submit" })).not.toBeInTheDocument();
  });

  it("shows hostile text literally and blocks it until edited", async () => {
    stubApi(() => new Response(null, { status: 500 }));
    const user = await previewRecipe(PASTED);
    await readyToSubmit(user);

    expect(screen.getByRole("heading", { name: "Toast <b>deluxe</b>" })).toBeInTheDocument();
    expect(document.querySelector(".submission-preview b")).toBeNull();
    expect(screen.getByText(/title: contains HTML-like markup/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Submit recipe" });
    expect(submit).toBeDisabled();

    const title = screen.getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Best Toast");
    expect(screen.getByText("Preview of recipes/best-toast.yaml")).toBeInTheDocument();
    expect(submit).toBeEnabled();
  });

  it("submits once and links to the pull request", async () => {
    let release: (response: Response) => void = () => undefined;
    const fetchMock = stubApi(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    );
    const user = await previewRecipe(VALID);
    await readyToSubmit(user);

    const submit = screen.getByRole("button", { name: "Submit recipe" });
    await user.click(submit);
    await user.click(screen.getByRole("button", { name: "Submitting…" }));
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/submissions")).toHaveLength(1);
    const body = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body));
    expect(body).toEqual({
      recipe: { title: "Toast", source: "Grandma", ingredients: ["2 slices bread"], instructions: ["Toast the bread."] },
      turnstile_token: "token-1",
    });

    await act(async () =>
      release(Response.json({ status: "submitted", pull_request_url: "https://github.com/o/r/pull/7" }, { status: 201 })),
    );
    expect(screen.getByRole("status")).toHaveTextContent("your recipe was submitted");
    expect(screen.getByRole("link", { name: "View the pull request on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/pull/7",
    );
  });

  it("keeps the recipe and resets the challenge after an error", async () => {
    stubApi(() =>
      Response.json(
        { detail: { code: "rate_limited", message: "Too many submissions." } },
        { status: 429, headers: { "Retry-After": "90" } },
      ),
    );
    const user = await previewRecipe(VALID);
    await readyToSubmit(user);
    const rendersBefore = renders;

    await user.click(screen.getByRole("button", { name: "Submit recipe" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Too many submissions.");
    expect(alert).toHaveTextContent("about 2 minutes");
    expect(screen.getByLabelText("Title")).toHaveValue("Toast");
    expect(renders).toBe(rendersBefore + 1);
    expect(screen.getByRole("button", { name: "Submit recipe" })).toBeDisabled();
  });

  it("shows server field errors", async () => {
    stubApi(() =>
      Response.json(
        { detail: { code: "invalid_recipe", message: "Check the recipe.", errors: ["recipe.title: too long"] } },
        { status: 422 },
      ),
    );
    const user = await previewRecipe(VALID);
    await readyToSubmit(user);
    await user.click(screen.getByRole("button", { name: "Submit recipe" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("recipe.title: too long");
  });
});
