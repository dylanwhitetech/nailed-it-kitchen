import { MostViewed } from "../components/MostViewed";
import { RecipeBrowser } from "../components/RecipeBrowser";

/** Landing page: a short welcome, the most-viewed recipes and the searchable A-Z list. */
export function HomePage() {
  return (
    <div className="page">
      <h1>Welcome to Nailed It Kitchen</h1>
      <p className="page__lead">
        Simple recipes you can actually cook: a list of ingredients followed by step-by-step instructions.
      </p>
      <MostViewed />
      <section className="recipe-section" aria-labelledby="all-recipes-heading">
        <h2 id="all-recipes-heading">Recipes A–Z</h2>
        <RecipeBrowser />
      </section>
    </div>
  );
}
