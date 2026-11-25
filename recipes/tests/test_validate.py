"""Tests for the plain-text recipe contract in ``recipes/validate.py``."""

import json
import re
from pathlib import Path

import pytest
import validate as v

RECIPES = Path(__file__).resolve().parents[1]
FIXTURES = sorted(RECIPES.glob("*.yaml"))
SOURCE_FIXTURES = [
    path for path in FIXTURES if (RECIPES / "source" / f"{path.stem}.md").exists()
]


def make_recipe(**overrides):
    recipe = {
        "slug": "toast",
        "title": "Toast",
        "ingredients": ["1 slice bread"],
        "instructions": ["Toast the bread."],
    }
    recipe.update(overrides)
    return {key: value for key, value in recipe.items() if value is not None}


def errors_for(recipe):
    return v.validate_recipe(recipe)


def paste_errors(text):
    with pytest.raises(v.RecipeError) as excinfo:
        v.parse_paste_template(text)
    return excinfo.value.errors


# Reviewed fixtures and source conversion


def test_both_source_recipes_have_yaml_fixtures():
    sources = sorted(path.stem for path in (RECIPES / "source").glob("*.md"))
    assert sources == ["cast-iron-pizza-dough", "pizza-stone-dough"]
    assert [path.stem for path in SOURCE_FIXTURES] == sources


def test_cli_validates_every_fixture(capsys):
    assert v.main([]) == 0
    assert capsys.readouterr().out.count(": ok") == len(FIXTURES)


def _markdown_sections(path):
    """Return (title, metadata, sections) from a source recipe, with bold markers removed."""
    title, metadata, sections, current = None, [], {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        plain = v.normalize_line(line.replace("**", ""))
        if line.startswith("# "):
            title = plain[2:]
        elif line.startswith("## "):
            current = sections.setdefault(plain[3:], [])
        elif plain and current is None:
            metadata.append(plain)
        elif plain:
            current.append(re.sub(r"^(?:-|\d+\.)\s+", "", plain))
    return title, metadata, sections


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=lambda path: path.stem)
def test_fixture_preserves_source_details_and_order(fixture):
    recipe = v.validate_file(fixture)
    title, metadata, sections = _markdown_sections(
        RECIPES / "source" / f"{fixture.stem}.md"
    )

    assert recipe["title"] == title
    assert recipe["ingredients"] == sections["Ingredients"]
    assert recipe["instructions"] == sections["Steps"]
    assert recipe["notes"] == [
        *metadata,
        "Equipment: " + "; ".join(sections["Equipment"]),
        *sections["Notes"],
    ]
    assert "**" not in v.format_paste_template(recipe)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_fixture_round_trips_through_yaml_and_paste_template(fixture):
    recipe = v.validate_file(fixture)
    assert fixture.read_text(encoding="utf-8") == v.dump_recipe_yaml(recipe)
    reparsed = v.parse_paste_template(v.format_paste_template(recipe))
    assert reparsed == {**recipe, "slug": v.slugify(recipe["title"])}


# Schema shape and extra rules


def test_minimal_and_full_recipes_are_valid():
    assert errors_for(make_recipe()) == []
    assert errors_for(make_recipe(source="Grandma", notes=["Serve warm."])) == []


@pytest.mark.parametrize("field", ["slug", "title", "ingredients", "instructions"])
def test_required_fields(field):
    assert errors_for(make_recipe(**{field: None})) == [f"{field}: is required"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"tags": ["pizza"]}, "recipe: unknown field(s) 'tags'"),
        ({"title": ""}, "title: must not be empty"),
        ({"title": "  Toast"}, "title: must be one line without control characters"),
        ({"title": "Two\nlines"}, "title: must be one line without control characters"),
        ({"title": "Tab\x07"}, "title: must be one line without control characters"),
        ({"title": 42}, "title: must be text"),
        ({"ingredients": "1 slice bread"}, "ingredients: must be a list"),
        ({"ingredients": [{"id": 1, "qty": 2}]}, "ingredients[0]: must be text"),
        ({"instructions": ["Ok", ""]}, "instructions[1]: must not be empty"),
        ({"notes": []}, "notes: must have at least 1 entry"),
        ({"slug": "Toast_Bread"}, "slug: must be lowercase letters and digits"),
        ({"slug": "a--b"}, "slug: must be lowercase letters and digits"),
        ({"slug": "toast\n"}, "slug: must be lowercase letters and digits"),
        ({"title": "Toast  bread"}, "title: must be normalized"),
        ({"ingredients": ["Cafe\u0301"]}, "ingredients[0]: must be normalized"),
    ],
)
def test_invalid_shapes_are_rejected(overrides, expected):
    errors = errors_for(make_recipe(**overrides))
    assert len(errors) == 1 and errors[0].startswith(expected), errors


def test_non_mapping_recipe_is_rejected():
    assert errors_for(["Toast"]) == ["recipe: must be a mapping"]


def test_slug_must_match_file_name():
    errors = v.validate_recipe(make_recipe(), slug_from_filename="bread")
    assert errors == ["slug: 'toast' must match the file name 'bread'.yaml"]


