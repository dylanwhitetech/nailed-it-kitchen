"""Load, validate, extract and serialize plain-text beta recipes.

This module is the executable contract described in ``docs/recipe-format.md``:

* :func:`load_recipe_yaml` parses one YAML document with a restricted safe loader.
* :func:`validate_recipe` checks a recipe against ``schema/recipe.schema.json`` plus the
  rules JSON Schema cannot express (normalization, content cap, file name).
* :func:`parse_paste_template` deterministically extracts a recipe from the paste template.
* :func:`format_paste_template` and :func:`dump_recipe_yaml` serialize recipes canonically.

Run ``python recipes/validate.py [FILE ...]`` to validate files (default: ``recipes/*.yaml``).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, ValidationError

RECIPES_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = RECIPES_DIR / "schema" / "recipe.schema.json"
SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(SCHEMA)

MAX_CONTENT_CHARS = 20_000
MAX_YAML_BYTES = 64 * 1024
MAX_SLUG_CHARS: int = SCHEMA["properties"]["slug"]["maxLength"]
FIELD_ORDER = ("slug", "title", "source", "ingredients", "instructions", "notes")
_LIST_FIELDS = ("ingredients", "instructions", "notes")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_WHITESPACE_RUN = re.compile(r"\s+")
_HEADING_PREFIX = re.compile(r"^#{1,6}\s+")
_SECTION_HEADER = re.compile(
    r"^(?:#{1,6}\s+)?(ingredients|instructions|directions|steps|notes)\s*:?$",
    re.IGNORECASE,
)
_SOURCE_LINE = re.compile(r"^(?:source|credit)\s*:\s*(.*)$", re.IGNORECASE)
_BULLET = re.compile(r"^[-*\u2022]\s+")
_STEP_NUMBER = re.compile(r"^(\d{1,3})[.)]\s+")
_SECTION_NAMES = {
    "ingredients": "Ingredients",
    "instructions": "Instructions",
    "directions": "Instructions",
    "steps": "Instructions",
    "notes": "Notes",
}
_YAML_MERGE_TAG = "tag:yaml.org,2002:merge"


class RecipeError(ValueError):
    """A recipe could not be loaded, extracted or validated.

    Attributes:
        errors: Human-readable problems, each safe to show to a submitter.
    """

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class _StrictSafeLoader(yaml.SafeLoader):
    """Safe loader that also rejects tags, anchors, aliases, merge keys and duplicate keys."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        event = self.peek_event()
        if (
            isinstance(event, yaml.AliasEvent)
            or getattr(event, "anchor", None) is not None
        ):
            raise yaml.composer.ComposerError(
                None, None, "YAML anchors and aliases are not allowed", event.start_mark
            )
        if getattr(event, "tag", None) is not None:
            raise yaml.composer.ComposerError(
                None,
                None,
                f"explicit YAML tags are not allowed ({event.tag})",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: Any, deep: bool = False) -> Any:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            if key_node.tag == _YAML_MERGE_TAG:
                raise yaml.constructor.ConstructorError(
                    None, None, "YAML merge keys are not allowed", key_node.start_mark
                )
            key = self.construct_object(key_node, deep=True)
            try:
                duplicate = key in seen
            except TypeError:
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    "mapping keys must be plain scalars",
                    key_node.start_mark,
                ) from None
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


class _IndentedSafeDumper(yaml.SafeDumper):
    """Safe dumper that indents sequences under their key for readable reviews."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def normalize_line(text: str) -> str:
    """Return the canonical form of one line of recipe text.

    Applies Unicode NFC, collapses every whitespace run (including tabs and non-breaking
    spaces) to one space and strips surrounding whitespace. Control characters are not
    removed; validation rejects them.
    """
    return _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFC", text)).strip()


def slugify(title: str) -> str:
    """Derive a URL slug from a title: ASCII-folded, lowercase, hyphen-separated, <= 80 chars.

    Returns an empty string when the title has no ASCII letters or digits.
    """
    folded = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug[:MAX_SLUG_CHARS].rstrip("-")


def load_recipe_yaml(data: str | bytes) -> Any:
    """Parse one YAML document with the restricted safe loader.

    Args:
        data: File contents. Bytes must be UTF-8 and at most 64 KiB.

    Returns:
        The parsed document (plain Python mappings, lists and scalars only).

    Raises:
        RecipeError: The input is too large, not UTF-8, empty, multi-document or uses
            tags, anchors, aliases, merge keys or duplicate keys.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > MAX_YAML_BYTES:
        raise RecipeError([f"recipe file is larger than {MAX_YAML_BYTES} bytes"])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecipeError(
            [f"recipe file is not valid UTF-8 (byte {exc.start})"]
        ) from None
    try:
        document = yaml.load(text, Loader=_StrictSafeLoader)
    except yaml.YAMLError as exc:
        raise RecipeError([f"invalid YAML: {_yaml_problem(exc)}"]) from None
    if document is None:
        raise RecipeError(["recipe file is empty"])
    return document


