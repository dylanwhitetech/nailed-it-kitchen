import type { ReactNode } from "react";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
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
 * Reading and submission pages replace the placeholders when they are built.
 */
export const routes: readonly Route[] = [
  { path: "/", label: "Home", render: () => <HomePage /> },
  {
    path: "/recipes",
    label: "Recipes",
    render: () => <PlaceholderPage title="Recipes" description="Browsing and searching recipes is coming soon." />,
  },
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

/** Renders the page for a pathname, or the not-found page. */
export function renderPage(pathname: string): ReactNode {
  return findRoute(pathname)?.render() ?? <NotFoundPage />;
}
