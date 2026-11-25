import type { ReactNode } from "react";
import { ApiStatus } from "./ApiStatus";
import { Logo } from "./Logo";
import { findRoute, routes } from "../routes";

interface LayoutProps {
  /** Path of the current page; its navigation link gets `aria-current="page"`. */
  currentPath: string;
  children: ReactNode;
}

/** Page shell: skip link, header with logo, beta badge and navigation, main content and footer. */
export function Layout({ currentPath, children }: LayoutProps) {
  const currentRoute = findRoute(currentPath);
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="site-header__inner">
          <a className="site-header__home" href="/">
            <Logo />
          </a>
          <span className="beta-badge">Beta</span>
          <nav className="site-nav" aria-label="Main">
            <ul>
              {routes.map((route) => (
                <li key={route.path}>
                  <a href={route.path} aria-current={route === currentRoute ? "page" : undefined}>
                    {route.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="site-main" tabIndex={-1}>
        {children}
      </main>
      <footer className="site-footer">
        <p>Nailed It Kitchen is in beta. Recipes are simple text: ingredients, then instructions.</p>
        <ApiStatus />
      </footer>
    </div>
  );
}
