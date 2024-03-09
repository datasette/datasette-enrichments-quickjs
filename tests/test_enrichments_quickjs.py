import asyncio
from datasette.app import Datasette
import pytest
import sqlite_utils


async def _cookies(datasette, path="/-/enrich/data/items/quickjs"):
    cookies = {"ds_actor": datasette.sign({"a": {"id": "root"}}, "actor")}
    csrftoken = (await datasette.client.get(path, cookies=cookies)).cookies[
        "ds_csrftoken"
    ]
    cookies["ds_csrftoken"] = csrftoken
    return cookies


@pytest.mark.asyncio
async def test_enrichment(tmpdir):
    data = str(tmpdir / "data.db")
    datasette = Datasette([data], memory=True)
    db = sqlite_utils.Database(data)
    rows = [
        {"id": 1, "name": "One", "description": "First item"},
        {"id": 2, "name": "Two", "description": "Second item"},
        {"id": 3, "name": "Three", "description": "Third item"},
    ]
    db["items"].insert_all(rows, pk="id")

    cookies = await _cookies(datasette)
    post = {
        "javascript": "function enrich(row) { return row.description.length }",
        "output_column": "description_length",
        "output_column_type": "integer",
    }
    post["csrftoken"] = cookies["ds_csrftoken"]
    response = await datasette.client.post(
        "/-/enrich/data/items/quickjs",
        data=post,
        cookies=cookies,
    )
    assert response.status_code == 302
    await asyncio.sleep(0.3)
    db = datasette.get_database("data")
    jobs = await db.execute("select * from _enrichment_jobs")
    job = dict(jobs.first())
    assert job["status"] == "finished"
    assert job["enrichment"] == "quickjs"
    assert job["done_count"] == 3
    results = await db.execute("select * from items order by id")
    rows = [dict(r) for r in results.rows]
    assert rows == [
        {"id": 1, "name": "One", "description": "First item", "description_length": 10},
        {
            "id": 2,
            "name": "Two",
            "description": "Second item",
            "description_length": 11,
        },
        {
            "id": 3,
            "name": "Three",
            "description": "Third item",
            "description_length": 10,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    "javascript,expected_error",
    [
        # Deeply nested object should run out of memory
        (
            """
    function enrich() {
        let obj = {};
        for (let i = 0; i < 100000; i++) {
            obj = {nested: obj};
        }
        return obj;
    }""",
            "null\n",
        ),
        # Long running operation should return interrupted error
        (
            """
    function enrich() {
        let start = Date.now();
        while (Date.now() - start < 500);
        return 'Task completed';
    }""",
            "InternalError: interrupted\n    at enrich (<input>:3)\n",
        ),
        # Should work
        (
            """
    function enrich() {
        return 1;
    }""",
            None,
        ),
    ],
)
async def test_time_and_memory_limit(javascript, expected_error):
    ds = Datasette()
    db = ds.add_memory_database("test_time_and_memory_limit")
    await db.execute_write("create table if not exists foo (id integer primary key)")
    await db.execute_write("insert or replace into foo (id) values (1)")
    try:
        # In-memory DB persists between runs, so clear it
        await db.execute_write("delete from _enrichment_jobs")
        await db.execute_write("delete from _enrichment_errors")
    except Exception:
        # Table does not exist yet
        pass
    cookies = await _cookies(
        ds, path="/-/enrich/test_time_and_memory_limit/foo/quickjs"
    )

    rows = [
        {"id": 1, "name": "One", "description": "First item"},
        {"id": 2, "name": "Two", "description": "Second item"},
        {"id": 3, "name": "Three", "description": "Third item"},
    ]
    post = {
        "javascript": javascript,
        "output_column": "description_length",
        "output_column_type": "integer",
    }
    post["csrftoken"] = cookies["ds_csrftoken"]
    response = await ds.client.post(
        "/-/enrich/test_time_and_memory_limit/foo/quickjs",
        data=post,
        cookies=cookies,
    )
    assert response.status_code == 302
    await asyncio.sleep(0.3)
    jobs = await db.execute("select * from _enrichment_jobs")
    row = dict(jobs.rows[0])
    assert row["status"] == "finished"

    if expected_error:
        assert row["error_count"] == 1
        errors = (await db.execute("select * from _enrichment_errors")).rows
        error = dict(errors[0])["error"]
        assert error == expected_error
    else:
        assert row["error_count"] == 0
