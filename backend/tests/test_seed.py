"""Exercise validated recipe synchronization against real PostgreSQL."""

import shutil

import pytest
from conftest import RECIPES


@pytest.fixture
def recipe_dir(tmp_path):
    for path in RECIPES.glob("*.yaml"):
        shutil.copy2(path, tmp_path / path.name)
    return tmp_path


def rows(engine):
    from sqlalchemy import text

    with engine.connect() as connection:
        return {
            row["slug"]: dict(row)
            for row in connection.execute(
                text(
                    "SELECT id, slug, title, ingredients, instructions, source, notes, "
                    "view_count, created_at, updated_at FROM recipes ORDER BY slug"
                )
            ).mappings()
        }


@pytest.mark.parametrize("additional_recipe", [False, True])
def test_seed_source_recipes_is_idempotent(migrated_db, recipe_dir, additional_recipe):
    from backend.app.seed import seed_recipes
    from recipes.validate import dump_recipe_yaml, validate_file

    if additional_recipe:
        recipe = {
            "slug": "seeder-regression-soup",
            "title": "Seeder Regression Soup",
            "ingredients": ["1 cup water", "1 carrot"],
            "instructions": ["Slice the carrot.", "Simmer in the water."],
            "source": "Test recipe",
            "notes": ["Serve warm."],
        }
        (recipe_dir / f"{recipe['slug']}.yaml").write_text(
            dump_recipe_yaml(recipe), encoding="utf-8"
        )

    expected_recipes = {
        path.stem: validate_file(path) for path in recipe_dir.glob("*.yaml")
    }
    seed_recipes(migrated_db, recipe_dir)
    first = rows(migrated_db)
    assert {"cast-iron-pizza-dough", "pizza-stone-dough"} <= set(first)
    assert set(first) == set(expected_recipes)
    for slug, expected in expected_recipes.items():
        actual = first[slug]
        for name in ("title", "ingredients", "instructions", "notes"):
            assert actual[name] == expected.get(name)
        assert actual["source"] == expected.get("source")
        assert actual["view_count"] == 0
        assert actual["id"] is not None
        assert actual["created_at"] is not None
        assert actual["updated_at"] is not None

    seed_recipes(migrated_db, recipe_dir)
    second = rows(migrated_db)
    assert second == first


def test_update_preserves_identity_views_and_syncs_optional_content(
    migrated_db, recipe_dir
):
    from sqlalchemy import text

    from backend.app.seed import seed_recipes
    from recipes.validate import dump_recipe_yaml, validate_file

    seed_recipes(migrated_db, recipe_dir)
    slug = "cast-iron-pizza-dough"
    with migrated_db.begin() as connection:
        connection.execute(
            text("UPDATE recipes SET view_count = 37 WHERE slug = :slug"),
            {"slug": slug},
        )
    before = rows(migrated_db)
    path = recipe_dir / f"{slug}.yaml"
    recipe = validate_file(path)
    recipe.update(
        title="Saffron skillet",
        ingredients=["Fresh cardamom", "Flour"],
        instructions=["Whisk gently.", "Bake."],
        source="Family notebook",
        notes=["Keep the original order.", "Serve warm."],
    )
    path.write_text(dump_recipe_yaml(recipe), encoding="utf-8")
    seed_recipes(migrated_db, recipe_dir)

    after = rows(migrated_db)
    for field in ("id", "view_count", "created_at"):
        assert after[slug][field] == before[slug][field]
    for field in ("title", "ingredients", "instructions", "source", "notes"):
        assert after[slug][field] == recipe[field]
    assert after["pizza-stone-dough"]["id"] == before["pizza-stone-dough"]["id"]
    with migrated_db.connect() as connection:
        for word in ("saffron", "cardamom", "whisk"):
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM recipes WHERE slug = :slug AND "
                        "search_document @@ plainto_tsquery('english', :word)"
                    ),
                    {"slug": slug, "word": word},
                )
                == 1
            )

    del recipe["source"]
    del recipe["notes"]
    path.write_text(dump_recipe_yaml(recipe), encoding="utf-8")
    seed_recipes(migrated_db, recipe_dir)
    cleared = rows(migrated_db)[slug]
    assert cleared["source"] is None
    assert cleared["notes"] is None
    assert cleared["id"] == before[slug]["id"]
    assert cleared["view_count"] == 37


@pytest.mark.parametrize(
    "invalid_yaml",
    [
        "slug: zzz-invalid\ntitle: Missing required fields\n",
        "slug: zzz-invalid\nslug: zzz-invalid\ntitle: Duplicate key\n",
    ],
)
def test_invalid_files_are_rejected_before_touching_database(recipe_dir, invalid_yaml):
    from backend.app.seed import seed_recipes
    from recipes.validate import RecipeError

    class UntouchedEngine:
        def begin(self):
            pytest.fail(
                "the database must not be touched before all files are validated"
            )

    (recipe_dir / "zzz-invalid.yaml").write_text(invalid_yaml, encoding="utf-8")
    with pytest.raises(RecipeError):
        seed_recipes(UntouchedEngine(), recipe_dir)


def test_invalid_input_is_atomic_and_removed_files_are_not_deleted(
    migrated_db, recipe_dir
):
    from backend.app.seed import seed_recipes
    from recipes.validate import RecipeError, dump_recipe_yaml, validate_file

    seed_recipes(migrated_db, recipe_dir)
    before = rows(migrated_db)
    path = recipe_dir / "cast-iron-pizza-dough.yaml"
    recipe = validate_file(path)
    recipe["title"] = "Valid changed title"
    path.write_text(dump_recipe_yaml(recipe), encoding="utf-8")
    invalid = recipe_dir / "zzz-invalid.yaml"
    invalid.write_text(
        "slug: zzz-invalid\ntitle: Missing required fields\n", encoding="utf-8"
    )

    with pytest.raises(RecipeError):
        seed_recipes(migrated_db, recipe_dir)
    assert rows(migrated_db) == before

    invalid.unlink()
    (recipe_dir / "pizza-stone-dough.yaml").unlink()
    seed_recipes(migrated_db, recipe_dir)
    after = rows(migrated_db)
    assert after["cast-iron-pizza-dough"]["title"] == "Valid changed title"
    assert after["pizza-stone-dough"] == before["pizza-stone-dough"]


def test_slug_change_creates_new_row_without_deleting_old(migrated_db, recipe_dir):
    from backend.app.seed import seed_recipes
    from recipes.validate import dump_recipe_yaml, validate_file

    seed_recipes(migrated_db, recipe_dir)
    old_slug = "cast-iron-pizza-dough"
    before = rows(migrated_db)[old_slug]
    path = recipe_dir / f"{old_slug}.yaml"
    recipe = validate_file(path)
    recipe["slug"] = "renamed-dough"
    path.unlink()
    (recipe_dir / "renamed-dough.yaml").write_text(
        dump_recipe_yaml(recipe), encoding="utf-8"
    )
    seed_recipes(migrated_db, recipe_dir)
    after = rows(migrated_db)
    assert after[old_slug] == before
    assert after["renamed-dough"]["id"] != before["id"]
    assert after["renamed-dough"]["title"] == before["title"]
    assert after["renamed-dough"]["view_count"] == 0
