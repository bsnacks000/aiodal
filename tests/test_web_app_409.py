import pytest
import httpx
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.anyio


async def test_create_book_409_IntegrityError(
    module_test_app, module_transaction, authors_fixture, books_fixture
):
    app = module_test_app
    transaction = module_transaction
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        path = app.url_path_for("create_book")
        response = await client.post(
            path,
            json={
                "author_id": 111,
                "name": "hitchhiker's guide to galaxy",
                "catalog": "geography",
            },
        )
        assert response.status_code == 409

        await transaction.rollback()


async def test_patch_book_409_IntegrityError(
    module_test_app, module_transaction, authors_fixture, books_fixture
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
                "author_id": 100,
            },
            headers=headers,
        )
        assert response.status_code == 409

        await transaction.rollback()


async def test_create_book_409_DBAPIError(
    module_test_app, module_transaction, authors_fixture, books_fixture, mocker
):
    app = module_test_app
    transaction = module_transaction
    async with httpx.AsyncClient(app=app, base_url="https://fake.com") as client:
        mocker.patch(
            "aiodal.dal.TransactionManager.execute",
            side_effect=DBAPIError(
                statement="create",
                params="error in your data",
                orig=ValueError("value error"),
            ),
        )
        path = app.url_path_for("create_book")
        response = await client.post(
            path,
            json={
                "author_id": 1,
                "name": "hitchhiker's guide to galaxy",
                "catalog": "geography",
            },
        )
        assert response.status_code == 409
        message = response.json()
        assert "value error" in message["detail"]

        await transaction.rollback()


async def test_patch_book_409_DBAPIError(
    module_test_app, module_transaction, authors_fixture, books_fixture, mocker
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

        # note two calls to transaction.execute..first in VersionDetailController.query and second in UpdateController.update
        # fake Context object for VersionDetailController.query..the first transaction call
        class DummyForm:
            def model_dump(self, **kwargs):
                return {"id": 1, "name": "blah"}

        class DummyContext:
            params = {"id": 1}
            etag_version = curr_etag
            form = DummyForm()
            deleted = False

            def one_or_none(self):
                return self

        mocker.patch(
            "aiodal.dal.TransactionManager.execute",
            side_effect=[
                DummyContext(),  # first call in VersionDetailController
                DBAPIError(  # second call in UpdateController
                    statement="patch",
                    params="error in your data",
                    orig=ValueError("patching error"),
                ),
            ],
        )

        path = app.url_path_for("patch_book", id=obj_id)
        response = await client.patch(
            path,
            json={
                "name": "new name",
            },
            headers=headers,
        )
        assert response.status_code == 409
        message = response.json()
        assert "patching error" in message["detail"]

        await transaction.rollback()