def test_dump_rejects_slug_with_trailing_newline():
    with pytest.raises(
        v.RecipeError, match="slug: must be lowercase letters and digits"
    ):
        v.dump_recipe_yaml(make_recipe(slug="toast\n"))


@pytest.mark.parametrize(
    ("field", "make", "limit"),
    [
        ("title", lambda n: "t" * n, 160),
        ("ingredients", lambda n: ["salt"] * n, 100),
        ("instructions", lambda n: ["Stir."] * n, 100),
        ("notes", lambda n: ["Tip."] * n, 100),
    ],
)
def test_size_and_count_boundaries(field, make, limit):
    assert errors_for(make_recipe(**{field: make(limit)})) == []
    assert len(errors_for(make_recipe(**{field: make(limit + 1)}))) == 1


def test_content_cap_boundary():
    steps = ["s" * 1990] * 10
    base = v.content_length(make_recipe(instructions=steps, notes=["x"]))
    at_limit = make_recipe(
        instructions=steps, notes=["x" * (1 + v.MAX_CONTENT_CHARS - base)]
    )
    assert v.content_length(at_limit) == v.MAX_CONTENT_CHARS
    assert errors_for(at_limit) == []

    over = make_recipe(instructions=steps, notes=at_limit["notes"] + ["y"])
    assert errors_for(over) == [
        f"recipe content is {v.MAX_CONTENT_CHARS + 4} characters; the maximum is 20000"
    ]


# Safe YAML loading

VALID_YAML = (
    "slug: toast\ntitle: Toast\ningredients:\n  - bread\ninstructions:\n  - Toast it.\n"
)


def test_valid_yaml_loads():
    assert v.load_recipe_yaml(VALID_YAML) == make_recipe(
        ingredients=["bread"], instructions=["Toast it."]
    )


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("title: !!python/object/apply:os.system ['echo hi']\n", "explicit YAML tags"),
        ("title: !!binary aGk=\n", "explicit YAML tags"),
        ("title: !!set {a: null}\n", "explicit YAML tags"),
        ("title: !custom Toast\n", "explicit YAML tags"),
        ("title: !!str Toast\n", "explicit YAML tags"),
        ("a: &x Toast\ntitle: *x\n", "anchors and aliases"),
        ("<<: {title: Toast}\n", "merge keys"),
        ("title: Toast\ntitle: Bread\n", "duplicate key 'title'"),
        ("? [a]\n: b\n", "plain scalars"),
        ("title: Toast\n---\ntitle: Bread\n", "invalid YAML"),
        ("", "recipe file is empty"),
        ("title: [unclosed\n", "invalid YAML"),
    ],
)
def test_unsafe_or_malformed_yaml_is_rejected(document, expected):
    with pytest.raises(v.RecipeError) as excinfo:
        v.load_recipe_yaml(document)
    assert expected in str(excinfo.value)


def test_yaml_byte_limits_and_encoding():
    with pytest.raises(v.RecipeError, match="larger than 65536 bytes"):
        v.load_recipe_yaml(b"#" * (v.MAX_YAML_BYTES + 1))
    with pytest.raises(v.RecipeError, match="not valid UTF-8"):
        v.load_recipe_yaml(b"title: \xff\n")


def test_implicitly_typed_yaml_values_fail_schema():
    recipe = v.load_recipe_yaml(VALID_YAML.replace("title: Toast", "title: 2024-01-01"))
    assert v.validate_recipe(recipe) == ["title: must be text"]


def test_cli_reports_invalid_file(tmp_path, capsys):
    path = tmp_path / "toast.yaml"
    path.write_text(VALID_YAML + "tags: [x]\n", encoding="utf-8")
    assert v.main([str(path)]) == 1
    assert "unknown field(s) 'tags'" in capsys.readouterr().err


# Paste template extraction

TEMPLATE = """Toast

Ingredients
- 1 slice bread
- Butter

Instructions
1. Toast the bread.
2. Spread with butter.
"""


def test_paste_template_extracts_recipe():
    assert v.parse_paste_template(TEMPLATE) == make_recipe(
        ingredients=["1 slice bread", "Butter"],
        instructions=["Toast the bread.", "Spread with butter."],
    )


@pytest.mark.parametrize(
    ("title_line", "expected_title"),
    [
        ("# # Toast", "# Toast"),
        (r"\Notes", "Notes"),
        (r"\# Toast", "# Toast"),
        (r"\\Notes", r"\Notes"),
    ],
)
def test_title_escaping_round_trips(title_line, expected_title):
    recipe = v.parse_paste_template(
        f"{title_line}\n\nIngredients\n- bread\n\nInstructions\n1. Toast."
    )

    assert recipe["title"] == expected_title
    assert v.parse_paste_template(v.format_paste_template(recipe)) == recipe


