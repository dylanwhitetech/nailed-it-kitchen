import type { RecipeSummary } from "../api/recipes";

/** Path of a recipe's detail page. */
export function recipePath(slug: string): string {
  return `/recipes/${encodeURIComponent(slug)}`;
}

interface RecipeLinkListProps {
  recipes: readonly RecipeSummary[];
  /** Accessible name of the list. */
  label: string;
  /** Ordered lists suit ranked content such as most-viewed. */
  ordered?: boolean;
}

/** Plain list of recipe title links. */
export function RecipeLinkList({ recipes, label, ordered = false }: RecipeLinkListProps) {
  const List = ordered ? "ol" : "ul";
  return (
    <List className="recipe-list" aria-label={label}>
      {recipes.map((recipe) => (
        <li key={recipe.slug}>
          <a href={recipePath(recipe.slug)}>{recipe.title}</a>
        </li>
      ))}
    </List>
  );
}
