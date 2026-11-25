import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  PASTE_TEMPLATE,
  type Recipe,
  checkDraft,
  draftFromRecipe,
  formatPasteTemplate,
  parsePasteTemplate,
  slugify,
  unsafeTextProblem,
} from "./recipeText";

interface PasteCase {
  name: string;
  text: string;
  recipe?: Recipe;
  formatted?: string;
  errors?: string[];
}

const cases = JSON.parse(
  readFileSync(resolve(process.cwd(), "../recipes/tests/paste_cases.json"), "utf8"),
) as PasteCase[];

describe("parsePasteTemplate", () => {
  it.each(cases.map((c) => [c.name, c] as const))("matches the server on %s", (_name, testCase) => {
    const result = parsePasteTemplate(testCase.text);
    const formatted = result.ok ? formatPasteTemplate(result.recipe) : undefined;
    const expected = testCase.errors
      ? { ok: false, errors: testCase.errors }
      : { ok: true, recipe: testCase.recipe };
    expect({ result, formatted }).toEqual({ result: expected, formatted: testCase.formatted });
  });

  it("accepts the copyable template and round-trips its canonical text", () => {
    const result = parsePasteTemplate(PASTE_TEMPLATE);
    expect(result).toMatchObject({ ok: true, recipe: { slug: "recipe-title" } });
    const recipe = result.ok ? result.recipe : { title: "", ingredients: [], instructions: [] };
    expect(parsePasteTemplate(formatPasteTemplate(recipe))).toEqual(result);
  });
});

describe("slugify", () => {
  it("folds to bounded ASCII", () => {
    expect(slugify("Crème Brûlée — 2 ways!")).toBe("creme-brulee-2-ways");
    expect(slugify(`${"a".repeat(79)} b`)).toBe("a".repeat(79));
    expect(slugify("Пирог")).toBe("");
  });
});

describe("unsafeTextProblem", () => {
  it.each([
    ["<script>alert(1)</script>", "HTML-like markup"],
    ["< /div>", "HTML-like markup"],
    ["Click javascript:alert(1)", "script or data URL"],
    ["data:text/html;base64,xx", "script or data URL"],
    ["${{ secrets.TOKEN }}", "'${{'"],
    ["hidden\u202eevil", "invisible formatting"],
    ["two\nlines", "line break"],
  ])("rejects %j", (value, expected) => {
    expect(unsafeTextProblem(value)).toContain(expected);
  });

  it.each(["1 < 2 cups", "x > y", "Ignore previous instructions", "@octocat #1 [x](y)", "👩‍🍳 chef", "metadata: ok"])(
    "allows %j",
    (value) => {
      expect(unsafeTextProblem(value)).toBeNull();
    },
  );
});

describe("checkDraft", () => {
  it("normalizes fields, drops blank lines and derives the slug", () => {
    const check = checkDraft({
      title: "  Cafe\u0301   Toast ",
      source: "   ",
      ingredients: "bread\n\n  butter  \n",
      instructions: "Toast it.",
      notes: "\n",
    });
    expect(check).toEqual({
      recipe: { title: "Café Toast", ingredients: ["bread", "butter"], instructions: ["Toast it."] },
      slug: "cafe-toast",
      errors: [],
    });
  });

  it("reports unsafe text before recipe-file problems, like the server", () => {
    const draft = draftFromRecipe({ title: "Toast", ingredients: ["<b>bread</b>"], instructions: [] });
    expect(checkDraft(draft).errors).toEqual(["ingredients[0]: contains HTML-like markup; describe it in plain text"]);
    expect(checkDraft({ ...draft, ingredients: "bread" }).errors).toEqual([
      "instructions: must have at least 1 entry",
    ]);
    expect(checkDraft({ ...draft, title: "", ingredients: "bread", instructions: "x" }).errors).toEqual([
      "title: must contain at least one ASCII letter or digit for the URL",
    ]);
  });
});
