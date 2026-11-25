"""Exercise the actual PostgreSQL migration, constraints and search index."""

import pytest


def test_upgrade_and_downgrade(database):
    from alembic import command
    from sqlalchemy import inspect

    engine, config = database
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == {"alembic_version", "recipes"}

    command.downgrade(config, "base")
    assert "recipes" not in inspect(engine).get_table_names()

    # A downgrade must leave the schema usable for a fresh upgrade.
    command.upgrade(config, "head")
    assert "recipes" in inspect(engine).get_table_names()


def test_schema_constraints_and_search_index(migrated_db):
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import IntegrityError

    engine = migrated_db
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("recipes")}
    for name in ("id", "slug", "title", "ingredients", "instructions", "view_count"):
        assert not columns[name]["nullable"]
    for name in ("ingredients", "instructions", "notes"):
        assert str(columns[name]["type"]).upper() == "JSONB"
    assert not columns["created_at"]["nullable"]
    assert not columns["updated_at"]["nullable"]
    assert str(columns["search_document"]["type"]).upper() == "TSVECTOR"

    with engine.connect() as connection:
        generated = connection.execute(
            text(
                "SELECT is_generated FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'recipes' "
                "AND column_name = 'search_document'"
            )
        ).scalar_one()
        assert generated == "ALWAYS"
        indexes = connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() AND tablename = 'recipes'"
            )
        ).scalars()
        assert any(
            " USING gin " in definition and "search_document" in definition
            for definition in indexes
        )

    insert = text(
        "INSERT INTO recipes (slug, title, ingredients, instructions, view_count) "
        "VALUES (:slug, :title, CAST(:ingredients AS jsonb), "
        "CAST(:instructions AS jsonb), :views)"
    )
    valid = {
        "slug": "one",
        "title": "One",
        "ingredients": '["bread"]',
        "instructions": '["Toast it"]',
        "views": 0,
    }
    with engine.begin() as connection:
        connection.execute(insert, valid)
        for invalid in (
            {**valid, "title": "Duplicate"},
            {**valid, "slug": "negative", "views": -1},
            {**valid, "slug": None},
            {**valid, "slug": "no-title", "title": None},
            {**valid, "slug": "no-ingredients", "ingredients": None},
            {**valid, "slug": "no-instructions", "instructions": None},
            {**valid, "slug": "empty-ingredients", "ingredients": "[]"},
            {**valid, "slug": "empty-instructions", "instructions": "[]"},
        ):
            # Each expected failure is isolated so the PostgreSQL transaction remains usable.
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(insert, invalid)


def test_search_covers_title_ingredients_and_instructions(migrated_db):
    from sqlalchemy import text

    with migrated_db.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO recipes (slug, title, ingredients, instructions) "
                "VALUES ('search-test', 'Saffron supper', "
                "'[\"cardamom\"]'::jsonb, '[\"Whisk gently\"]'::jsonb)"
            )
        )
        matches = text(
            "SELECT slug FROM recipes WHERE "
            "search_document @@ plainto_tsquery('english', :term)"
        )
        for word in ("saffron", "cardamom", "whisk"):
            assert connection.execute(matches, {"term": word}).scalars().all() == [
                "search-test"
            ]
        assert connection.execute(matches, {"term": "cabbage"}).scalars().all() == []
