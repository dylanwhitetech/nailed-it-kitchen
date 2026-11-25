# Recipe format

Beta recipes are plain text: a title, ingredient lines and ordered instruction steps. Reviewed
recipes live in `recipes/<slug>.yaml`; the original free-text recipes in `recipes/source/` are kept
unchanged as fixtures. There are no ingredient IDs, structured quantities, tags, graph links,
branching or grid layout.

- Schema: [`recipes/schema/recipe.schema.json`](../recipes/schema/recipe.schema.json) (JSON Schema 2020-12).
- Validator, paste extraction and safe serializer: [`recipes/validate.py`](../recipes/validate.py).
- Decision record: [`guidance/0010-plain-text-beta-recipes.md`](../guidance/0010-plain-text-beta-recipes.md).

## Recipe file

```yaml
slug: buttered-toast
title: Buttered Toast
source: Grandma's recipe card
ingredients:
  - 1 slice bread
  - 1 tbsp butter
instructions:
  - Toast the bread.
  - Spread with butter.
notes:
  - Serve warm.
```

| Field | Required | Rules |
| --- | --- | --- |
| `slug` | yes | 1–80 lowercase ASCII letters/digits separated by single hyphens; must equal the file name (`<slug>.yaml`). |
| `title` | yes | Text line, at most 160 characters. |
| `source` | no | Plain-text source or credit, at most 300 characters. Never rendered as markup or a link. |
| `ingredients` | yes | 1–100 text lines, at most 500 characters each, in display order. Quantities stay in the text. |
| `instructions` | yes | 1–100 text lines, at most 2,000 characters each. The list position is the step number. |
| `notes` | no | 1–100 text lines, at most 1,000 characters each (yield, equipment, tips). Omit when empty. |

Every text value is a nonempty single line with no control characters, Unicode surrogate code
points, or surrounding whitespace, and is already normalized (see below). Unknown fields are
rejected. The **normalized recipe content** is the canonical paste-template text from
`format_paste_template` and must be at most **20,000 characters** (Unicode code points). The
request-wide 32 KiB cap is enforced separately by the submission API.

### Safe YAML

Recipe files are data, never code. The loader accepts one UTF-8 YAML document of at most 64 KiB
built from plain mappings, lists and strings, and rejects:

- explicit tags of any kind (`!!python/...`, `!!binary`, `!!set`, `!custom`, even `!!str`);
- anchors, aliases and merge keys (`&`, `*`, `<<`);
- duplicate or non-scalar keys, multiple documents and empty files;
- values YAML would read as numbers, dates or booleans (they fail the schema's text type; quote
  them).

`dump_recipe_yaml` writes canonical YAML (schema key order, indented lists, UTF-8). The reviewed
fixtures are in that form.

## Paste template

Submitters paste one recipe in this shape:

```text
Recipe title
Source: optional plain-text source or credit

Ingredients
- First ingredient
- Second ingredient

Instructions
1. First cooking instruction.
2. Second cooking instruction.

Notes
- Optional note.
```

The `Source:` line and the `Notes` section are optional. Text is stored and shown exactly as
plain text; HTML or Markdown characters are kept as literal text, not interpreted.

### Extraction rules

`parse_paste_template` is deterministic and never guesses:

1. Line endings (`\r\n`, `\r`) become `\n` and a leading byte-order mark is dropped. A line with a
   control character other than tab is rejected.
2. Each line is normalized: Unicode NFC, every whitespace run (tabs, non-breaking spaces) becomes
   one space, and surrounding spaces are trimmed. Blank lines are ignored.
3. The first nonblank line is the title. A leading backslash escapes the title: exactly one
   backslash is removed, and heading/section recognition is skipped. Otherwise a leading Markdown
   heading marker (`# `) is removed.
4. Between the title and `Ingredients`, only one `Source:` (or `Credit:`) line is allowed.
5. A section header is a whole line, case-insensitive, optionally prefixed with `#` marks and
   followed by `:`. `Ingredients` comes first, then `Instructions` (also `Directions` or `Steps`),
   then optional `Notes`.
6. Every nonblank line in a section is one entry. One leading `-`, `*` or `•` bullet is removed.
7. Instructions are either all unnumbered or numbered `1.`/`1)` consecutively from 1; the numbers
   are removed and the line order is the step order. Write each step on a single line.
8. The slug is derived from the title: accents folded to ASCII, lowercase, other characters become
   single hyphens, trimmed to 80 characters.
9. The extracted recipe then passes the same validation as a recipe file.

`format_paste_template` renders a recipe back into this template, and parsing that output returns
the same recipe (with the title-derived slug). It escapes titles that start with a backslash or
would otherwise be read as a Markdown heading or section header by prefixing one backslash.

### Errors

Errors are explicit, safe to show to the submitter and include 1-based line numbers where useful:

| Problem | Example message |
| --- | --- |
| Section before the title | `line 1: the first line must be the recipe title, not a section` |
| Text between title and `Ingredients` | `line 2: expected 'Ingredients' after the title; remove or move this text` |
| Missing or empty section | `missing the 'Instructions' section`, `the 'Ingredients' section has no entries` |
| Sections out of order | `line 4: 'Notes' must come after 'Instructions'` |
| More than one recipe or repeated section | `line 13: found a second 'Ingredients' section; paste exactly one recipe at a time` |
| Wrapped, skipped or mixed step numbers | `line 6: expected step 2; number every instruction in order and keep each step on one line` |
| Control characters | `line 3: contains a control character` |
| Title without ASCII letters or digits | `title: must contain at least one ASCII letter or digit for the URL` |
| Size and count limits | `title: must be at most 160 characters`, `ingredients: must have at most 100 entries` |

### Intentional normalization and limits

- Whitespace collapsing and NFC can change invisible spacing or composed accents, never words.
- Bullets and step numbers are formatting, not content; exactly one marker is removed, so text
  such as `1 1/2 cups` or `1.5 minutes` is kept.
- An unbulleted line that is exactly a section word (for example `Steps`) is read as a header;
  bullet it to keep it as an entry.
- Titles need an ASCII letter or digit for the slug; a submitter can add one rather than the
  server inventing a name.
- Markdown emphasis is not interpreted. The reviewed fixtures were converted with `**` markers
  removed, the source front matter (mixer, yield, yeast) and equipment kept as notes, and all
  ingredient, step and note text and order unchanged.

## Validate recipes locally

Requires Python 3.12.

```bash
python -m venv .venv
.venv/bin/pip install -r recipes/requirements.txt   # Windows: .venv\Scripts\pip
.venv/bin/python recipes/validate.py                # validates recipes/*.yaml, or pass files
.venv/bin/python -m pytest recipes
.venv/bin/ruff check recipes && .venv/bin/ruff format --check recipes
```

`recipes/validate.py` prints `<file>: ok` per valid file and exits nonzero with one line per
problem otherwise.