def test_paste_normalization_is_deterministic():
    text = (
        "\ufeff  ## Buttered\tToast  \r\n"
        "Source:   Grandma's card\r\n"
        "\r\n"
        "INGREDIENTS:\r\n"
        "* 1\u00a0slice   bread\r\n"
        "\u2022 Butter\r\n"
        "Steps\r\n"
        "Toast the bread.\r\n"
        "- Spread with butter.\r\n"
        "notes\r\n"
        "Serve warm.\r"
    )
    assert v.parse_paste_template(text) == {
        "slug": "buttered-toast",
        "title": "Buttered Toast",
        "source": "Grandma's card",
        "ingredients": ["1 slice bread", "Butter"],
        "instructions": ["Toast the bread.", "Spread with butter."],
        "notes": ["Serve warm."],
    }


def test_paste_keeps_quantities_and_plain_markup_text():
    text = TEMPLATE.replace("- Butter", "- 1 1/2 tbsp butter <b>soft</b>").replace(
        "2. Spread", "2. 1.5 minutes later, spread"
    )
    recipe = v.parse_paste_template(text)
    assert recipe["ingredients"][1] == "1 1/2 tbsp butter <b>soft</b>"
    assert recipe["instructions"][1] == "1.5 minutes later, spread with butter."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "the paste is empty"),
        (
            "Ingredients\n- bread\nInstructions\n1. Toast.",
            "line 1: the first line must be the recipe title",
        ),
        (
            "Toast\nInstructions\n1. Toast.",
            "line 2: 'Instructions' must come after 'Ingredients'",
        ),
        ("Toast\nIngredients\n- bread", "missing the 'Instructions' section"),
        (
            "Toast\nIngredients\nInstructions\n1. Toast.",
            "the 'Ingredients' section has no entries",
        ),
        (
            "Toast\nIngredients\n- bread\nInstructions\n",
            "the 'Instructions' section has no entries",
        ),
        (
            "Toast\nIngredients\n- bread\nNotes\n- x\nInstructions\n1. a",
            "line 4: 'Notes' must come after 'Instructions'",
        ),
        (
            "Toast\nA lovely snack.\nIngredients\n- bread\nInstructions\n1. a",
            "line 2: expected 'Ingredients' after the title",
        ),
        (
            "Toast\nSource:\nIngredients\n- b\nInstructions\n1. a",
            "line 2: 'Source:' needs text",
        ),
        ("Toast\nIngredients\n-\nInstructions\n1. a", "line 3: empty list item"),
        (
            "Toast\nIngredients\n- b\nInstructions\n1.\n2.",
            "line 5: empty instruction step",
        ),
        ("Toast\nIngredients\n- b\nInstructions\n2)", "line 5: empty instruction step"),
        (
            "Toast\nIngredients\n- b\nInstructions\n1. a\n3. c",
            "line 6: expected step 2",
        ),
        (
            "Toast\nIngredients\n- b\nInstructions\n1. a\nwrapped text",
            "line 6: expected step 2",
        ),
        ("Toast\nIngredients\n- b\nInstructions\na\n2. b", "line 5: expected step 1"),
        (
            "Toast\nIngredients\n- b\x00\nInstructions\n1. a",
            "line 3: contains a control character",
        ),
        (
            "\u98df\u3079\u7269\nIngredients\n- b\nInstructions\n1. a",
            "title: must contain at least one ASCII",
        ),
    ],
)
def test_malformed_paste_is_rejected(text, expected):
    errors = paste_errors(text)
    assert len(errors) == 1 and errors[0].startswith(expected), errors


@pytest.mark.parametrize("section", ["Ingredients", "Instructions", "Notes"])
def test_second_section_is_a_multiple_recipe_error(section):
    text = TEMPLATE + "\nNotes\n- n\n" + f"{section}\n- again\n"
    assert paste_errors(text) == [
        f"line 13: found a second '{section}' section; paste exactly one recipe at a time"
    ]


def test_two_pasted_recipes_are_rejected():
    errors = paste_errors(TEMPLATE + "\n" + TEMPLATE.replace("Toast", "Jam"))
    assert errors[0].startswith("line 13: found a second 'Ingredients' section")


def test_paste_limits_use_the_same_validation():
    many = "\n".join(f"- item {n}" for n in range(101))
    errors = paste_errors(f"Toast\nIngredients\n{many}\nInstructions\n1. a")
    assert errors == ["ingredients: must have at most 100 entries"]
    assert paste_errors("t" * 161 + "\nIngredients\n- b\nInstructions\n1. a") == [
        "title: must be at most 160 characters"
    ]


def test_slugify_is_ascii_and_bounded():
    assert v.slugify("Cast-Iron Pizza Dough — 10-inch + 12-inch Lodge") == (
        "cast-iron-pizza-dough-10-inch-12-inch-lodge"
    )
    assert v.slugify("Crème brûlée") == "creme-brulee"
    assert v.slugify("a " * 100) == "-".join(["a"] * 40)


PASTE_CASES = json.loads(
    (Path(__file__).with_name("paste_cases.json")).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", PASTE_CASES, ids=[c["name"] for c in PASTE_CASES])
def test_shared_paste_cases(case):
    """The browser preview runs the same cases against its TypeScript parser."""
    if "errors" in case:
        assert paste_errors(case["text"]) == case["errors"]
    else:
        recipe = v.parse_paste_template(case["text"])
        assert recipe == case["recipe"]
        assert v.format_paste_template(recipe) == case["formatted"]
