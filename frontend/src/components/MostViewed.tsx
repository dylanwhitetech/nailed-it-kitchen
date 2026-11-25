import { useEffect, useState } from "react";
import { fetchMostViewed, type RecipeSummary } from "../api/recipes";
import { LoadError } from "./LoadError";
import { RecipeLinkList } from "./RecipeLinkList";

type State =
  | { status: "loading" }
  | { status: "ready"; recipes: RecipeSummary[] }
  | { status: "error"; error: unknown };

/** Fetches once on mount; the parent remounts it with a new key to retry. */
function MostViewedList({ onRetry }: { onRetry: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchMostViewed(controller.signal)
      .then((recipes) => {
        if (!controller.signal.aborted) setState({ status: "ready", recipes });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error("Most-viewed recipes failed to load", error);
        setState({ status: "error", error });
      });
    return () => controller.abort();
  }, []);

  if (state.status === "loading") return <p className="recipe-section__note">Loading popular recipes…</p>;
  if (state.status === "error") return <LoadError error={state.error} subject="popular recipes" onRetry={onRetry} />;
  if (state.recipes.length === 0) return <p className="recipe-section__note">No recipes have been added yet.</p>;
  return <RecipeLinkList recipes={state.recipes} label="Most viewed recipes" ordered />;
}

/** Home page section listing the few most-viewed recipes, independent of A-Z browsing. */
export function MostViewed() {
  const [attempt, setAttempt] = useState(0);
  return (
    <section className="recipe-section" aria-labelledby="most-viewed-heading">
      <h2 id="most-viewed-heading">Most viewed</h2>
      <MostViewedList key={attempt} onRetry={() => setAttempt((n) => n + 1)} />
    </section>
  );
}
