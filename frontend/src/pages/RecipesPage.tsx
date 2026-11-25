import { RecipeBrowser } from "../components/RecipeBrowser";

/** Recipe browsing page: keyword search and the full A-Z list. */
export function RecipesPage() {
  return (
    <section className="page">
      <h1>Recipes</h1>
      <p>Search by keyword, or browse every recipe from A to Z.</p>
      <RecipeBrowser />
    </section>
  );
}
