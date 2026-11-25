/*
 * Browser copy of the recipe paste contract in recipes/validate.py and the unsafe-text checks in
 * backend/app/submissions.py. It powers the preview only: the server repeats every check and is
 * authoritative. recipes/tests/paste_cases.json keeps both parsers on the same golden cases.
 */

/** A submittable recipe: the slug is derived by the server from the title. */
export interface RecipeFields {
  title: string;
  source?: string;
  ingredients: string[];
  instructions: string[];
  notes?: string[];
}

/** A recipe with its derived URL slug, as stored in `recipes/<slug>.yaml`. */
export interface Recipe extends RecipeFields {
  slug: string;
}

export type ParseResult = { ok: true; recipe: Recipe } | { ok: false; errors: string[] };

export const MAX_CONTENT_CHARS = 20_000;
const MAX_SLUG_CHARS = 80;
const MAX_ENTRIES = 100;
const MAX_CHARS = { title: 160, source: 300, ingredients: 500, instructions: 2000, notes: 1000 } as const;

/** Copyable single-recipe template; it parses as a valid recipe. */
export const PASTE_TEMPLATE = `Recipe title
Source: where the recipe came from (optional; delete this line if none)

Ingredients
- 1 cup flour
- 2 eggs

Instructions
1. First step, on one line.
2. Second step.

Notes
- Optional yield, equipment or tips (delete this section if none)`;

// Python's str whitespace (re \s and str.strip), which differs from JavaScript's \s.
const WS = "\\t\\n\\v\\f\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const WHITESPACE_RUN = new RegExp(`[${WS}]+`, "gu");
const EDGE_WHITESPACE = new RegExp(`^[${WS}]+|[${WS}]+$`, "gu");
// Control characters are matched on purpose: the server rejects them.
// oxlint-disable-next-line no-control-regex
const PASTE_CONTROL = /[\x00-\x08\x0b-\x1f\x7f-\x9f]/u;
const HEADING_PREFIX = new RegExp(`^#{1,6}[${WS}]+`, "u");
const SECTION_HEADER = new RegExp(
  `^(?:#{1,6}[${WS}]+)?(ingredients|instructions|directions|steps|notes)[${WS}]*:?$`,
  "iu",
);
const SOURCE_LINE = new RegExp(`^(?:source|credit)[${WS}]*:[${WS}]*(.*)$`, "isu");
const BULLET = new RegExp(`^[-*\\u2022][${WS}]+`, "u");
// Python's \d also accepts non-ASCII digits; the server stays authoritative for those rare steps.
const STEP_NUMBER = new RegExp(`^([0-9]{1,3})[.)][${WS}]+`, "u");
const EMPTY_STEP_NUMBER = /^[0-9]{1,3}[.)]$/u;
const LINE_PATTERN = new RegExp(
  `^(?:[^${WS}\\x00-\\x1f\\x7f-\\x9f](?:[^\\x00-\\x1f\\x7f-\\x9f]*[^${WS}\\x00-\\x1f\\x7f-\\x9f])?)?$`,
  "u",
);
const SECTION_NAMES: Record<string, string> = {
  ingredients: "Ingredients",
  instructions: "Instructions",
  directions: "Instructions",
  steps: "Instructions",
  notes: "Notes",
};

// oxlint-disable-next-line no-control-regex
const FIELD_CONTROL = /[\x00-\x08\x0a-\x1f\x7f-\x9f]/u;
const FORMAT_CHAR = /\p{Cf}/gu;
// Python's Unicode \b: no letter, digit or underscore directly before the word.
const NOT_WORD_BEFORE = "(?<![\\p{L}\\p{N}_])";
const MARKUP_TAG_START = new RegExp(`<[${WS}]*(?:/[${WS}]*)?[a-z!?]`, "iu");
const SCRIPT_URL = new RegExp(
  `${NOT_WORD_BEFORE}(?:javascript|vbscript)[${WS}]*:|${NOT_WORD_BEFORE}data[${WS}]*:[${WS}]*[a-z]+/[a-z0-9.+-]+`,
  "iu",
);

const codePoints = (text: string) => [...text].length;
const quoted = (name: string) => `'${name}'`;

/** Applies NFC, collapses whitespace runs to one space and trims, like the server. */
export function normalizeLine(text: string): string {
  return text.normalize("NFC").replace(WHITESPACE_RUN, " ").replace(EDGE_WHITESPACE, "");
}

/** ASCII-folded, lowercase, hyphen-separated slug of at most 80 characters; empty if none. */
export function slugify(title: string): string {
  const folded = title.normalize("NFKD").replace(/\P{ASCII}/gu, "");
  const slug = folded
    .toLowerCase()
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/^-+|-+$/gu, "");
  return slug.slice(0, MAX_SLUG_CHARS).replace(/-+$/u, "");
}

function formatTitle(title: string): string {
  return title.startsWith("\\") || HEADING_PREFIX.test(title) || SECTION_HEADER.test(title) ? `\\${title}` : title;
}

