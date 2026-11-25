"""Create the minimal recipe table and PostgreSQL lexical search index."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create recipes and a generated, indexed search document."""
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("source", sa.String(300)),
        sa.Column("ingredients", postgresql.JSONB(), nullable=False),
        sa.Column("instructions", postgresql.JSONB(), nullable=False),
        sa.Column("notes", postgresql.JSONB(none_as_null=True)),
        sa.Column(
            "view_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english'::regconfig, title) || "
                """jsonb_to_tsvector('english'::regconfig, ingredients, '["string"]'::jsonb) || """
                """jsonb_to_tsvector('english'::regconfig, instructions, '["string"]'::jsonb)""",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.CheckConstraint("view_count >= 0", name="ck_recipes_view_count_nonnegative"),
        sa.CheckConstraint(
            "jsonb_typeof(ingredients) = 'array' AND jsonb_array_length(ingredients) > 0",
            name="ck_recipes_ingredients_nonempty",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(instructions) = 'array' AND jsonb_array_length(instructions) > 0",
            name="ck_recipes_instructions_nonempty",
        ),
    )
    op.create_index(
        "ix_recipes_search_document",
        "recipes",
        ["search_document"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove the search index and recipe table."""
    op.drop_index("ix_recipes_search_document", table_name="recipes")
    op.drop_table("recipes")
