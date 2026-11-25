import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { fetchRecipe, type RecipeDetail } from "../api/recipes";
import { LoadError } from "../components/LoadError";

const SITE_NAME = "Nailed It Kitchen";

type State =
  | { status: "loading" }
  | { status: "ready"; recipe: RecipeDetail }
  | { status: "not-found" }
  | { status: "error"; error: unknown };

/** Sets the document title and meta description, restoring the previous values on unmount. */
function usePageMetadata(title: string | null, description: string | null) {
  useEffect(() => {
    if (title === null) return;
    const meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const previousTitle = document.title;
    const previousDescription = meta?.content;
    document.title = title;
    if (meta && description !== null) meta.content = description;
    return () => {
      document.title = previousTitle;
      if (meta && previousDescription !== undefined) meta.content = previousDescription;
    };
  }, [title, description]);
}

interface RecipePageProps {
  /** Decoded recipe slug from the URL. */
  slug: string;
}

/** Plain recipe page: title, ingredients, then numbered instructions, all rendered as escaped text. */
export function RecipePage({ slug }: RecipePageProps) {
  const [attempt, setAttempt] = useState(0);
  return <RecipeContent key={`${slug}:${attempt}`} slug={slug} onRetry={() => setAttempt((n) => n + 1)} />;
}

/** Reads the recipe once on mount; `RecipePage` remounts it with a new key to retry. */
function RecipeContent({ slug, onRetry }: RecipePageProps & { onRetry: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchRecipe(slug, controller.signal)
      .then((recipe) => {
        if (!controller.signal.aborted) setState({ status: "ready", recipe });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "not-found" });
          return;
        }
        console.error("Recipe failed to load", error);
        setState({ status: "error", error });
      });
    return () => controller.abort();
  }, [slug]);

  const recipe = state.status === "ready" ? state.recipe : null;
  usePageMetadata(
    recipe ? `${recipe.title} | ${SITE_NAME}` : state.status === "not-found" ? `Recipe not found | ${SITE_NAME}` : null,
    recipe ? `Ingredients and step-by-step instructions for ${recipe.title} on ${SITE_NAME} (beta).` : null,
  );

  if (state.status === "not-found") {
    return (
      <section className="page">
        <h1>Recipe not found</h1>
        <p>
          We couldn't find that recipe. It may have been renamed or removed. <a href="/recipes">Browse all recipes</a>.
        </p>
      </section>
    );
  }

  if (!recipe) {
    return (
      <section className="page">
        <h1>Recipe</h1>
        {state.status === "loading" && <p className="recipe-section__note">Loading recipe…</p>}
        {state.status === "error" && (
          <LoadError error={state.error} subject="this recipe" onRetry={onRetry} />
        )}
        <p>
          <a href="/recipes">Back to all recipes</a>
        </p>
      </section>
    );
  }

  return (
    <article className="page recipe" aria-labelledby="recipe-title">
      <p className="recipe__back">
        <a href="/recipes">All recipes</a>
      </p>
      <h1 id="recipe-title">{recipe.title}</h1>

      <section aria-labelledby="ingredients-heading">
        <h2 id="ingredients-heading">Ingredients</h2>
        <ul className="recipe__lines">
          {recipe.ingredients.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="instructions-heading">
        <h2 id="instructions-heading">Instructions</h2>
        <ol className="recipe__lines recipe__steps">
          {recipe.instructions.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ol>
      </section>

      {recipe.notes && recipe.notes.length > 0 && (
        <section aria-labelledby="notes-heading">
          <h2 id="notes-heading">Notes</h2>
          <ul className="recipe__lines">
            {recipe.notes.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      {recipe.source && <p className="recipe__source recipe__lines">Source: {recipe.source}</p>}
    </article>
  );
}
