import { Layout } from "./components/Layout";
import { renderPage } from "./routes";

interface AppProps {
  /** Current URL path; defaults to the browser location. */
  pathname?: string;
}

export function App({ pathname = window.location.pathname }: AppProps) {
  return <Layout currentPath={pathname}>{renderPage(pathname)}</Layout>;
}
