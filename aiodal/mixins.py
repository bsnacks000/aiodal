"""
Some lightweight classes for working with the dal and creating objects.

"""
from typing import (
    Callable,
    List,
    Dict,
    Any,
    Awaitable,
    Optional,
    MutableMapping,
)
import abc
import sqlalchemy as sa

from . import dal

RecordT = Dict[str, Any]

# for now ... there should be some kind of constraint...
Where = MutableMapping[str, Any]

GetListCoro = Callable[
    [dal.TransactionManager, Optional[Where]], Awaitable[sa.CursorResult[Any]]
]

GetDetailCoro = Callable[
    [dal.TransactionManager, Where], Awaitable[Optional[sa.Row[Any]]]
]


InsertManyCoro = Callable[
    [dal.TransactionManager, List[RecordT]], Awaitable[sa.CursorResult[Any]]
]

InsertOneCoro = Callable[[dal.TransactionManager, RecordT], Awaitable[sa.Row[Any]]]


UpdateOneCoro = Callable[
    [dal.TransactionManager, Where, RecordT], Awaitable[sa.Row[Any]]
]

UpdateManyCoro = Callable[
    [dal.TransactionManager, Where, List[RecordT]], Awaitable[sa.CursorResult[Any]]
]

DeleteListCoro = Callable[[dal.TransactionManager, Optional[Where]], Awaitable[None]]

DeleteDetailCoro = Callable[[dal.TransactionManager, Where], Awaitable[None]]


class ListQ(abc.ABC):
    __list_query__: GetListCoro

    @classmethod
    async def list(
        cls, t: dal.TransactionManager, where: Optional[Where] = None
    ) -> List["ListQ"]:
        result = await cls.__list_query__(t, where)
        return [cls(**r._mapping) for r in result]


class DetailQ(abc.ABC):
    __detail_query__: GetDetailCoro

    @classmethod
    async def detail(
        cls, t: dal.TransactionManager, where: Where
    ) -> Optional["DetailQ"]:
        row = await cls.__detail_query__(t, where)
        return cls(**row._mapping) if row is not None else row


class InsertDetailQ(abc.ABC):
    __insert_detail_query__: InsertOneCoro

    @classmethod
    async def insert_one(
        cls, t: dal.TransactionManager, data: RecordT
    ) -> "InsertDetailQ":
        result = await cls.__insert_detail_query__(t, data)
        return cls(**result._mapping)


class InsertManyQ(abc.ABC):
    __insert_many_query__: InsertManyCoro

    @classmethod
    async def insert_many(
        cls, t: dal.TransactionManager, data: List[RecordT]
    ) -> List["InsertManyQ"]:
        result = await cls.__insert_many_query__(t, data)
        return [cls(**r) for r in result]


class UpdateDetailQ(abc.ABC):
    __update_detail_query__: UpdateOneCoro

    @classmethod
    async def update(
        cls, t: dal.TransactionManager, where: Where, data: RecordT
    ) -> "UpdateDetailQ":
        row = await cls.__update_detail_query__(t, where, data)
        return cls(**row._mapping)


class UpdateManyQ(abc.ABC):
    __update_many_query__: UpdateManyCoro

    @classmethod
    async def update_many(
        cls, t: dal.TransactionManager, where: Where, data: List[RecordT]
    ) -> List["UpdateManyQ"]:
        result = await cls.__update_many_query__(t, where, data)
        return [cls(**r) for r in result]


class DeleteManyQ(abc.ABC):
    __delete_many_query__: DeleteListCoro

    @classmethod
    async def list(
        cls, t: dal.TransactionManager, where: Optional[Where] = None
    ) -> None:
        await cls.__delete_many_query__(t, where)


class DeleteDetailQ(abc.ABC):
    __delete_detail_query__: DeleteDetailCoro

    @classmethod
    async def detail(cls, t: dal.TransactionManager, where: Where) -> None:
        await cls.__delete_detail_query__(t, where)