/** Renders the canonical paste text (no trailing newline); its length is the content size. */
export function formatPasteTemplate(recipe: RecipeFields): string {
  const lines = [formatTitle(recipe.title)];
  if (recipe.source !== undefined) lines.push(`Source: ${recipe.source}`);
  lines.push("", "Ingredients", ...recipe.ingredients.map((item) => `- ${item}`));
  lines.push("", "Instructions", ...recipe.instructions.map((step, index) => `${index + 1}. ${step}`));
  if (recipe.notes !== undefined) lines.push("", "Notes", ...recipe.notes.map((note) => `- ${note}`));
  return lines.join("\n");
}

/** Normalized recipe content size in Unicode code points. */
export function contentLength(recipe: RecipeFields): number {
  return codePoints(formatPasteTemplate(recipe));
}

function textFields(recipe: RecipeFields): [string, string, number][] {
  const fields: [string, string, number][] = [["title", recipe.title, MAX_CHARS.title]];
  if (recipe.source !== undefined) fields.push(["source", recipe.source, MAX_CHARS.source]);
  for (const key of ["ingredients", "instructions", "notes"] as const) {
    recipe[key]?.forEach((value, index) => fields.push([`${key}[${index}]`, value, MAX_CHARS[key]]));
  }
  return fields;
}

/** Returns every recipe-file problem, in the server's order and wording; empty means valid. */
export function validateRecipe(recipe: RecipeFields): string[] {
  const schema: [string, string][] = [];
  for (const key of ["ingredients", "instructions", "notes"] as const) {
    const entries = recipe[key];
    if (entries === undefined) continue;
    if (entries.length < 1) schema.push([`${key}\0minItems`, `${key}: must have at least 1 entry`]);
    if (entries.length > MAX_ENTRIES) {
      schema.push([`${key}\0maxItems`, `${key}: must have at most ${MAX_ENTRIES} entries`]);
    }
  }
  for (const [location, value, max] of textFields(recipe)) {
    if (value === "") schema.push([`${location}\0minLength`, `${location}: must not be empty`]);
    if (codePoints(value) > max) {
      schema.push([`${location}\0maxLength`, `${location}: must be at most ${max} characters`]);
    }
    if (!LINE_PATTERN.test(value)) {
      schema.push([
        `${location}\0pattern`,
        `${location}: must be one line without control characters or surrounding spaces`,
      ]);
    }
  }
  if (schema.length > 0) {
    return schema.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([, message]) => message);
  }
  const problems: string[] = [];
  for (const [location, value] of textFields(recipe)) {
    if (/\p{Cs}/u.test(value)) problems.push(`${location}: contains a surrogate code point`);
    if (normalizeLine(value) !== value) problems.push(`${location}: must be normalized (NFC, single spaces)`);
  }
  const size = contentLength(recipe);
  if (size > MAX_CONTENT_CHARS) {
    problems.push(`recipe content is ${size} characters; the maximum is ${MAX_CONTENT_CHARS}`);
  }
  return problems;
}

class PasteError extends Error {}

function stripBullets(entries: [number, string][]): string[] {
  return entries.map(([number, line]) => {
    const item = line.replace(BULLET, "");
    if (item === "" || item === "-" || item === "*" || item === "\u2022") {
      throw new PasteError(`line ${number}: empty list item`);
    }
    return item;
  });
}

function stripStepNumbers(entries: [number, string][]): string[] {
  for (const [number, line] of entries) {
    if (EMPTY_STEP_NUMBER.test(line)) throw new PasteError(`line ${number}: empty instruction step`);
  }
  const numbered = entries.map(([, line]) => STEP_NUMBER.exec(line));
  if (!numbered.some(Boolean)) return stripBullets(entries);
  return entries.map(([number, line], index) => {
    const match = numbered[index];
    if (!match || Number(match[1]) !== index + 1) {
      throw new PasteError(
        `line ${number}: expected step ${index + 1}; number every instruction in order and keep each step on one line`,
      );
    }
    return line.slice(match[0].length);
  });
}

