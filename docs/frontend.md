# Frontend guide

The web app is a small React + Vite + strict TypeScript project in `frontend/`, styled with plain
CSS. Layout, page content and API access live in separate files, so the look can change without
touching how data is fetched.

## Commands

Run these from `frontend/` with Node.js 26, or Node.js 24.15+ in the 24.x line:

| Task | Command |
| --- | --- |
| Install exact locked dependencies | `npm ci` |
| Dev server on http://localhost:5173 | `npm run dev` |
| Lint (Oxlint, warnings fail) | `npm run lint` |
| Type check | `npm run typecheck` |
| Tests (Vitest + Testing Library) | `npm test` |
| Production build to `dist/` | `npm run build` |
| Container image (from the repo root) | `docker build -t nik-web frontend` |
| Multi-arch image | `docker buildx build --platform linux/amd64,linux/arm64 -t nik-web frontend` |

The dev server forwards `/api` to the backend at `http://localhost:8000`. Set
`VITE_API_PROXY_TARGET` to use another backend address, for example
`VITE_API_PROXY_TARGET=http://api:8000 npm run dev`.

The image builds with `node:26-alpine` and serves `dist/` from non-root `nginx-unprivileged` on
port 8080. Unknown paths fall back to `index.html` so the app can show its own not-found page;
`/api/*` is never served by this container and returns 404 if it reaches it. In production the
ingress routes `/api` to the backend.

Compose mounts `nginx.local.conf` over the production config to proxy `/api/*` to `api:8000`,
preserving the API prefix. This override is local-only; it does not change the production image.
From the repository root, `docker compose --profile checks run --build --rm frontend-checks`
runs lint, type checks, tests and the production build using the image's Node environment.

## Pages and routes

| Path | Page | Purpose |
| --- | --- | --- |
| `/` | `HomePage` | Most-viewed recipes and the searchable A–Z list |
| `/recipes` | `RecipesPage` | Search and browse recipes A–Z |
| `/recipes/<slug>` | `RecipePage` | Plain-text ingredients and instructions for one recipe |
| `/submit` | `SubmitPage` | Recipe submission page |
| Other paths | `NotFoundPage` | Unrecognized page |

`src/routes.tsx` owns route matching and navigation. Unknown recipe slugs get a separate recipe
not-found page; the submission page is documented below.

## Where things live

The `src/submission/*` and `src/styles/submit.css` paths define the integration boundary added
with the submission feature; the other paths describe the existing frontend.

| Path | Owns | Change it to… |
| --- | --- | --- |
| `src/styles/theme.css` | Named colors, fonts, sizes, spacing, focus ring | Restyle the whole app |
| `src/styles/global.css` | Base and shell styles; recipe-reading `recipe-*`, `recipe__*` and `load-error` classes | Adjust shared layout or recipe-reading looks |
| `src/styles/submit.css` | Submission-specific styles | Restyle the submission page |
| `src/components/Layout.tsx` | Skip link, header, beta badge, navigation, main area, footer | Change the page frame |
| `src/components/Logo.tsx` | NIK mark and text wordmark | Change the header logo |
| `public/favicon.svg` | Browser tab icon (same mark as `Logo.tsx`) | Change the favicon |
| `src/components/ApiStatus.tsx` | Backend health message in the footer | Change health wording |
| `src/components/SubmissionAvailability.tsx`, `src/components/TurnstileWidget.tsx` | Shared submission availability and Turnstile components | Change their reusable behavior |
| `src/components/RecipeBrowser.tsx` | Keyword search (debounced, `?q=` in the URL) and the A-Z list with "Load more" | Change search or paging behavior |
| `src/components/MostViewed.tsx` | Home page most-viewed section | Change the popular-recipes section |
| `src/components/RecipeLinkList.tsx`, `src/components/LoadError.tsx` | Recipe title links; announced error with "Try again" | Change list or error wording |
| `src/pages/HomePage.tsx` | Welcome, most-viewed section and recipe browser | Change the home page |
| `src/pages/RecipesPage.tsx`, `src/pages/RecipePage.tsx` | Recipe browser and plain recipe detail page | Change recipe page structure |
| `src/pages/SubmitPage.tsx`, `src/submission/*` | Submission page and feature-specific code | Change the submission UI |
| `src/routes.tsx` | Page paths, navigation labels and order; `/recipes/<slug>` matching | Add or rename a page |
| `src/api/client.ts`, `src/api/health.ts` | Shared API client and backend health read | Change common request or health behavior |
| `src/api/recipes.ts` | Recipe-list, most-viewed and detail reads | Change recipe data fetching |
| `src/api/submissions.ts` | Submission API access | Change submission requests |
| `src/testing/mockApi.ts` | Request-path API stub and recipe-page fixture for tests | Change shared frontend test setup |

Rule of thumb: components call functions from `src/api/`, never `fetch` directly, and styling
never lives in `src/api/`.

## Submission page

See [Recipe submissions](submissions.md) for the submission page and API.

## Changing the appearance

1. Start with `src/styles/theme.css`. Changing `--color-brand`, `--font-body` or the `--space-*`
   scale restyles every component that uses them.
2. Adjust classes in `src/styles/global.css` for layout and recipe reading, or
   `src/styles/submit.css` for the submission page. Class names follow `block__element` (for
   example `site-header__inner`, `logo__mark`).
3. Keep text/background pairs at WCAG AA contrast (4.5:1 for normal text) and keep a visible
   `:focus-visible` outline for keyboard users.
4. Check a narrow phone width (about 360px) and a desktop width before opening a PR.

No component library or CSS framework is used; adding one needs an issue and a guidance record.

## Accessibility and fallbacks

- A "Skip to content" link appears on keyboard focus and moves to `<main id="main">`.
- A matching top-level navigation link has `aria-current="page"`; recipe detail paths do not
  match a top-level navigation link.
- The site name is real text next to the SVG mark, so it remains readable without the image.
- `index.html` shows a short `<noscript>` message when JavaScript is disabled.
- The footer announces backend health in a status region; the page stays usable when the backend
  is down.
- Recipe text is always rendered as escaped plain text; line breaks inside an ingredient or step
  are kept. Unknown recipe slugs show a "Recipe not found" page.
- The recipe browser announces loading and result counts in a polite live region. Failed reads show
  an alert with the reason (unreachable, unavailable or the HTTP status) and a "Try again" button;
  they never fall back to an empty list. After "Load more recipes", focus moves to the first newly
  loaded recipe.
- Typing in the search box searches after a short pause (Enter searches at once). The query is kept
  in `?q=` so links and reloads keep it; a new query starts again from the first page.

## Logo

The NIK mark is original artwork: white "NIK" strokes on a rounded brand-green square. It is drawn
with simple paths (no font dependency) so it stays legible at 16px. When changing it, update both
`src/components/Logo.tsx` and `public/favicon.svg`.
