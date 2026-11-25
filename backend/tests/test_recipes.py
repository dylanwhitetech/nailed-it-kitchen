"""Exercise recipe discovery and durable read counts through the real API."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier, Event, Lock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select
from sqlalchemy.exc import OperationalError

from backend.app.main import app
from backend.app.models import Recipe
from backend.app.seed import seed_recipes
from recipes.validate import dump_recipe_yaml

SUMMARY_FIELDS = {"id", "slug", "title", "view_count", "created_at", "updated_at"}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed(migrated_db, tmp_path):
    """Seed only schema-validated YAML, including later content replacements."""

    def write(recipes):
        for recipe in recipes:
            (tmp_path / f"{recipe['slug']}.yaml").write_text(
                dump_recipe_yaml(recipe), encoding="utf-8"
            )
        seed_recipes(migrated_db, tmp_path)

    return write


def recipe(slug, title="Simple soup", **content):
    return {
        "slug": slug,
        "title": title,
        "ingredients": ["Water"],
        "instructions": ["Simmer gently."],
        **content,
    }


def snapshot(engine):
    with engine.connect() as connection:
        return {
            row["slug"]: dict(row)
            for row in connection.execute(select(Recipe.__table__)).mappings()
        }


def summaries(items):
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert isinstance(item["id"], int)
        assert isinstance(item["view_count"], int) and item["view_count"] >= 0
        for field in ("created_at", "updated_at"):
            assert datetime.fromisoformat(item[field]).tzinfo is not None
    return [item["slug"] for item in items]


def page(client, **params):
    response = client.get("/api/recipes", params=params)
    assert response.status_code == 200, response.text
    result = response.json()
    assert set(result) == {"items", "next_offset"}
    summaries(result["items"])
    return result


def test_empty_discovery_and_unknown_detail(client, migrated_db):
    assert page(client) == {"items": [], "next_offset": None}
    assert page(client, q="saffron") == {"items": [], "next_offset": None}
    response = client.get("/api/most-viewed")
    assert response.status_code == 200
    assert response.json() == []
    response = client.get("/api/recipes/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Recipe was not found"}
    assert snapshot(migrated_db) == {}


@pytest.mark.parametrize("q", ["", "water"])
def test_pages_are_case_insensitive_with_slug_ties(client, seed, migrated_db, q):
    # Slug insertion/ID order and title casing disagree with expected A-Z order.
    seed(
        [
            recipe("a-zebra", "Zebra"),
            recipe("z-alpha", "ALPHA"),
            recipe("m-alpha", "alpha"),
            recipe("b-beta", "beta"),
            recipe("a-alpha", "Alpha"),
            recipe("c-beta", "BETA"),
        ]
    )
    before = snapshot(migrated_db)
    expected = ["a-alpha", "m-alpha", "z-alpha", "b-beta", "c-beta", "a-zebra"]
    actual = []
    offset = 0
    for next_offset in (2, 4, None):
        result = page(client, limit=2, offset=offset, q=q)
        actual.extend(summaries(result["items"]))
        assert result["next_offset"] == next_offset
        offset += 2
    assert actual == expected
    assert page(client, limit=2, offset=6, q=q)["items"] == []
    assert snapshot(migrated_db) == before


def test_default_and_maximum_page_limits_use_a_sentinel(client, seed):
    seed([recipe(f"soup-{i:03}", f"Soup {i:03}") for i in range(101)])
    expected = [f"soup-{i:03}" for i in range(101)]
    first = page(client)
    assert summaries(first["items"]) == expected[:20]
    assert first["next_offset"] == 20
    boundary = page(client, offset=81)
    assert summaries(boundary["items"]) == expected[81:]
    assert boundary["next_offset"] is None
    maximum = page(client, limit=100)
    assert summaries(maximum["items"]) == expected[:100]
    assert maximum["next_offset"] == 100
    exact = page(client, limit=100, offset=1)
    assert summaries(exact["items"]) == expected[1:]
    assert exact["next_offset"] is None
    last = page(client, limit=1, offset=100)
    assert summaries(last["items"]) == expected[-1:]
    assert last["next_offset"] is None
    assert page(client, offset=10000) == {"items": [], "next_offset": None}
    assert page(client, offset=9_223_372_036_854_775_807) == {
        "items": [],
        "next_offset": None,
    }
    assert page(client, q="nonexistent") == {"items": [], "next_offset": None}


@pytest.fixture
def searchable(seed):
    seed(
        [
            recipe(
                "z-title",
                "Saffron Soup",
                source="Sourceonly",
                notes=["Noteonly"],
            ),
            recipe("a-ingredient", "Apple", ingredients=["Saffron and carrots"]),
            recipe("b-instruction", "Banana", instructions=["Whisk saffron gently."]),
            recipe("c-other", "Carrot", ingredients=["Carrot"]),
        ]
    )


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("saffron", ["a-ingredient", "b-instruction", "z-title"]),
        ("SOUP", ["z-title"]),
        ("carrots", ["a-ingredient", "c-other"]),
        ("whisking", ["b-instruction"]),
        ("saffron carrot", ["a-ingredient"]),
        ("saffron whisk", ["b-instruction"]),
        ("saffron nonexistent", []),
        ("saffron | carrot", ["a-ingredient"]),
        ("saffron & !whisk", ["b-instruction"]),
        ("!!!", []),
        ("the and of", []),
        ("sourceonly", []),
        ("noteonly", []),
        (" \t\n ", ["a-ingredient", "b-instruction", "c-other", "z-title"]),
        ("", ["a-ingredient", "b-instruction", "c-other", "z-title"]),
    ],
)
def test_english_plain_search_contract(client, searchable, migrated_db, q, expected):
    before = snapshot(migrated_db)
    result = page(client, q=q)
    assert summaries(result["items"]) == expected
    assert result["next_offset"] is None
    assert snapshot(migrated_db) == before


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/recipes", {"limit": 0}),
        ("/api/recipes", {"limit": 101}),
        ("/api/recipes", {"limit": "bad"}),
        ("/api/recipes", {"offset": -1}),
        ("/api/recipes", {"offset": 9_223_372_036_854_775_808}),
        ("/api/recipes", {"offset": "bad"}),
        ("/api/recipes", {"q": "x" * 201}),
        ("/api/recipes", {"q": " " * 201}),
        ("/api/most-viewed", {"limit": 0}),
        ("/api/most-viewed", {"limit": 11}),
        ("/api/most-viewed", {"limit": "bad"}),
    ],
)
def test_invalid_bounds_are_rejected(client, migrated_db, path, params):
    response = client.get(path, params=params)
    assert response.status_code == 422
    assert snapshot(migrated_db) == {}


@pytest.mark.parametrize("q", ["x" * 200, " " * 200])
def test_query_limit_accepts_exactly_200_raw_characters(client, seed, q):
    seed([recipe("soup")])
    result = page(client, q=q)
    assert summaries(result["items"]) == (["soup"] if q.isspace() else [])


def test_most_viewed_bounds_ties_and_slug_route(client, seed, migrated_db):
    seed([recipe(f"soup-{i:02}") for i in range(11)] + [recipe("most-viewed")])
    # Counts come from API reads, not a direct database counter update.
    for slug in ("soup-09", "soup-08", "soup-09", "soup-08", "most-viewed"):
        assert client.get(f"/api/recipes/{slug}").status_code == 200
    before = snapshot(migrated_db)
    expected = (
        ["soup-08", "soup-09", "most-viewed"]
        + [f"soup-{i:02}" for i in range(8)]
        + ["soup-10"]
    )
    for params, limit in (({}, 5), ({"limit": 1}, 1), ({"limit": 10}, 10)):
        response = client.get("/api/most-viewed", params=params)
        assert response.status_code == 200
        assert summaries(response.json()) == expected[:limit]
        assert [row["view_count"] for row in response.json()] == [
            before[slug]["view_count"] for slug in expected[:limit]
        ]
    # Browsing stays A-Z rather than inheriting popularity ordering.
    assert summaries(page(client)["items"]) == ["most-viewed"] + [
        f"soup-{i:02}" for i in range(11)
    ]
    assert snapshot(migrated_db) == before
    with TestClient(app) as fresh_client:
        response = fresh_client.get("/api/most-viewed", params={"limit": 1})
        assert response.status_code == 200
        assert response.json()[0]["slug"] == "soup-08"
        assert response.json()[0]["view_count"] == 2


@pytest.mark.parametrize("optional", [False, True])
def test_detail_preserves_plain_ordered_content_and_timestamps(
    client, seed, migrated_db, optional
):
    content = recipe(
        "plain-soup",
        ingredients=["2 carrots", "1 cup water"],
        instructions=["Slice <carrots> & reserve.", "Simmer.", "Serve."],
    )
    if optional:
        content.update(
            source="Notebook <credit> & family",
            notes=["Yield: two bowls", "Equipment: pot", "Do not reorder."],
        )
    seed([content])
    before = snapshot(migrated_db)["plain-soup"]
    for count in (1, 2):
        response = client.get("/api/recipes/plain-soup")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        detail = response.json()
        assert set(detail) == SUMMARY_FIELDS | {
            "ingredients",
            "instructions",
            "source",
            "notes",
        }
        for field in ("slug", "title", "ingredients", "instructions"):
            assert detail[field] == content[field]
        for field in ("source", "notes"):
            assert detail[field] == content.get(field)
        assert detail["view_count"] == count
        assert detail["id"] == before["id"]
        for field in ("created_at", "updated_at"):
            assert datetime.fromisoformat(detail[field]) == before[field]
    after = snapshot(migrated_db)["plain-soup"]
    assert after == {**before, "view_count": 2}
    response = client.get("/api/recipes/unknown")
    assert response.status_code == 404
    assert snapshot(migrated_db)["plain-soup"] == after


def test_non_detail_endpoints_and_head_do_not_count(client, seed, migrated_db):
    seed([recipe("soup")])
    before = snapshot(migrated_db)
    for path in (
        "/api/recipes",
        "/api/recipes?q=water",
        "/api/most-viewed",
        "/api/healthz",
        "/api/readyz",
        "/api/metrics",
    ):
        assert client.get(path).status_code == 200
    for path in ("/api/recipes/soup", "/api/recipes/missing"):
        response = client.head(path)
        assert response.status_code == 405
        assert response.content == b""
    assert snapshot(migrated_db) == before
    assert client.get("/api/recipes/soup").json()["view_count"] == 1


def test_concurrent_api_reads_and_reseed_preserve_durable_identity(
    client, seed, migrated_db
):
    original = recipe("durable", "Old saffron", notes=["Original note"])
    seed([original])
    before = snapshot(migrated_db)["durable"]

    def read(barrier, seed_changed=None):
        with TestClient(app) as fresh_client:
            barrier.wait(timeout=30)
            if seed_changed is not None:
                assert seed_changed.wait(timeout=30)
            response = fresh_client.get("/api/recipes/durable")
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            return response.json()

    barrier = Barrier(8)
    with ThreadPoolExecutor(max_workers=8) as executor:
        details = list(executor.map(read, [barrier] * 8))
    assert sorted(detail["view_count"] for detail in details) == list(range(1, 9))
    for detail in details:
        assert detail["id"] == before["id"]
        assert datetime.fromisoformat(detail["updated_at"]) == before["updated_at"]

    changed = recipe(
        "durable",
        "New cardamom",
        ingredients=["Cardamom pods", "Water"],
        instructions=["Whisk.", "Serve."],
        source="New notebook",
        notes=["First new note", "Second new note"],
    )
    barrier = Barrier(9)
    seed_changed = Event()
    updates_started = Event()
    update_lock = Lock()
    update_count = 0

    def hold_seed_transaction(
        connection, cursor, statement, parameters, context, executemany
    ):
        if statement.startswith("INSERT INTO recipes"):
            # The changed-content upsert now owns the row lock. Keep its real
            # transaction open until all eight API updates reach SQL execution.
            seed_changed.set()
            assert updates_started.wait(timeout=30)

    def observe_detail_update(
        connection, cursor, statement, parameters, context, executemany
    ):
        nonlocal update_count
        if statement.startswith("UPDATE recipes"):
            assert seed_changed.is_set()
            with update_lock:
                update_count += 1
                if update_count == 8:
                    updates_started.set()

    def reseed():
        barrier.wait(timeout=30)
        seed([changed])

    event.listen(migrated_db, "after_cursor_execute", hold_seed_transaction)
    event.listen(Engine, "before_cursor_execute", observe_detail_update)
    try:
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = [executor.submit(read, barrier, seed_changed) for _ in range(8)]
            seeded = executor.submit(reseed)
            details = [future.result(timeout=60) for future in futures]
            seeded.result(timeout=60)
    finally:
        event.remove(migrated_db, "after_cursor_execute", hold_seed_transaction)
        event.remove(Engine, "before_cursor_execute", observe_detail_update)
    assert update_count == 8
    assert sorted(detail["view_count"] for detail in details) == list(range(9, 17))
    for detail in details:
        for field in ("title", "ingredients", "instructions", "source", "notes"):
            assert detail[field] == changed[field]
    after = snapshot(migrated_db)["durable"]
    assert after["id"] == before["id"]
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] > before["updated_at"]
    assert after["view_count"] == 16
    for field in ("title", "ingredients", "instructions", "source", "notes"):
        assert after[field] == changed[field]
    with TestClient(app) as fresh_client:
        listed = page(fresh_client)["items"][0]
        assert listed["id"] == before["id"] and listed["view_count"] == 16
        assert page(fresh_client, q="saffron")["items"] == []
        assert summaries(page(fresh_client, q="cardamom whisk")["items"]) == ["durable"]
        response = fresh_client.get("/api/most-viewed")
        assert response.status_code == 200
        assert response.json()[0]["view_count"] == 16
        detail = fresh_client.get("/api/recipes/durable").json()
        assert detail["view_count"] == 17 and detail["id"] == before["id"]
        for field in ("title", "ingredients", "instructions", "source", "notes"):
            assert detail[field] == changed[field]
        assert datetime.fromisoformat(detail["updated_at"]) == after["updated_at"]
    assert snapshot(migrated_db)["durable"] == {**after, "view_count": 17}


@pytest.mark.parametrize(
    "path",
    ["/api/recipes", "/api/recipes?q=water", "/api/most-viewed", "/api/recipes/soup"],
)
@pytest.mark.parametrize("failure", ["configuration", "connect", "execute", "commit"])
def test_database_failures_are_sanitized_503(
    client, monkeypatch, caplog, path, failure
):
    from backend.app import recipes

    sql = "SELECT private_recipe_content FROM recipes"
    content = "private-ingredient-marker"
    url = "postgresql+psycopg://localhost/private-url-marker"
    error = OperationalError(sql, {"ingredient": content}, OSError(url))

    class BrokenTransaction:
        def __enter__(self):
            if failure == "connect":
                raise error
            return self

        def execute(self, _statement):
            if failure == "execute":
                raise error
            return self

        def mappings(self):
            return self

        def all(self):
            return []

        def one_or_none(self):
            # Commit errors must be tested after a success-shaped detail result.
            return {
                "id": 1,
                "slug": "soup",
                "title": "Soup",
                "view_count": 1,
                "created_at": datetime.now().astimezone(),
                "updated_at": datetime.now().astimezone(),
                "ingredients": ["Water"],
                "instructions": ["Simmer."],
                "source": None,
                "notes": None,
            }

        def __exit__(self, exc_type, exc, traceback):
            if failure == "commit" and exc_type is None:
                raise error

    class BrokenEngine:
        disposed = False

        def begin(self):
            return BrokenTransaction()

        def dispose(self):
            self.disposed = True

    engine = BrokenEngine()

    def create(_settings):
        if failure == "configuration":
            raise ValueError(f"{url} {content} {sql}")
        return engine

    monkeypatch.setattr(recipes, "create_database_engine", create)
    response = client.get(path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Recipe database is unavailable"}
    for marker in (sql, content, url):
        assert marker not in response.text
        assert marker not in caplog.text
    if failure != "configuration":
        assert engine.disposed