function parse(text: string): Recipe {
  const lines = text.replace(/^\ufeff/u, "").replace(/\r\n?/gu, "\n").split("\n");
  let title: string | undefined;
  let source: string | undefined;
  const sections = new Map<string, [number, string][]>();
  let current: [number, string][] | undefined;

  lines.forEach((rawLine, index) => {
    const number = index + 1;
    if (PASTE_CONTROL.test(rawLine)) throw new PasteError(`line ${number}: contains a control character`);
    const line = normalizeLine(rawLine);
    if (!line) return;
    const header = SECTION_HEADER.exec(line);
    if (title === undefined) {
      if (line.startsWith("\\")) title = line.slice(1);
      else if (header) throw new PasteError(`line ${number}: the first line must be the recipe title, not a section`);
      else title = line.replace(HEADING_PREFIX, "");
      return;
    }
    if (header) {
      const name = SECTION_NAMES[(header[1] ?? "").toLowerCase()] ?? "";
      if (sections.has(name)) {
        throw new PasteError(
          `line ${number}: found a second ${quoted(name)} section; paste exactly one recipe at a time`,
        );
      }
      if (name !== "Ingredients" && !sections.has("Ingredients")) {
        throw new PasteError(`line ${number}: ${quoted(name)} must come after 'Ingredients'`);
      }
      if (name === "Notes" && !sections.has("Instructions")) {
        throw new PasteError(`line ${number}: 'Notes' must come after 'Instructions'`);
      }
      current = [];
      sections.set(name, current);
      return;
    }
    if (current === undefined) {
      const sourceMatch = SOURCE_LINE.exec(line);
      if (sourceMatch && source === undefined) {
        source = sourceMatch[1] ?? "";
        if (!source) throw new PasteError(`line ${number}: 'Source:' needs text or should be removed`);
        return;
      }
      const after = source !== undefined ? "the title and source" : "the title";
      throw new PasteError(`line ${number}: expected 'Ingredients' after ${after}; remove or move this text`);
    }
    current.push([number, line]);
  });

  if (title === undefined) throw new PasteError("the paste is empty; start with the recipe title");
  for (const name of ["Ingredients", "Instructions"]) {
    if (!sections.has(name)) throw new PasteError(`missing the ${quoted(name)} section`);
  }
  for (const [name, entries] of sections) {
    if (entries.length === 0) throw new PasteError(`the ${quoted(name)} section has no entries`);
  }
  const slug = slugify(title);
  if (!slug) throw new PasteError("title: must contain at least one ASCII letter or digit for the URL");
  const recipe: Recipe = {
    slug,
    title,
    ...(source !== undefined && { source }),
    ingredients: stripBullets(sections.get("Ingredients") ?? []),
    instructions: stripStepNumbers(sections.get("Instructions") ?? []),
  };
  const notes = sections.get("Notes");
  if (notes) recipe.notes = stripBullets(notes);
  return recipe;
}

/** Extracts exactly one recipe from pasted template text without guessing. */
export function parsePasteTemplate(text: string): ParseResult {
  try {
    const recipe = parse(text);
    const problems = validateRecipe(recipe);
    return problems.length > 0 ? { ok: false, errors: problems } : { ok: true, recipe };
  } catch (error) {
    if (error instanceof PasteError) return { ok: false, errors: [error.message] };
    throw error;
  }
}

function containsMarkup(value: string): boolean {
  const closing = value.lastIndexOf(">");
  return closing > 0 && MARKUP_TAG_START.test(value.slice(0, closing));
}

/** The server's unsafe-text check for one field value, or `null` when it is allowed. */
export function unsafeTextProblem(value: string): string | null {
  if (FIELD_CONTROL.test(value)) return "contains a line break or control character; keep each entry on one line";
  if ((value.match(FORMAT_CHAR) ?? []).some((char) => char !== "\u200d")) {
    return "contains an invisible formatting character";
  }
  if (containsMarkup(value)) return "contains HTML-like markup; describe it in plain text";
  if (SCRIPT_URL.test(value)) return "contains a script or data URL";
  if (value.includes("${{")) return "contains '${{', which is not allowed";
  return null;
}

/** Editable preview fields; list fields hold one entry per line. */
export interface RecipeDraft {
  title: string;
  source: string;
  ingredients: string;
  instructions: string;
  notes: string;
}

/** Fills the editable fields from a parsed recipe. */
export function draftFromRecipe(recipe: RecipeFields): RecipeDraft {
  return {
    title: recipe.title,
    source: recipe.source ?? "",
    ingredients: recipe.ingredients.join("\n"),
    instructions: recipe.instructions.join("\n"),
    notes: (recipe.notes ?? []).join("\n"),
  };
}

export interface DraftCheck {
  /** Normalized fields to submit; blank list lines and an empty source or notes are dropped. */
  recipe: RecipeFields;
  /** Derived URL slug; empty when the title has no ASCII letters or digits. */
  slug: string;
  /** Problems the server would report, without its `recipe.` prefix; empty means submittable. */
  errors: string[];
}

const listEntries = (text: string) =>
  text
    .split("\n")
    .map(normalizeLine)
    .filter((line) => line !== "");

/**
 * Deterministically converts the editable fields into the submission recipe and lists every
 * problem the server would reject: unsafe text first, then the recipe-file contract.
 */
export function checkDraft(draft: RecipeDraft): DraftCheck {
  const source = normalizeLine(draft.source);
  const notes = listEntries(draft.notes);
  const recipe: RecipeFields = {
    title: normalizeLine(draft.title),
    ...(source !== "" && { source }),
    ingredients: listEntries(draft.ingredients),
    instructions: listEntries(draft.instructions),
    ...(notes.length > 0 && { notes }),
  };
  const slug = slugify(recipe.title);
  const unsafe = textFields(recipe).flatMap(([location, value]) => {
    const problem = unsafeTextProblem(value);
    return problem ? [`${location}: ${problem}`] : [];
  });
  if (unsafe.length > 0) return { recipe, slug, errors: unsafe };
  if (slug === "") return { recipe, slug, errors: ["title: must contain at least one ASCII letter or digit for the URL"] };
  return { recipe, slug, errors: validateRecipe(recipe) };
}
