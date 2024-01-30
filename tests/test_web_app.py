import pytest
import httpx
import sqlalchemy as sa

pytestmark = pytest.mark.anyio


async def test_get_book_list(module_test_app, module_authors, module_books):
    app = module_test_app
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        path = app.url_path_for("get_book_list")
        response = await client.get(path)
        assert response.status_code == 200

        res = response.json()
        result = res["results"]
        assert len(result) == 3


async def test_create_book(
    module_test_app, module_transaction, module_authors, module_books
):
    app = module_test_app
    transaction = module_transaction
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        path = app.url_path_for("create_book")
        response = await client.post(
            path,
            json={
                "author_id": 1,
                "name": "hitchhiker's guide to galaxy",
                "catalog": "geography",
            },
        )
        assert response.status_code == 201

        res = response.json()
        assert res["name"] == "hitchhiker's guide to galaxy"

        obj_id = res["id"]
        # delete afterward
        t = transaction.get_table("book")
        stmt = sa.delete(t).where(t.c.id == obj_id).returning(t)
        res = await transaction.execute(stmt)
        obj = res.one()
        assert obj.id == obj_id


async def test_get_book_detail(
    module_test_app, module_transaction, module_authors, module_books
):
    app = module_test_app
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        path = app.url_path_for("get_book_detail", id=1)
        response = await client.get(
            path,
        )
        assert response.status_code == 200

        res = response.json()
        assert res["name"] == "Gone with the Fin"


async def test_patch_book(
    module_test_app, module_transaction, module_authors, module_books
):
    app = module_test_app
    transaction = module_transaction
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        obj_id = 1
        path = app.url_path_for("get_book_detail", id=obj_id)
        response = await client.get(
            path,
        )
        assert response.status_code == 200

        obj_ = response.json()
        assert obj_["id"] == obj_id
        curr_etag = obj_["etag_version"]
        headers = {"If-Match": curr_etag}

        path = app.url_path_for("patch_book", id=obj_id)
        response = await client.patch(
            path,
            json={
                "name": "new name",
            },
            headers=headers,
        )
        assert response.status_code == 200

        res = response.json()
        assert res["name"] == "new name"

        # use the same old etag
        path = app.url_path_for("patch_book", id=obj_id)
        response = await client.patch(
            path,
            json={
                "name": "new new name",
            },
            headers=headers,
        )
        assert response.status_code == 412
