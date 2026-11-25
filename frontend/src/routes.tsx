import type { ReactNode } from "react";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RecipePage } from "./pages/RecipePage";
import { RecipesPage } from "./pages/RecipesPage";
import { SubmitPage } from "./pages/SubmitPage";

/** A top-level page: its path, navigation label and content. */
export interface Route {
  path: string;
  label: string;
  render: () => ReactNode;
}

/**
 * Top-level pages, in navigation order. Matching is by exact pathname; nginx and
 * the Vite dev server fall back to `index.html` so every path reaches the app.
 * Recipe detail pages (`/recipes/<slug>`) are matched separately in `renderPage`.
 */
export const routes: readonly Route[] = [
  { path: "/", label: "Home", render: () => <HomePage /> },
  { path: "/recipes", label: "Recipes", render: () => <RecipesPage /> },
  {
    path: "/submit",
    label: "Submit a recipe",
    render: () => <SubmitPage />,
  },
];

/** Returns the route for a pathname, ignoring one trailing slash. */
export function findRoute(pathname: string): Route | undefined {
  const normalized = pathname.length > 1 ? pathname.replace(/\/$/, "") : pathname;
  return routes.find((route) => route.path === normalized);
}

/**
 * Returns the decoded slug for a `/recipes/<slug>` path (one trailing slash allowed),
 * or `undefined` for other paths and malformed encodings.
 */
export function matchRecipeSlug(pathname: string): string | undefined {
  const match = /^\/recipes\/([^/]+)\/?$/.exec(pathname);
  if (!match?.[1]) return undefined;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return undefined;
  }
}

/** Renders the page for a pathname, or the not-found page. */
export function renderPage(pathname: string): ReactNode {
  const slug = matchRecipeSlug(pathname);
  if (slug !== undefined) return <RecipePage slug={slug} />;
  return findRoute(pathname)?.render() ?? <NotFoundPage />;
}
