import { type FormEvent, useEffect, useRef, useState } from "react";
import { fetchRecipePage, type RecipeSummary } from "../api/recipes";
import { LoadError } from "./LoadError";
import { RecipeLinkList } from "./RecipeLinkList";

/** Delay after the last keystroke before searching, in milliseconds. */
export const SEARCH_DEBOUNCE_MS = 300;

type ListState =
  | { status: "loading" }
  | { status: "error"; error: unknown }
  | { status: "ready"; recipes: RecipeSummary[]; nextOffset: number | null };

type MoreState = { status: "idle" | "loading" } | { status: "error"; error: unknown };

function readQueryFromUrl(): string {
  return (new URLSearchParams(window.location.search).get("q") ?? "").trim();
}

/** Keeps `?q=` in the current URL without adding a history entry per keystroke. */
function writeQueryToUrl(query: string) {
  const url = new URL(window.location.href);
  if (query) url.searchParams.set("q", query);
  else url.searchParams.delete("q");
  if (url.href !== window.location.href) window.history.replaceState(window.history.state, "", url);
}

function describeResults(query: string, count: number, hasMore: boolean): string {
  if (count === 0) return query ? `No recipes match “${query}”.` : "No recipes have been added yet.";
  const recipes = `${count} ${count === 1 ? "recipe" : "recipes"}`;
  const matching = query ? ` matching “${query}”` : "";
  return `Showing ${recipes}${matching}${hasMore ? " so far" : ""}.`;
}

interface RecipeResultsProps {
  /** Trimmed keyword query; empty browses A-Z. */
  query: string;
  onRetry: () => void;
}

/**
 * Results for one query, starting from the first page. `RecipeBrowser` remounts it with a new key
 * whenever the query changes or a retry is requested, which resets paging and aborts stale reads.
 */
function RecipeResults({ query, onRetry }: RecipeResultsProps) {
  const [list, setList] = useState<ListState>({ status: "loading" });
  const [more, setMore] = useState<MoreState>({ status: "idle" });
  const moreController = useRef<AbortController | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const paginationFocus = useRef<{ index: number; moved: boolean; ready: boolean } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchRecipePage(query, 0, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) setList({ status: "ready", recipes: page.items, nextOffset: page.nextOffset });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Recipe list failed to load", error);
        setList({ status: "error", error });
      });
    return () => {
      controller.abort();
      moreController.current?.abort();
    };
  }, [query]);

  useEffect(() => {
    function trackFocus() {
      if (paginationFocus.current) paginationFocus.current.moved = true;
    }
    document.addEventListener("focusin", trackFocus);
    return () => document.removeEventListener("focusin", trackFocus);
  }, []);

  useEffect(() => {
    const focus = paginationFocus.current;
    if (!focus?.ready || list.status !== "ready") return;
    paginationFocus.current = null;
    if (!focus.moved) container.current?.querySelectorAll<HTMLAnchorElement>(".recipe-list a")[focus.index]?.focus();
  }, [list]);

  function loadMore() {
    if (list.status !== "ready" || list.nextOffset === null) return;
    const loaded = list.recipes;
    const controller = new AbortController();
    moreController.current?.abort();
    moreController.current = controller;
    const focus = { index: loaded.length, moved: false, ready: false };
    paginationFocus.current = focus;
    setMore({ status: "loading" });
    fetchRecipePage(query, list.nextOffset, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return;
        focus.ready = true;
        setList({ status: "ready", recipes: [...loaded, ...page.items], nextOffset: page.nextOffset });
        setMore({ status: "idle" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        paginationFocus.current = null;
        console.error("More recipes failed to load", error);
        setMore({ status: "error", error });
      });
  }

  const subject = query ? "search results" : "recipes";
  let summary = query ? "Searching recipes…" : "Loading recipes…";
  if (list.status === "error") summary = "";
  if (list.status === "ready") summary = describeResults(query, list.recipes.length, list.nextOffset !== null);

  return (
    <div ref={container}>
      <p className="recipe-section__note" aria-live="polite">
        {summary}
      </p>
      {list.status === "error" && <LoadError error={list.error} subject={subject} onRetry={onRetry} />}
      {list.status === "ready" && list.recipes.length > 0 && (
        <RecipeLinkList recipes={list.recipes} label={query ? `Recipes matching ${query}` : "Recipes A to Z"} />
      )}
      {list.status === "ready" && list.nextOffset !== null && (
        <div className="recipe-browser__more">
          {more.status === "error" ? (
            <LoadError error={more.error} subject={`more ${subject}`} onRetry={loadMore} />
          ) : (
            <button type="button" onClick={loadMore} disabled={more.status === "loading"}>
              {more.status === "loading" ? "Loading more…" : "Load more recipes"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Keyword search plus the A-Z recipe list with accessible "load more" paging.
 *
 * The search term is debounced, mirrored in the `q` URL parameter and restored from it on load.
 * Pressing Enter searches immediately. Changing the term restarts from the first page.
 */
export function RecipeBrowser() {
  const [input, setInput] = useState(readQueryFromUrl);
  const [query, setQuery] = useState(readQueryFromUrl);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const trimmed = input.trim();
    if (trimmed === query) return;
    const timer = window.setTimeout(() => setQuery(trimmed), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [input, query]);

  useEffect(() => writeQueryToUrl(query), [query]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setQuery(input.trim());
  }

  return (
    <div className="recipe-browser">
      <search className="recipe-search">
        <form onSubmit={onSubmit}>
          <label htmlFor="recipe-search-input">Search recipes</label>
          <div className="recipe-search__row">
            <input
              id="recipe-search-input"
              type="search"
              name="q"
              value={input}
              maxLength={200}
              autoComplete="off"
              onChange={(event) => setInput(event.target.value)}
            />
            <button type="submit">Search</button>
          </div>
        </form>
      </search>
      <RecipeResults key={`${query}:${attempt}`} query={query} onRetry={() => setAttempt((n) => n + 1)} />
    </div>
  );
}
