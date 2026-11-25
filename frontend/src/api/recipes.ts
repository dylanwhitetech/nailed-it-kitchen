import { ApiError, apiGet } from "./client";

/** Recipe identity used in lists, from the API's recipe summary. */
export interface RecipeSummary {
  slug: string;
  title: string;
}

/** One A-Z page; `nextOffset` is `null` on the last page. */
export interface RecipePage {
  items: RecipeSummary[];
  nextOffset: number | null;
}

/** A plain-text recipe. Ingredients and instructions keep the server's order. */
export interface RecipeDetail extends RecipeSummary {
  ingredients: string[];
  instructions: string[];
  source: string | null;
  notes: string[] | null;
}

/** Recipes per A-Z page. Keep it with `q` unchanged when following `nextOffset`. */
export const RECIPE_PAGE_SIZE = 20;
/** Size of the home page's most-viewed section (the API allows at most 10). */
export const MOST_VIEWED_LIMIT = 5;

function unexpected(path: string, status: number): ApiError {
  return new ApiError(`Unexpected response from ${path}`, status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function toSummary(value: unknown): RecipeSummary | null {
  if (!isRecord(value) || typeof value.slug !== "string" || typeof value.title !== "string") return null;
  return { slug: value.slug, title: value.title };
}

function toSummaries(value: unknown): RecipeSummary[] | null {
  if (!Array.isArray(value)) return null;
  const summaries = value.map(toSummary);
  return summaries.every((summary) => summary !== null) ? (summaries as RecipeSummary[]) : null;
}

async function readJson(path: `/api/${string}`, signal?: AbortSignal): Promise<{ body: unknown; status: number }> {
  const response = await apiGet(path, signal);
  return { body: await response.json().catch(() => undefined), status: response.status };
}

/**
 * Reads one case-insensitive A-Z page, optionally filtered by keywords.
 * A blank `query` browses every recipe.
 *
 * @throws {ApiError} when the backend is unreachable, errors or returns an unexpected shape.
 */
export async function fetchRecipePage(query: string, offset: number, signal?: AbortSignal): Promise<RecipePage> {
  const params = new URLSearchParams({ limit: String(RECIPE_PAGE_SIZE), offset: String(offset) });
  if (query.trim()) params.set("q", query.trim());
  const path = `/api/recipes?${params.toString()}` as const;
  const { body, status } = await readJson(path, signal);
  if (isRecord(body)) {
    const items = toSummaries(body.items);
    const next = body.next_offset;
    if (items && (next === null || (typeof next === "number" && Number.isInteger(next)))) {
      return { items, nextOffset: next };
    }
  }
  throw unexpected("/api/recipes", status);
}

/**
 * Reads the small most-viewed list for the home page.
 *
 * @throws {ApiError} when the backend is unreachable, errors or returns an unexpected shape.
 */
export async function fetchMostViewed(signal?: AbortSignal): Promise<RecipeSummary[]> {
  const { body, status } = await readJson(`/api/most-viewed?limit=${MOST_VIEWED_LIMIT}`, signal);
  const items = toSummaries(body);
  if (items) return items;
  throw unexpected("/api/most-viewed", status);
}

/**
 * Reads one recipe by slug. Each successful read counts as a view on the server.
 *
 * @throws {ApiError} with `status` 404 for an unknown slug, or on any other failure.
 */
export async function fetchRecipe(slug: string, signal?: AbortSignal): Promise<RecipeDetail> {
  const { body, status } = await readJson(`/api/recipes/${encodeURIComponent(slug)}`, signal);
  const summary = toSummary(body);
  if (summary && isRecord(body) && isStringList(body.ingredients) && isStringList(body.instructions)) {
    const { source, notes } = body;
    if ((source === null || source === undefined || typeof source === "string") &&
      (notes === null || notes === undefined || isStringList(notes))) {
      return {
        ...summary,
        ingredients: body.ingredients,
        instructions: body.instructions,
        source: source ?? null,
        notes: notes ?? null,
      };
    }
  }
  throw unexpected("/api/recipes/{slug}", status);
}