def validate_recipe(recipe: Any, *, slug_from_filename: str | None = None) -> list[str]:
    """Return every problem with a recipe; an empty list means it is valid.

    Args:
        recipe: Parsed recipe data.
        slug_from_filename: When set, the recipe ``slug`` must equal it (``<slug>.yaml``).

    Returns:
        Human-readable problems in a stable order.
    """
    schema_errors = sorted(_VALIDATOR.iter_errors(recipe), key=_error_sort_key)
    if schema_errors:
        return [_describe(error) for error in schema_errors]

    problems = []
    for location, value in _text_fields(recipe):
        if normalize_line(value) != value:
            problems.append(f"{location}: must be normalized (NFC, single spaces)")
    length = content_length(recipe)
    if length > MAX_CONTENT_CHARS:
        problems.append(
            f"recipe content is {length} characters; the maximum is {MAX_CONTENT_CHARS}"
        )
    if slug_from_filename is not None and recipe["slug"] != slug_from_filename:
        problems.append(
            f"slug: {recipe['slug']!r} must match the file name {slug_from_filename!r}.yaml"
        )
    return problems


def validate_file(path: Path) -> dict[str, Any]:
    """Load and validate one ``recipes/<slug>.yaml`` file.

    Raises:
        RecipeError: The file is unsafe, malformed or invalid.
    """
    recipe = load_recipe_yaml(path.read_bytes())
    problems = validate_recipe(recipe, slug_from_filename=path.stem)
    if problems:
        raise RecipeError(problems)
    return recipe


def parse_paste_template(text: str) -> dict[str, Any]:
    """Extract one recipe from the paste template without guessing.

    Args:
        text: Pasted text: a title line, an optional ``Source:`` line, an ``Ingredients``
            section, an ``Instructions`` section and an optional ``Notes`` section.

    Returns:
        A valid recipe whose slug is derived from the title.

    Raises:
        RecipeError: The paste is malformed, ambiguous, contains more than one recipe or
            fails validation. Messages reference 1-based line numbers.
    """
    lines = (
        text.removeprefix("\ufeff")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )
    title: str | None = None
    source: str | None = None
    sections: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None

    for number, raw_line in enumerate(lines, start=1):
        if _CONTROL_CHARS.search(raw_line):
            raise RecipeError([f"line {number}: contains a control character"])
        line = normalize_line(raw_line)
        if not line:
            continue
        header = _SECTION_HEADER.match(line)
        if title is None:
            if header:
                raise RecipeError(
                    [
                        f"line {number}: the first line must be the recipe title, not a section"
                    ]
                )
            title = _HEADING_PREFIX.sub("", line)
            continue
        if header:
            name = _SECTION_NAMES[header.group(1).lower()]
            if name in sections:
                raise RecipeError(
                    [
                        (
                            f"line {number}: found a second {name!r} section; "
                            "paste exactly one recipe at a time"
                        )
                    ]
                )
            if name != "Ingredients" and "Ingredients" not in sections:
                raise RecipeError(
                    [f"line {number}: {name!r} must come after 'Ingredients'"]
                )
            if name == "Notes" and "Instructions" not in sections:
                raise RecipeError(
                    [f"line {number}: 'Notes' must come after 'Instructions'"]
                )
            sections[name] = []
            current = name
            continue
        if current is None:
            source_match = _SOURCE_LINE.match(line)
            if source_match and source is None:
                source = source_match.group(1)
                if not source:
                    raise RecipeError(
                        [f"line {number}: 'Source:' needs text or should be removed"]
                    )
                continue
            raise RecipeError(
                [
                    f"line {number}: expected 'Ingredients' after the title"
                    + (" and source" if source is not None else "")
                    + "; remove or move this text"
                ]
            )
        sections[current].append((number, line))

    if title is None:
        raise RecipeError(["the paste is empty; start with the recipe title"])
    for name in ("Ingredients", "Instructions"):
        if name not in sections:
            raise RecipeError([f"missing the {name!r} section"])
    for name, entries in sections.items():
        if not entries:
            raise RecipeError([f"the {name!r} section has no entries"])

    recipe: dict[str, Any] = {"slug": slugify(title), "title": title}
    if not recipe["slug"]:
        raise RecipeError(
            ["title: must contain at least one ASCII letter or digit for the URL"]
        )
    if source is not None:
        recipe["source"] = source
    recipe["ingredients"] = _strip_bullets(sections["Ingredients"])
    recipe["instructions"] = _strip_step_numbers(sections["Instructions"])
    if "Notes" in sections:
        recipe["notes"] = _strip_bullets(sections["Notes"])

    problems = validate_recipe(recipe)
    if problems:
        raise RecipeError(problems)
    return recipe


