"""Validate reviewed recipe files and synchronize them into PostgreSQL."""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, func, or_
from sqlalchemy.dialects.postgresql import insert

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.models import Recipe
from recipes.validate import RecipeError, validate_file

RECIPES_DIR = Path(__file__).resolve().parents[2] / "recipes"
CONTENT_FIELDS = ("title", "source", "ingredients", "instructions", "notes")


def seed_recipes(engine: Engine, recipes_dir: Path = RECIPES_DIR) -> None:
    """Validate all files, then atomically upsert content without resetting counters.

    Missing files do not delete rows. A changed slug creates a new recipe.

    Raises:
        RecipeError: A file is invalid or no recipe files exist.
        OSError: A recipe cannot be read.
        sqlalchemy.exc.SQLAlchemyError: The database operation fails.
    """
    paths = sorted(recipes_dir.glob("*.yaml"))
    if not paths:
        raise RecipeError([f"{recipes_dir}: no recipe files found"])

    recipes: list[dict[str, Any]] = []
    for path in paths:
        try:
            recipe = validate_file(path)
        except RecipeError as exc:
            raise RecipeError([f"{path}: {error}" for error in exc.errors]) from exc
        recipes.append(
            {**recipe, "source": recipe.get("source"), "notes": recipe.get("notes")}
        )

    with engine.begin() as connection:
        for recipe in recipes:
            statement = insert(Recipe).values(**recipe)
            excluded = statement.excluded
            statement = statement.on_conflict_do_update(
                index_elements=[Recipe.slug],
                set_={
                    **{field: getattr(excluded, field) for field in CONTENT_FIELDS},
                    "updated_at": func.now(),
                },
                where=or_(
                    *(
                        getattr(Recipe, field).is_distinct_from(
                            getattr(excluded, field)
                        )
                        for field in CONTENT_FIELDS
                    )
                ),
            )
            connection.execute(statement)


def main() -> None:
    """Synchronize reviewed recipes into an already-migrated database."""
    engine = create_database_engine(Settings())
    try:
        seed_recipes(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