def format_paste_template(recipe: Mapping[str, Any]) -> str:
    """Render a recipe as canonical paste-template text (no trailing newline).

    :func:`parse_paste_template` reads this output back to the same recipe, and its length
    defines the normalized recipe content size.
    """
    lines = [recipe["title"]]
    if "source" in recipe:
        lines.append(f"Source: {recipe['source']}")
    lines += ["", "Ingredients", *(f"- {item}" for item in recipe["ingredients"])]
    lines += ["", "Instructions"]
    lines += [
        f"{index}. {step}" for index, step in enumerate(recipe["instructions"], start=1)
    ]
    if "notes" in recipe:
        lines += ["", "Notes", *(f"- {note}" for note in recipe["notes"])]
    return "\n".join(lines)


def content_length(recipe: Mapping[str, Any]) -> int:
    """Return the normalized recipe content size in characters (Unicode code points)."""
    return len(format_paste_template(recipe))


def dump_recipe_yaml(recipe: Mapping[str, Any]) -> str:
    """Serialize a valid recipe as canonical YAML with keys in schema order.

    Raises:
        RecipeError: The recipe is invalid.
    """
    problems = validate_recipe(recipe)
    if problems:
        raise RecipeError(problems)
    ordered = {key: recipe[key] for key in FIELD_ORDER if key in recipe}
    return yaml.dump(
        ordered,
        Dumper=_IndentedSafeDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1_000_000,
    )


def _strip_bullets(entries: list[tuple[int, str]]) -> list[str]:
    items = []
    for number, line in entries:
        item = _BULLET.sub("", line, count=1)
        if not item or item in {"-", "*", "\u2022"}:
            raise RecipeError([f"line {number}: empty list item"])
        items.append(item)
    return items


def _strip_step_numbers(entries: list[tuple[int, str]]) -> list[str]:
    numbered = [_STEP_NUMBER.match(line) for _, line in entries]
    if not any(numbered):
        return _strip_bullets(entries)
    steps = []
    for expected, ((number, line), match) in enumerate(
        zip(entries, numbered, strict=True), 1
    ):
        if match is None or int(match.group(1)) != expected:
            raise RecipeError(
                [
                    (
                        f"line {number}: expected step {expected}; number every instruction in "
                        "order and keep each step on one line"
                    )
                ]
            )
        steps.append(line[match.end() :])
    return steps


def _text_fields(recipe: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    for key in ("title", "source"):
        if key in recipe:
            yield key, recipe[key]
    for key in _LIST_FIELDS:
        for index, value in enumerate(recipe.get(key, [])):
            yield f"{key}[{index}]", value


def _error_sort_key(error: ValidationError) -> tuple[str, str]:
    return _location(error), error.validator


def _location(error: ValidationError) -> str:
    location = ""
    for part in error.absolute_path:
        location += (
            f"[{part}]" if isinstance(part, int) else (f".{part}" if location else part)
        )
    return location or "recipe"


def _describe(error: ValidationError) -> str:
    location = _location(error)
    value = error.validator_value
    match error.validator:
        case "required":
            missing = error.message.split("'")[1]
            return f"{missing}: is required"
        case "additionalProperties":
            unknown = sorted(
                repr(key)[:60]
                for key in error.instance
                if key not in SCHEMA["properties"]
            )
            return f"{location}: unknown field(s) {', '.join(unknown)}"
        case "type":
            return f"{location}: must be {'a list' if value == 'array' else 'a mapping' if value == 'object' else 'text'}"
        case "minLength":
            return f"{location}: must not be empty"
        case "maxLength":
            return f"{location}: must be at most {value} characters"
        case "minItems":
            return f"{location}: must have at least {value} entry"
        case "maxItems":
            return f"{location}: must have at most {value} entries"
        case "pattern" if location == "slug":
            return (
                "slug: must be lowercase letters and digits separated by single hyphens"
            )
        case "pattern":
            return f"{location}: must be one line without control characters or surrounding spaces"
        case _:
            return f"{location}: {error.message[:200]}"


def _yaml_problem(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    mark = getattr(exc, "problem_mark", None)
    return f"{problem} (line {mark.line + 1})" if mark is not None else problem


def main(argv: list[str] | None = None) -> int:
    """Validate recipe files and print one result line per file.

    Returns:
        0 when every file is valid, otherwise 1.
    """
    args = sys.argv[1:] if argv is None else argv
    paths = [Path(arg) for arg in args] or sorted(RECIPES_DIR.glob("*.yaml"))
    if not paths:
        print("no recipe files found", file=sys.stderr)
        return 1
    failed = False
    for path in paths:
        try:
            validate_file(path)
        except (OSError, RecipeError) as exc:
            failed = True
            details = exc.errors if isinstance(exc, RecipeError) else [str(exc)]
            for detail in details:
                print(f"{path}: {detail}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
